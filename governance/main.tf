# governance/main.tf
# Enterprise Multi-Account Governance via AWS Organizations + SCPs.
# This configuration enforces immutable security baselines across all member accounts:
#   - SCP A: Protect CloudTrail integrity (no tampering, reduction of scope, or deletion)
#   - SCP B: Data sovereignty via regional restriction (us-east-1 / us-east-2 only)
#   - SCP C: Deny root account API actions (CIS Benchmark Level 1 control)
# All SCPs are attached at the Organisation ROOT level to ensure no OU can bypass them.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.67.0" # Pinned for LocalStack compatibility
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
    organizations = "http://localhost:4566"
    sts           = "http://localhost:4566"
    config        = "http://localhost:4566"
  }
}

# =============================================================================
# AWS ORGANIZATION — The root governance container
# =============================================================================
resource "aws_organizations_organization" "org" {
  aws_service_access_principals = [
    "cloudtrail.amazonaws.com",
    "config.amazonaws.com"
  ]
  feature_set          = "ALL" # Required for SCPs
  enabled_policy_types = ["SERVICE_CONTROL_POLICY"]
}

# =============================================================================
# ORGANIZATIONAL UNITS — Department containers
# =============================================================================
resource "aws_organizations_organizational_unit" "security" {
  name      = "Security-Prod"
  parent_id = aws_organizations_organization.org.roots[0].id
}

resource "aws_organizations_organizational_unit" "workloads" {
  name      = "Workloads-Prod"
  parent_id = aws_organizations_organization.org.roots[0].id
}

# =============================================================================
# SCP A: CloudTrail Integrity — Anti-Tamper
# Blocks stopping, deleting, updating, or reducing the scope of CloudTrail.
# Without this, an attacker with admin access could erase their tracks.
# =============================================================================
resource "aws_organizations_policy" "protect_cloudtrail" {
  name        = "Deny-CloudTrail-Tampering"
  description = "Prevents stopping, deleting, or reducing the scope of CloudTrail logging"
  content     = file("${path.module}/policies/scp_deny_cloudtrail_stop.json")
  type        = "SERVICE_CONTROL_POLICY"
}

# =============================================================================
# SCP B: Data Sovereignty — Region Lock
# Only allows API calls to us-east-1 and us-east-2.
# Prevents accidental or malicious deployment in unapproved regions.
# =============================================================================
resource "aws_organizations_policy" "region_restrict" {
  name        = "Restrict-Regions-US"
  description = "Allows AWS operations only in us-east-1 and us-east-2"
  content     = file("${path.module}/policies/scp_region_restriction.json")
  type        = "SERVICE_CONTROL_POLICY"
}

# =============================================================================
# SCP C: Root Account Protection (CIS Benchmark Level 1)
# Denies all API actions performed by the root account.
# Root should only be used for account recovery, never for daily operations.
# =============================================================================
resource "aws_organizations_policy" "deny_root_actions" {
  name        = "Deny-Root-Account-Actions"
  description = "CIS Benchmark L1: Prevents root account from performing any API actions"
  # NOTE: The SCP JSON uses 'arn:aws:iam::*:root' where '*' is a wildcard over account IDs.
  # This is intentional and required for organisation-wide enforcement — it must match
  # root accounts in ALL member accounts. This is different from the KMS key policy fix
  # (which scopes the key admin to a specific account ARN). Organisation SCPs target
  # cross-account principals by design; a wildcard here is the correct AWS pattern.
  content = file("${path.module}/policies/scp_deny_root_actions.json")
  type    = "SERVICE_CONTROL_POLICY"
}

# =============================================================================
# POLICY ATTACHMENTS — Attached to Organisation ROOT
# Attaching at ROOT level ensures every OU and account inherits these controls.
# No OU or account can escape these guardrails.
# =============================================================================

resource "aws_organizations_policy_attachment" "attach_cloudtrail_root" {
  policy_id = aws_organizations_policy.protect_cloudtrail.id
  target_id = aws_organizations_organization.org.roots[0].id
}

resource "aws_organizations_policy_attachment" "attach_regions_root" {
  policy_id = aws_organizations_policy.region_restrict.id
  target_id = aws_organizations_organization.org.roots[0].id
}

resource "aws_organizations_policy_attachment" "attach_deny_root_root" {
  policy_id = aws_organizations_policy.deny_root_actions.id
  target_id = aws_organizations_organization.org.roots[0].id
}
