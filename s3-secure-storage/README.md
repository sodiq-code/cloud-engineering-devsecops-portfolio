# 🛡️ Secure-by-Design Cloud Storage (IaC Foundations)

<div align="center">

![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![AWS S3](https://img.shields.io/badge/AWS_S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white)
![KMS](https://img.shields.io/badge/KMS_CMK-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![Security](https://img.shields.io/badge/Trivy-0-critical?style=for-the-badge&logo=aqua&color=brightgreen&label=Findings)

**Infrastructure as Code | KMS Customer Managed Key | TLS-Only | Zero Public Access**

</div>

---

## 🎯 Project Mission

Demonstrate the transition from manual cloud provisioning to **Infrastructure as Code** — provisioning a production-grade, "Secure-by-Design" S3 storage layer that passes automated security scanning (Trivy) out of the box.

> Most IaC tutorials deploy S3 buckets that are publicly accessible, unencrypted, and have no access controls. This project does the opposite: security is the default, not an afterthought.

---

## 1. Security Architecture

```
S3 Bucket
├── KMS CMK Encryption (aws:kms)         ← Data encrypted with Customer Managed Key
│     └── Annual automatic key rotation    ← Compliance: FIPS 140-2, SOC2
├── Public Access Block (4-setting)       ← Network-level hard block
│     ├── block_public_acls = true
│     ├── block_public_policy = true
│     ├── ignore_public_acls = true
│     └── restrict_public_buckets = true
├── BucketOwnerEnforced (no ACLs)         ← Post-2022 AWS recommendation
├── Versioning Enabled                    ← Tamper evidence, WORM-like immutability
├── TLS-Only Bucket Policy                ← Deny any HTTP (non-HTTPS) request
└── Lifecycle Rules                       ← Cost-optimised log retention
      ├── 0-30 days:   STANDARD (hot storage)
      ├── 30-90 days:  STANDARD_IA (~40% cheaper)
      ├── 90-365 days: GLACIER (~80% cheaper)
      └── After 365:   Expire (cleanup)
```

---

## 2. Resources Provisioned

| Resource | Terraform Type | Security Purpose |
| :--- | :--- | :--- |
| S3 Bucket | `aws_s3_bucket` | Primary storage |
| KMS CMK | `aws_kms_key` | Customer-controlled encryption key |
| KMS Alias | `aws_kms_alias` | Human-readable key reference |
| Ownership Controls | `aws_s3_bucket_ownership_controls` | Disables legacy ACL system |
| Public Access Block | `aws_s3_bucket_public_access_block` | Hard network block (4 settings) |
| Versioning | `aws_s3_bucket_versioning` | Tamper evidence |
| Encryption Config | `aws_s3_bucket_server_side_encryption_configuration` | KMS SSE with bucket key |
| Lifecycle Config | `aws_s3_bucket_lifecycle_configuration` | Cost-optimised retention |
| Bucket Policy | `aws_s3_bucket_policy` | TLS-only enforcement |

---

## 3. Security Controls Explained

### Why a Customer Managed Key (CMK)?

AWS offers two S3 encryption options:
- **SSE-S3 (AWS managed):** AWS controls the key — your data is encrypted, but AWS can theoretically decrypt it
- **SSE-KMS with CMK (our choice):** *You* control the key. You can audit every decryption via CloudTrail, rotate the key, and revoke access by disabling the key

This gives you cryptographic control over your data — a requirement for PCI-DSS, HIPAA, and GDPR compliance.

### Why Disable ACLs?

In April 2023, AWS updated S3 to recommend disabling ACLs (`BucketOwnerEnforced`) in favour of bucket policies. ACLs are a legacy access control mechanism with complex, error-prone permission inheritance. Disabling them eliminates an entire class of misconfiguration vulnerabilities.

### Why a TLS-Only Policy?

Without this policy, AWS S3 accepts requests over HTTP (unencrypted). An attacker performing a MITM attack can intercept data in transit. The `aws:SecureTransport: false` deny condition rejects any API call not made over TLS.

---

## 4. Outputs

After `terraform apply`, the following values are exported:

```
bucket_name = "afsod-week3-bucket-12345"
bucket_arn  = "arn:aws:s3:::afsod-week3-bucket-12345"
kms_key_arn = "arn:aws:kms:us-east-1:000000000000:key/..."
kms_key_id  = "abc123-..."
```

---

## 5. Deployment

```bash
cd s3-secure-storage

# Start LocalStack
docker-compose -f localstack-docker-compose.yml up -d

# Deploy
terraform init
terraform plan
terraform apply -auto-approve

# Verify bucket exists
aws --endpoint-url=http://localhost:4566 s3 ls
```

---

## 6. Evidence

![Terraform Plan](../docs/week3/screenshots/plan.png)
*Terraform plan showing all 9 security resources to be created*

![Terraform Apply](../docs/week3/screenshots/apply.png)
*Terraform apply completing successfully with all security controls active*

---

**Author:** Jimoh Sodiq Bolaji  
**Standard:** AWS Well-Architected Framework (Security Pillar) | CIS AWS Foundations Benchmark  
**Decision Records:** [ADR-001](../docs/adr/ADR-001-localstack-over-real-aws.md)
