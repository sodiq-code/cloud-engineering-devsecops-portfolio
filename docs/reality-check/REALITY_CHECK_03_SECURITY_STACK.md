# Reality Check: Security Stack (`security-stack`)

**Project:** `security-stack/`  
**Stack:** Terraform, AWS CloudTrail, GuardDuty, KMS, S3, LocalStack  
**Summary:** Adding the full security monitoring layer (CloudTrail + GuardDuty + KMS) on top of the foundation infrastructure surfaced a circular dependency between the trail and its log bucket policy, a GuardDuty enablement state problem, and a cross-module dependency ordering issue.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| CloudTrail requires a bucket policy that references the trail ARN — circular dependency | P2 | 1.5 hours | ✅ Fixed — split resource creation order |
| GuardDuty returned "already enabled" error when running `terraform apply` twice | P2 | 30 min | ✅ Fixed — added `lifecycle { prevent_destroy }` |
| CloudTrail log validation requires KMS key, but key policy requires trail ARN — ordering deadlock | P2 | 1 hour | ✅ Fixed — use account ARN in key policy, not trail ARN |

---

## Problem 1 — CloudTrail S3 Bucket Policy: Circular ARN Reference

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Infrastructure |
| **Time Lost** | ~1.5 hours |
| **Discovered** | `terraform apply` failed with `InsufficientS3BucketPolicyException` on the CloudTrail resource |

**Symptom:**

After creating the S3 log bucket and the CloudTrail trail in the same Terraform plan, the apply failed:

```
│ Error: creating CloudTrail: InsufficientS3BucketPolicyException:
│ Bucket my-trail-bucket does not exist, or insufficient permissions.
│ Make sure the bucket policy grants CloudTrail permission to write to the bucket.
```

The bucket existed (Terraform had just created it). The bucket policy had been written to allow `cloudtrail.amazonaws.com` to `s3:PutObject` on the bucket.

**Root Cause:**

The CloudTrail S3 bucket policy requires the trail's own ARN in the condition key:

```json
{
  "Condition": {
    "StringEquals": {
      "aws:SourceArn": "arn:aws:cloudtrail:region:account:trail/my-trail"
    }
  }
}
```

But the trail ARN is not known until the trail is created. And the trail cannot be created until the bucket policy is applied. This is a genuine circular dependency: the bucket policy needs the trail ARN, and the trail creation needs the bucket policy.

The naive approach — put both in the same Terraform plan — hits the dependency deadlock because Terraform cannot determine a valid creation order.

**Fix Applied:**

Broke the circular dependency by using the account-level CloudTrail service principal without a specific trail ARN condition in the bucket policy, then adding the trail-specific condition separately as a separate resource after the trail exists:

```hcl
# Step 1: Bucket policy without trail-specific ARN (allows CloudTrail service to start)
data "aws_iam_policy_document" "cloudtrail_bucket" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.trail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

# Step 2: CloudTrail references the bucket (policy is already in place)
resource "aws_cloudtrail" "main" {
  name           = "org-cloudtrail"
  s3_bucket_name = aws_s3_bucket.trail_logs.id
  depends_on     = [aws_s3_bucket_policy.trail_logs]
}
```

**Business Impact:**

A CloudTrail trail that cannot write to its S3 bucket logs nothing. Every AWS API call in the account goes unrecorded. This is the equivalent of disabling all security cameras in a building — attackers can perform privilege escalation, data exfiltration, and account takeover without any audit evidence. For SOC2 and PCI-DSS compliance, a gap in CloudTrail coverage is a reportable finding.

---

## Problem 2 — GuardDuty "Already Enabled" Error on Re-Apply

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Infrastructure |
| **Time Lost** | ~30 minutes |
| **Discovered** | Second `terraform apply` in the same account failed on the GuardDuty detector resource |

**Symptom:**

The first `terraform apply` succeeded. After destroying and re-applying (a common development workflow), the apply failed:

```
│ Error: creating GuardDuty Detector: BadRequestException:
│ The request is rejected because a GuardDuty master account is already enabled.
│ Account ID: 000000000000
```

**Root Cause:**

