# week6-deploy/main.tf
# Full-stack local deployment: VPC + IAM + Security Monitoring + Hardened EC2.
# Extends week5 by adding CloudTrail audit trail and GuardDuty threat detection,
# demonstrating the "Security Layer" composition pattern.

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
    s3_use_path_style           = true

    endpoints {
        ec2        = "http://localhost:4566"
        iam        = "http://localhost:4566"
        sts        = "http://localhost:4566"
        s3         = "http://localhost:4566"
        cloudtrail = "http://localhost:4566"
        guardduty  = "http://localhost:4566"
        kms        = "http://localhost:4566"
    }
}

# =============================================================================
# LAYER 1: Logging (Audit Log Storage)
# =============================================================================
module "logging" {
    source        = "../modules/logging"
    environment   = "local"
    random_suffix = "12345"
}

# =============================================================================
# LAYER 2: Security Monitoring (CloudTrail + GuardDuty)
# =============================================================================
module "security" {
    source          = "../modules/security"
    environment     = "local"
    log_bucket_name = module.logging.bucket_name
}

# =============================================================================
# LAYER 3: Network Infrastructure
# =============================================================================
module "vpc" {
    source      = "../modules/vpc"
    environment = "local"
    region      = "us-east-1"
}

# =============================================================================
# LAYER 4: Identity & Access (Least Privilege)
# =============================================================================
module "iam" {
    source            = "../modules/iam"
    environment       = "local"
    target_bucket_arn = module.logging.bucket_arn
}

# =============================================================================
# SECURITY GROUP — Hardened firewall rules
# =============================================================================
resource "aws_security_group" "web_sg" {
    name        = "web-server-sg"
    description = "Allow HTTP inbound; restrict egress to VPC CIDR"
    vpc_id      = module.vpc.vpc_id

    ingress {
        description = "HTTP from internet"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        description = "Restrict egress to VPC only — prevents data exfiltration"
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["10.0.0.0/16"]
    }
}

# =============================================================================
# EC2 WEB SERVER — Fully hardened, security-monitored instance
# Added in week6: instance is now audited by CloudTrail + GuardDuty
# =============================================================================
resource "aws_instance" "web" {
    ami                    = "ami-12345678"        # LocalStack dummy AMI
    instance_type          = "t2.micro"
    subnet_id              = module.vpc.public_subnet_id
    iam_instance_profile   = module.iam.instance_profile_name
    vpc_security_group_ids = [aws_security_group.web_sg.id]

    # IMDSv2: Prevents SSRF credential theft via instance metadata endpoint
    metadata_options {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
    }

    # Encrypt root volume at rest using AES-256
    root_block_device {
        encrypted             = true
        volume_type           = "gp3"
        delete_on_termination = true
    }

    timeouts {
        create = "2m"
    }

    tags = {
        Name        = "Week6-Secure-WebServer"
        Environment = "local"
        ManagedBy   = "Terraform"
    }
}
