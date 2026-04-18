"""
auto_remediate_nacl.py — Automated Network ACL Remediation (SOAR)

Reduces Time-to-Containment from minutes (manual) to milliseconds (automated).
Designed to be invoked by AWS Lambda in production, triggered by GuardDuty findings
via EventBridge. Can also be executed manually for ad-hoc remediation.

Production flow:
    GuardDuty Finding → EventBridge Rule → Lambda (this script) → NACL DENY Rule

Usage:
    python auto_remediate_nacl.py --ip 203.0.113.5/32
    python auto_remediate_nacl.py --ip 203.0.113.5/32 --dry-run
    python auto_remediate_nacl.py --ip 203.0.113.5/32 --rule-number 50
    python auto_remediate_nacl.py --cleanup --ip 203.0.113.5/32
"""

import argparse
import logging
import sys
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# =============================================================================
# LOGGING — structured output for both CLI and Lambda CloudWatch consumption
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
AWS_REGION    = "us-east-2"
ENDPOINT_URL  = "http://localhost:4566"   # LocalStack endpoint for local dev


# =============================================================================
# CUSTOM EXCEPTIONS — avoids sys.exit() anti-pattern inside library functions
# =============================================================================
class VPCNotFoundError(Exception):
    """Raised when no VPC exists in the target account."""

class NACLNotFoundError(Exception):
    """Raised when no NACL is associated with the target VPC."""

class RuleConflictError(Exception):
    """Raised when the target rule number is already in use."""


# =============================================================================
# AWS CLIENT FACTORY
# =============================================================================
def get_ec2_client(region: str = AWS_REGION, endpoint_url: str = ENDPOINT_URL) -> boto3.client:
    """
    Create a boto3 EC2 client.

    In production (Lambda), credentials come from the execution role — no
    hardcoded keys. The endpoint_url is omitted in production.
    """
    return boto3.client(
        "ec2",
        region_name=region,
        endpoint_url=endpoint_url,
        aws_access_key_id="test",      # LocalStack accepts any value
        aws_secret_access_key="test",  # Remove hardcoded creds in production
    )


# =============================================================================
# DISCOVERY FUNCTIONS
# =============================================================================
def find_vpc_id(ec2: boto3.client) -> str:
    """
    Retrieve the first VPC ID in the account.

    Returns:
        str: VPC ID (e.g., "vpc-abc123")

    Raises:
        VPCNotFoundError: if no VPCs exist
        ClientError: on AWS API failure
    """
    logger.info("Querying EC2 API for VPC list...")
    response = ec2.describe_vpcs()

    vpcs = response.get("Vpcs", [])
    if not vpcs:
        raise VPCNotFoundError(
            "No VPC found. Ensure Terraform has been applied in week8-ha-deploy."
        )

    vpc_id = vpcs[0]["VpcId"]
    logger.info("Target VPC identified: %s", vpc_id)
    return vpc_id


def find_nacl_id(ec2: boto3.client, vpc_id: str) -> str:
    """
    Retrieve the Network ACL associated with the given VPC.

    NACL operates at subnet level (stateless). Rules are evaluated in ascending
    order — lowest rule number wins. We inject at rule #1 for highest priority.

    Returns:
        str: Network ACL ID (e.g., "acl-abc123")

    Raises:
        NACLNotFoundError: if no NACL is found for the VPC
    """
    logger.info("Searching for NACL in VPC %s...", vpc_id)
    response = ec2.describe_network_acls(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )

    nacls = response.get("NetworkAcls", [])
    if not nacls:
        raise NACLNotFoundError(f"No Network ACL found for VPC {vpc_id}.")

    nacl_id = nacls[0]["NetworkAclId"]
    logger.info("Network ACL identified: %s", nacl_id)
    return nacl_id


def rule_exists(ec2: boto3.client, nacl_id: str, rule_number: int) -> bool:
    """
    Check whether a rule with the given number already exists in the NACL.

    Prevents duplicate-rule errors on repeated executions of this script.
    """
    response = ec2.describe_network_acls(NetworkAclIds=[nacl_id])
    entries = response["NetworkAcls"][0].get("Entries", [])
    return any(e["RuleNumber"] == rule_number and not e["Egress"] for e in entries)


