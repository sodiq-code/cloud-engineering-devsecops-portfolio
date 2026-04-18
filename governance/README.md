# 🏛️ Enterprise Multi-Account Governance & Compliance Automation

<div align="center">

![AWS Organizations](https://img.shields.io/badge/AWS_Organizations-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![CIS](https://img.shields.io/badge/CIS_Benchmark-L1_Compliant-brightgreen?style=for-the-badge)
![SCPs](https://img.shields.io/badge/SCPs-3_Active-blue?style=for-the-badge)

**AWS Organizations | 3 SCPs at Root Level | CIS L1 | Region Lock | CloudTrail Protection**

</div>

---

## 🎯 Project Mission

Implement **Immutable Governance at Scale** — enforcing compliance baselines across an entire AWS organisation using Service Control Policies (SCPs), eliminating Shadow IT, and achieving regulatory compliance automatically without relying on human discipline.

> "A security control that depends on humans remembering to do the right thing will eventually fail. SCPs remove the human from the equation." 

---

## 1. Governance Architecture

```
AWS Organisation (Root)
│
│  ← SCPs applied HERE at Root = no OU or account can bypass
│  ├── SCP-A: Deny-CloudTrail-Tampering  (Log integrity)
│  ├── SCP-B: Restrict-Regions-US        (Data sovereignty)  
│  └── SCP-C: Deny-Root-Account-Actions  (CIS Benchmark L1)
│
├── OU: Security-Prod
│     └── [Security accounts — log archive, audit]
│
└── OU: Workloads-Prod
      └── [Application accounts — dev, staging, prod]
```

**Key Design Decision:** SCPs are attached at the **Organisation Root**, not individual OUs. This is the most secure pattern — even if a new OU is created or an account is moved, the guardrails follow automatically. The previous implementation (OU-level only) allowed the Security OU to bypass its own controls.

---

## 2. Service Control Policies

### SCP-A: CloudTrail Integrity Protection
**File:** [`policies/scp_deny_cloudtrail_stop.json`](policies/scp_deny_cloudtrail_stop.json)

Blocks 5 critical CloudTrail manipulation actions:

| Blocked Action | Why It Matters |
| :--- | :--- |
| `cloudtrail:StopLogging` | An attacker stops logging to hide API activity |
| `cloudtrail:DeleteTrail` | Permanent destruction of audit trail |
| `cloudtrail:UpdateTrail` | Reduce logging scope to miss specific events |
| `cloudtrail:CreateTrail` | Create a "shadow trail" with different settings |
| `cloudtrail:PutEventSelectors` | Filter out events (e.g., S3 data events) to create blind spots |

Even an account root user cannot perform these actions. This is the "Immutable Audit" requirement for SOC2, PCI-DSS, and ISO 27001 compliance.

### SCP-B: Data Sovereignty — Region Lock
**File:** [`policies/scp_region_restriction.json`](policies/scp_region_restriction.json)

Denies all AWS API calls to regions outside `us-east-1` and `us-east-2`. Uses the `NotAction` pattern to exclude globally-scoped services (IAM, Route53, CloudFront, etc.) that have no concept of region.

**Business Impact:**
- ✅ Prevents accidental/malicious deployment in non-compliant regions (GDPR residency)
- ✅ Eliminates "Shadow IT" in unapproved regions
- ✅ Reduces attack surface by 90% (only 2 of 30+ regions are active)

### SCP-C: Root Account Protection (CIS Benchmark Level 1)
**File:** [`policies/scp_deny_root_actions.json`](policies/scp_deny_root_actions.json)

Denies all API actions performed by root account credentials. Root accounts should only be used for account recovery — never for day-to-day operations. This SCP enforces that principle automatically.

**CIS Control:** CIS AWS Foundations Benchmark v1.4 — Control 1.7 (Eliminate use of the root account)

---

## 3. Compliance Mapping

| Requirement | Framework | SCP Enforcing It |
| :--- | :--- | :--- |
| Tamper-proof audit logs | SOC2 CC7.2, PCI-DSS 10.5 | SCP-A |
| Data residency / no unauthorised regions | GDPR Art.44, ISO 27001 A.17 | SCP-B |
| No root account usage | CIS AWS L1 1.7, NIST AC-6 | SCP-C |

---

## 4. Deployment

```bash
cd governance

# Start LocalStack Pro (organizations service required)
docker-compose -f ../week3-s3-localstack/localstack-docker-compose.yml up -d

# Deploy governance stack
terraform init
terraform plan
terraform apply -auto-approve
```

### Verify Policy Attachments
```bash
aws --endpoint-url=http://localhost:4566 organizations list-policies \
    --filter SERVICE_CONTROL_POLICY

aws --endpoint-url=http://localhost:4566 organizations list-targets-for-policy \
    --policy-id <policy-id>
```

---

## 5. What Makes This Enterprise-Grade

1. **Root-level attachment** — controls are inescapable; no OU is exempt
2. **`NotAction` pattern in region SCP** — correctly handles global services (IAM, Route53) rather than naive deny-all which breaks account management
3. **5 CloudTrail actions covered** — not just StopLogging, but all tampering vectors
4. **Terraform-managed** — policies are version-controlled, reviewable, and auditable via `git blame`

---

![Organisation Structure](../docs/week11/screenshots/org-success.png)
*AWS Organizations structure deployed via Terraform to LocalStack*

---

**Author:** Jimoh Sodiq Bolaji  
**Standards:** CIS AWS Foundations Benchmark v1.4 | SOC2 | PCI-DSS | ISO 27001
