# week3-s3-localstack/main.tf
# Secure-by-Design S3 storage provisioned with Terraform.
# Security controls applied:
#   - KMS Customer Managed Key (CMK) with annual rotation
#   - All public access blocked (4-setting complete block)
#   - ACLs disabled (BucketOwnerEnforced — post-2022 AWS recommendation)
#   - TLS-only bucket policy (deny HTTP requests)
#   - S3 Versioning for tamper evidence
#   - Lifecycle rules for cost-optimised log retention

# =============================================================================
# KMS CMK — Customer Managed Key for bucket encryption
# =============================================================================
resource "aws_kms_key" "logs_key" {
    description             = "KMS CMK for logs bucket encryption — ${var.bucket_name}"
    deletion_window_in_days = 10
    enable_key_rotation     = true  # Automated annual rotation — compliance best practice
}

resource "aws_kms_alias" "logs_key_alias" {
    name          = "alias/week3-logs-key"
    target_key_id = aws_kms_key.logs_key.key_id
}

# =============================================================================
# S3 BUCKET
# =============================================================================
resource "aws_s3_bucket" "logs" {
    bucket = var.bucket_name

    tags = {
        Name      = "week3-tf-s3"
        Env       = "dev"
        ManagedBy = "Terraform"
    }
}

# Disable ACLs entirely — use bucket policies for access control instead
# (aws_s3_bucket_acl is deprecated since AWS April 2023)
resource "aws_s3_bucket_ownership_controls" "logs" {
    bucket = aws_s3_bucket.logs.id
    rule {
        object_ownership = "BucketOwnerEnforced"
    }
}

# Block ALL forms of public access to the bucket (4-setting hard block)
resource "aws_s3_bucket_public_access_block" "logs_public_access_block" {
    bucket = aws_s3_bucket.logs.id

    block_public_acls       = true  # Reject PUT requests with public ACLs
    block_public_policy     = true  # Reject bucket policies that grant public access
    ignore_public_acls      = true  # Ignore any existing public ACLs on objects
    restrict_public_buckets = true  # Restrict cross-account access via policies
}

# Enable versioning — each object version is immutable; supports WORM-like guarantees
resource "aws_s3_bucket_versioning" "logs" {
    bucket = aws_s3_bucket.logs.id
    versioning_configuration {
        status = "Enabled"
    }
}

# Enforce KMS SSE on all objects written to this bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "logs_encryption" {
    bucket = aws_s3_bucket.logs.id

    rule {
        apply_server_side_encryption_by_default {
            sse_algorithm     = "aws:kms"
            kms_master_key_id = aws_kms_key.logs_key.arn
        }
        bucket_key_enabled = true  # Reduces KMS API call cost by ~99%
    }
}

# Lifecycle policy — archive and expire logs to control storage costs
resource "aws_s3_bucket_lifecycle_configuration" "logs_lifecycle" {
    bucket = aws_s3_bucket.logs.id

    rule {
        id     = "log-archival-and-expiry"
        status = "Enabled"

        transition {
            days          = 30
            storage_class = "STANDARD_IA"  # Infrequent Access tier after 30 days
        }

        transition {
            days          = 90
            storage_class = "GLACIER"      # Deep archive after 90 days
        }

        expiration {
            days = 365  # Expire after 1 year (adjust to regulatory requirement)
        }

        noncurrent_version_expiration {
            noncurrent_days = 30  # Remove old versions after 30 days
        }
    }
}

# =============================================================================
# BUCKET POLICY — Enforce TLS-only access
# Denies any API call made without HTTPS (aws:SecureTransport = false)
# =============================================================================
resource "aws_s3_bucket_policy" "enforce_tls" {
    bucket = aws_s3_bucket.logs.id

    depends_on = [aws_s3_bucket_public_access_block.logs_public_access_block]

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Sid       = "DenyNonTLSRequests"
                Effect    = "Deny"
                Principal = "*"
                Action    = "s3:*"
                Resource = [
                    aws_s3_bucket.logs.arn,
                    "${aws_s3_bucket.logs.arn}/*"
                ]
                Condition = {
                    Bool = { "aws:SecureTransport" = "false" }
                }
            }
        ]
    })
}
