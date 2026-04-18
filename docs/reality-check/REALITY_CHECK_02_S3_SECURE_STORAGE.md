# Reality Check: S3 Secure Storage (`s3-secure-storage`)

**Project:** `s3-secure-storage/`  
**Stack:** Terraform, AWS S3, KMS, LocalStack  
**Summary:** Provisioning a "Secure-by-Design" S3 bucket revealed three non-obvious pitfalls: a broken bucket policy when used with LocalStack's HTTP endpoint, a deprecated ACL model that changed mid-2023, and a KMS key that appeared correct but allowed over-broad access.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| TLS-only bucket policy rejected all LocalStack requests (HTTP-only dev environment) | P2 | 1 hour | ✅ Fixed — skip enforcement in dev |
| AWS changed S3 ACL model in April 2023 — `aws_s3_bucket_acl` resource silently deprecated | P2 | 45 min | ✅ Fixed — migrated to `BucketOwnerEnforced` |
| KMS key rotation disabled by default — missed because Terraform apply succeeds without it | P3 | Caught at review | ✅ Fixed — added `enable_key_rotation = true` |

---

## Problem 1 — TLS-Only Bucket Policy Blocked All LocalStack Access

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Development Blocker |
| **Time Lost** | ~1 hour |
| **Discovered** | `aws s3 ls` via LocalStack CLI returned `403 Forbidden` after applying bucket policy |

**Symptom:**

After adding the TLS-only enforcement bucket policy — the recommended pattern to deny any HTTP request to the bucket — all S3 operations against LocalStack started returning:

```
An error occurred (AccessDenied) when calling the ListObjectsV2 operation:
Access Denied
```

The bucket, the KMS key, and the versioning config had all applied successfully. Only requests to the bucket failed.

**Root Cause:**

The TLS bucket policy uses the `aws:SecureTransport` condition key to deny requests where `SecureTransport = false` (i.e., HTTP, not HTTPS):

```json
{
  "Effect": "Deny",
  "Principal": "*",
  "Action": "s3:*",
  "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
  "Condition": {
    "Bool": { "aws:SecureTransport": "false" }
  }
}
```

LocalStack's default endpoint is `http://localhost:4566` — plain HTTP, not HTTPS. So `aws:SecureTransport` evaluates to `false` for every LocalStack request, and the Deny effect fires. Every `aws s3` CLI command or Terraform S3 data source was immediately rejected by the bucket policy that was just applied.

This is the correct production behaviour — in real AWS, all requests should be HTTPS. But in the LocalStack development environment, it breaks everything.

**Fix Applied:**

The bucket policy condition was scoped to allow LocalStack requests in the development environment. The cleaner long-term approach was to accept the limitation and treat the TLS policy as a production-only control:

```hcl
# Production TLS policy is defined but applied conditionally:
# In dev (LocalStack), this policy is not attached because LocalStack uses HTTP.
# In production (real AWS), this policy must be attached before the bucket is used.
resource "aws_s3_bucket_policy" "tls_only" {
  count  = var.environment == "production" ? 1 : 0
  bucket = aws_s3_bucket.main.id
  policy = data.aws_iam_policy_document.tls_only.json
}
```

This was documented in ADR-001 as a known LocalStack deviation: security controls that depend on transport protocol inspection cannot be validated locally and must be tested against real AWS or with a LocalStack HTTPS proxy.

**Business Impact:**

In production, this bucket policy is not optional — without it, HTTP (unencrypted) requests to S3 are accepted, allowing a network attacker to intercept data in transit. Any HIPAA, PCI-DSS, or GDPR-regulated bucket must enforce TLS. The dev/prod conditional pattern ensures the policy is written and tested without blocking development.

---

## Problem 2 — AWS Changed the S3 ACL Model in April 2023

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — API Breakage |
| **Time Lost** | ~45 minutes |
| **Discovered** | Terraform apply produced a deprecation warning, then `aws_s3_bucket_acl` resource failed to create |

**Symptom:**

When following older Terraform AWS S3 examples, the `aws_s3_bucket_acl` resource was included to set the bucket to `private`:

```hcl
resource "aws_s3_bucket_acl" "main" {
  bucket = aws_s3_bucket.main.id
  acl    = "private"
}
```

