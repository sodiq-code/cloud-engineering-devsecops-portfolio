# Reality Check Documentation

> **This portfolio was not built on the happy path.** Every project hit real engineering failures. These documents record what broke, why it broke, exactly how it was fixed, and what it would have cost in production.

---

## Overview: The Failures That Shaped This Portfolio

| # | Project | Hardest Failure | Time Lost | Business Impact |
| :-- | :-- | :-- | :-- | :-- |
| 1 | [IaC Foundations](./REALITY_CHECK_01_IaC_FOUNDATIONS.md) | KMS wildcard key policy grants every IAM identity decryption access | Caught at review | Any IAM identity in the account could read encrypted logs |
| 2 | [S3 Secure Storage](./REALITY_CHECK_02_S3_SECURE_STORAGE.md) | Terraform AWS provider v5.x breaks LocalStack EC2/VPC API silently | 2 hours | All `terraform apply` runs fail mid-plan with opaque errors |
| 3 | [Security Stack](./REALITY_CHECK_03_SECURITY_STACK.md) | CloudTrail log bucket policy rejected KMS CMK encryption for the trail | 1 hour | CloudTrail would write unencrypted logs or fail entirely |
| 4 | [HA AWS Architecture](./REALITY_CHECK_04_HA_AWS_ARCHITECTURE.md) | ALB requires ≥ 2 subnets in different AZs — single-AZ VPC module broke creation | 3 hours | `terraform apply` errors; zero traffic distribution across AZs |
| 5 | [Enterprise Governance](./REALITY_CHECK_05_ENTERPRISE_GOVERNANCE.md) | SCP attached at OU level instead of Root — Security OU could bypass its own controls | Caught at review | Governance policy had a critical structural gap; SCPs did not apply universally |
| 6 | [SOAR Automation](./REALITY_CHECK_06_SOAR_AUTOMATION.md) | `sys.exit()` inside library function made unit tests impossible to run | 4 hours | CI would never test remediation logic; bugs in Lambda would go undetected |
| 7 | [DFIR Investigation](./REALITY_CHECK_07_DFIR_INVESTIGATION.md) | Manual IP blocking after SSH breach — 46 minutes from detection to containment | 46 min window | Attacker had 46 minutes inside the network after detection |
| 8 | [KubeScale Platform](./REALITY_CHECK_08_KUBESCALE_PLATFORM.md) | OOMKill crashing pods — no resource limits meant unbounded memory consumption | 2 hours | Noisy-neighbour outage; one service's memory spike killed unrelated pods |
| 9 | [DevSecOps Pipeline](./REALITY_CHECK_09_DEVSECOPS_PIPELINE.md) | `trivy-action@0.28.0` tag did not exist — entire CI gate was silently broken | Undetected for duration of development | Security scanning was not running on any pull request |

---

## Format

Each document covers multiple failures per project in the following structure:

```
### Problem N — Title

| Field       | Value                   |
|-------------|-------------------------|
| Severity    | P1 / P2 / P3            |
| Time Lost   | X hours / caught early  |
| Discovered  | How the bug surfaced     |

**Symptom:** What was observed in the terminal / logs.

**Root Cause:** The actual engineering reason it failed.

**Fix Applied:** What was changed to resolve it.

**Business Impact:** What this failure costs in production.
```

---

*Full Reality Check documentation for each project is linked in the table above.*
