# Reality Check: Enterprise Governance (`governance`)

**Project:** `governance/`  
**Stack:** Terraform, AWS Organizations, Service Control Policies, LocalStack Pro  
**Summary:** Implementing organisation-wide governance via SCPs exposed a structural design flaw in the initial approach — attaching SCPs at the OU level instead of the Root — which meant the Security OU could bypass its own controls. The region restriction SCP also broke global AWS services when written naively.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| SCPs attached at OU level — Security OU could bypass its own controls | P1 | Caught at design review | ✅ Fixed — moved all SCPs to Root |
| Region restriction SCP with naive deny-all broke IAM, Route53, CloudFront | P1 | 2 hours debugging | ✅ Fixed — added `NotAction` for global services |
| LocalStack Pro required for Organizations — free tier failed silently | P2 | 45 min | ✅ Documented — requires Pro subscription |

---

## Problem 1 — SCPs Attached at OU Level: Security OU Bypassed Its Own Controls

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Governance Architecture |
| **Time Lost** | Caught during design review before deployment |
| **Discovered** | Reviewing AWS Organizations SCP inheritance model |

**Symptom:**

The initial design attached the three SCPs to the `Security-Prod` OU and the `Workloads-Prod` OU individually:

```hcl
resource "aws_organizations_policy_attachment" "cloudtrail_protection" {
  policy_id = aws_organizations_policy.deny_cloudtrail_stop.id
  target_id = aws_organizations_organizational_unit.security_prod.id
}
```

This appeared correct: the policy was attached and the OUs should be protected.

**Root Cause:**

AWS Organizations uses a **hierarchical permission evaluation** model. A policy attached at a specific OU applies only to accounts directly within that OU. However, the Root (the top of the hierarchy) is not an OU — it is a separate attachment point.

The critical implication: any account that is **not** inside the OU where the SCP is attached is **not subject to the policy**. If a new account is created at the Root level (outside any OU), or if an account is moved from one OU to another, the SCP does not follow automatically.

More specifically: the intent was to protect the Security OU from CloudTrail tampering. But an administrator could achieve the same effect by simply moving an account out of the `Security-Prod` OU to the Root level, perform the action, then move it back — bypassing the SCP entirely.

The correct pattern — and the one AWS recommends for immutable guardrails — is to attach the SCP to the **Organisation Root**. The Root encompasses every OU and every account in the organisation. No account can escape Root-level SCPs by being moved.

**Fix Applied:**

Changed all three SCP attachments from OU targets to the Organisation Root:

```hcl
# Fetch the organisation root ID
data "aws_organizations_organization" "main" {}

resource "aws_organizations_policy_attachment" "cloudtrail_protection" {
  policy_id = aws_organizations_policy.deny_cloudtrail_stop.id
  target_id = data.aws_organizations_organization.main.roots[0].id   # Root, not OU
}
```

This ensures every account in the organisation — current and future, regardless of OU placement — is covered by all three SCPs.

**Business Impact:**

An SCP attached at the wrong level of the hierarchy provides the appearance of governance without the substance. An auditor reviewing the configuration would see "SCP attached to Security-Prod OU" and mark it compliant. An attacker with account-level admin access would simply move the account out of the OU, perform the action, and move it back — all within seconds using the AWS CLI. The fix eliminates this bypass. This is the difference between governance that looks correct and governance that is correct.

---

## Problem 2 — Region Restriction SCP Broke IAM, Route53, and CloudFront

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Operational Impact |
| **Time Lost** | ~2 hours |
| **Discovered** | After applying the initial region SCP, all `aws iam` and `aws route53` CLI commands returned `AccessDeniedException` |

**Symptom:**

The initial region restriction SCP was written with a simple deny:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Action": "*",
    "Resource": "*",
    "Condition": {
      "StringNotEquals": {
        "aws:RequestedRegion": ["us-east-1", "us-east-2"]
      }
    }
  }]
}
```

After applying this SCP, the following commands failed:

```
$ aws iam list-users
An error occurred (AccessDenied) when calling the ListUsers operation:
  User is not authorized to perform: iam:ListUsers

$ aws route53 list-hosted-zones
An error occurred (AccessDenied) when calling the ListHostedZones operation:
  User is not authorized to perform: route53:ListHostedZones
