# modules/s3_test/main.tf

# Create an S3 bucket with a fixed, globally-unique name
resource "aws_s3_bucket" "test_bucket" {
  bucket = "afsod-week4-test-bucket-12345"
}

# Block all forms of public access to the S3 bucket
resource "aws_s3_bucket_public_access_block" "good_security" {
  bucket = aws_s3_bucket.test_bucket.id

  block_public_acls       = true # Prevent public ACLs on objects
  block_public_policy     = true # Prevent bucket policies that allow public access
  ignore_public_acls      = true # Ignore any public ACLs that might be set
  restrict_public_buckets = true # Restrict access to only AWS accounts and users
}

resource "aws_kms_key" "s3_key" {
  description             = "KMS Key for S3 bucket encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true # Best practice to enable rotation
}

resource "aws_kms_alias" "s3_alias" {
  name          = "alias/s3-app-key"
  target_key_id = aws_kms_key.s3_key.key_id
}

# Enforce server-side encryption by default on the S3 bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "encryption" {
  bucket = aws_s3_bucket.test_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"              # Use KMS encryption
      kms_master_key_id = aws_kms_key.s3_key.arn # Reference the key ARN
    }
  }
}