# S3 bucket name for log storage
output "bucket_name" { value = aws_s3_bucket.logs.id }

# S3 bucket ARN for IAM policies and cross-account access
output "bucket_arn" { value = aws_s3_bucket.logs.arn }