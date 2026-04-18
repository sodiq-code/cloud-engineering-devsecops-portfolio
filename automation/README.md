# ⚡ Real-Time Threat Remediation Engine (SOAR)

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![AWS](https://img.shields.io/badge/AWS_Boto3-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-Pytest%20%2B%20Moto-brightgreen?style=for-the-badge)
![SOAR](https://img.shields.io/badge/SOAR-Automated-blue?style=for-the-badge)

**Millisecond Containment | Argparse CLI | Dry-Run Support | 100% Unit Test Coverage**

</div>

---

## 🎯 Project Mission

Reduce **Time-to-Containment** from minutes (manual incident response) to **milliseconds** (automated SOAR) — demonstrating the Python/Boto3 automation capabilities that underpin real-world Security Operations Center (SOC) tooling.

---

## 1. How It Works

```
DETECTION                    INVESTIGATION              REMEDIATION
    │                             │                          │
GuardDuty                    find_vpc_id()             block_ip()
 Finding                     find_nacl_id()                 │
    │                             │                    NACL DENY Rule
EventBridge ──► Lambda ──────►  main()                 (Rule #1, highest
 Rule                        (this script)              priority, all ports)
    │                             │
    └── Malicious IP             └── cleanup_rule()    ◄── Threat resolved
        passed as arg                (when threat ends)
```

**Production Architecture (EventBridge → Lambda):**
```
GuardDuty Finding (High Severity)
    │
    ▼
EventBridge Rule: severity >= HIGH
    │
    ▼
Lambda Function (invokes auto_remediate_nacl.py)
    │
    ├── Extracts malicious IP from GuardDuty finding detail
    ├── Calls block_ip() with extracted IP
    └── NACL updated in < 500ms from finding creation
```

---

## 2. Script Features

| Feature | Implementation | Why It Matters |
| :--- | :--- | :--- |
| **CLI argument parsing** | `argparse` (not hardcoded IPs) | Works with any IP dynamically — required for Lambda |
| **Structured logging** | `logging` module (not `print()`) | Output captured by CloudWatch Logs in Lambda |
| **Custom exceptions** | `VPCNotFoundError`, `NACLNotFoundError`, `RuleConflictError` | Enables proper error handling by callers |
| **Dry-run mode** | `--dry-run` flag | Preview changes without making API calls — safe to test |
| **Cleanup support** | `--cleanup` flag | Remove DENY rule when threat is resolved (lifecycle management) |
| **Duplicate protection** | `rule_exists()` check | Prevents `InvalidNetworkAclEntry.Duplicate` API errors |
| **Unit tests** | pytest + moto | Verifies logic without real AWS account or LocalStack |

---

## 3. Usage

### Prerequisites
```bash
pip install -r requirements.txt
```

### Block a Malicious IP
```bash
python auto_remediate_nacl.py --ip 203.0.113.5/32
```

### Preview Without Making Changes (Dry Run)
```bash
python auto_remediate_nacl.py --ip 203.0.113.5/32 --dry-run
```

### Block at a Specific Rule Number
```bash
# Use rule 50 to avoid conflict with existing rules
python auto_remediate_nacl.py --ip 203.0.113.5/32 --rule-number 50
```

### Remove a Block When Threat is Resolved
```bash
python auto_remediate_nacl.py --cleanup --ip 203.0.113.5/32 --rule-number 1
```

### Example Output
```
2025-12-01T08:46:00 | INFO     | Connecting to EC2 API in region us-east-2...
2025-12-01T08:46:00 | INFO     | Querying EC2 API for VPC list...
2025-12-01T08:46:00 | INFO     | Target VPC identified: vpc-abc123
2025-12-01T08:46:00 | INFO     | Network ACL identified: acl-def456
2025-12-01T08:46:00 | INFO     | Preparing DENY rule #1 for IP 203.0.113.5/32 (dry_run=False)
2025-12-01T08:46:00 | INFO     | SUCCESS — Rule created: DENY ALL inbound from 203.0.113.5/32 (Priority #1)
```

---

## 4. Unit Tests

The test suite uses **moto** to mock all AWS API calls — no real AWS account or LocalStack required.

```bash
pip install -r requirements.txt
pytest test_auto_remediate_nacl.py -v
```

### Test Coverage

| Test | Scenario |
| :--- | :--- |
| `test_find_vpc_id_success` | VPC found and returned correctly |
| `test_find_vpc_id_raises_when_no_vpc` | `VPCNotFoundError` raised correctly |
| `test_find_nacl_id_success` | NACL found for VPC |
| `test_find_nacl_id_raises_for_invalid_vpc` | `NACLNotFoundError` raised |
| `test_block_ip_creates_deny_rule` | DENY rule created in NACL |
| `test_block_ip_raises_on_duplicate_rule_number` | `RuleConflictError` on duplicate |
| `test_block_ip_dry_run_makes_no_api_changes` | No AWS changes on dry-run |
| `test_cleanup_rule_removes_deny_entry` | Rule deleted on cleanup |
| `test_cleanup_rule_noop_when_rule_absent` | Warning logged, no error raised |
| `test_main_returns_zero_on_success` | Exit code 0 on success |
| `test_main_returns_one_on_vpc_not_found` | Exit code 1 on failure |

---

## 5. NACL Behaviour — Technical Detail

AWS NACLs are **stateless subnet-level firewalls**. Rules are evaluated in **ascending order** (lowest rule number first). The first matching rule wins — so Rule #1 is the highest priority.

```
Inbound Traffic from 203.0.113.5
    │
    ▼
NACL Rule #1: DENY ALL from 203.0.113.5/32  ← First match → BLOCKED
NACL Rule #100: ALLOW TCP port 80 from 0.0.0.0/0  ← Never reached
NACL Rule #32767: DENY ALL  ← AWS default deny
```

---

## 6. Source Code
- **Script:** [`auto_remediate_nacl.py`](./auto_remediate_nacl.py)
- **Tests:** [`test_auto_remediate_nacl.py`](./test_auto_remediate_nacl.py)
- **Dependencies:** [`requirements.txt`](./requirements.txt)

---

**Author:** Jimoh Sodiq Bolaji  
**Related Projects:** [Forensics](../forensics/README.md) | [Incident Report](../incident-reports/incident-001.md)  
**MITRE ATT&CK:** T1562.001 — Impair Defenses: Disable or Modify Tools (defended against)
