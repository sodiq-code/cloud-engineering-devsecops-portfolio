# Reality Check: IaC Foundations (`aws-foundation` + `security-stack`)

**Projects:** `aws-foundation/` and `security-stack/`  
**Stack:** Terraform, AWS VPC, EC2, IAM, KMS, S3, CloudTrail, GuardDuty, LocalStack  
**Summary:** Deploying the four-layer module composition (Network → Identity → Security → Compute) surfaced three non-obvious production-critical failures that would have been costly on real AWS.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| KMS key policy with wildcard `"AWS": "*"` principal | P1 | Caught at review | ✅ Fixed |
| Terraform AWS provider v5.x incompatible with LocalStack EC2 API | P2 | 2 hours | ✅ Fixed — pinned to `~> 4.67` |
| EC2 module missing second public subnet output | P2 | 45 min | ✅ Fixed |
| `t2.micro` EBS optimisation check is a false-positive for that instance class | P3 | 30 min | ✅ Suppressed with justification |

---

## Problem 1 — KMS Key Policy: Wildcard Principal Grants Universal Decryption Access

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Security |
| **Time Lost** | Caught during code review |
| **Discovered** | Manual review of generated key policy in `modules/security/main.tf` |

**Symptom:**

The KMS Customer Managed Key (CMK) protecting CloudTrail logs was created with a root principal:

```hcl
# What was written initially:
policy = jsonencode({
  Statement = [{
    Principal = { AWS = "*" }
    Action    = "kms:*"
    Effect    = "Allow"
  }]
})
```

This looked correct because many AWS examples use this shorthand. The KMS key was created successfully and CloudTrail encryption was enabled without errors.

**Root Cause:**

`"AWS": "*"` in a KMS key policy means *any IAM identity in any AWS account* can use the key if they have the IAM permissions. This is categorically different from `"AWS": "arn:aws:iam::${account_id}:root"`, which scopes the principal to identities within the account that own the key.

The difference is subtle but the security gap is severe: the wildcard version effectively makes the key usable by any AWS account in the world, limited only by IAM policies — which themselves can be misconfigured.

**Fix Applied:**

```hcl
# Corrected: scope principal to the owning account only
data "aws_caller_identity" "current" {}

policy = jsonencode({
  Statement = [{
    Principal = {
      AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
    }
    Action   = "kms:*"
    Effect   = "Allow"
  }]
})
```

This was documented in ADR-002 as a known production requirement.

**Business Impact:**

In production, a wildcard KMS key policy is a catastrophic misconfiguration. Any IAM identity in the AWS account — including compromised service accounts, developer credentials, and even cross-account roles — can call `kms:Decrypt` to read any CloudTrail log encrypted with that key. For SOC2 and PCI-DSS compliant environments, this would be a critical audit finding and could result in audit failure.

---

## Problem 2 — Terraform AWS Provider v5.x Breaks LocalStack EC2/VPC API Silently

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Infrastructure |
| **Time Lost** | ~2 hours debugging |
| **Discovered** | `terraform apply` failed mid-plan with HTTP 400 errors after upgrading provider |

**Symptom:**

After allowing Terraform to upgrade the AWS provider from `~> 4.67` to `~> 5.0` during a `terraform init -upgrade`, subsequent `terraform plan` runs failed:

```
│ Error: creating EC2 VPC: operation error EC2: CreateVpc,
│ https response error StatusCode: 400, RequestID: ...,
│ api error InvalidParameterValue: The tenancy value 'default' is invalid.
```

The same code deployed successfully the previous day on provider `4.67.0`. No changes were made to the Terraform HCL.

**Root Cause:**

AWS provider v5.x changed how it serialises certain EC2 API parameters (specifically around tenancy and VPC creation). LocalStack's EC2 implementation, which mimics the AWS EC2 API surface, had not yet been updated to handle the new v5.x parameter encoding. The provider and LocalStack were out of sync.

This is a known compatibility issue when using LocalStack as a development backend — the LocalStack team tracks AWS provider compatibility but there is always a lag for major version bumps.

**Fix Applied:**

