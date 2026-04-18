# modules/vpc/variables.tf

variable "vpc_cidr" {
    description = "CIDR block for the main VPC (covers 65,536 IPs)"
    type        = string
    default     = "10.0.0.0/16"

    validation {
        condition     = can(cidrhost(var.vpc_cidr, 0))
        error_message = "vpc_cidr must be a valid IPv4 CIDR block."
    }
}

variable "public_subnet_cidr" {
    description = "CIDR for public subnet A (ALB, NAT Gateway, bastion hosts)"
    type        = string
    default     = "10.0.1.0/24"

    validation {
        condition     = can(cidrhost(var.public_subnet_cidr, 0))
        error_message = "public_subnet_cidr must be a valid IPv4 CIDR block."
    }
}

variable "public_subnet_b_cidr" {
    description = "CIDR for public subnet B (second AZ — required for ALB HA)"
    type        = string
    default     = "10.0.3.0/24"

    validation {
        condition     = can(cidrhost(var.public_subnet_b_cidr, 0))
        error_message = "public_subnet_b_cidr must be a valid IPv4 CIDR block."
    }
}

variable "private_subnet_cidr" {
    description = "CIDR for private subnet A (application servers, databases)"
    type        = string
    default     = "10.0.2.0/24"

    validation {
        condition     = can(cidrhost(var.private_subnet_cidr, 0))
        error_message = "private_subnet_cidr must be a valid IPv4 CIDR block."
    }
}

variable "private_subnet_b_cidr" {
    description = "CIDR for private subnet B (second AZ for HA)"
    type        = string
    default     = "10.0.4.0/24"

    validation {
        condition     = can(cidrhost(var.private_subnet_b_cidr, 0))
        error_message = "private_subnet_b_cidr must be a valid IPv4 CIDR block."
    }
}

variable "environment" {
    description = "Deployment environment name used in resource naming and tagging (e.g., dev, staging, prod)"
    type        = string

    validation {
        condition     = length(var.environment) > 0
        error_message = "environment must not be empty."
    }
}

variable "region" {
    description = "AWS region for subnet AZ placement"
    type        = string
    default     = "us-east-1"
}
