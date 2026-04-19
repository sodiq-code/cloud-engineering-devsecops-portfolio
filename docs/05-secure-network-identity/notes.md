# Week 5: Project A - Secure Network & Identity

## Project Overview

This week, I designed and implemented the foundational infrastructure for a secure web application using Infrastructure as Code (IaC) principles with Terraform. The project demonstrates core cloud security concepts including network segmentation, identity management, and the principle of least privilege.

## What I Built

### VPC Module (Virtual Private Cloud)

I created a custom network architecture with proper segmentation:

- **Public Subnet:** Internet-facing subnet designed to host resources that require direct internet access, such as load balancers and bastion hosts. This subnet is associated with an Internet Gateway for inbound/outbound traffic.
- **Private Subnet:** A secure, isolated subnet with no direct internet access. This is where sensitive workloads like databases and application servers reside. Outbound traffic (if needed) would route through a NAT Gateway.
- **Route Tables:** Configured separate route tables for public and private subnets to control traffic flow.

### IAM Module (Identity and Access Management)

I implemented a "Least Privilege" access model:

- **IAM Role:** Created a dedicated role for the web server EC2 instance, eliminating the need for long-lived access keys.
- **IAM Policy:** Crafted a custom policy that grants:
    - `s3:GetObject` - Read access to specific S3 buckets
    - `s3:ListBucket` - Ability to list bucket contents
- **Explicit Denies:** All other AWS actions are implicitly denied, ensuring the instance cannot perform unauthorized operations.

### Integration

- Connected all modules using Terraform's module composition pattern
- Deployed the complete infrastructure stack to LocalStack for local testing and validation
- Verified resource creation and policy attachments

## Security Controls Implemented

| Control | Implementation | Security Benefit |
|---------|----------------|------------------|
| **Network Isolation** | Database resources placed in Private Subnet | No direct internet exposure; reduces attack surface |
| **Least Privilege** | EC2 uses IAM Role instead of access keys | No credential management; automatic rotation; scoped permissions |
| **Security Groups** | Inbound rule allowing only port 80 (HTTP) | Minimizes open ports; explicit allow-list approach |
| **Defense in Depth** | Multiple layers (VPC + IAM + Security Groups) | If one control fails, others still protect resources |

## Key Learnings

1. **IAM Roles vs. Access Keys:** Using IAM roles attached to EC2 instances is more secure than embedding access keys, as credentials are automatically rotated and never stored on disk.
2. **Subnet Design:** Proper network segmentation is the first line of defense—resources that don't need internet access should never have it.
3. **Infrastructure as Code:** Terraform modules enable repeatable, auditable, and version-controlled infrastructure deployments.

## Evidence & Artifacts

| Artifact | File Location | Description |
|----------|---------------|-------------|
| Architecture Diagram | `architecture-diagram.png` | Visual representation of VPC, subnets, and internet gateway |
| Deployment Verification | `screenshots/terraform-apply-success.png` | Screenshot showing successful `terraform apply` output on LocalStack |