This produced:

```
│ Error: creating S3 Bucket ACL: OperationAborted: A conflicting conditional operation
│ is currently in progress against this resource. Please try again.
│
│ (later) Error: setting ACL: AccessControlListNotSupported: The bucket does not allow ACLs
```

**Root Cause:**

In April 2023, AWS changed the default Object Ownership setting for all new S3 buckets from `ObjectWriter` (ACL-based) to `BucketOwnerEnforced` (ACL-disabled). Under `BucketOwnerEnforced`, ACLs are permanently disabled at the API level — any call to `PutBucketAcl` or `PutObjectAcl` returns `AccessControlListNotSupported`.

Most Terraform tutorials and Stack Overflow answers predating April 2023 still use `aws_s3_bucket_acl`. Following these examples on any bucket created after April 2023 will fail immediately.

**Fix Applied:**

Removed `aws_s3_bucket_acl` entirely and added the explicit ownership control resource instead:

```hcl
resource "aws_s3_bucket_ownership_controls" "main" {
  bucket = aws_s3_bucket.main.id
  rule {
    object_ownership = "BucketOwnerEnforced"    # Disables the entire ACL system
  }
}
```

This is now the correct, AWS-recommended approach. It explicitly sets the post-April-2023 default, making the configuration self-documenting and portable.

**Business Impact:**

Any Terraform module written before April 2023 that manages S3 ACLs will silently fail when applied against new buckets. In a CI/CD pipeline that applies IaC automatically, this failure surfaces as a cryptic API error, not as "your ACL configuration is outdated." Teams that aren't actively monitoring their pipelines will discover this failure the wrong way — when a bucket is created during an incident or go-live.

---

## Problem 3 — KMS Key Rotation Was Disabled by Default

| Field | Value |
| :-- | :-- |
| **Severity** | P3 — Compliance |
| **Time Lost** | Caught at review |
| **Discovered** | Code review of `aws_kms_key` resource in `s3-secure-storage/main.tf` |

**Symptom:**

The KMS CMK was created without explicitly setting `enable_key_rotation`. Terraform apply succeeded. The key worked correctly. There was no error. The problem was invisible until reviewing the resource against the CIS AWS Foundations Benchmark.

**Root Cause:**

The `enable_key_rotation` attribute on `aws_kms_key` defaults to `false` in the Terraform AWS provider. AWS's own default for new KMS keys is also disabled rotation. This means a KMS key — which may protect years of CloudTrail logs — never has its cryptographic material rotated unless explicitly configured.

The CIS AWS Foundations Benchmark (control 3.7) requires annual KMS key rotation for keys used in regulated workloads. The key rotation is also a FIPS 140-2 requirement for keys protecting data subject to US government data standards.

**Fix Applied:**

```hcl
resource "aws_kms_key" "main" {
  description             = "CMK for S3 log bucket encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true    # Required: CIS Benchmark 3.7, FIPS 140-2
  
  tags = {
    Purpose   = "S3-Encryption"
    Rotation  = "Annual-Auto"
  }
}
```

**Business Impact:**

A KMS key that never rotates uses the same cryptographic material indefinitely. If an attacker gains access to the key material (through a side-channel attack or a compromised HSM), they can decrypt all data encrypted by that key — past, present, and future. With annual rotation, the exposure window is limited to one year of data. In regulated industries (PCI-DSS, HIPAA), missing key rotation is a critical audit finding.

---

## What These Failures Prove

The S3 project encountered three different classes of failure that appear in production environments:

1. **Dev/prod environment gap** — a security control (TLS-only) that is correct and required in production can break the development environment if the tooling (LocalStack) doesn't support the same protocol. The solution is to document the gap and ensure the control exists in the production Terraform code even if not exercised locally.
2. **AWS API evolution** — AWS changes defaults over time. Code written in 2022 breaks in 2024 not because of a bug in your code, but because the API contract changed. The only defence is staying current with AWS release notes and running `terraform plan` regularly against real AWS (not just LocalStack, which may lag).
3. **Silent non-compliance** — some security controls don't fail loudly; they just aren't applied. `enable_key_rotation = false` is the default and the system works perfectly without it — right up until an auditor looks at your KMS console.
