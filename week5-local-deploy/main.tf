# week5-local-deploy/main.tf
# First full-stack local deployment: VPC + IAM + Security + Hardened EC2.
# All four modules work together to create a production-mirrored local environment.
# Demonstrates the module composition pattern used in all subsequent projects.

terraform {
    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 5.0"
        }
    }
}

provider "aws" {
    region                      = "us-east-1"
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_requesting_account_id  = true

    endpoints {
        ec2 = "http://localhost:4566"
        iam = "http://localhost:4566"
        sts = "http://localhost:4566"
        kms = "http://localhost:4566"
    }
}

# =============================================================================
# MODULE 1: Network Layer
# =============================================================================
module "vpc" {
    source      = "../modules/vpc"
    environment = "local"
    region      = "us-east-1"
}

# =============================================================================
# MODULE 2: Identity Layer (Least Privilege)
# =============================================================================
module "iam" {
    source            = "../modules/iam"
    environment       = "local"
    target_bucket_arn = "*"    # Scoped to specific bucket in production
}

# =============================================================================
# SECURITY GROUP — Web Server Firewall Rules
# Inbound: HTTP from internet only
# Outbound: Restricted to VPC CIDR (defence-in-depth, prevents exfiltration)
# =============================================================================
resource "aws_security_group" "web_sg" {
    name        = "web-server-sg"
    description = "Allow HTTP inbound; restrict egress to VPC"
    vpc_id      = module.vpc.vpc_id

    ingress {
        description = "HTTP from internet"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        description = "Restrict egress to VPC CIDR only (prevents internet exfiltration)"
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["10.0.0.0/16"]
    }
}

# =============================================================================
# EC2 WEB SERVER — Hardened Configuration
# Security controls: IMDSv2, encrypted root volume, IAM role, no public IP
# =============================================================================
resource "aws_instance" "web" {
    ami                    = "ami-12345678"        # LocalStack dummy AMI
    instance_type          = "t2.micro"
    subnet_id              = module.vpc.public_subnet_id
    iam_instance_profile   = module.iam.instance_profile_name
    vpc_security_group_ids = [aws_security_group.web_sg.id]

    # IMDSv2: Session tokens required — prevents SSRF attacks on the metadata service
    metadata_options {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
    }

    # Encrypt root volume — all data at rest is protected
    root_block_device {
        encrypted             = true
        volume_type           = "gp3"
        delete_on_termination = true
    }

    timeouts {
        create = "2m"
    }

    tags = {
        Name        = "Week5-Secure-WebServer"
        Environment = "local"
        ManagedBy   = "Terraform"
    }
}
