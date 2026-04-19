"""
test_auto_remediate_nacl.py — Unit tests for the SOAR NACL remediation script.

Uses moto (v5+) to mock all AWS API calls — no real AWS account or LocalStack required.
Tests cover the full lifecycle: discover → block → verify → cleanup.

Run with:
    pip install -r requirements.txt
    pytest test_auto_remediate_nacl.py -v
"""

import pytest
import boto3
from moto import mock_aws

from auto_remediate_nacl import (
    block_ip,
    cleanup_rule,
    find_nacl_id,
    find_vpc_id,
    NACLNotFoundError,
    RuleConflictError,
    VPCNotFoundError,
    main,
)


# =============================================================================
# CREDENTIALS FIXTURE — inject dummy credentials for boto3 under moto
# =============================================================================
@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Inject dummy AWS credentials — moto accepts any value."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def make_ec2_client():
    """Return a boto3 EC2 client pointing at the moto-mocked service."""
    return boto3.client("ec2", region_name="us-east-1")


def make_test_nacl(ec2, vpc_id):
    """
    Create a fresh (non-default) NACL for tests.
    Avoids conflicts with the default NACL's pre-existing rules (100, 32767).
    """
    result = ec2.create_network_acl(VpcId=vpc_id)
    return result["NetworkAcl"]["NetworkAclId"]


# =============================================================================
# DISCOVERY TESTS
# =============================================================================

def test_find_vpc_id_success():
    with mock_aws():
        ec2 = make_ec2_client()
        ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = find_vpc_id(ec2)
        assert vpc_id.startswith("vpc-")


def test_find_vpc_id_raises_when_no_vpc():
    with mock_aws():
        ec2 = make_ec2_client()
        # Moto provides a default VPC that may not be deletable due to dependencies.
        # Simulate an empty account response directly instead of force-deleting infra.
        ec2.describe_vpcs = lambda: {"Vpcs": []}
        with pytest.raises(VPCNotFoundError):
            find_vpc_id(ec2)


def test_find_nacl_id_success():
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = find_nacl_id(ec2, vpc_id)
        assert nacl_id.startswith("acl-")


def test_find_nacl_id_raises_for_invalid_vpc():
    with mock_aws():
        ec2 = make_ec2_client()
        with pytest.raises(NACLNotFoundError):
            find_nacl_id(ec2, "vpc-00000000")


# =============================================================================
# BLOCK IP TESTS — use a custom NACL (no pre-existing rules)
# =============================================================================

def test_block_ip_creates_deny_rule():
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = make_test_nacl(ec2, vpc_id)

        block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=10)

        entries = ec2.describe_network_acls(NetworkAclIds=[nacl_id])["NetworkAcls"][0]["Entries"]
        rule = next((e for e in entries if e["RuleNumber"] == 10 and not e["Egress"]), None)
        assert rule is not None
        assert rule["RuleAction"] == "deny"
        assert rule["CidrBlock"] == "203.0.113.5/32"


def test_block_ip_raises_on_duplicate_rule_number():
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = make_test_nacl(ec2, vpc_id)

        block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=10)
        with pytest.raises(RuleConflictError):
            block_ip(ec2, nacl_id, "198.51.100.1/32", rule_number=10)


def test_block_ip_dry_run_makes_no_api_changes():
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = make_test_nacl(ec2, vpc_id)

        block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=10, dry_run=True)

        entries = ec2.describe_network_acls(NetworkAclIds=[nacl_id])["NetworkAcls"][0]["Entries"]
        rule = next((e for e in entries if e["RuleNumber"] == 10 and not e["Egress"]), None)
        assert rule is None, "Dry run must not create any AWS resources"


# =============================================================================
# CLEANUP TESTS
# =============================================================================

def test_cleanup_rule_removes_deny_entry():
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = make_test_nacl(ec2, vpc_id)

        block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=10)
        cleanup_rule(ec2, nacl_id, rule_number=10)

        entries = ec2.describe_network_acls(NetworkAclIds=[nacl_id])["NetworkAcls"][0]["Entries"]
        rule = next((e for e in entries if e["RuleNumber"] == 10 and not e["Egress"]), None)
        assert rule is None, "Cleanup must remove the DENY rule"


def test_cleanup_rule_noop_when_rule_absent(caplog):
    """Cleanup on a non-existent rule should warn but not raise."""
    with mock_aws():
        ec2 = make_ec2_client()
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        nacl_id = make_test_nacl(ec2, vpc_id)

        import logging
        with caplog.at_level(logging.WARNING):
            cleanup_rule(ec2, nacl_id, rule_number=999)

        assert any(
            "not found" in m.lower() or "nothing to clean" in m.lower()
            for m in caplog.messages
        )


# =============================================================================
# CLI / MAIN INTEGRATION TESTS
# =============================================================================

def test_main_returns_zero_on_success(monkeypatch):
    """main() returns exit code 0 on a successful block operation."""
    with mock_aws():
        ec2 = make_ec2_client()
        ec2.create_vpc(CidrBlock="10.0.0.0/16")

        monkeypatch.setattr("auto_remediate_nacl.get_ec2_client", lambda **kw: ec2)
        result = main(["--ip", "203.0.113.5/32", "--rule-number", "10"])
        assert result == 0


def test_main_returns_one_on_vpc_not_found(monkeypatch):
    """main() returns exit code 1 when no VPC exists."""
    with mock_aws():
        ec2 = make_ec2_client()
        monkeypatch.setattr("auto_remediate_nacl.get_ec2_client", lambda **kw: ec2)
        monkeypatch.setattr(
            "auto_remediate_nacl.find_vpc_id",
            lambda _ec2: (_ for _ in ()).throw(VPCNotFoundError("No VPC found")),
        )
        result = main(["--ip", "203.0.113.5/32"])
        assert result == 1
