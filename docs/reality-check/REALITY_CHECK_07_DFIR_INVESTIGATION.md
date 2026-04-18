# Reality Check: DFIR Investigation (`forensics`)

**Project:** `forensics/` + `incident-reports/`  
**Stack:** Bash, Linux forensics tools (`grep`, `awk`, `ss`, `find`), NACL remediation, NIST SP 800-61  
**Summary:** Simulating a real SSH brute-force breach and subsequent DFIR investigation exposed the operational gap between manual and automated incident response, the challenge of detecting low-noise persistence techniques, and the importance of having a structured IR process before an incident occurs.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| 46-minute gap between detection and containment — manual IP blocking too slow | P1 | 46 min real-time window | ✅ Resolved — automated via SOAR |
| Backdoor account (`support_service` UID=0) was not detected by routine monitoring | P1 | Undetected until log analysis | ✅ Detected via `awk -F: '($3==0)'` on `/etc/passwd` |
| Non-standard SSH port (`5566`) not monitored — attacker tooling indicator missed | P2 | Detected retrospectively | ✅ Added to IoC list |
| No file integrity baseline — could not prove when `/etc/passwd` was modified | P2 | Forensic gap | ✅ Documented as lesson learned |

---

## Problem 1 — 46-Minute Containment Gap: Manual Response Is Too Slow

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Operational |
| **Time Lost** | 46-minute attacker dwell time after initial detection |
| **Discovered** | During timeline reconstruction in incident-001.md |

**Symptom:**

The attack timeline from `auth.log` showed:

```
08:45:00  Analyst detected anomaly via log review
08:46:03  auto_remediate_nacl.py executed — 192.168.1.50 blocked in NACL
```

But the actual breach had occurred at:

```
08:20:01  Successful login as admin from 192.168.1.50
08:25:30  Backdoor account support_service (UID=0) created
08:30:15  /var/www/html compressed to /tmp/data_dump.tar.gz
```

The attacker completed all their objectives — persistence, privilege escalation, and data staging — **25 minutes before detection**. And from detection to containment was another 1 minute. Total dwell time: 26 minutes of active post-breach activity before the IP was blocked.

**Root Cause:**

The detection mechanism was **manual log review** — a human analyst periodically checking `auth.log`. There was no automated alerting for:
- Multiple failed SSH attempts in a 15-minute window (the brute-force phase)
- A successful SSH login from a new IP address (the breach event)
- A new UID=0 account being created (the persistence event)

Any of these events could have triggered an alert within seconds. Instead, the detection latency was measured in tens of minutes — the time between analyst log review cycles.

**Fix Applied:**

The SOAR automation project (`automation/auto_remediate_nacl.py`) was built specifically to address this gap. The full automated response chain is:

```
GuardDuty Finding (SSH brute force, high severity)
    │  ~15 minutes (GuardDuty finding publication interval)
    ▼
EventBridge Rule matches severity >= HIGH
    │  milliseconds
    ▼
Lambda invokes auto_remediate_nacl.py --ip [malicious_ip]
    │  < 500ms (AWS SDK call to create NACL rule)
    ▼
NACL DENY rule active — IP blocked at subnet level
```

