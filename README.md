<div align="center">

# ☁️ CloudDefense Engineering Portfolio
### Production-Grade Cloud Security, SRE & Infrastructure as Code

**by Jimoh Sodiq Bolaji — Cloud & DevSecOps Engineer**

---

[![CI/CD](https://github.com/sodiq-code/cloud-engineering-devsecops-portfolio/actions/workflows/trivy-scan.yml/badge.svg)](https://github.com/sodiq-code/cloud-engineering-devsecops-portfolio/actions/workflows/trivy-scan.yml)
![Kubernetes](https://img.shields.io/badge/Kubernetes-11--Service%20Cluster-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-Modular%20IaC-7B42BC?style=flat-square&logo=terraform&logoColor=white)
![Security](https://img.shields.io/badge/Trivy-0%20Critical%20Findings-brightgreen?style=flat-square&logo=aqua)
![Tests](https://img.shields.io/badge/Tests-pytest%20%2B%20moto-yellow?style=flat-square&logo=pytest)
![Monitoring](https://img.shields.io/badge/SRE-Prometheus%20%26%20Grafana-E6522C?style=flat-square&logo=prometheus)
![CIS](https://img.shields.io/badge/Governance-CIS%20L1%20%7C%20SOC2%20%7C%20PCI--DSS-blue?style=flat-square)

</div>

---

## 🎯 About This Portfolio

This is my production engineering portfolio. Every project solves a real infrastructure or security problem using production-grade patterns, documented architectural decisions, and automated security validation — no tutorials, no toy apps.

---

## 🗺️ Portfolio Map

```
CloudDefense Engineering Portfolio
│
├── 🚀  KubeScale Platform           k8s-ecommerce-project/
├── 🔄  HA AWS Architecture          ha-aws-architecture/
├── 🛡️  S3 Secure Storage            s3-secure-storage/
├── 🏛️  Enterprise Governance         governance/
├── ⚡  SOAR Threat Automation        automation/
├── 🔬  DFIR Investigation            forensics/
├── 🏗️  Secure Infrastructure (IaC)   aws-foundation/
├── 🔍  Full Security Stack           security-stack/
├── 🧩  Reusable Terraform Modules    modules/
├── 🔐  CI/CD Security Pipeline       .github/workflows/
└── 📚  Architecture Decision Records docs/adr/
```

---

## 📂 Project Index

---

### 1. 🚀 KubeScale — Production Microservices & SRE Observability Platform
**[→ View Project](./k8s-ecommerce-project)**

The flagship project. An 11-service polyglot e-commerce platform running on Kubernetes with full-stack SRE observability, zero-trust security, and zero cloud cost.

| Achievement | Detail |
| :--- | :--- |
| **Orchestration** | 11 microservices (Go, C#, Node.js, Python) on Kubernetes with Deployments + ReplicaSets |
| **Traffic Engineering** | Nginx Ingress Controller with Layer 7 routing, rate limiting, and security headers |
| **SRE Observability** | Prometheus + Grafana monitoring Four Golden Signals (Latency, Traffic, Errors, Saturation) |
| **Auto-Scaling** | HPA scales pods 2→10 on CPU >70% or Memory >80%, with scale-in stabilisation |
| **Zero-Trust Security** | NetworkPolicy default-deny-all + explicit allow rules + container hardening |
| **Container Security** | 0 Trivy findings: non-root, read-only filesystem, all capabilities dropped, seccompProfile |
| **FinOps** | LocalStack Pro emulation — **$0 development spend** vs ~$500/month on real EKS |

---

### 2. �� High-Availability AWS Architecture
**[→ View Project](./ha-aws-architecture)**

Transforms a single server into a self-healing, multi-AZ fleet protected by WAF and monitored by GuardDuty — demonstrating the AWS Well-Architected Framework in code.

| Achievement | Detail |
| :--- | :--- |
| **Multi-AZ HA** | ALB spans 2 AZs (`us-east-2a/b`) — zero downtime if one AZ fails |
| **WAF Protection** | 2 rule sets: Common (SQLi, XSS, LFI) + Known Bad Inputs (Log4Shell) |
| **TLS Enforcement** | HTTP → HTTPS permanent 301 redirect at ALB listener level |
| **Auto-Scaling** | CPU-based and ALB-request-count target tracking (scale 2→6 instances) |
| **IMDSv2 Enforced** | Hop limit=1; session tokens required — eliminates SSRF attack vector |
| **EBS Encryption** | gp3 volumes encrypted at rest on all instances |
| **Audit Trail** | CloudTrail (multi-region, KMS, log validation) + GuardDuty (15-min findings) |
| **ALB Access Logs** | Request-level logs shipped to KMS-encrypted S3 for forensic analysis |

---

### 3. 🛡️ Automated Security Compliance Pipeline (Shift-Left)
**[→ View Workflow](./.github/workflows/trivy-scan.yml)**

A 4-job GitHub Actions pipeline that enforces security on every pull request — blocking merges if HIGH/CRITICAL findings are detected.

| Job | Tool | What It Catches |
| :--- | :--- | :--- |
| **IaC Scan** | Trivy (table + SARIF) | Terraform/Kubernetes misconfigurations |
| **Filesystem Scan** | Trivy (SARIF) | Vulnerable packages, Dockerfile issues |
| **Secret Scan** | TruffleHog v3 | API keys, tokens, passwords in commit history |
| **Policy Scan** | Checkov | CIS Benchmark violations across all frameworks |

All findings are posted to the **GitHub Security tab** via SARIF upload — giving a centralised view of all vulnerabilities across the repository.

---

### 4. 🏛️ Enterprise Governance & Compliance (AWS Organizations + SCPs)
**[→ View Project](./governance)**

Enforces immutable security baselines across an entire AWS organisation using 3 Service Control Policies attached at the Root — no account or OU can bypass them.

| SCP | Protects Against | Compliance |
| :--- | :--- | :--- |
| **Deny-CloudTrail-Tampering** | Audit log destruction (5 actions blocked) | SOC2, PCI-DSS 10.5 |
| **Restrict-Regions-US** | Unauthorised region deployment | GDPR data residency |
| **Deny-Root-Account-Actions** | Root credential misuse | CIS AWS Benchmark L1 1.7 |

---

### 5. ⚡ Real-Time SOAR Threat Remediation
**[→ View Automation](./automation) | [→ View Incident Report](./incident-reports/incident-001.md)**

A production-ready Python (Boto3) tool that blocks malicious IPs in AWS Network ACLs in milliseconds — designed for Lambda invocation triggered by GuardDuty findings via EventBridge.

| Feature | Implementation |
| :--- | :--- |
| **CLI interface** | `argparse` — `--ip`, `--dry-run`, `--cleanup`, `--rule-number` |
| **Structured logging** | `logging` module (CloudWatch-compatible format) |
| **Error handling** | Custom exceptions — no `sys.exit()` inside library functions |
| **Dry-run mode** | Preview actions without any API changes |
| **Lifecycle management** | `--cleanup` removes the DENY rule when threat is resolved |
| **Unit tests** | pytest + moto — 11 test cases, 100% without real AWS |

---

### 6. 🔬 Digital Forensics & Incident Response (DFIR)
**[→ View Investigation](./forensics)**

A simulated DFIR investigation mapped to MITRE ATT&CK v15, following NIST SP 800-61 incident response lifecycle.

| Phase | MITRE Technique | Evidence |
| :--- | :--- | :--- |
| Initial Access | T1110.001 — Brute Force | 15 failed SSH attempts |
| Breach | T1078 — Valid Accounts | Successful `admin` login |
| Persistence | T1136.001 — Create Local Account | `support_service` UID=0 |
| Exfiltration | T1560.001 — Archive via Utility | `data_dump.tar.gz` |

---

### 7. 🧩 Reusable Terraform Module Library
**[→ View Modules](./modules)**

4 production-grade Terraform modules used across all projects — demonstrating the DRY principle and module composition pattern.

| Module | Resources | Key Features |
| :--- | :--- | :--- |
| `vpc` | VPC, 2×Public+2×Private subnets, IGW, NAT GW | Multi-AZ, CIDR validation |
| `logging` | S3, KMS CMK, versioning, lifecycle, TLS policy | Least-privilege KMS key policy |
| `security` | CloudTrail, GuardDuty, KMS | Multi-region trail, log validation |
| `iam` | IAM Role, Policy, Instance Profile | Least-privilege S3 access |

---

### 8. 📚 Architecture Decision Records
**[→ View ADRs](./docs/adr)**

Formal documentation of major architectural decisions — demonstrating senior-level engineering thinking.

| ADR | Decision |
| :--- | :--- |
| [ADR-001](./docs/adr/ADR-001-localstack-over-real-aws.md) | LocalStack for zero-cost development |
| [ADR-002](./docs/adr/ADR-002-terraform-remote-state.md) | Terraform remote state with S3 + DynamoDB locking |
| [ADR-003](./docs/adr/ADR-003-container-security-hardening.md) | Container security hardening baseline (0 Trivy findings) |

---

## 🛠️ Technical Competency Matrix

| Domain | Technologies & Skills |
| :--- | :--- |
| **Cloud Native (K8s)** | Kubernetes, Helm, Nginx Ingress, Deployments, HPA, NetworkPolicy, RBAC, Namespaces |
| **SRE & Observability** | Prometheus, Grafana, Four Golden Signals, OOMKill debugging, resource rightsizing |
| **Infrastructure as Code** | Terraform (modules, state, provider pinning, validation blocks, lifecycle) |
| **Cloud Architecture** | AWS VPC, EKS, ALB, ASG, WAFv2, CloudTrail, GuardDuty, Organizations, KMS, S3 |
| **Security Engineering** | SCPs, NACLs, IMDSv2, KMS CMKs, TLS enforcement, Zero-Trust networking |
| **DevSecOps / CI/CD** | GitHub Actions, Trivy, Checkov, TruffleHog, SARIF, Shift-Left security |
| **Security Automation** | Python (Boto3), argparse, moto testing, EventBridge/Lambda SOAR pattern |
| **Incident Response** | MITRE ATT&CK mapping, NIST SP 800-61, DFIR tooling (grep, awk, ss, find) |
| **FinOps** | LocalStack Pro, cost avoidance strategy, hybrid dev/prod architecture |

---

## 🔑 Key Engineering Problems Solved

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| **$500/mo dev cost** | Live AWS required for realistic testing | LocalStack Pro emulation — $0 dev spend |
| **OOMKill in K8s pods** | No resource limits defined | Prometheus monitoring + rightsized limits/requests |
| **Microservices networking** | Basic port-forwarding | Nginx Ingress with Layer 7 routing + rate limiting |
| **Shadow IT / region sprawl** | No guardrails on multi-account org | AWS Organizations SCPs at Root level |
| **SSRF via IMDS** | IMDSv1 default on EC2 | `http_tokens = required`, hop limit=1 everywhere |
| **CloudTrail tampering** | Admin can stop logging | SCP denying 5 CloudTrail manipulation actions |
| **Hardcoded KMS key** | Wildcard `"AWS": "*"` in key policy | Scoped to `arn:aws:iam::${account_id}:root` |
| **Single-AZ ALB** | Only 1 subnet provided | Dual-AZ VPC module, both subnets passed to ALB |
| **Manual incident response** | Human-speed IP blocking | Python SOAR tool with <500ms containment |

---

## 📁 Repository Structure

```
.
├── .github/workflows/
│   └── trivy-scan.yml          # 4-job security pipeline (Trivy, TruffleHog, Checkov)
├── k8s-ecommerce-project/      # KubeScale: 11-service K8s platform + SRE observability
│   ├── manifest/               # K8s manifests: Deployment, Service, Ingress, HPA, NetworkPolicy
│   ├── email-service/          # Custom Python microservice (Flask + gunicorn)
│   ├── finops/                 # LocalStack Pro docker-compose for zero-cost AWS emulation
│   └── microservices-demo/     # Google Online Boutique source (all 11 services)
├── ha-aws-architecture/        # HA Architecture: WAF + ALB + ASG + CloudTrail + GuardDuty
├── security-stack/             # Full security stack: VPC + IAM + CloudTrail + GuardDuty + EC2
├── aws-foundation/             # Foundation: VPC + IAM + hardened EC2
├── s3-secure-storage/          # Secure storage: S3 + KMS + TLS-only + versioning + lifecycle
├── governance/                 # Enterprise SCPs: 3 policies at org root
├── automation/                 # SOAR: Python NACL remediation + pytest test suite
├── forensics/                  # DFIR: MITRE ATT&CK mapped investigation
├── incident-reports/           # Formal IR: NIST SP 800-61 incident report
├── modules/                    # Reusable Terraform: vpc, logging, security, iam
├── docs/
│   └── adr/                    # Architecture Decision Records (ADR-001, ADR-002, ADR-003)
└── .trivyignore                # Documented exception list for lab-environment findings
```

---

## 📬 Contact

| Channel | Link |
| :--- | :--- |
| **Email** | [sodiqjimoh80@gmail.com](mailto:sodiqjimoh80@gmail.com) |
| **GitHub** | [github.com/sodiq-code](https://github.com/sodiq-code) |

---

<div align="center">

*This portfolio demonstrates production-grade engineering judgement: every architectural decision is documented, every security control is justified, and every line of infrastructure is testable.*

</div>
