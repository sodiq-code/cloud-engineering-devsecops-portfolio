# 🔍 Project A (Full Stack): Security Monitoring + Hardened Infrastructure

<div align="center">

![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![CloudTrail](https://img.shields.io/badge/CloudTrail-Enabled-brightgreen?style=for-the-badge)
![GuardDuty](https://img.shields.io/badge/GuardDuty-Active-blue?style=for-the-badge)
![KMS](https://img.shields.io/badge/KMS_CMK-Encrypted-orange?style=for-the-badge)

**CloudTrail + GuardDuty + KMS + VPC + EC2 | Complete 4-Module Security Stack**

</div>

---

## 🎯 Project Mission

Extend the week5 infrastructure with a **full security monitoring layer** — adding CloudTrail for API audit logging and GuardDuty for ML-powered threat detection, demonstrating the complete security stack required for production cloud environments.

---

## 1. What's New in Week 6

| Component | Added | Purpose |
| :--- | :--- | :--- |
| **CloudTrail** | ✅ | Records every AWS API call for audit and forensic investigation |
| **GuardDuty** | ✅ | ML-powered threat detection on VPC flow logs, DNS, CloudTrail |
| **KMS CMK** | ✅ | Customer-managed encryption for CloudTrail logs |
| **S3 Log Bucket** | ✅ | Secure, versioned, TLS-only log archive |
| **Lifecycle Policy** | ✅ | Auto-archives logs to GLACIER (80% cost reduction after 90 days) |

---

## 2. Module Composition

```
week6-deploy/main.tf
├── module "logging"   → S3 bucket (KMS, versioning, TLS-only)
│                          Output: bucket_name, bucket_arn
├── module "security"  → CloudTrail + GuardDuty
│                          Input: log_bucket_name from logging module
├── module "vpc"       → Multi-AZ VPC (public + private + NAT)
│                          Output: vpc_id, subnet IDs
├── module "iam"       → EC2 role (S3 read-only to log bucket)
│                          Input: target_bucket_arn from logging module
└── aws_instance "web" → Hardened EC2 (IMDSv2, encrypted EBS, no public IP)
```

---

## 3. Security Event Flow

```
EC2 Instance makes API call (e.g., s3:GetObject)
         │
         ▼
CloudTrail records the API call
         │
         ▼
Log file written to S3 (KMS encrypted, TLS only)
         │
         ▼
GuardDuty analyses the log pattern
         │
         ├── Normal behaviour → No action
         └── Suspicious pattern → Finding created (severity: LOW/MED/HIGH/CRITICAL)
                                       │
                                       ▼
                              [EventBridge] → [Lambda] → [NACL Block]
                              (see automation/ module for SOAR integration)
```

---

## 4. Deployment

```bash
cd week6-deploy

# Start LocalStack Pro
docker-compose -f ../week3-s3-localstack/localstack-docker-compose.yml up -d

terraform init
terraform apply -auto-approve
terraform output
```

---

## 5. Outputs

```
vpc_id               = "vpc-abc123"
instance_id          = "i-abc123"
security_group_id    = "sg-abc123"
log_bucket_name      = "local-security-logs-12345"
iam_instance_profile = "local-ec2-profile"
```

---

**Author:** Jimoh Sodiq Bolaji  
**Progression:** [week5-local-deploy](../week5-local-deploy) → **week6-deploy** → [week8-ha-deploy](../week8-ha-deploy) (HA + WAF + ALB)
