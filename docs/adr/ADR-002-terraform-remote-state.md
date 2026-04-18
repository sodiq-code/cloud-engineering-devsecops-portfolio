# ADR-002: Terraform Remote State with S3 Backend and DynamoDB Locking

**Date:** 2025-11-01  
**Status:** Accepted (Production Recommendation)  
**Deciders:** Jimoh Sodiq Bolaji  
**Category:** IaC / State Management

---

## Context

All Terraform projects in this portfolio currently use **local state** (`terraform.tfstate` stored on the developer's machine). This creates three production-critical risks:

1. **State Loss:** If the local machine is lost or `terraform.tfstate` is accidentally deleted, Terraform loses track of what it created — resources become "orphaned" and unmanageable.
2. **Collaboration Conflict:** Two engineers running `terraform apply` simultaneously can corrupt the state file (race condition).
3. **Security:** Local state files may contain sensitive values (resource IDs, ARNs) and should not be committed to Git.

## Decision

Adopt the **S3 Remote Backend with DynamoDB State Locking** pattern for all production Terraform deployments. This is the AWS-recommended, industry-standard approach for team-based IaC.

### Implementation Pattern

```hcl
# Add this backend block to any Terraform project's main.tf
terraform {
  backend "s3" {
    bucket         = "my-org-terraform-state"    # Dedicated state bucket
    key            = "week8-ha-deploy/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true                        # SSE-KMS encryption at rest
    dynamodb_table = "terraform-state-lock"      # Prevents concurrent applies
  }
}
```

### State Backend Infrastructure (bootstrap once)

```hcl
# Create the state bucket (one-time bootstrap — apply before all other projects)
resource "aws_s3_bucket" "tf_state" {
  bucket = "my-org-terraform-state"
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}
```

## Consequences

### Positive
- ✅ State is shared and consistent across team members
- ✅ DynamoDB locking prevents concurrent `apply` conflicts
- ✅ S3 versioning enables state rollback if drift occurs
- ✅ KMS encryption protects sensitive values in state

### Negative
- ⚠️ State bucket and DynamoDB table must be bootstrapped before first use
- ⚠️ State bucket itself cannot be managed by Terraform (chicken-and-egg)
- ⚠️ Costs: ~$0.50/month for S3 + minimal DynamoDB

### LocalStack Note
This portfolio uses LocalStack for development. The S3 backend is not used locally because LocalStack does not fully emulate the Terraform S3 backend protocol. This is the only deviation from the production pattern and is documented here for transparency.

## Alternatives Considered

| Option | Reason Not Chosen |
| :--- | :--- |
| Terraform Cloud | Requires account; adds external dependency for a portfolio |
| GitLab/GitHub state | GitHub does not natively support Terraform state; requires third-party action |
| Local state | Accepted for LocalStack dev; not acceptable for production |
