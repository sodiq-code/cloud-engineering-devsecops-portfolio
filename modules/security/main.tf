# modules/security/main.tf
# Threat detection and audit trail stack:
#   - CloudTrail: full API activity logging with KMS encryption
#   - GuardDuty: ML-powered threat detection
#   - KMS CMK with least-privilege key policy (no wildcard principals)

data "aws_caller_identity" "current" {}

# =============================================================================
# KMS KEY — CloudTrail log encryption
# SECURITY FIX: Principal scoped to root account ARN (no wildcard "*")
# =============================================================================
resource "aws_kms_key" "cloudtrail_key" {
  description             = "CMK for CloudTrail log encryption — ${var.environment}"
  deletion_window_in_days = 10
  enable_key_rotation     = true

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

resource "aws_kms_alias" "cloudtrail_alias" {
  name          = "alias/${var.environment}-cloudtrail"
  target_key_id = aws_kms_key.cloudtrail_key.key_id
}

# =============================================================================
# CLOUDTRAIL — Organisation-wide API audit log
# Features: multi-region, log file validation, KMS encryption
# =============================================================================
resource "aws_cloudtrail" "main" {
    name                          = "${var.environment}-audit-trail"
    s3_bucket_name                = var.log_bucket_name
    include_global_service_events = true  # Capture IAM, STS, CloudFront events
    is_multi_region_trail         = true  # Monitor all AWS regions
    enable_log_file_validation    = true  # Detect log tampering via SHA-256 digest files
    kms_key_id                    = aws_kms_key.cloudtrail_key.arn
}

# =============================================================================
# GUARDDUTY — ML-powered threat detection
# Monitors VPC flow logs, DNS logs, CloudTrail events for suspicious behaviour
# =============================================================================
resource "aws_guardduty_detector" "main" {
    enable                       = true
    finding_publishing_frequency = "FIFTEEN_MINUTES"  # Export findings every 15 min
}
