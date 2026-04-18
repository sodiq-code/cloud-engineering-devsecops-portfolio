# Reality Check: SOAR Automation (`automation`)

**Project:** `automation/`  
**Stack:** Python, Boto3, pytest, moto, AWS Network ACLs, AWS Lambda (target runtime)  
**Summary:** Building a production-grade IP blocking tool for Lambda surfaced three engineering failures that would cause the tool to silently not work in production: `sys.exit()` inside library functions, `print()` instead of structured logging, and no duplicate rule protection causing AWS API errors.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| `sys.exit()` inside library functions — unit tests impossible, Lambda handler breaks | P1 | 4 hours refactoring | ✅ Fixed — replaced with custom exceptions |
| `print()` instead of `logging` — all output invisible in CloudWatch | P1 | Caught at review | ✅ Fixed — full structured logging |
| No duplicate rule detection — AWS API throws `InvalidNetworkAclEntry.Duplicate` | P2 | 1 hour | ✅ Fixed — `rule_exists()` check added |
| No dry-run mode — dangerous to test containment logic on real infrastructure | P2 | 2 hours | ✅ Fixed — `--dry-run` flag added |

---

## Problem 1 — `sys.exit()` in Library Functions Made Unit Testing Impossible

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Architecture |
| **Time Lost** | ~4 hours of refactoring |
| **Discovered** | `pytest` test suite exited the entire test process when the "VPC not found" test ran |

**Symptom:**

The initial version of `auto_remediate_nacl.py` used `sys.exit(1)` to signal errors:

```python
def find_vpc_id(ec2_client):
    vpcs = ec2_client.describe_vpcs()["Vpcs"]
    if not vpcs:
        print("ERROR: No VPCs found")
        sys.exit(1)   # <-- this was the problem
    return vpcs[0]["VpcId"]
```

When running the unit test for the "VPC not found" case:

```python
def test_find_vpc_id_raises_when_no_vpc():
    # No VPCs created in this moto mock
    with pytest.raises(VPCNotFoundError):
        find_vpc_id(boto3.client("ec2"))
```

The test would never reach the `pytest.raises` assertion. Instead, the entire `pytest` process would exit with code 1 — terminating all remaining tests. The test output showed:

```
PASSED ✓ test_find_vpc_id_success
(pytest process exited — no further output)
```

**Root Cause:**

`sys.exit()` calls `SystemExit`, which is an exception that propagates up and terminates the Python interpreter — including the `pytest` process running the tests. It cannot be caught by `pytest.raises(VPCNotFoundError)` because `SystemExit` is not `VPCNotFoundError`.

The deeper issue: `sys.exit()` is a program-level termination call. Inside a library function — a function designed to be called by other code — it is categorically wrong. Library functions signal errors by raising exceptions. `sys.exit()` is only appropriate in the `if __name__ == "__main__"` block or a CLI entry point.

In an AWS Lambda handler, `sys.exit()` is even more problematic: Lambda does not respect `SystemExit`. The Lambda runtime catches `SystemExit` and converts it to a Lambda execution error with a generic message, losing all context about what actually went wrong. CloudWatch shows the invocation as an error with no useful diagnostic information.

**Fix Applied:**

Replaced all `sys.exit()` calls with custom exceptions throughout the library functions:

```python
# Custom exception hierarchy
class NACLRemediationError(Exception):
    """Base class for all NACL remediation errors."""

class VPCNotFoundError(NACLRemediationError):
    """Raised when no VPC is found in the AWS account/region."""

class NACLNotFoundError(NACLRemediationError):
    """Raised when no NACL is found for the specified VPC."""

class RuleConflictError(NACLRemediationError):
    """Raised when the specified rule number is already in use."""

# Library function raises exception, does not call sys.exit()
def find_vpc_id(ec2_client):
    vpcs = ec2_client.describe_vpcs()["Vpcs"]
    if not vpcs:
        raise VPCNotFoundError("No VPCs found in the current region and account.")
    return vpcs[0]["VpcId"]

# Only the CLI entry point calls sys.exit()
if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except NACLRemediationError as e:
        logger.error("Remediation failed: %s", e)
        sys.exit(1)
```

All 11 unit tests now run to completion and produce accurate coverage data.

**Business Impact:**

A Lambda function that uses `sys.exit()` for error handling will:

1. **Lose all error context** — CloudWatch shows "Task exited with status 1" instead of the actual error
2. **Never trigger error alarms** — Lambda error metrics require exceptions, not SystemExit
3. **Be impossible to unit test** — CI cannot validate the remediation logic without the test suite terminating prematurely
4. **Fail silently in production** — an invocation that fails due to a missing VPC looks identical to one that was never triggered

In a real incident, this means a GuardDuty finding triggers the Lambda, the Lambda "fails" silently, and the malicious IP is never blocked — while the CloudWatch dashboard shows "invocation error" with no remediation information.

---

## Problem 2 — `print()` Instead of `logging`: Output Invisible in CloudWatch

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Operational |
| **Time Lost** | Caught during code review |
| **Discovered** | Reviewing the script against Lambda operational requirements |

**Symptom:**

The initial version used `print()` statements for all output:

