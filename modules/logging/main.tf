# modules/logging/main.tf
# Centralized, secure S3 logging bucket used by CloudTrail, ALB, and GuardDuty.
# Security posture:
#   - KMS CMK with key rotation and least-privilege key policy
#   - All public access blocked
#   - TLS-only bucket policy
#   - Versioning enabled for tamper evidence
#   - Lifecycle rules to archive and expire old logs

# =============================================================================
# KMS KEY — Customer Managed Key for log encryption
# SECURITY FIX: Principal no longer uses wildcard "*" — root account is scoped
# =============================================================================
data "aws_caller_identity" "current" {}

resource "aws_kms_key" "cloudtrail_kms_key" {
  description             = "KMS key for CloudTrail logging bucket — ${var.environment}"
  deletion_window_in_days = 10
  enable_key_rotation     = true   # Automated annual key rotation (compliance requirement)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRootAccountManagement"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudTrailEncrypt"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "kms:GenerateDataKey*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudTrailDescribeKey"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "kms:DescribeKey"
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "cloudtrail_kms_alias" {
  name          = "alias/${var.environment}-cloudtrail-logs"
  target_key_id = aws_kms_key.cloudtrail_kms_key.key_id
}

# =============================================================================
# S3 LOG BUCKET
# =============================================================================
resource "aws_s3_bucket" "logs" {
    bucket        = "${var.environment}-security-logs-${var.random_suffix}"
    force_destroy = true # NOTE: Lab only — prevents stuck state during destroy
}

# Disable ACLs in favour of bucket policy (AWS-recommended post-2022 approach)
resource "aws_s3_bucket_ownership_controls" "logs" {
    bucket = aws_s3_bucket.logs.id
    rule {
        object_ownership = "BucketOwnerEnforced"  # Disables ACLs entirely
    }
}

# Block all public access — four settings required for complete coverage
resource "aws_s3_bucket_public_access_block" "logs" {
    bucket = aws_s3_bucket.logs.id

    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
}

# Enable versioning — critical for tamper evidence (each log file is immutable)
resource "aws_s3_bucket_versioning" "logs" {
    bucket = aws_s3_bucket.logs.id
    versioning_configuration {
        status = "Enabled"
    }
}

# Enforce KMS encryption for all objects written to this bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
    bucket = aws_s3_bucket.logs.id
    rule {
        apply_server_side_encryption_by_default {
            sse_algorithm     = "aws:kms"
            kms_master_key_id = aws_kms_key.cloudtrail_kms_key.arn
        }
        bucket_key_enabled = true   # Reduces KMS API costs by ~99% for high-volume logging
    }
}

# Lifecycle policy — transition to cheaper storage and expire old logs
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
    bucket = aws_s3_bucket.logs.id

    rule {
        id     = "log-lifecycle"
        status = "Enabled"

        transition {
            days          = 30
            storage_class = "STANDARD_IA"  # Infrequent Access after 30 days
        }

        transition {
            days          = 90
            storage_class = "GLACIER"      # Deep archive after 90 days
        }

        expiration {
            days = 365                     # Expire after 1 year (adjust to compliance requirement)
        }

        noncurrent_version_expiration {
            noncurrent_days = 30           # Clean up old versions after 30 days
        }
    }
}

# =============================================================================
# BUCKET POLICY — CloudTrail write access + mandatory TLS enforcement
# =============================================================================
resource "aws_s3_bucket_policy" "allow_cloudtrail" {
    bucket = aws_s3_bucket.logs.id

    # Ensure ownership controls are set before attaching policy
    depends_on = [aws_s3_bucket_public_access_block.logs]

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Sid       = "DenyNonTLS"
                Effect    = "Deny"
                Principal = "*"
                Action    = "s3:*"
                Resource  = [
                    aws_s3_bucket.logs.arn,
                    "${aws_s3_bucket.logs.arn}/*"
                ]
                Condition = {
                    Bool = { "aws:SecureTransport" = "false" }
                }
            },
            {
                # CloudTrail: verify bucket ownership before writing
                Sid       = "AWSCloudTrailAclCheck"
                Effect    = "Allow"
                Principal = { Service = "cloudtrail.amazonaws.com" }
                Action    = "s3:GetBucketAcl"
                Resource  = aws_s3_bucket.logs.arn
            },
            {
                # CloudTrail: write log files — bucket owner retains full control
                Sid       = "AWSCloudTrailWrite"
                Effect    = "Allow"
                Principal = { Service = "cloudtrail.amazonaws.com" }
                Action    = "s3:PutObject"
                Resource  = "${aws_s3_bucket.logs.arn}/*"
                Condition = {
                    StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
                }
            }
        ]
    })
}