Total automated time-to-containment: ~15 minutes (dominated by GuardDuty's finding publication interval). Manual time-to-containment: 46 minutes in this simulation.

The corrective actions documented in incident-001.md also include:

```bash
# CloudWatch alarm to trigger on failed SSH threshold:
aws cloudwatch put-metric-alarm \
  --alarm-name "SSHBruteForce" \
  --metric-name "FailedSSHAttempts" \
  --threshold 5 \
  --evaluation-periods 1 \
  --period 60 \
  --comparison-operator GreaterThanThreshold
```

**Business Impact:**

Every minute of attacker dwell time after a breach is a minute during which more data is exfiltrated, more persistence mechanisms are installed, and more lateral movement occurs. Industry data (IBM Cost of a Data Breach 2024) puts average breach cost at $4.88M. Studies consistently show that breaches contained in under 30 minutes cost significantly less than those contained in hours. The gap between manual and automated containment — 46 minutes vs 15 minutes — directly correlates to breach cost and regulatory exposure.

---

## Problem 2 — Backdoor Account Was Invisible to Routine Monitoring

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Detection Gap |
| **Time Lost** | Account existed undetected for ~25 minutes |
| **Discovered** | Only through forensic log analysis during incident response |

**Symptom:**

At 08:25:30, the attacker created a backdoor account:

```bash
# Observed in auth.log:
useradd support_service
passwd support_service
# support_service was assigned UID=0 — root-level privileges
```

The account name `support_service` was chosen to look like a legitimate system service account. No monitoring alert fired. The account was only discovered when running forensic queries against `auth.log` during the incident response.

**Root Cause:**

Three monitoring gaps allowed this to go undetected:

1. **No alerting on `useradd` events** — CloudWatch could trigger on log lines containing "useradd" in `/var/log/auth.log`, but this metric filter was not configured.
2. **No regular `/etc/passwd` auditing** — a cron job that checks for accounts with UID=0 beyond the root account would have flagged this within minutes. No such check existed.
3. **Account name camouflage** — `support_service` follows the pattern of legitimate system accounts. Without a baseline of expected accounts, a new account blends in.

The forensic detection command used during incident response:

```bash
# Detect all UID=0 accounts (should only be "root"):
awk -F: '($3 == 0) {print}' /etc/passwd
# Output: root:x:0:0:root:/root:/bin/bash
#         support_service:x:0:0::/home/support_service:/bin/bash  ← attacker backdoor
```

**Fix Applied:**

Two compensating controls were added as lessons learned:

```bash
# 1. File integrity monitoring via AWS Config custom rule:
# Config rule that compares /etc/passwd hash against a baseline every 24 hours
# and triggers a finding if the hash changes

# 2. CloudWatch Logs metric filter for account creation events:
aws logs put-metric-filter \
  --log-group-name "/var/log/auth" \
  --filter-name "NewAccountCreated" \
  --filter-pattern "[date, time, host, service, action=useradd, ...]" \
  --metric-transformations \
    metricName=UserAccountCreations,metricNamespace=SecurityEvents,metricValue=1
```

**Business Impact:**

A UID=0 account is a root-equivalent backdoor. Even after the attacker's initial access vector (the `admin` SSH password) is remediated, the `support_service` account persists as a permanent root backdoor. If the incident response had not discovered it, the attacker could return at any time using `support_service` credentials — and all the remediation work (locking `admin`, rotating keys, disabling password auth) would be ineffective. This is MITRE ATT&CK T1136 — the most common persistence technique for compromised Linux servers.

---

## Problem 3 — Non-Standard SSH Port Detected Retrospectively

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Investigation Gap |
| **Time Lost** | Discovered retrospectively, not during active containment |
| **Discovered** | Timeline analysis of `auth.log` revealed SSH session on port `5566` |

**Symptom:**

The incident report noted:

> *SSH Port Used: 5566 (non-standard — may indicate attacker tooling) — Confidence: MEDIUM*

The attacker's SSH connection was on port 5566, not the standard port 22. This detail was only noticed during the post-incident documentation phase — not during containment.

**Root Cause:**

Network monitoring (VPC Flow Logs, if enabled) would have flagged a successful connection on a non-standard port immediately. In this simulation:
- VPC Flow Logs were not enabled on the subnet
- The NACL did not restrict inbound SSH to port 22 only (it was open to all ports from any IP)
- The alerting configuration did not include port-based anomaly detection

Non-standard port usage is a common attacker technique: some attackers configure their SSH clients to connect on unusual ports to evade IDS/IPS systems that only inspect standard ports.

**Fix Applied:**

Three controls were identified as lessons learned:

1. Enable VPC Flow Logs with CloudWatch Logs delivery for all production subnets
2. Add a security group rule that explicitly restricts SSH to port 22 (or a known non-standard management port consistently applied across all servers)
3. Add a GuardDuty finding type for unusual port usage as a supplementary detection signal

**Business Impact:**

Non-standard port usage is an IoC — Indicator of Compromise. In threat hunting, it is a pivot point: if the attacker used custom tooling on port 5566 in this incident, the same tooling may appear on other hosts in the environment. Without VPC Flow Log visibility, this lateral movement is invisible.

---

## Problem 4 — No File Integrity Baseline: Cannot Prove When `/etc/passwd` Was Modified

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Forensic Quality |
| **Time Lost** | Forensic gap — could not reconstruct precise modification timeline |
| **Discovered** | Attempting to establish chain of custody during incident documentation |

**Symptom:**

During incident documentation, it was not possible to confirm the precise timestamp when `/etc/passwd` was modified to add the `support_service` account. The `auth.log` showed the `useradd` command at 08:25:30, but:

```bash
# File system timestamp — not reliable (can be changed by attacker):
stat /etc/passwd
# Modify: 2025-12-01 08:25:30 UTC   ← attacker could have reset this with `touch -t`

# MD5 hash — baseline was not taken before the incident:
md5sum /etc/passwd
# No baseline to compare against — cannot prove tampering
```

**Root Cause:**

Without a pre-incident baseline hash of `/etc/passwd` (and other critical system files), it is impossible to prove in court or in an audit that the file was modified during the incident rather than before. This matters for:
- Legal proceedings (chain of custody requirements)
- Insurance claims (proof of breach event)
- Regulatory reporting (precise breach timeline required)

**Fix Applied:**

File integrity monitoring (FIM) was added to the remediation plan:

```bash
# AWS Config custom rule — takes daily hash of /etc/passwd and alerts on change
# Tripwire or AIDE for in-host FIM
# AWS Systems Manager — compare parameter store baseline against live file

# During incident, document hash at the moment of discovery:
md5sum /etc/passwd >> /tmp/evidence/passwd-hash-at-incident-discovery.txt
sha256sum /etc/passwd >> /tmp/evidence/passwd-sha256-at-incident-discovery.txt
```

**Business Impact:**

In regulatory breach notifications (GDPR 72-hour notification, PCI-DSS incident reporting), organisations are required to state when the breach occurred and what data was exposed. Without file integrity monitoring, the timeline is reconstructed from logs — which the attacker may have partially modified. A missing baseline makes it impossible to prove definitively when the attacker first modified the system, weakening both the legal case and the regulatory report.

---

## What These Failures Prove

The DFIR investigation demonstrated that forensic investigation is only possible when detection and evidence collection infrastructure exist before the incident:

1. **Detection speed is a function of automation** — a 46-minute manual containment window vs a potential 15-minute automated window is the difference between "contained" and "breach confirmed."
2. **Persistence goes unnoticed without baselining** — UID=0 backdoor accounts are invisible without either continuous monitoring or regular `/etc/passwd` audits against a known-good baseline.
3. **Forensic quality requires preparation** — MD5 baselines, VPC Flow Logs, and file integrity monitoring cannot be retroactively applied during an incident. They must exist before the incident to be useful.

The SOAR automation project was built directly as a response to lesson learned #1. The governance project (AWS Config rules) addresses lessons learned #2 and #4.
