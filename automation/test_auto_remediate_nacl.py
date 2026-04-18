"""
test_auto_remediate_nacl.py — Unit tests for the SOAR NACL remediation script.

Uses moto to mock AWS API calls without requiring a real AWS account or LocalStack.
Tests cover the full lifecycle: discover → block → verify → cleanup.

Run with:
    pip install -r requirements.txt
    pytest test_auto_remediate_nacl.py -v
"""

import pytest
import boto3
from moto import mock_ec2

from auto_remediate_nacl import (
    block_ip,
    cleanup_rule,
    find_nacl_id,
    find_vpc_id,
    get_ec2_client,
    NACLNotFoundError,
    RuleConflictError,
    VPCNotFoundError,
    main,
)


# =============================================================================
# FIXTURES — Provide a mocked EC2 environment for each test
# =============================================================================

def make_ec2_client():
    """Return a boto3 EC2 client pointed at the moto-mocked AWS service."""
    return boto3.client("ec2", region_name="us-east-1")


@pytest.fixture
def mocked_vpc(aws_credentials):
    """Create a real (mocked) VPC with an attached NACL and return their IDs."""
    ec2 = make_ec2_client()
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]

    # Describe the default NACL auto-created for this VPC
    nacls = ec2.describe_network_acls(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    nacl_id = nacls["NetworkAcls"][0]["NetworkAclId"]
    return {"ec2": ec2, "vpc_id": vpc_id, "nacl_id": nacl_id}


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Inject dummy AWS credentials to satisfy boto3 requirement under moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


# =============================================================================
# DISCOVERY TESTS
# =============================================================================

@mock_ec2
def test_find_vpc_id_success(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    vpc_id  = find_vpc_id(ec2)
    assert vpc_id.startswith("vpc-")


@mock_ec2
def test_find_vpc_id_raises_when_no_vpc():
    ec2 = make_ec2_client()
    with pytest.raises(VPCNotFoundError):
        find_vpc_id(ec2)


@mock_ec2
def test_find_nacl_id_success(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    vpc_id  = mocked_vpc["vpc_id"]
    nacl_id = find_nacl_id(ec2, vpc_id)
    assert nacl_id.startswith("acl-")


@mock_ec2
def test_find_nacl_id_raises_for_invalid_vpc(mocked_vpc):
    ec2 = mocked_vpc["ec2"]
    with pytest.raises(NACLNotFoundError):
        find_nacl_id(ec2, "vpc-00000000")


# =============================================================================
# BLOCK IP TESTS
# =============================================================================

@mock_ec2
def test_block_ip_creates_deny_rule(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    nacl_id = mocked_vpc["nacl_id"]

    block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=100)

    response = ec2.describe_network_acls(NetworkAclIds=[nacl_id])
    entries  = response["NetworkAcls"][0]["Entries"]
    rule     = next((e for e in entries if e["RuleNumber"] == 100 and not e["Egress"]), None)

    assert rule is not None
    assert rule["RuleAction"] == "deny"
    assert rule["CidrBlock"] == "203.0.113.5/32"


@mock_ec2
def test_block_ip_raises_on_duplicate_rule_number(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    nacl_id = mocked_vpc["nacl_id"]

    block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=100)

    with pytest.raises(RuleConflictError):
        block_ip(ec2, nacl_id, "198.51.100.1/32", rule_number=100)


@mock_ec2
def test_block_ip_dry_run_makes_no_api_changes(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    nacl_id = mocked_vpc["nacl_id"]

    block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=100, dry_run=True)

    response = ec2.describe_network_acls(NetworkAclIds=[nacl_id])
    entries  = response["NetworkAcls"][0]["Entries"]
    rule     = next((e for e in entries if e["RuleNumber"] == 100 and not e["Egress"]), None)

    assert rule is None, "Dry run must not create any AWS resources"


# =============================================================================
# CLEANUP TESTS
# =============================================================================

@mock_ec2
def test_cleanup_rule_removes_deny_entry(mocked_vpc):
    ec2     = mocked_vpc["ec2"]
    nacl_id = mocked_vpc["nacl_id"]

    block_ip(ec2, nacl_id, "203.0.113.5/32", rule_number=100)
    cleanup_rule(ec2, nacl_id, rule_number=100)

    response = ec2.describe_network_acls(NetworkAclIds=[nacl_id])
    entries  = response["NetworkAcls"][0]["Entries"]
    rule     = next((e for e in entries if e["RuleNumber"] == 100 and not e["Egress"]), None)

    assert rule is None, "Cleanup must remove the DENY rule"


@mock_ec2
def test_cleanup_rule_noop_when_rule_absent(mocked_vpc, caplog):
    """Cleanup should log a warning but not raise when the rule doesn't exist."""
    ec2     = mocked_vpc["ec2"]
    nacl_id = mocked_vpc["nacl_id"]

    import logging
    with caplog.at_level(logging.WARNING):
        cleanup_rule(ec2, nacl_id, rule_number=999)

    assert "nothing to clean up" in caplog.text.lower() or "not found" in caplog.text.lower()


# =============================================================================
# CLI / MAIN INTEGRATION TESTS
# =============================================================================

@mock_ec2
def test_main_returns_zero_on_success(mocked_vpc, monkeypatch):
    """main() should return exit code 0 on a successful block."""
    # Patch get_ec2_client to return our mocked client
    monkeypatch.setattr(
        "auto_remediate_nacl.get_ec2_client",
        lambda **kwargs: mocked_vpc["ec2"],
    )
    result = main(["--ip", "203.0.113.5/32", "--rule-number", "200"])
    assert result == 0


@mock_ec2
def test_main_returns_one_on_vpc_not_found(monkeypatch):
    """main() should return exit code 1 when no VPC exists."""
    monkeypatch.setattr(
        "auto_remediate_nacl.get_ec2_client",
        lambda **kwargs: make_ec2_client(),
    )
    result = main(["--ip", "203.0.113.5/32"])
    assert result == 1
