# 🚨 Incident Report: IR-2025-001

| Field | Value |
| :--- | :--- |
| **Report ID** | IR-2025-001 |
| **Date Opened** | 2025-12-01 08:00 UTC |
| **Date Closed** | 2025-12-01 10:15 UTC |
| **Total Response Time** | 2h 15m |
| **Analyst** | Jimoh Sodiq Bolaji |
| **Severity** | 🔴 CRITICAL |
| **Classification** | Unauthorised Access / Data Breach Attempt |
| **Status** | ✅ CLOSED — Fully Contained |

---

## 1. Executive Summary

On December 1st 2025, a brute-force SSH campaign originating from IP `192.168.1.50` successfully compromised the `admin` account on a production web server. Post-compromise, the attacker created a root-level backdoor account (`support_service`) and staged website data for exfiltration. The threat was detected via log analysis, contained using automated NACL remediation, and the backdoor was eradicated.

**Business Impact:** Potential exfiltration of `/var/www/html` contents. No customer PII confirmed in scope at time of closure.

---

## 2. Attack Timeline

| Timestamp (UTC) | MITRE ATT&CK Technique | Event | Severity |
| :--- | :--- | :--- | :--- |
| **08:00 – 08:15** | T1110.001 — Brute Force: Password Guessing | 15 failed SSH attempts from `192.168.1.50` | 🟡 HIGH |
| **08:20:01** | T1078 — Valid Accounts | Successful login as `admin` from `192.168.1.50` | 🔴 CRITICAL |
| **08:20:01** | T1021.004 — SSH | New session 54 established for `admin` | 🔴 CRITICAL |
| **08:25:30** | T1136.001 — Create Local Account | Backdoor user `support_service` (UID=0) created | 🔴 CRITICAL |
| **08:25:30** | T1098 — Account Manipulation | Password set for `support_service` | 🔴 CRITICAL |
| **08:30:15** | T1560.001 — Archive via Utility | `/var/www/html` compressed to `/tmp/data_dump.tar.gz` via `sudo tar` | 🔴 CRITICAL |
| **08:45:00** | — | Analyst detected anomaly via log review | — |
| **08:46:03** | — | `auto_remediate_nacl.py` executed — `192.168.1.50` blocked in NACL | — |
| **09:00:00** | — | `admin` account locked; `support_service` deleted | — |
| **10:15:00** | — | Full forensic review complete; incident closed | — |

---

## 3. Indicators of Compromise (IoCs)

| IoC Type | Value | Confidence |
| :--- | :--- | :--- |
| **Attacker IP** | `192.168.1.50` | HIGH |
| **Compromised Account** | `admin` | HIGH |
| **Backdoor Account** | `support_service` (UID=0) | HIGH |
| **Staged File** | `/tmp/data_dump.tar.gz` | HIGH |
| **SSH Port Used** | `5566` (non-standard — may indicate attacker tooling) | MEDIUM |

---

## 4. Root Cause Analysis

| Factor | Detail |
| :--- | :--- |
| **Primary Cause** | SSH password authentication was enabled on a public-facing server |
| **Contributing Factor** | No automated brute-force protection (Fail2Ban not installed) |
| **Contributing Factor** | No SIEM/alerting for repeated failed authentication attempts |
| **Contributing Factor** | `admin` account with weak/guessable password |

---

## 5. Containment, Eradication & Recovery

### 5.1 Containment (Time to Contain: 26 minutes)
1. ✅ Blocked `192.168.1.50` in VPC Network ACL (Rule #1, highest priority) via automated remediation script
2. ✅ Terminated attacker's active SSH session

### 5.2 Eradication
3. ✅ Locked `admin` account: `usermod -L admin`
4. ✅ Deleted backdoor account: `userdel -r support_service`
5. ✅ Removed staged exfiltration file: `rm -f /tmp/data_dump.tar.gz`
6. ✅ Audited all UID=0 accounts: `awk -F: '($3 == 0)' /etc/passwd`
7. ✅ Rotated all SSH authorised keys

### 5.3 Recovery
8. ✅ Disabled password authentication: `PasswordAuthentication no` in `/etc/ssh/sshd_config`
9. ✅ Forced password resets for all service accounts
10. ✅ Verified system integrity via file hash comparison

---

## 6. Lessons Learned & Corrective Actions

| Priority | Lesson | Action | Owner | Due Date |
| :--- | :--- | :--- | :--- | :--- |
| 🔴 CRITICAL | Password SSH on public server | Enforce SSH key-only auth on all servers | SysOps | Immediate |
| 🔴 CRITICAL | No automated brute-force protection | Deploy Fail2Ban with 5-attempt ban threshold | SysOps | 2025-12-08 |
| 🟡 HIGH | No alert on failed auth spike | Add CloudWatch metric alarm for `>5 failed SSH/min` | DevSecOps | 2025-12-15 |
| 🟡 HIGH | Manual containment too slow | Integrate GuardDuty → EventBridge → Lambda auto-block | DevSecOps | 2025-12-30 |
| 🟢 MEDIUM | No file integrity monitoring | Deploy AWS Config with custom `passwd` integrity rule | DevSecOps | 2026-01-15 |

---

## 7. Evidence

- **Log File:** [`../forensics/auth.log`](../forensics/auth.log)
- **Forensics Report:** [`../forensics/README.md`](../forensics/README.md)
- **SOAR Script Used:** [`../automation/auto_remediate_nacl.py`](../automation/auto_remediate_nacl.py)

---

*Report prepared in accordance with NIST SP 800-61 Rev.2 — Computer Security Incident Handling Guide.*