Pinned the AWS provider version in all Terraform projects to prevent silent upgrades:

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.67"    # Pinned — v5.x breaks LocalStack EC2/VPC API
    }
  }
}
```

The version constraint was also committed to `.terraform.lock.hcl` to ensure reproducible applies across machines. This decision was documented in ADR-001.

**Business Impact:**

On real AWS, this specific provider version issue would not appear — AWS's real API handles both encodings. However, the underlying lesson applies directly to production: unpinned provider versions cause `terraform apply` to fail after a routine `terraform init -upgrade`, which can block infrastructure changes during an incident. Pinning provider versions is a production requirement and a core Terraform best practice.

---

## Problem 3 — EC2 Module Missing Second Public Subnet Output

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Infrastructure |
| **Time Lost** | ~45 minutes |
| **Discovered** | `terraform plan` error when building `ha-aws-architecture` on top of the VPC module |

**Symptom:**

When composing the `ha-aws-architecture` module (which requires two subnets for ALB multi-AZ placement) on top of the `modules/vpc` module, `terraform plan` failed:

```
│ Error: Unsupported attribute
│   on ha-aws-architecture/main.tf line 47, in resource "aws_lb" "main":
│   │ module.vpc.public_subnet_b_id
│ This object does not have an attribute named "public_subnet_b_id".
```

The VPC module had a `public_subnet_a` resource but its output was named `public_subnet_id`, and there was no output at all for `public_subnet_b`.

**Root Cause:**

The VPC module was designed initially for the `aws-foundation` project, which only needed one public subnet. The second subnet (`public_b`) was added to the VPC module's `main.tf` for HA purposes, but its corresponding output was not added to `modules/vpc/output.tf`. The `ha-aws-architecture` project assumed both outputs would be available.

**Fix Applied:**

Added the missing output to `modules/vpc/output.tf`:

```hcl
output "public_subnet_b_id" {
  description = "ID of the second public subnet (AZ-b) — required for ALB multi-AZ placement"
  value       = aws_subnet.public_b.id
}
```

Also renamed `public_subnet_id` to `public_subnet_a_id` for clarity and consistency, and updated all callers.

**Business Impact:**

A module interface that does not expose what consumers need forces callers to break encapsulation (reaching into module internals). In a team environment with shared modules, this breaks dependent projects silently until `terraform plan` is run. This is the exact reason module interfaces should be defined and versioned before callers are written.

---

## Problem 4 — `t2.micro` EBS Optimisation: False-Positive Security Finding

| Field | Value |
| :-- | :-- |
| **Severity** | P3 — Tooling / False Positive |
| **Time Lost** | ~30 minutes investigation |
| **Discovered** | Checkov CI scan flagging `CKV_AWS_135` on `aws_instance.web` |

**Symptom:**

Checkov reported the following finding on every run:

```
Check: CKV_AWS_135: "Ensure that EC2 instance should disable IMDSv1"
...
Check: CKV_AWS_135: "Ensure that AWS EC2 instance has EBS optimization enabled"
FAILED for resource: aws_instance.web
File: aws-foundation/main.tf
```

**Root Cause:**

The `t2.micro` instance type does not support EBS optimisation — it is not a capability of that instance class. AWS's own documentation lists `t2.*` as not supporting EBS optimisation. Checkov's CKV_AWS_135 check does not filter by instance type and flags any instance without `ebs_optimized = true` regardless of whether the instance type supports the feature.

Adding `ebs_optimized = true` to a `t2.micro` would cause `terraform apply` to fail with:

```
│ Error: creating EC2 Instance: EbsOptimizedNotSupported:
│ The requested configuration is not supported.
```

**Fix Applied:**

Added a suppression comment directly above the resource with a clear justification:

```hcl
#checkov:skip=CKV_AWS_135:t2.micro does not support EBS optimisation;
# upgrade to t3.micro or larger in production for this feature
resource "aws_instance" "web" {
```

**Business Impact:**

Uninvestigated false-positives cause engineers to suppress all scanner findings indiscriminately ("alert fatigue"), which eventually leads to real critical findings being missed. The correct approach — suppress with justification — keeps the scanner signal high. In production, the instance type would be `t3.micro` or larger, which does support EBS optimisation, and the skip comment would be removed.

---

## What These Failures Prove

Building these two projects in sequence forced solutions to four classes of production problem:

1. **Security reasoning, not just security tools** — recognising a wildcard KMS principal is wrong requires understanding AWS's trust model, not just knowing that KMS encryption exists.
2. **Dependency management under time pressure** — provider version pinning is often skipped in tutorials and discovered the hard way in production during an upgrade.
3. **Module interface design** — a module without complete outputs is a contract violation. The fix required designing the VPC module's interface upfront with all known consumers in mind.
4. **Scanner signal discipline** — distinguishing a real finding from a false-positive and documenting the decision is as important as fixing real findings.
