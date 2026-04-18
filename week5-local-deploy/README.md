# 🏗️ Project A: Secure Local Infrastructure Deployment (IaC Foundations)

<div align="center">

![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![AWS VPC](https://img.shields.io/badge/AWS_VPC-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![EC2](https://img.shields.io/badge/EC2-Hardened-brightgreen?style=for-the-badge)
![LocalStack](https://img.shields.io/badge/LocalStack-Dev-blue?style=for-the-badge)

**VPC + IAM + EC2 | IMDSv2 | Encrypted EBS | Least Privilege | Zero Cloud Cost**

</div>

---

## 🎯 Project Mission

Deploy a fully hardened, modular web server infrastructure using Terraform — demonstrating the four-layer composition pattern that scales from local development to production: **Networking → Identity → Compute → Security**.

---

## 1. Infrastructure Layers

```
┌─────────────────────────────────────────────────────┐
│  Layer 4: Compute (EC2 Web Server)                  │
│  ├── IMDSv2 enforced (http_tokens = required)       │
│  ├── Encrypted gp3 EBS root volume                  │
│  ├── No public IP assignment                        │
│  └── Security Group: HTTP in / VPC-only egress      │
├─────────────────────────────────────────────────────┤
│  Layer 3: Identity (IAM Module)                     │
│  └── EC2 instance profile (least-privilege S3 role) │
├─────────────────────────────────────────────────────┤
│  Layer 2: Security (Firewall Rules)                 │
│  ├── Inbound: HTTP (port 80) from internet          │
│  └── Egress: VPC CIDR only (no internet exfiltration)│
├─────────────────────────────────────────────────────┤
│  Layer 1: Networking (VPC Module)                   │
│  ├── VPC 10.0.0.0/16                                │
│  ├── Public Subnet A (AZ-a) + Subnet B (AZ-b)      │
│  ├── Private Subnet A (AZ-a) + Subnet B (AZ-b)     │
│  ├── Internet Gateway                               │
│  └── NAT Gateway (private subnet egress)           │
└─────────────────────────────────────────────────────┘
```

---

## 2. Security Controls

| Control | Implementation | Threat Mitigated |
| :--- | :--- | :--- |
| **IMDSv2** | `http_tokens = "required"`, hop_limit=1 | SSRF credential theft via metadata endpoint |
| **EBS Encryption** | `encrypted = true`, `volume_type = "gp3"` | Data-at-rest exposure |
| **Egress restriction** | `cidr_blocks = ["10.0.0.0/16"]` | Data exfiltration to internet |
| **IAM least privilege** | S3 read-only to specific bucket ARN | Credential abuse / lateral movement |
| **No public IP** | `map_public_ip_on_launch = false` | Direct internet exposure of EC2 |

---

## 3. Deployment

```bash
cd week5-local-deploy

# Start LocalStack
docker-compose -f ../week3-s3-localstack/localstack-docker-compose.yml up -d

# Deploy
terraform init
terraform apply -auto-approve

# View outputs
terraform output
```

---

## 4. Outputs

```
vpc_id                = "vpc-abc123"
instance_id           = "i-abc123"
security_group_id     = "sg-abc123"
iam_instance_profile  = "local-ec2-profile"
```

---

**Author:** Jimoh Sodiq Bolaji  
**Next Project:** [week6-deploy](../week6-deploy) — adds CloudTrail + GuardDuty security monitoring layer