# =============================================================================
# REMEDIATION FUNCTIONS
# =============================================================================
def block_ip(
    ec2: boto3.client,
    nacl_id: str,
    ip_cidr: str,
    rule_number: int = 1,
    dry_run: bool = False,
) -> None:
    """
    Inject a DENY rule into the NACL to block all traffic from ip_cidr.

    Args:
        ec2:         boto3 EC2 client
        nacl_id:     Target Network ACL ID
        ip_cidr:     IP address in CIDR notation (e.g., "203.0.113.5/32")
        rule_number: NACL rule number (lower = higher priority, evaluated first)
        dry_run:     If True, log the action but do not create the rule

    Raises:
        RuleConflictError: if the rule number is already in use
    """
    if rule_exists(ec2, nacl_id, rule_number):
        raise RuleConflictError(
            f"Rule #{rule_number} already exists in NACL {nacl_id}. "
            "Use --rule-number to specify a different number, or --cleanup first."
        )

    logger.info(
        "Preparing DENY rule #%d for IP %s in NACL %s (dry_run=%s)",
        rule_number, ip_cidr, nacl_id, dry_run,
    )

    if dry_run:
        logger.info(
            "[DRY RUN] Would create: DENY ALL from %s (Rule #%d, NACL %s) — no changes made.",
            ip_cidr, rule_number, nacl_id,
        )
        return

    ec2.create_network_acl_entry(
        NetworkAclId=nacl_id,
        RuleNumber=rule_number,
        Protocol="-1",      # All protocols (TCP, UDP, ICMP)
        RuleAction="deny",
        Egress=False,       # Inbound traffic block
        CidrBlock=ip_cidr,
        PortRange={"From": 0, "To": 65535},
    )
    logger.info("SUCCESS — Rule created: DENY ALL inbound from %s (Priority #%d)", ip_cidr, rule_number)


def cleanup_rule(
    ec2: boto3.client,
    nacl_id: str,
    rule_number: int,
    dry_run: bool = False,
) -> None:
    """
    Remove a previously created DENY rule from the NACL.

    Used when a threat is resolved and the block should be lifted.

    Args:
        ec2:         boto3 EC2 client
        nacl_id:     Target Network ACL ID
        rule_number: The rule number to remove
        dry_run:     If True, log the action but do not delete the rule
    """
    if not rule_exists(ec2, nacl_id, rule_number):
        logger.warning(
            "Rule #%d not found in NACL %s — nothing to clean up.", rule_number, nacl_id
        )
        return

    if dry_run:
        logger.info(
            "[DRY RUN] Would delete: Rule #%d from NACL %s — no changes made.",
            rule_number, nacl_id,
        )
        return

    ec2.delete_network_acl_entry(
        NetworkAclId=nacl_id,
        RuleNumber=rule_number,
        Egress=False,
    )
    logger.info("SUCCESS — Rule #%d removed from NACL %s", rule_number, nacl_id)


# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================
def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SOAR: Automated NACL IP block/unblock tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Block a malicious IP:
  python auto_remediate_nacl.py --ip 203.0.113.5/32

  # Preview the action without making changes:
  python auto_remediate_nacl.py --ip 203.0.113.5/32 --dry-run

  # Block at a specific rule number (e.g., to avoid conflict):
  python auto_remediate_nacl.py --ip 203.0.113.5/32 --rule-number 50

  # Remove a previously created block:
  python auto_remediate_nacl.py --cleanup --ip 203.0.113.5/32 --rule-number 1
        """,
    )
    parser.add_argument(
        "--ip",
        required=True,
        help="IP address to block/unblock in CIDR notation (e.g., 203.0.113.5/32)",
    )
    parser.add_argument(
        "--rule-number",
        type=int,
        default=1,
        help="NACL rule number to create or remove (default: 1 — highest priority)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the action without making any AWS API changes",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove the DENY rule instead of creating one (incident resolved)",
    )
    return parser.parse_args(argv)


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main(argv=None) -> int:
    """
    Entry point for CLI and Lambda invocation.

    Returns:
        0 on success, 1 on error
    """
    args = parse_args(argv)

    logger.info("Connecting to EC2 API in region %s...", AWS_REGION)
    ec2 = get_ec2_client()

    try:
        vpc_id  = find_vpc_id(ec2)
        nacl_id = find_nacl_id(ec2, vpc_id)

        if args.cleanup:
            cleanup_rule(ec2, nacl_id, args.rule_number, dry_run=args.dry_run)
        else:
            block_ip(ec2, nacl_id, args.ip, rule_number=args.rule_number, dry_run=args.dry_run)

    except VPCNotFoundError as exc:
        logger.error("VPC discovery failed: %s", exc)
        return 1
    except NACLNotFoundError as exc:
        logger.error("NACL discovery failed: %s", exc)
        return 1
    except RuleConflictError as exc:
        logger.error("Rule conflict: %s", exc)
        return 1
    except (BotoCoreError, ClientError) as exc:
        logger.error("AWS API error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
