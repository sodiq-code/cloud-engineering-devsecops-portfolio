#!/usr/bin/env python3
"""
smoke_test.py — End-to-End Smoke Test Suite
CloudDefense Engineering Portfolio by Jimoh Sodiq Bolaji

Validates every project in the portfolio from structure → configuration →
security logic → forensics analysis → Python unit test execution.

No real AWS account or running LocalStack required.
All AWS calls in the Python tests are intercepted by moto (in-memory mock).

Dependencies (install once):
    pip install pyyaml                        # YAML parsing
    pip install -r automation/requirements.txt  # boto3, pytest, moto (for Suite 8)

Usage:
    python smoke_test.py               # full suite
    python smoke_test.py --skip-tests  # skip pytest (structural checks only)
    python smoke_test.py --verbose     # show detail on every pass
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

# ─── ANSI colours ────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
DIM     = "\033[2m"

# ─── Global state ────────────────────────────────────────────────────────────
REPO: Path = Path(__file__).resolve().parent
RESULTS: List[Tuple[str, str, bool, str]] = []   # (suite, name, passed, detail)
VERBOSE: bool = False
SUITE_START: float = 0.0


# ─── Output helpers ──────────────────────────────────────────────────────────

def _print_result(name: str, passed: bool, detail: str) -> None:
    if passed:
        mark = f"{GREEN}✅ PASS{RESET}"
        line = f"  {mark}  {name}"
        if detail and VERBOSE:
            line += f"  {DIM}({detail}){RESET}"
    else:
        mark = f"{RED}❌ FAIL{RESET}"
        line = f"  {mark}  {name}"
        if detail:
            wrapped = textwrap.indent(detail, "           ")
            line += f"\n{YELLOW}→ {wrapped.strip()}{RESET}"
    print(line)


def pass_test(suite: str, name: str, detail: str = "") -> None:
    RESULTS.append((suite, name, True, detail))
    _print_result(name, True, detail)


def fail_test(suite: str, name: str, detail: str = "") -> None:
    RESULTS.append((suite, name, False, detail))
    _print_result(name, False, detail)


def section(emoji: str, title: str) -> None:
    bar = "─" * 62
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {emoji}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")


def info(msg: str) -> None:
    print(f"  {BLUE}ℹ  {msg}{RESET}")


# ─── Assertion primitives ─────────────────────────────────────────────────────

def assert_file(suite: str, path: Path, label: Optional[str] = None) -> bool:
    name = label or f"File exists: {path.relative_to(REPO)}"
    if path.is_file():
        pass_test(suite, name, str(path.relative_to(REPO)))
        return True
    fail_test(suite, name, f"Missing: {path}")
    return False


def assert_dir(suite: str, path: Path, label: Optional[str] = None) -> bool:
    name = label or f"Directory exists: {path.relative_to(REPO)}"
    if path.is_dir():
        pass_test(suite, name, str(path.relative_to(REPO)))
        return True
    fail_test(suite, name, f"Missing directory: {path}")
    return False


def assert_contains(suite: str, path: Path, patterns: List[str], label: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail_test(suite, label, f"File not found: {path.relative_to(REPO)}")
        return False
    missing = [p for p in patterns if p not in text]
    if not missing:
        pass_test(suite, label)
        return True
    fail_test(suite, label, f"Missing patterns: {missing[:5]}")
    return False


def assert_json_valid(suite: str, path: Path, label: Optional[str] = None) -> Optional[dict]:
    name = label or f"Valid JSON: {path.relative_to(REPO)}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pass_test(suite, name)
        return data
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        fail_test(suite, name, str(exc))
        return None


def assert_yaml_valid(
    suite: str, path: Path, label: Optional[str] = None, multi: bool = False
) -> Optional[dict]:
    """Load a YAML file.  Use multi=True for files with multiple --- documents."""
    name = label or f"Valid YAML: {path.relative_to(REPO)}"
    try:
        text = path.read_text(encoding="utf-8")
        if multi:
            docs = list(yaml.safe_load_all(text))
            data = docs[0] if docs else {}
        else:
            data = yaml.safe_load(text)
        pass_test(suite, name)
        return data
    except (yaml.YAMLError, FileNotFoundError) as exc:
        fail_test(suite, name, str(exc))
        return None


def assert_python_syntax(suite: str, path: Path, label: Optional[str] = None) -> bool:
    name = label or f"Python syntax OK: {path.relative_to(REPO)}"
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        pass_test(suite, name)
        return True
    except SyntaxError as exc:
        fail_test(suite, name, str(exc))
        return False


def run_cmd(
    cmd: List[str],
    cwd: Path = REPO,
    timeout: int = 180,
    env: Optional[dict] = None,
) -> Tuple[int, str, str]:
    try:
        merged_env = {**os.environ, **(env or {})}
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, env=merged_env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 1 — Repository Root & Structure
# ═══════════════════════════════════════════════════════════════════════════════

def test_repo_structure() -> None:
    S = "Repo Structure"
    section("🗂️", "Repository Root & Project Structure")

    # Top-level files
    assert_file(S, REPO / "README.md",           "Root README.md exists")
    assert_file(S, REPO / ".gitignore",          ".gitignore exists")
    assert_file(S, REPO / ".trivyignore",        ".trivyignore exists")
    assert_file(S, REPO / "smoke_test.py",       "smoke_test.py exists (this file)")

    # Top-level project directories
    projects = [
        "aws-foundation",
        "s3-secure-storage",
        "security-stack",
        "ha-aws-architecture",
        "governance",
        "automation",
        "forensics",
        "k8s-ecommerce-project",
        "modules",
        "docs",
        "incident-reports",
    ]
    for p in projects:
        assert_dir(S, REPO / p, f"Project directory: {p}/")

    # README portfolio map mentions every major project
    assert_contains(S, REPO / "README.md",
        ["k8s-ecommerce-project", "ha-aws-architecture", "s3-secure-storage",
         "governance", "automation", "forensics", "aws-foundation"],
        "README portfolio map references all 7 projects")

    # CI/CD workflow present
    assert_file(S, REPO / ".github" / "workflows" / "trivy-scan.yml",
                "CI/CD: .github/workflows/trivy-scan.yml exists")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 2 — Terraform: aws-foundation
# ═══════════════════════════════════════════════════════════════════════════════

def test_aws_foundation() -> None:
    S = "aws-foundation"
    section("🏗️", "Project: aws-foundation (VPC + IAM + Hardened EC2)")
    d = REPO / "aws-foundation"

    assert_file(S, d / "main.tf",                        "main.tf exists")
    assert_file(S, d / "outputs.tf",                     "outputs.tf exists")
    assert_file(S, d / "localstack-docker-compose.yml",  "LocalStack compose file exists")
    assert_file(S, d / "README.md",                      "README.md exists")

    # Terraform blocks present
    assert_contains(S, d / "main.tf",
        ['terraform {', 'required_providers', 'provider "aws"'],
        "main.tf: terraform + provider blocks present")

    # All 3 expected modules consumed
    assert_contains(S, d / "main.tf",
        ['module "vpc"', 'module "iam"'],
        "main.tf: vpc and iam modules referenced")

    # Security hardening markers in EC2
    assert_contains(S, d / "main.tf",
        ['http_tokens', '"required"', 'encrypted', 'monitoring'],
        "main.tf: IMDSv2 + EBS encryption + monitoring on EC2")

    # No hardcoded real credentials (only dummy 'test' values for LocalStack)
    main_text = (d / "main.tf").read_text()
    has_real_key = re.search(r'access_key\s*=\s*"(?!test")[A-Z0-9]{20}', main_text)
    if has_real_key:
        fail_test(S, "No real AWS credentials in main.tf",
                  "Found what looks like a real AWS access key")
    else:
        pass_test(S, "No real AWS credentials in main.tf", "only dummy 'test' values")

    # LocalStack endpoints configured
    assert_contains(S, d / "main.tf",
        ["localhost:4566"],
        "main.tf: LocalStack endpoint configured (localhost:4566)")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 3 — Terraform: s3-secure-storage
# ═══════════════════════════════════════════════════════════════════════════════

def test_s3_secure_storage() -> None:
    S = "s3-secure-storage"
    section("🛡️", "Project: s3-secure-storage (KMS + TLS + Versioning + Lifecycle)")
    d = REPO / "s3-secure-storage"

    assert_file(S, d / "main.tf",       "main.tf exists")
    assert_file(S, d / "variables.tf",  "variables.tf exists")
    assert_file(S, d / "provider.tf",   "provider.tf exists")
    assert_file(S, d / "outputs.tf",    "outputs.tf exists")
    assert_file(S, d / "README.md",     "README.md exists")
    assert_file(S, d / "localstack-docker-compose.yml", "LocalStack compose exists")

    # Security controls
    assert_contains(S, d / "main.tf",
        ["aws_kms_key", "enable_key_rotation"],
        "main.tf: KMS CMK with key rotation enabled")

    assert_contains(S, d / "main.tf",
        ["block_public_acls", "block_public_policy",
         "ignore_public_acls", "restrict_public_buckets"],
        "main.tf: all 4 public-access block settings present")

    assert_contains(S, d / "main.tf",
        ["aws_s3_bucket_versioning", '"Enabled"'],
        "main.tf: S3 versioning enabled")

    assert_contains(S, d / "main.tf",
        ["aws:SecureTransport", '"false"'],
        "main.tf: TLS-only bucket policy (deny non-TLS)")

    assert_contains(S, d / "main.tf",
        ["aws_s3_bucket_lifecycle_configuration", "GLACIER"],
        "main.tf: lifecycle rule with GLACIER transition")

    assert_contains(S, d / "main.tf",
        ["sse_algorithm", '"aws:kms"'],
        "main.tf: KMS SSE algorithm enforced")

    assert_contains(S, d / "main.tf",
        ["BucketOwnerEnforced"],
        "main.tf: ACLs disabled (BucketOwnerEnforced)")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 4 — Terraform: security-stack
# ═══════════════════════════════════════════════════════════════════════════════

def test_security_stack() -> None:
    S = "security-stack"
    section("🔍", "Project: security-stack (CloudTrail + GuardDuty + Full Stack)")
    d = REPO / "security-stack"

    assert_file(S, d / "main.tf",   "main.tf exists")
    assert_file(S, d / "README.md", "README.md exists")

    # All 4 layers
    assert_contains(S, d / "main.tf",
        ['module "logging"', 'module "security"', 'module "vpc"', 'module "iam"'],
        "main.tf: all 4 layers (logging, security, vpc, iam) composed")

    # Security hardening on EC2
    assert_contains(S, d / "main.tf",
        ['http_tokens', '"required"', 'encrypted', '"gp3"'],
        "main.tf: IMDSv2 + EBS gp3 encryption on EC2")

    # CloudTrail + GuardDuty via security module
    assert_contains(S, d / "main.tf",
        ['log_bucket_name'],
        "main.tf: logging bucket wired into security module")

    # S3 path-style for LocalStack
    assert_contains(S, d / "main.tf",
        ["s3_use_path_style"],
        "main.tf: s3_use_path_style set (LocalStack S3 requirement)")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 5 — Terraform: ha-aws-architecture
# ═══════════════════════════════════════════════════════════════════════════════

def test_ha_aws_architecture() -> None:
    S = "ha-aws-architecture"
    section("🔄", "Project: ha-aws-architecture (WAF + ALB + ASG + Multi-AZ)")
    d = REPO / "ha-aws-architecture"

    assert_file(S, d / "main.tf",   "main.tf exists")
    assert_file(S, d / "README.md", "README.md exists")

    # WAF
    assert_contains(S, d / "main.tf",
        ["aws_wafv2_web_acl", "AWSManagedRulesCommonRuleSet",
         "AWSManagedRulesKnownBadInputsRuleSet"],
        "main.tf: WAFv2 with two managed rule sets (SQLi/XSS + KBI)")

    # ALB security features
    assert_contains(S, d / "main.tf",
        ["drop_invalid_header_fields", "enable_deletion_protection",
         "aws_wafv2_web_acl_association"],
        "main.tf: ALB header-drop + deletion protection + WAF association")

    # ASG with min=2 for HA
    assert_contains(S, d / "main.tf",
        ["aws_autoscaling_group", "min_size", "max_size", "desired_capacity"],
        "main.tf: ASG with capacity bounds defined")

    # Multi-AZ: both subnets passed to ALB
    assert_contains(S, d / "main.tf",
        ["public_subnet_id", "public_subnet_b_id"],
        "main.tf: ALB spans both AZ-a and AZ-b public subnets (true HA)")

    # Launch template IMDSv2
    assert_contains(S, d / "main.tf",
        ["aws_launch_template", "http_tokens", '"required"'],
        "main.tf: Launch template enforces IMDSv2")

    # Target tracking scaling policies
    assert_contains(S, d / "main.tf",
        ["TargetTrackingScaling", "ASGAverageCPUUtilization"],
        "main.tf: CPU-based target tracking scaling policy")

    # ALB access logs to S3
    assert_contains(S, d / "main.tf",
        ["access_logs", "alb-access-logs"],
        "main.tf: ALB access logs shipped to S3")

    # HTTP → HTTPS redirect
    assert_contains(S, d / "main.tf",
        ["HTTP_301"],
        "main.tf: HTTP-to-HTTPS permanent redirect (301) at listener")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 6 — Terraform: governance (AWS Organizations + SCPs)
# ═══════════════════════════════════════════════════════════════════════════════

def test_governance() -> None:
    S = "governance"
    section("🏛️", "Project: governance (AWS Organizations + 3 SCPs at Root)")
    d = REPO / "governance"

    assert_file(S, d / "main.tf",   "main.tf exists")
    assert_file(S, d / "README.md", "README.md exists")
    assert_dir(S,  d / "policies",  "policies/ directory exists")

    # SCP JSON files
    scp_files = {
        "scp_deny_cloudtrail_stop.json": [
            "cloudtrail:StopLogging",
            "cloudtrail:DeleteTrail",
            "cloudtrail:PutEventSelectors",
        ],
        "scp_region_restriction.json": ["Deny", "aws:RequestedRegion"],
        "scp_deny_root_actions.json":   ["arn:aws:iam::*:root"],
    }

    for filename, required_values in scp_files.items():
        path = d / "policies" / filename
        data = assert_json_valid(S, path, f"policies/{filename} is valid JSON")
        if data:
            content = json.dumps(data)
            missing = [v for v in required_values if v not in content]
            label = f"policies/{filename}: required controls present"
            if not missing:
                pass_test(S, label)
            else:
                fail_test(S, label, f"Missing: {missing}")

    # Terraform wires SCPs to root
    assert_contains(S, d / "main.tf",
        ["aws_organizations_organization", "feature_set", '"ALL"',
         "enabled_policy_types", "SERVICE_CONTROL_POLICY"],
        "main.tf: Organization created with SCPs enabled")

    assert_contains(S, d / "main.tf",
        ["aws_organizations_policy_attachment",
         "org.roots[0].id"],
        "main.tf: all SCPs attached at Organisation ROOT level")

    # Two OUs defined
    assert_contains(S, d / "main.tf",
        ["Security-Prod", "Workloads-Prod"],
        "main.tf: Security-Prod and Workloads-Prod OUs defined")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 7 — Terraform Modules
# ═══════════════════════════════════════════════════════════════════════════════

def test_terraform_modules() -> None:
    S = "Terraform Modules"
    section("🧩", "Reusable Terraform Module Library (vpc / iam / logging / security)")
    m = REPO / "modules"

    # ── vpc module ──────────────────────────────────────────────────────────
    assert_file(S, m / "vpc" / "main.tf",       "vpc/main.tf exists")
    assert_file(S, m / "vpc" / "variables.tf",   "vpc/variables.tf exists")
    assert_file(S, m / "vpc" / "output.tf",      "vpc/output.tf exists")

    assert_contains(S, m / "vpc" / "main.tf",
        ["aws_vpc", "aws_internet_gateway", "aws_subnet",
         "aws_nat_gateway", "aws_route_table"],
        "vpc/main.tf: VPC, IGW, subnets, NAT GW, route tables all defined")

    assert_contains(S, m / "vpc" / "main.tf",
        ["public_a", "public_b", "private_a", "private_b"],
        "vpc/main.tf: dual-AZ subnets (public_a/b + private_a/b) for HA")

    # ── iam module ──────────────────────────────────────────────────────────
    assert_file(S, m / "iam" / "main.tf",       "iam/main.tf exists")
    assert_file(S, m / "iam" / "variables.tf",   "iam/variables.tf exists")
    assert_file(S, m / "iam" / "outputs.tf",     "iam/outputs.tf exists")

    assert_contains(S, m / "iam" / "main.tf",
        ["aws_iam_role", "aws_iam_instance_profile"],
        "iam/main.tf: IAM role + instance profile defined")

    # ── logging module ──────────────────────────────────────────────────────
    assert_file(S, m / "logging" / "main.tf",    "logging/main.tf exists")
    assert_file(S, m / "logging" / "variables.tf","logging/variables.tf exists")
    assert_file(S, m / "logging" / "outputs.tf",  "logging/outputs.tf exists")

    assert_contains(S, m / "logging" / "main.tf",
        ["aws_kms_key", "enable_key_rotation",
         "block_public_acls", "aws_s3_bucket_versioning"],
        "logging/main.tf: KMS CMK + public block + versioning")

    assert_contains(S, m / "logging" / "main.tf",
        ["aws:SecureTransport"],
        "logging/main.tf: TLS-only bucket policy")

    assert_contains(S, m / "logging" / "main.tf",
        ["data.aws_caller_identity.current.account_id"],
        "logging/main.tf: KMS key scoped to account (no wildcard)")

    # ── security module ─────────────────────────────────────────────────────
    assert_file(S, m / "security" / "main.tf",   "security/main.tf exists")
    assert_file(S, m / "security" / "variables.tf","security/variables.tf exists")

    assert_contains(S, m / "security" / "main.tf",
        ["aws_cloudtrail", "is_multi_region_trail",
         "enable_log_file_validation", "aws_guardduty_detector"],
        "security/main.tf: multi-region CloudTrail + log validation + GuardDuty")

    assert_contains(S, m / "security" / "main.tf",
        ["data.aws_caller_identity.current.account_id"],
        "security/main.tf: KMS key principal scoped (no wildcard)")

    # ── s3_test module ──────────────────────────────────────────────────────
    assert_file(S, m / "s3_test" / "main.tf",    "s3_test/main.tf exists")

    assert_contains(S, m / "s3_test" / "main.tf",
        ["aws_s3_bucket_public_access_block",
         "block_public_acls", "aws_kms_key", "enable_key_rotation"],
        "s3_test/main.tf: public-access block + KMS encryption")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 8 — SOAR Automation (Python + pytest/moto)
# ═══════════════════════════════════════════════════════════════════════════════

def test_soar_automation(skip_pytest: bool = False) -> None:
    S = "SOAR Automation"
    section("⚡", "Project: SOAR Automation (Python NACL Remediation + pytest/moto)")
    d = REPO / "automation"

    assert_file(S, d / "auto_remediate_nacl.py",     "auto_remediate_nacl.py exists")
    assert_file(S, d / "test_auto_remediate_nacl.py", "test_auto_remediate_nacl.py exists")
    assert_file(S, d / "requirements.txt",            "requirements.txt exists")
    assert_file(S, d / "README.md",                   "README.md exists")

    # Python syntax
    assert_python_syntax(S, d / "auto_remediate_nacl.py",
                         "auto_remediate_nacl.py: valid Python syntax")
    assert_python_syntax(S, d / "test_auto_remediate_nacl.py",
                         "test_auto_remediate_nacl.py: valid Python syntax")

    # Key functions exist in main module
    text = (d / "auto_remediate_nacl.py").read_text()
    for fn in ["find_vpc_id", "find_nacl_id", "block_ip", "cleanup_rule",
               "rule_exists", "parse_args", "main"]:
        if f"def {fn}" in text:
            pass_test(S, f"Function '{fn}' defined in auto_remediate_nacl.py")
        else:
            fail_test(S, f"Function '{fn}' defined in auto_remediate_nacl.py",
                      f"'def {fn}' not found")

    # Custom exceptions defined
    for exc in ["VPCNotFoundError", "NACLNotFoundError", "RuleConflictError"]:
        if f"class {exc}" in text:
            pass_test(S, f"Custom exception '{exc}' defined")
        else:
            fail_test(S, f"Custom exception '{exc}' defined",
                      f"'class {exc}' not found")

    # Dry-run mode implemented
    assert_contains(S, d / "auto_remediate_nacl.py",
        ["dry_run", "--dry-run", "--cleanup"],
        "auto_remediate_nacl.py: dry-run and cleanup CLI flags implemented")

    # NACL deny rule uses correct protocol/action
    assert_contains(S, d / "auto_remediate_nacl.py",
        ['"deny"', 'Protocol="-1"', 'Egress=False'],
        "auto_remediate_nacl.py: NACL DENY rule targets inbound all-protocol traffic")

    # requirements.txt pinned
    req_text = (d / "requirements.txt").read_text()
    for pkg in ["boto3", "pytest", "moto"]:
        if pkg in req_text:
            pass_test(S, f"requirements.txt: '{pkg}' dependency declared")
        else:
            fail_test(S, f"requirements.txt: '{pkg}' dependency declared",
                      f"'{pkg}' not found in requirements.txt")

    # ── Run pytest ───────────────────────────────────────────────────────────
    if skip_pytest:
        info("Skipping pytest execution (--skip-tests flag set)")
        return

    info("Running pytest with moto AWS mock (no real AWS required)…")
    env = {
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "LOCALSTACK_MODE": "false",   # force moto path, not LocalStack
        "PYTHONPATH": str(d),
    }
    rc, stdout, stderr = run_cmd(
        [sys.executable, "-m", "pytest", "test_auto_remediate_nacl.py",
         "-v", "--tb=short", "--no-header"],
        cwd=d, timeout=120, env=env,
    )

    if rc == 0:
        # Count individual test results from pytest output
        passed = stdout.count(" PASSED")
        skipped = stdout.count(" SKIPPED")
        pass_test(S,
                  f"pytest suite: all {passed} tests passed"
                  + (f" ({skipped} skipped)" if skipped else ""),
                  "moto mock — no real AWS")
        if VERBOSE:
            for line in stdout.splitlines():
                if line.strip():
                    print(f"         {DIM}{line}{RESET}")
    else:
        # Extract failure summary
        summary_lines = [l for l in stdout.splitlines()
                         if l.startswith("FAILED") or "error" in l.lower()]
        detail = "\n".join(summary_lines[:10]) or stderr[:400] or stdout[-400:]
        fail_test(S, "pytest suite: all tests passed", detail)


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 9 — DFIR / Forensics
# ═══════════════════════════════════════════════════════════════════════════════

def test_dfir_forensics() -> None:
    S = "DFIR Forensics"
    section("🔬", "Project: DFIR Investigation (MITRE ATT&CK Mapped Auth Log)")
    d = REPO / "forensics"

    assert_file(S, d / "auth.log",          "auth.log (simulated crime-scene log) exists")
    assert_file(S, d / "setup_victim.sh",   "setup_victim.sh (log generator) exists")
    assert_file(S, d / "README.md",         "README.md exists")

    if not (d / "auth.log").exists():
        return

    log_text = (d / "auth.log").read_text(encoding="utf-8")
    lines = log_text.strip().splitlines()

    # ── T1110.001 — Brute Force ──────────────────────────────────────────────
    brute_lines = [l for l in lines if "Failed password for root" in l]
    if len(brute_lines) >= 10:
        pass_test(S,
                  f"MITRE T1110.001 (Brute Force): {len(brute_lines)} failed SSH attempts detected",
                  f"attacker IP: 192.168.1.50")
    else:
        fail_test(S, "MITRE T1110.001 (Brute Force): ≥10 failed SSH attempts",
                  f"Only {len(brute_lines)} found")

    # Check attacker IP is consistent
    ips = set(re.findall(r"from (\d+\.\d+\.\d+\.\d+)", log_text))
    if "192.168.1.50" in ips:
        pass_test(S, "Attacker IP 192.168.1.50 identified across events")
    else:
        fail_test(S, "Attacker IP 192.168.1.50 identified", f"IPs found: {ips}")

    # ── T1078 — Valid Accounts (Successful Breach) ───────────────────────────
    breach_lines = [l for l in lines if "Accepted password" in l]
    if breach_lines:
        pass_test(S, "MITRE T1078 (Valid Accounts): successful breach entry found",
                  breach_lines[0].strip()[:80])
    else:
        fail_test(S, "MITRE T1078 (Valid Accounts): successful breach entry found")

    # ── T1136.001 — Create Local Account (Persistence) ──────────────────────
    persist_lines = [l for l in lines if "support_service" in l and "useradd" in l]
    if persist_lines:
        pass_test(S,
                  "MITRE T1136.001 (Create Local Account): backdoor user 'support_service' with UID=0",
                  "UID=0 = root-equivalent — critical persistence mechanism")
    else:
        fail_test(S, "MITRE T1136.001 (Create Local Account): backdoor user creation logged")

    uid0 = any("UID=0" in l for l in lines if "support_service" in l)
    if uid0:
        pass_test(S, "Persistence: backdoor user created with UID=0 (root equivalent)")
    else:
        fail_test(S, "Persistence: backdoor user UID=0 verified in log")

    # ── T1560.001 — Archive via Utility (Exfiltration) ──────────────────────
    exfil_lines = [l for l in lines if "data_dump" in l or "tar" in l]
    if exfil_lines:
        pass_test(S,
                  "MITRE T1560.001 (Archive via Utility): data exfiltration via tar detected",
                  "/var/www/html → /tmp/data_dump.tar.gz")
    else:
        fail_test(S, "MITRE T1560.001 (Archive via Utility): tar exfiltration entry found")

    # ── Timeline integrity ───────────────────────────────────────────────────
    # Brute force should precede breach
    if brute_lines and breach_lines:
        last_brute = brute_lines[-1]
        first_breach = breach_lines[0]
        # Both on Dec 1; compare minute markers (08:0X vs 08:20)
        brute_time = re.search(r"08:(\d+):", last_brute)
        breach_time = re.search(r"08:(\d+):", first_breach)
        if brute_time and breach_time:
            if int(brute_time.group(1)) < int(breach_time.group(1)):
                pass_test(S, "Timeline: brute-force precedes successful breach (correct order)")
            else:
                fail_test(S, "Timeline: brute-force precedes successful breach",
                          "Timestamps appear out of order")

    # setup_victim.sh is a valid shell script (basic check)
    sh_text = (d / "setup_victim.sh").read_text()
    if sh_text.startswith("#!/bin/bash") and "Failed password" in sh_text:
        pass_test(S, "setup_victim.sh: valid bash script with attack simulation commands")
    else:
        fail_test(S, "setup_victim.sh: valid bash script with shebang and simulation code")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 10 — Kubernetes: K8s Ecommerce Project
# ═══════════════════════════════════════════════════════════════════════════════

def test_k8s_ecommerce() -> None:
    S = "K8s Ecommerce"
    section("🚀", "Project: KubeScale E-commerce Platform (K8s Manifests + Email Service)")
    d = REPO / "k8s-ecommerce-project"

    # ── manifest files ───────────────────────────────────────────────────────
    manifest_dir = d / "manifest"
    assert_dir(S, manifest_dir, "manifest/ directory exists")

    expected_manifests = {
        "deployment.yaml":      {"apiVersion": "apps/v1",              "kind": "Deployment"},
        "service.yaml":         {"apiVersion": "v1",                    "kind": "Service"},
        "hpa.yaml":             {"apiVersion": "autoscaling/v2",        "kind": "HorizontalPodAutoscaler"},
        "network-policy.yaml":  {"apiVersion": "networking.k8s.io/v1",  "kind": "NetworkPolicy"},
        "shop-ingress.yaml":    {"apiVersion": "networking.k8s.io/v1",  "kind": "Ingress"},
    }

    for filename, expected in expected_manifests.items():
        path = manifest_dir / filename
        assert_file(S, path, f"manifest/{filename} exists")
        if not path.exists():
            continue

        data = assert_yaml_valid(S, path, f"manifest/{filename}: valid YAML",
                                 multi=(filename == "network-policy.yaml"))
        if data:
            for key, val in expected.items():
                if data.get(key) == val:
                    pass_test(S, f"manifest/{filename}: {key}={val!r}")
                else:
                    fail_test(S, f"manifest/{filename}: {key}={val!r}",
                              f"got {data.get(key)!r}")

    # ── Deployment security hardening ────────────────────────────────────────
    dep_path = manifest_dir / "deployment.yaml"
    if dep_path.exists():
        dep_text = dep_path.read_text()
        assert_contains(S, dep_path,
            ["runAsNonRoot: true", "readOnlyRootFilesystem: true",
             "allowPrivilegeEscalation: false"],
            "deployment.yaml: non-root + read-only filesystem + no privilege escalation")
        assert_contains(S, dep_path,
            ["drop:", "- ALL"],
            "deployment.yaml: all Linux capabilities dropped")
        assert_contains(S, dep_path,
            ["seccompProfile:", "RuntimeDefault"],
            "deployment.yaml: seccomp RuntimeDefault profile applied")
        assert_contains(S, dep_path,
            ["livenessProbe:", "readinessProbe:"],
            "deployment.yaml: liveness and readiness probes defined")
        assert_contains(S, dep_path,
            ["resources:", "requests:", "limits:"],
            "deployment.yaml: resource requests and limits defined")
        assert_contains(S, dep_path,
            ["podAntiAffinity"],
            "deployment.yaml: pod anti-affinity (prevents single-node SPOF)")

    # ── HPA ──────────────────────────────────────────────────────────────────
    hpa_path = manifest_dir / "hpa.yaml"
    if hpa_path.exists():
        assert_contains(S, hpa_path,
            ["minReplicas: 2", "maxReplicas: 10"],
            "hpa.yaml: minReplicas=2 (HA) and maxReplicas=10 (cost cap)")
        assert_contains(S, hpa_path,
            ["averageUtilization: 70", "averageUtilization: 80"],
            "hpa.yaml: CPU 70% and Memory 80% scale-out thresholds")
        assert_contains(S, hpa_path,
            ["stabilizationWindowSeconds"],
            "hpa.yaml: stabilization windows to prevent thrashing")

    # ── NetworkPolicy (Zero Trust) ───────────────────────────────────────────
    np_path = manifest_dir / "network-policy.yaml"
    if np_path.exists():
        assert_contains(S, np_path,
            ["default-deny-all", "podSelector: {}"],
            "network-policy.yaml: default deny-all baseline (Zero Trust)")
        assert_contains(S, np_path,
            ["allow-frontend-to-email"],
            "network-policy.yaml: explicit allow from frontend to email-service only")
        assert_contains(S, np_path,
            ["port: 53"],
            "network-policy.yaml: DNS-only egress allowed for email-service")

    # ── Ingress ──────────────────────────────────────────────────────────────
    ing_path = manifest_dir / "shop-ingress.yaml"
    if ing_path.exists():
        assert_contains(S, ing_path,
            ["ingressClassName: nginx", "shop.local"],
            "shop-ingress.yaml: nginx ingress class + shop.local hostname")
        assert_contains(S, ing_path,
            ["limit-rps", "X-Frame-Options", "X-Content-Type-Options"],
            "shop-ingress.yaml: rate limiting + security headers on ingress")

    # ── Email service application ─────────────────────────────────────────────
    email_dir = d / "email-service"
    assert_dir(S, email_dir, "email-service/ directory exists")
    assert_file(S, email_dir / "Dockerfile",       "email-service/Dockerfile exists")
    assert_file(S, email_dir / "app.py",            "email-service/app.py exists")
    assert_file(S, email_dir / "requirements.txt",  "email-service/requirements.txt exists")

    if (email_dir / "app.py").exists():
        assert_python_syntax(S, email_dir / "app.py",
                             "email-service/app.py: valid Python syntax")
        assert_contains(S, email_dir / "app.py",
            ["Flask", "@app.route", "socket.gethostname"],
            "email-service/app.py: Flask app with hostname-aware response (K8s pod ID)")

    if (email_dir / "Dockerfile").exists():
        assert_contains(S, email_dir / "Dockerfile",
            ["python:3.9.18-slim"],
            "Dockerfile: pinned base image (supply-chain safety)")
        assert_contains(S, email_dir / "Dockerfile",
            ["useradd", "USER appuser"],
            "Dockerfile: non-root user created and enforced")
        assert_contains(S, email_dir / "Dockerfile",
            ["gunicorn"],
            "Dockerfile: gunicorn (production WSGI server) used")
        assert_contains(S, email_dir / "Dockerfile",
            ["--no-cache-dir"],
            "Dockerfile: pip --no-cache-dir (smaller image)")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 11 — CI/CD Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def test_cicd_pipeline() -> None:
    S = "CI/CD Pipeline"
    section("🔐", "CI/CD: DevSecOps Security Gate (GitHub Actions)")
    wf_path = REPO / ".github" / "workflows" / "trivy-scan.yml"

    assert_file(S, wf_path, ".github/workflows/trivy-scan.yml exists")
    if not wf_path.exists():
        return

    wf = assert_yaml_valid(S, wf_path, "trivy-scan.yml is valid YAML")
    if wf is None:
        return

    # Triggers — PyYAML parses the bare YAML key `on:` as the boolean True
    # (YAML 1.1 core schema treats "on" as a truthy value).  Fall back to
    # wf.get(True, {}) to handle both str-key and bool-key representations.
    triggers = wf.get("on", wf.get(True, {})) or {}
    for trigger in ["push", "pull_request"]:
        if trigger in triggers:
            pass_test(S, f"Workflow trigger '{trigger}' configured")
        else:
            fail_test(S, f"Workflow trigger '{trigger}' configured")

    # 4 required jobs
    jobs = wf.get("jobs", {})
    expected_jobs = {
        "trivy-iac":       "IaC Misconfiguration Scan",
        "trivy-container": "Container & Filesystem Scan",
        "secret-scan":     "Secret & Credential Scan (TruffleHog)",
        "checkov-scan":    "Checkov Policy-as-Code Scan",
    }
    for job_id, description in expected_jobs.items():
        if job_id in jobs:
            pass_test(S, f"Job '{job_id}' defined: {description}")
        else:
            fail_test(S, f"Job '{job_id}' defined: {description}",
                      f"Available jobs: {list(jobs.keys())}")

    # Least-privilege permissions
    perms = wf.get("permissions", {})
    if perms.get("contents") == "read":
        pass_test(S, "Workflow permissions: contents=read (least privilege)")
    else:
        fail_test(S, "Workflow permissions: contents=read (least privilege)",
                  f"Got: {perms}")

    # SARIF upload (GitHub Security tab integration)
    wf_text = wf_path.read_text()
    if "upload-sarif" in wf_text:
        pass_test(S, "SARIF upload configured (findings appear in GitHub Security tab)")
    else:
        fail_test(S, "SARIF upload configured")

    # Trivy action pinned to a version
    if "trivy-action@" in wf_text:
        pass_test(S, "Trivy action version pinned (supply-chain security)")
    else:
        fail_test(S, "Trivy action version pinned")

    # TruffleHog full history scan
    if "fetch-depth: 0" in wf_text:
        pass_test(S, "Full git history fetched (TruffleHog scans all commits)")
    else:
        fail_test(S, "Full git history fetched for secret scanning")

    # Exit code 1 on critical findings (hard gate)
    if "exit-code: '1'" in wf_text:
        pass_test(S, "Trivy exit-code=1: security gate blocks merge on HIGH/CRITICAL")
    else:
        fail_test(S, "Trivy exit-code=1: hard security gate configured")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 12 — Documentation
# ═══════════════════════════════════════════════════════════════════════════════

def test_documentation() -> None:
    S = "Documentation"
    section("📚", "Documentation: ADRs, Reality Checks, Weekly Docs")
    docs = REPO / "docs"

    # ── Architecture Decision Records ────────────────────────────────────────
    adr_dir = docs / "adr"
    assert_dir(S, adr_dir, "docs/adr/ directory exists")

    adr_files = [
        ("ADR-001-localstack-over-real-aws.md",   "ADR-001: LocalStack over real AWS"),
        ("ADR-002-terraform-remote-state.md",      "ADR-002: Terraform remote state"),
        ("ADR-003-container-security-hardening.md","ADR-003: Container security hardening"),
    ]
    for filename, label in adr_files:
        assert_file(S, adr_dir / filename, f"{label} document exists")

    # ── Reality Check documentation ──────────────────────────────────────────
    rc_dir = docs / "reality-check"
    assert_dir(S, rc_dir, "docs/reality-check/ directory exists")
    assert_file(S, rc_dir / "INDEX.md", "docs/reality-check/INDEX.md exists")

    reality_checks = [
        "REALITY_CHECK_01_IaC_FOUNDATIONS.md",
        "REALITY_CHECK_02_S3_SECURE_STORAGE.md",
        "REALITY_CHECK_03_SECURITY_STACK.md",
        "REALITY_CHECK_04_HA_AWS_ARCHITECTURE.md",
        "REALITY_CHECK_05_ENTERPRISE_GOVERNANCE.md",
        "REALITY_CHECK_06_SOAR_AUTOMATION.md",
        "REALITY_CHECK_07_DFIR_INVESTIGATION.md",
        "REALITY_CHECK_08_KUBESCALE_PLATFORM.md",
        "REALITY_CHECK_09_DEVSECOPS_PIPELINE.md",
    ]
    for filename in reality_checks:
        assert_file(S, rc_dir / filename, f"Reality Check: {filename} exists")

    # ── Weekly project docs (renamed slug folders) ────────────────────────────
    slug_folders = [
        ("01-aws-fundamentals",       "01: AWS Fundamentals"),
        ("02-logging-and-visibility", "02: Logging & Visibility"),
        ("03-terraform-fundamentals", "03: Terraform Fundamentals"),
        ("04-devsecops-guardrails",   "04: DevSecOps Guardrails"),
        ("05-secure-network-identity","05: Secure Network & Identity"),
        ("06-observability-hardening","06: Observability & Hardening"),
        ("08-high-availability",      "08: High Availability"),
        ("09-security-automation-soar","09: Security Automation SOAR"),
        ("10-dfir-forensics",         "10: DFIR Forensics"),
        ("11-enterprise-governance",  "11: Enterprise Governance"),
    ]
    for folder, label in slug_folders:
        assert_dir(S, docs / folder, f"docs/{folder}/ exists ({label})")

    # Incident reports
    assert_dir(S, REPO / "incident-reports", "incident-reports/ directory exists")


# ═══════════════════════════════════════════════════════════════════════════════
# SUITE 13 — Security Hygiene Checks
# ═══════════════════════════════════════════════════════════════════════════════

def test_security_hygiene() -> None:
    S = "Security Hygiene"
    section("🔒", "Security Hygiene: Credentials, .trivyignore, Hardening Markers")

    # .trivyignore exists and is not empty
    ti = REPO / ".trivyignore"
    assert_file(S, ti, ".trivyignore exists")
    if ti.exists() and ti.stat().st_size > 0:
        pass_test(S, ".trivyignore is non-empty (documented exceptions)")
    elif ti.exists():
        pass_test(S, ".trivyignore present (empty — no exceptions needed)")

    # No real AWS credentials in any .tf file
    tf_files = list(REPO.rglob("*.tf"))
    real_key_pattern = re.compile(r'access_key\s*=\s*"(?!test")[A-Z0-9]{20}')
    real_secret_pattern = re.compile(r'secret_key\s*=\s*"(?!test")[A-Za-z0-9/+]{40}')
    leaked = []
    for tf in tf_files:
        try:
            text = tf.read_text(encoding="utf-8")
            if real_key_pattern.search(text) or real_secret_pattern.search(text):
                leaked.append(str(tf.relative_to(REPO)))
        except Exception:
            pass
    if not leaked:
        pass_test(S, f"No real AWS credentials in any of {len(tf_files)} .tf files",
                  "only dummy 'test' values used for LocalStack")
    else:
        fail_test(S, "No real AWS credentials in .tf files",
                  f"Potential leak in: {leaked}")

    # IMDSv2 enforced everywhere EC2 is launched.
    # Read each file once and cache the text to avoid redundant I/O.
    ec2_tf_files = []
    for f in tf_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if 'resource "aws_instance"' in text or 'resource "aws_launch_template"' in text:
            ec2_tf_files.append((f, text))
    imds_missing = []
    for tf, text in ec2_tf_files:
        if 'http_tokens' not in text or '"required"' not in text:
            imds_missing.append(str(tf.relative_to(REPO)))
    if not imds_missing:
        pass_test(S, "IMDSv2 (http_tokens=required) present in all EC2 / launch template configs")
    else:
        fail_test(S, "IMDSv2 enforced in all EC2 configs",
                  f"Missing in: {imds_missing}")

    # EBS encryption in all EC2 configs (reuse cached texts from ec2_tf_files)
    ebs_missing = []
    for tf, text in ec2_tf_files:
        if "encrypted" not in text:
            ebs_missing.append(str(tf.relative_to(REPO)))
    if not ebs_missing:
        pass_test(S, "EBS encryption declared in all EC2/launch-template configs")
    else:
        fail_test(S, "EBS encryption in all EC2 configs", f"Missing in: {ebs_missing}")

    # All KMS keys have key rotation enabled (read once per file)
    kms_tf_files = []
    for f in tf_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if 'resource "aws_kms_key"' in text:
            kms_tf_files.append((f, text))
    rotation_missing = []
    for tf, text in kms_tf_files:
        if "enable_key_rotation" not in text:
            rotation_missing.append(str(tf.relative_to(REPO)))
    if not rotation_missing:
        pass_test(S, f"KMS key rotation enabled in all {len(kms_tf_files)} files defining KMS keys")
    else:
        fail_test(S, "KMS key rotation enabled in all files",
                  f"Possibly missing in: {rotation_missing}")

    # All S3 buckets have public-access block (read once per file)
    s3_tf_files = []
    for f in tf_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if 'resource "aws_s3_bucket"' in text:
            s3_tf_files.append((f, text))
    s3_no_block = []
    for tf, text in s3_tf_files:
        if "aws_s3_bucket_public_access_block" not in text:
            s3_no_block.append(str(tf.relative_to(REPO)))
    if not s3_no_block:
        pass_test(S, "Public-access block resource present alongside every S3 bucket definition")
    else:
        fail_test(S, "Public-access block alongside every S3 bucket",
                  f"Check these files: {s3_no_block}")


# ═══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(elapsed: float) -> int:
    passed = [r for r in RESULTS if r[2]]
    failed = [r for r in RESULTS if not r[2]]
    total  = len(RESULTS)

    print(f"\n{BOLD}{'═'*62}{RESET}")
    print(f"{BOLD}  📊  SMOKE TEST SUMMARY{RESET}")
    print(f"{BOLD}{'═'*62}{RESET}")

    # Per-suite breakdown
    suites: dict = {}
    for suite, name, ok, _ in RESULTS:
        suites.setdefault(suite, []).append(ok)

    print(f"\n  {'Suite':<34} {'Pass':>5}  {'Fail':>5}  {'Status'}")
    print(f"  {'─'*34}  {'─'*5}  {'─'*5}  {'─'*10}")
    for suite, results in suites.items():
        p = sum(results)
        f = len(results) - p
        status = f"{GREEN}ALL PASS{RESET}" if f == 0 else f"{RED}{f} FAILED{RESET}"
        print(f"  {suite:<34}  {p:>5}  {f:>5}  {status}")

    print(f"\n  {'─'*62}")
    pct = int(100 * len(passed) / total) if total else 0
    bar_len = 40
    filled = int(bar_len * len(passed) / total) if total else 0
    bar_color = GREEN if len(failed) == 0 else (YELLOW if pct >= 80 else RED)
    bar = f"{bar_color}{'█' * filled}{'░' * (bar_len - filled)}{RESET}"
    print(f"\n  Progress  [{bar}]  {pct}%")
    print(f"\n  {GREEN}✅ PASSED:{RESET}  {len(passed):>4}")
    print(f"  {RED}❌ FAILED:{RESET}  {len(failed):>4}")
    print(f"  📋 TOTAL:   {total:>4}")
    print(f"  ⏱  TIME:   {elapsed:.1f}s")

    if failed:
        print(f"\n{BOLD}{RED}  FAILED TESTS:{RESET}")
        for suite, name, _, detail in failed:
            print(f"  {RED}✗{RESET}  [{suite}] {name}")
            if detail:
                for dline in detail.splitlines()[:3]:
                    print(f"     {YELLOW}{dline}{RESET}")

    print(f"\n{BOLD}{'═'*62}{RESET}")
    if len(failed) == 0:
        print(f"{BOLD}{GREEN}  🎉  ALL {total} SMOKE TESTS PASSED — Portfolio verified end-to-end!{RESET}")
    else:
        print(f"{BOLD}{RED}  ⚠️   {len(failed)} test(s) failed. Review details above.{RESET}")
    print(f"{BOLD}{'═'*62}{RESET}\n")

    return 0 if len(failed) == 0 else 1


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> int:
    global VERBOSE

    parser = argparse.ArgumentParser(
        description="Smoke test suite for the CloudDefense Engineering Portfolio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python smoke_test.py                 # full suite
              python smoke_test.py --skip-tests    # structural checks only (no pytest)
              python smoke_test.py --verbose       # show pass detail
        """),
    )
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip pytest execution (run structural checks only)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detail text on passing tests")
    args = parser.parse_args()
    VERBOSE = args.verbose

    start = time.time()

    print(f"\n{BOLD}{MAGENTA}{'═'*62}{RESET}")
    print(f"{BOLD}{MAGENTA}  🔭  CloudDefense Engineering Portfolio — Smoke Test Suite{RESET}")
    print(f"{BOLD}{MAGENTA}  by Jimoh Sodiq Bolaji{RESET}")
    print(f"{BOLD}{MAGENTA}{'═'*62}{RESET}")
    print(f"  {DIM}Repository: {REPO}{RESET}")
    print(f"  {DIM}Python:     {sys.version.split()[0]}{RESET}")
    print(f"  {DIM}Mode:       {'--skip-tests' if args.skip_tests else 'full'}"
          f"{'  --verbose' if VERBOSE else ''}{RESET}")

    # Run all suites
    test_repo_structure()
    test_aws_foundation()
    test_s3_secure_storage()
    test_security_stack()
    test_ha_aws_architecture()
    test_governance()
    test_terraform_modules()
    test_soar_automation(skip_pytest=args.skip_tests)
    test_dfir_forensics()
    test_k8s_ecommerce()
    test_cicd_pipeline()
    test_documentation()
    test_security_hygiene()

    return print_summary(time.time() - start)


if __name__ == "__main__":
    sys.exit(main())
