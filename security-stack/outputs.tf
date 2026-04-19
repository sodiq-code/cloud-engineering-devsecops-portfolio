# security-stack/outputs.tf

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "instance_id" {
  description = "EC2 instance ID of the hardened web server"
  value       = aws_instance.web.id
}

output "security_group_id" {
  description = "Security Group ID applied to the web server"
  value       = aws_security_group.web_sg.id
}

output "log_bucket_name" {
  description = "S3 bucket name where CloudTrail and GuardDuty logs are stored"
  value       = module.logging.bucket_name
}

output "iam_instance_profile" {
  description = "IAM instance profile name providing EC2 access to the log bucket"
  value       = module.iam.instance_profile_name
}
