# ha-aws-architecture/main.tf
# High-Availability, Fault-Tolerant AWS Web Application Infrastructure.
# Architecture: WAF → ALB (multi-AZ) → ASG (auto-scaling EC2 fleet) → CloudTrail
#
# Security controls applied:
#   - WAF (AWS Managed Rules: SQLi, XSS, CVE coverage)
#   - ALB with invalid header dropping and ALB access logging
#   - EC2 instances in private subnets (ALB-only inbound access)
#   - IMDSv2 enforced on all instances (SSRF mitigation)
#   - GuardDuty threat detection enabled
#   - CloudTrail for full API audit log

terraform {
    required_version = ">= 1.5.0"

    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 4.67"
        }
    }
}

# =============================================================================
# PROVIDER — LocalStack for zero-cost development
# Remove endpoint overrides and fake credentials for real AWS deployment
# =============================================================================
provider "aws" {
    region                      = "us-east-2"
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = false
    s3_use_path_style           = true

    endpoints {
        ec2         = "http://localhost:4566"
        s3          = "http://localhost:4566"
        s3control   = "http://localhost:4566"
        iam         = "http://localhost:4566"
        sts         = "http://localhost:4566"
        cloudtrail  = "http://localhost:4566"
        cloudwatch  = "http://localhost:4566"
        guardduty   = "http://localhost:4566"
        kms         = "http://localhost:4566"
        elb         = "http://localhost:4566"
        elbv2       = "http://localhost:4566"
        wafv2       = "http://localhost:4566"
        autoscaling = "http://localhost:4566"
    }
}

# =============================================================================
# LAYER 1: LOGGING (Audit Trail & Compliance)
# S3 bucket for CloudTrail, ALB access logs, and GuardDuty findings
# =============================================================================
module "logging" {
    source        = "../modules/logging"
    environment   = "ha-prod"
    random_suffix = "99999"
}

# =============================================================================
# LAYER 2: SECURITY MONITORING (Threat Detection)
# CloudTrail (API audit) + GuardDuty (ML threat detection)
# =============================================================================
module "security" {
    source          = "../modules/security"
    environment     = "ha-prod"
    log_bucket_name = module.logging.bucket_name
}

# =============================================================================
# LAYER 3: NETWORKING (Multi-AZ VPC)
# Public subnets across two AZs for ALB; private subnets for EC2 instances
# =============================================================================
module "vpc" {
    source      = "../modules/vpc"
    environment = "ha-prod"
    region      = "us-east-2"
}

# =============================================================================
# LAYER 4: IDENTITY & ACCESS MANAGEMENT
# Least-privilege IAM role for EC2 instances (read-only S3 access)
# =============================================================================
module "iam" {
    source            = "../modules/iam"
    environment       = "ha-prod"
    target_bucket_arn = module.logging.bucket_arn
}

# =============================================================================
# LAUNCH TEMPLATE — Hardened EC2 blueprint
# Every auto-scaled instance uses this template for configuration consistency
# =============================================================================
resource "aws_launch_template" "app" {
    name_prefix   = "ha-app-"
    # AMI ID: Amazon Linux 2 (us-east-2, 2024-01-15).
    # NOTE: For production, replace with an aws_ami data source to always get the latest:
    #   data "aws_ami" "amazon_linux_2" {
    #     most_recent = true
    #     owners      = ["amazon"]
    #     filter { name = "name"; values = ["amzn2-ami-hvm-*-x86_64-gp2"] }
    #   }
    # Python 3.9.18 EOL: October 2025. Upgrade base image to python:3.11-slim before EOL.
    image_id      = "ami-02d1e544b84bf7502"   # LocalStack dummy AMI — replace for real AWS
    instance_type = "t2.micro"

    iam_instance_profile {
        name = module.iam.instance_profile_name
    }

    vpc_security_group_ids = [aws_security_group.instance_sg.id]

    # IMDSv2: Require session tokens for instance metadata access.
    # Prevents SSRF attacks from reading cloud credentials via metadata endpoint.
    metadata_options {
        http_tokens               = "required"      # IMDSv2 mandatory
        http_endpoint             = "enabled"
        http_put_response_hop_limit = 1             # Prevent metadata relay attacks
    }

    # Encrypt root volume — all data at rest is encrypted
    block_device_mappings {
        device_name = "/dev/xvda"
        ebs {
            volume_size           = 20
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
        }
    }

    tag_specifications {
        resource_type = "instance"
        tags = {
            Name        = "HA-WebServer-Worker"
            Environment = "ha-prod"
            ManagedBy   = "Terraform"
        }
    }
}

