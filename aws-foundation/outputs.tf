# aws-foundation/outputs.tf

output "vpc_id" {
    description = "VPC ID"
    value       = module.vpc.vpc_id
}

output "instance_id" {
    description = "EC2 instance ID of the web server"
    value       = aws_instance.web.id
}

output "security_group_id" {
    description = "Security Group ID applied to the web server"
    value       = aws_security_group.web_sg.id
}

output "iam_instance_profile" {
    description = "IAM instance profile name attached to the EC2 instance"
    value       = module.iam.instance_profile_name
}