GuardDuty is an account-level service. When you enable it with `aws_guardduty_detector`, AWS creates a regional detector in your account. If you then run `terraform destroy` and `terraform apply` again, Terraform attempts to create a new detector — but the old one was not fully removed by the destroy (LocalStack's GuardDuty state is persistent across docker restarts in some versions).

Additionally, in real AWS, GuardDuty has a 30-day pending period before a trial ends — disabling and re-enabling it within that period can leave residual state.

**Fix Applied:**

Added a `lifecycle` block to prevent accidental destruction and a `terraform import` step for the existing detector:

```hcl
resource "aws_guardduty_detector" "main" {
  enable = true

  # Prevent destroy — GuardDuty detectors should never be accidentally deleted
  # Deletion creates a 30-day coverage gap and may require AWS support to reset
  lifecycle {
    prevent_destroy = true
  }
}
```

For development resets, the destroy sequence was changed to disable before destroy:

```bash
# Correct GuardDuty teardown sequence:
aws guardduty delete-detector --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
terraform destroy
```

**Business Impact:**

A GuardDuty detector that gets accidentally deleted creates an immediate and silent coverage gap. GuardDuty inspects VPC Flow Logs, DNS query logs, and CloudTrail events for malicious patterns — if it is disabled, threats like cryptocurrency mining, data exfiltration, and compromised IAM credentials are not detected. In real AWS, a `prevent_destroy = true` lifecycle policy is non-negotiable for GuardDuty and CloudTrail resources.

---

## Problem 3 — KMS Key Policy Deadlock with CloudTrail Log Validation

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Configuration |
| **Time Lost** | ~1 hour |
| **Discovered** | `terraform apply` failed on CloudTrail resource with `KMSAccessDeniedException` |

**Symptom:**

Enabling CloudTrail with `enable_log_file_validation = true` and a KMS CMK failed:

```
│ Error: creating CloudTrail: KMSAccessDeniedException:
│ CloudTrail is not authorized to use key: arn:aws:kms:.../my-key
│ Please check your KMS key policy, CloudTrail does not have permission to use this key.
```

The KMS key policy had a statement allowing `cloudtrail.amazonaws.com` to use the key, but the policy also included a condition requiring the source ARN to match the trail ARN — which didn't exist yet.

**Root Cause:**

Similar to Problem 1, this was a circular reference: the KMS key policy required the trail ARN in a condition (`aws:SourceArn`), but the trail ARN is only known after the trail is created, and the trail can only be created after the KMS key policy is applied.

The AWS documentation shows the trail ARN condition as a security best-practice recommendation. When followed naively, it creates the same deadlock as the S3 bucket policy problem.

**Fix Applied:**

For the initial apply, the KMS key policy was written without the `aws:SourceArn` condition on the CloudTrail statement. After the trail ARN was known (from `terraform output` or `aws cloudtrail describe-trails`), the key policy was updated with the specific ARN:

```hcl
# In the KMS key policy — allow CloudTrail service (no trail ARN condition on first apply)
statement {
  principals {
    type        = "Service"
    identifiers = ["cloudtrail.amazonaws.com"]
  }
  actions = [
    "kms:GenerateDataKey*",
    "kms:DescribeKey"
  ]
  resources = ["*"]
}
```

A two-stage apply was used for the initial deployment, which is a documented AWS pattern for CloudTrail + KMS provisioning.

**Business Impact:**

CloudTrail log file validation uses a cryptographic hash chain to prove that log files have not been tampered with after delivery. Without the KMS key, log validation either doesn't work or falls back to unencrypted storage. For forensic investigation purposes, tampered CloudTrail logs are inadmissible evidence. This control is required for PCI-DSS Requirement 10.5.5 (log file integrity).

---

## What These Failures Prove

The security stack project hit three versions of the same underlying pattern — **circular resource dependencies** — each expressed differently:

1. CloudTrail bucket policy needs the trail ARN → trail needs the bucket policy
2. KMS key policy needs the trail ARN → trail needs the KMS key
3. GuardDuty lifecycle management is stateful at the AWS account level, not just in Terraform state

These failures demonstrate that **security infrastructure is the hardest class of infrastructure to provision idempotently** because the resources it creates are interdependent by design. Recognising and resolving circular dependencies — rather than papering over them — is a core IaC competency.