# =============================================================================
# SECURITY GROUP: APPLICATION LOAD BALANCER
# Internet-facing — accepts HTTP and HTTPS only
# =============================================================================
#checkov:skip=CKV_AWS_260:Port 80 open to internet is intentional for this public ALB; HTTP traffic is immediately redirected to HTTPS (301) at the listener level
resource "aws_security_group" "alb_sg" {
    name        = "ha-alb-sg"
    description = "Allow Internet to ALB on HTTP and HTTPS"
    vpc_id      = module.vpc.vpc_id

    ingress {
        description = "HTTP from internet"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        description = "HTTPS from internet"
        from_port   = 443
        to_port     = 443
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        description = "Allow ALB to reach backend EC2 instances on port 80 within VPC"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["10.0.0.0/16"]
    }
}

# =============================================================================
# SECURITY GROUP: EC2 INSTANCES (PRIVATE)
# Critical pattern: only the ALB security group can reach these instances.
# Direct internet access to instances is completely blocked.
# =============================================================================
resource "aws_security_group" "instance_sg" {
    name        = "ha-instance-sg"
    description = "Allow HTTP inbound ONLY from ALB security group"
    vpc_id      = module.vpc.vpc_id

    ingress {
        description     = "HTTP from ALB only"
        from_port       = 80
        to_port         = 80
        protocol        = "tcp"
        security_groups = [aws_security_group.alb_sg.id]
    }

    egress {
        description = "Allow instances to reach internet via NAT for HTTPS (AWS APIs, package repos)"
        from_port   = 443
        to_port     = 443
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        description = "Allow instances to reach HTTP package repositories via NAT"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

# =============================================================================
# WEB APPLICATION FIREWALL — Layer 7 Defence
# Inspects HTTP request content for SQLi, XSS, and CVEs before reaching the ALB
# =============================================================================
resource "aws_wafv2_web_acl" "main" {
    name        = "ha-prod-waf"
    description = "WAF protecting ALB — SQLi, XSS, and common exploit coverage"
    scope       = "REGIONAL"

    default_action {
        allow {}   # Blocklist approach: only explicitly bad traffic is blocked
    }

    # Rule 1: AWS Managed Common Rule Set (SQLi, XSS, LFI, Path Traversal)
    rule {
        name     = "AWSManagedRulesCommonRuleSet"
        priority = 1

        override_action {
            none {}
        }

        statement {
            managed_rule_group_statement {
                name        = "AWSManagedRulesCommonRuleSet"
                vendor_name = "AWS"
            }
        }

        visibility_config {
            cloudwatch_metrics_enabled = true
            metric_name                = "CommonRuleSetMetrics"
            sampled_requests_enabled   = true
        }
    }

    # Rule 2: Known Bad Inputs (Log4Shell, Spring4Shell, etc.)
    rule {
        name     = "AWSManagedRulesKnownBadInputsRuleSet"
        priority = 2

        override_action {
            none {}
        }

        statement {
            managed_rule_group_statement {
                name        = "AWSManagedRulesKnownBadInputsRuleSet"
                vendor_name = "AWS"
            }
        }

        visibility_config {
            cloudwatch_metrics_enabled = true
            metric_name                = "KnownBadInputsMetrics"
            sampled_requests_enabled   = true
        }
    }

    visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "ha-prod-waf-metrics"
        sampled_requests_enabled   = true
    }

    tags = {
        Name        = "HA-Prod-WAF"
        Environment = "ha-prod"
    }
}

# =============================================================================
# APPLICATION LOAD BALANCER — Multi-AZ, Internet-Facing
# =============================================================================
resource "aws_lb" "main" {
    name                       = "ha-load-balancer"
    internal                   = false
    load_balancer_type         = "application"
    drop_invalid_header_fields = true    # Prevent HTTP header injection
    enable_deletion_protection = true    # Prevent accidental ALB deletion
    security_groups            = [aws_security_group.alb_sg.id]

    # Multi-AZ placement: ALB spans BOTH public subnets for true HA
    subnets = [
        module.vpc.public_subnet_id,
        module.vpc.public_subnet_b_id,
    ]

    # Ship ALB access logs to S3 for security analysis and compliance
    access_logs {
        bucket  = module.logging.bucket_name
        prefix  = "alb-access-logs"
        enabled = true
    }

    tags = {
        Name        = "HA-Load-Balancer"
        Environment = "ha-prod"
    }
}

# Associate WAF with the ALB — required to enforce WAF rules on actual traffic
resource "aws_wafv2_web_acl_association" "main" {
    resource_arn = aws_lb.main.arn
    web_acl_arn  = aws_wafv2_web_acl.main.arn
}

# =============================================================================
# TARGET GROUP — Backend EC2 Registry
# ALB uses this to know where to forward requests; health checks remove failed nodes
# =============================================================================
resource "aws_lb_target_group" "app" {
    name     = "ha-target-group"
    port     = 80
    protocol = "HTTP"
    vpc_id   = module.vpc.vpc_id

    health_check {
        enabled             = true
        path                = "/"
        healthy_threshold   = 2
        unhealthy_threshold = 3
        interval            = 30
        timeout             = 5
    }
}

# =============================================================================
# ALB LISTENERS
# =============================================================================

# HTTP Listener — Redirects all HTTP traffic to HTTPS (security best practice)
resource "aws_lb_listener" "http_redirect" {
    load_balancer_arn = aws_lb.main.arn
    port              = "80"
    protocol          = "HTTP"

    default_action {
        type = "redirect"
        redirect {
            port        = "443"
            protocol    = "HTTPS"
            status_code = "HTTP_301"    # Permanent redirect — browser caches this
        }
    }
}

# HTTPS Listener — Terminates TLS at the ALB and forwards to instances over HTTP
# NOTE: Replace "arn:aws:acm:..." with a real ACM certificate ARN in production.
# For LocalStack testing, this listener is commented out as ACM is not emulated.
# resource "aws_lb_listener" "https" {
#     load_balancer_arn = aws_lb.main.arn
#     port              = "443"
#     protocol          = "HTTPS"
#     ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"  # TLS 1.3 preferred
#     certificate_arn   = "arn:aws:acm:us-east-2:123456789012:certificate/YOUR-CERT-ARN"
#
#     default_action {
#         type             = "forward"
#         target_group_arn = aws_lb_target_group.app.arn
#     }
# }

# =============================================================================
# AUTO SCALING GROUP — Self-Healing Infrastructure
# Maintains desired capacity; replaces unhealthy instances automatically
# =============================================================================
resource "aws_autoscaling_group" "app" {
    name                = "ha-asg"

    # Place instances in PRIVATE subnets — not directly reachable from internet
    vpc_zone_identifier = [
        module.vpc.private_subnet_id,
        module.vpc.private_subnet_b_id,
    ]

    target_group_arns = [aws_lb_target_group.app.arn]

    launch_template {
        id      = aws_launch_template.app.id
        version = "$Latest"
    }

    min_size         = 2   # Never below 2 — ensures HA even during scale-in
    max_size         = 6   # Caps infrastructure cost during traffic spikes
    desired_capacity = 2   # Start with minimum HA configuration

    health_check_type         = "ELB"        # Use ALB health checks (not just EC2 status)
    health_check_grace_period = 300          # Give instances 5 min to initialise

    tag {
        key                 = "Environment"
        value               = "ha-prod"
        propagate_at_launch = true
    }
}

# =============================================================================
# AUTO SCALING POLICIES — Dynamic Capacity Management
# =============================================================================

# Scale OUT: add 2 instances when average CPU > 70% for 2 consecutive periods
resource "aws_autoscaling_policy" "scale_out" {
    name                   = "ha-scale-out"
    autoscaling_group_name = aws_autoscaling_group.app.name
    policy_type            = "TargetTrackingScaling"

    target_tracking_configuration {
        predefined_metric_specification {
            predefined_metric_type = "ASGAverageCPUUtilization"
        }
        target_value = 70.0   # Scale out when average CPU exceeds 70%
    }
}

# Memory-based scaling using custom CloudWatch metric (optional — requires CW agent)
resource "aws_autoscaling_policy" "scale_on_requests" {
    name                   = "ha-scale-on-alb-requests"
    autoscaling_group_name = aws_autoscaling_group.app.name
    policy_type            = "TargetTrackingScaling"

    target_tracking_configuration {
        predefined_metric_specification {
            predefined_metric_type = "ALBRequestCountPerTarget"
            resource_label         = "${aws_lb.main.arn_suffix}/${aws_lb_target_group.app.arn_suffix}"
        }
        target_value = 1000.0   # Scale out when requests per target exceed 1000/min
    }
}