```

These calls were made from `us-east-1` — which was explicitly allowed.

**Root Cause:**

IAM, Route53, CloudFront, AWS Support, AWS Billing, and several other AWS services are **global services** — they do not have a concept of region. When you make an IAM API call, the request is always routed to a single global endpoint. AWS evaluates the `aws:RequestedRegion` condition key for these calls against an empty or null value (since there is no region for a global service).

The `StringNotEquals` condition evaluates to `true` when the key is null (because null is not equal to "us-east-1"), so the Deny fires on every IAM and Route53 call — even though the intent was only to block operations in non-US regions.

**Fix Applied:**

Changed the SCP to use `NotAction` to explicitly exclude global services from the region restriction:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "NotAction": [
      "iam:*",
      "route53:*",
      "cloudfront:*",
      "support:*",
      "aws-portal:*",
      "budgets:*",
      "sts:GetCallerIdentity"
    ],
    "Resource": "*",
    "Condition": {
      "StringNotEquals": {
        "aws:RequestedRegion": ["us-east-1", "us-east-2"]
      }
    }
  }]
}
```

`NotAction` means "apply this Deny to all actions EXCEPT the listed ones." The listed global services are excluded from the region condition entirely.

**Business Impact:**

A region SCP written without the `NotAction` exclusion is an immediate operational outage — it blocks all IAM operations across the organisation. In a production multi-account environment, this would prevent all IAM role assumption, break all service-to-service authentication, and disable all Route53 DNS management. The window between policy application and discovery could be 10–30 minutes. During that time, all automated systems that depend on IAM (CI/CD, Lambda functions, ECS tasks) would fail. This is a self-inflicted organisation-wide outage caused by a one-line policy error.

---

## Problem 3 — LocalStack Free Tier Does Not Support AWS Organizations

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Development Environment |
| **Time Lost** | ~45 minutes |
| **Discovered** | `terraform apply` returned `FeatureNotAvailable` for `aws_organizations_create_organization` |

**Symptom:**

After setting up LocalStack for the governance project, the first `terraform apply` failed:

```
│ Error: creating Organizations Organization:
│ FeatureNotAvailable: The requested feature is only available in LocalStack Pro.
│ https://localstack.cloud/pricing
```

**Root Cause:**

AWS Organizations is a complex, multi-account service that requires significant emulation infrastructure. LocalStack places it in the Pro tier because the emulation work is non-trivial. The free Community edition of LocalStack only emulates a subset of AWS services (primarily S3, SQS, Lambda basics).

The LocalStack documentation does mention this, but it is not prominently highlighted in the getting-started guide, leading to confusion when the service fails with an opaque error.

**Fix Applied:**

Confirmed that the existing `LS_TOKEN` Pro subscription covers Organizations (it does). Added an explicit service check to the deployment documentation:

```bash
# Verify LocalStack Pro is running with Organizations support
curl http://localhost:4566/_localstack/info | python3 -c "
import sys, json
data = json.load(sys.stdin)
pro = data.get('pro', False)
print(f'LocalStack Pro: {pro}')
assert pro, 'ERROR: Organizations requires LocalStack Pro. Set LS_TOKEN in .env'
"
```

**Business Impact:**

In a real environment, AWS Organizations is a production-only service — there is no free tier equivalent. The correct validation environment for SCP logic is either a dedicated AWS sandbox account with full Organizations access, or LocalStack Pro. This is documented as a deviation from the LocalStack-only development model in ADR-001.

---

## What These Failures Prove

The governance project encountered three different levels of correctness failure:

1. **Architecturally wrong but syntactically correct** — OU-level SCP attachment passes every validation check and produces a "working" deployment. The structural flaw is only visible when reasoning through the AWS Organizations inheritance model.
2. **Contextually wrong** — the region SCP was logically correct for regional services but failed to account for global services that operate outside the region model entirely. This class of failure requires deep AWS service-level knowledge to anticipate.
3. **Environment gap** — some AWS services cannot be locally emulated without a paid tooling subscription. Knowing where the boundaries are between "testable locally" and "testable only on real AWS" is itself a production-relevant skill.
