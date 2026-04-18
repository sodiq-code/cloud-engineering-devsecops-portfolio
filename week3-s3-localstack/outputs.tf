# week3-s3-localstack/outputs.tf

output "bucket_name" {
    description = "Name of the created S3 bucket"
    value       = aws_s3_bucket.logs.id
}

output "bucket_arn" {
    description = "ARN of the S3 bucket — use in IAM policies"
    value       = aws_s3_bucket.logs.arn
}

output "kms_key_arn" {
    description = "ARN of the KMS CMK used for bucket encryption"
    value       = aws_kms_key.logs_key.arn
}

output "kms_key_id" {
    description = "ID of the KMS CMK"
    value       = aws_kms_key.logs_key.key_id
}