```python
print(f"Blocking IP: {ip_address}")
print(f"Created rule: DENY ALL from {ip_address}")
```

**Root Cause:**

AWS Lambda captures `stdout` and sends it to CloudWatch Logs. `print()` writes to `stdout`, so technically the output does appear in CloudWatch. However:

1. **No severity levels** — CloudWatch Logs Insights cannot filter `print()` output by severity (ERROR, WARNING, INFO). You cannot write an alarm on `ERROR` level events.
2. **No structured format** — `print()` output is free-form text. CloudWatch Logs Insights metric filters require consistent structure to extract fields.
3. **No timestamps in the message** — CloudWatch adds a timestamp, but the log line itself has no structured timestamp field.
4. **Cannot set log level at runtime** — `print()` cannot be silenced by changing `LOG_LEVEL=WARNING` without code changes.

In a production SOC environment, the first thing an on-call engineer does when an incident automation runs is check CloudWatch Logs — filtered to ERROR level events in the last 15 minutes. A script that uses `print()` produces output that is invisible to that workflow.

**Fix Applied:**

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Usage
logger.info("Blocking IP: %s", ip_address)
logger.warning("Duplicate rule detected for rule number %d", rule_number)
logger.error("VPC not found — no NACL update performed")
```

CloudWatch Logs Insights can now filter by `@message` containing "ERROR" or create a metric filter on log lines where `levelname == ERROR`.

**Business Impact:**

In a production SOC environment running at scale, Lambda functions may be invoked thousands of times per day. `print()` logging produces a wall of unstructured text. Structured `logging` enables:
- Automated alarms on ERROR-level events
- Dashboards showing remediation success vs failure rate over time
- Incident post-mortems with precise timestamps and event sequences

The difference between `print()` and `logging` is the difference between a script that runs and a tool that is operationally manageable.

---

## Problem 3 — No Duplicate Rule Detection: AWS API Throws Hard Error

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Reliability |
| **Time Lost** | ~1 hour |
| **Discovered** | Running the script twice against the same VPC raised an unhandled exception |

**Symptom:**

Running the remediation script twice with the same IP address and rule number:

```bash
python auto_remediate_nacl.py --ip 203.0.113.5/32 --rule-number 1
python auto_remediate_nacl.py --ip 203.0.113.5/32 --rule-number 1   # second run
```

Second run output:

```
botocore.exceptions.ClientError: An error occurred (InvalidNetworkAclEntry.Duplicate)
when calling the CreateNetworkAclEntry operation: A rule with this number already exists.
```

Unhandled exception, no cleanup, no useful error message to the operator.

**Root Cause:**

AWS NACLs do not support idempotent rule creation — you cannot call `create_network_acl_entry` with a rule number that already exists. In a production SOAR workflow, the Lambda may be invoked multiple times for the same GuardDuty finding (EventBridge retries, duplicate findings from multiple sources). Without idempotency, every invocation after the first would fail with an unhandled exception.

**Fix Applied:**

Added a `rule_exists()` check before attempting to create the rule:

```python
def rule_exists(ec2_client, nacl_id: str, rule_number: int) -> bool:
    """Check if a NACL rule with the specified rule number already exists (inbound)."""
    nacl = ec2_client.describe_network_acls(
        NetworkAclIds=[nacl_id]
    )["NetworkAcls"][0]
    
    existing_numbers = [
        entry["RuleNumber"]
        for entry in nacl.get("Entries", [])
        if not entry["Egress"]    # Inbound rules only
    ]
    return rule_number in existing_numbers

def block_ip(ec2_client, nacl_id: str, ip_cidr: str, rule_number: int, dry_run: bool):
    if rule_exists(ec2_client, nacl_id, rule_number):
        raise RuleConflictError(
            f"Rule #{rule_number} already exists in NACL {nacl_id}. "
            "Use --cleanup first or specify a different rule number."
        )
    # ... proceed with rule creation
```

The function is now idempotent-aware: it raises `RuleConflictError` on duplicates (catchable by the caller) instead of letting the AWS API error propagate as an unhandled exception.

**Business Impact:**

In production, GuardDuty findings may trigger multiple EventBridge events for the same malicious IP (e.g., finding updates as the threat actor continues activity). Each event invokes the Lambda. Without idempotency, the second invocation crashes with an unhandled error and may alert the on-call team that the automation is broken — when in fact the IP was already blocked by the first invocation. The signal/noise ratio of SOAR alerts degrades, and teams start ignoring automation failure alerts.

---

## What These Failures Prove

All four problems in the SOAR project share a common root cause: the initial implementation was written as a script, not as a library designed for programmatic invocation by Lambda.

The transition from "script that works on the command line" to "library that is safe to invoke from Lambda in production" required:

1. **Exception-based error signalling** — `sys.exit()` terminates processes; Lambda doesn't support that contract
2. **Structured logging** — `print()` produces unactionable logs; `logging` produces operational telemetry  
3. **Idempotent operations** — a script run once by a human can be corrected; a Lambda invoked automatically must handle duplicate invocations gracefully
4. **Dry-run mode** — a human testing a script can inspect it first; a Lambda invoked by automation needs a safe preview mode

These are not minor style preferences — they are the baseline requirements for code that operates in a production automated pipeline.
