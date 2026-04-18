# Reality Check: HA AWS Architecture (`ha-aws-architecture`)

**Project:** `ha-aws-architecture/`  
**Stack:** Terraform, AWS ALB, ASG, WAFv2, EC2, CloudTrail, GuardDuty, LocalStack  
**Summary:** Transforming a single-server architecture into a self-healing multi-AZ fleet exposed four real failures that would each cause production outages or security incidents: a single-AZ ALB that silently accepts deployment, an IMDSv1 SSRF vector that was the default, open egress rules flagged by policy scanners, and a missing ALB deletion protection setting.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| ALB creation failed — single-AZ VPC module did not expose the second public subnet | P1 | 3 hours | ✅ Fixed — updated VPC module + outputs |
| IMDSv1 was the default — `http_tokens = "required"` not set explicitly | P1 | Caught at review | ✅ Fixed |
| ALB and EC2 security groups had unrestricted egress (`0.0.0.0/0 -1`) | P2 | 30 min CI investigation | ✅ Fixed — restricted to necessary ports |
| ALB deletion protection not set — Checkov CKV_AWS_150 failing | P2 | 15 min | ✅ Fixed |

---

## Problem 1 — ALB Creation Failed: Single-AZ VPC Module

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Infrastructure Blocker |
| **Time Lost** | ~3 hours (including VPC module rewrite) |
| **Discovered** | `terraform apply` failed immediately on `aws_lb.main` with a subnet validation error |

**Symptom:**

```
│ Error: creating elbv2 Load Balancer (ha-load-balancer):
│ ValidationError: Load balancers require at least two subnets in two different
│ Availability Zones. The following AZs are covered: [us-east-2a].
│ Need at least one more AZ.
```

The VPC module was providing one public subnet. The ALB resource listed that single subnet. The plan succeeded (`terraform plan` showed no errors) but the actual API call to create the ALB failed.

**Root Cause:**

AWS ALBs are multi-AZ by design — they require subnets in at least two distinct Availability Zones to operate. This is not optional and cannot be waived. The original VPC module was designed for the simpler `aws-foundation` project which only needed a single public EC2 instance. That module had:

- `public_subnet_a` (AZ-a) — resource existed
- `public_subnet_b` (AZ-b) — resource existed in `main.tf` but had **no output** exposed

The `ha-aws-architecture` project consumed the VPC module and passed `module.vpc.public_subnet_id` to the ALB. Because there was no `public_subnet_b_id` output, the second subnet was not included. Terraform plan succeeded because plan only checks resource configuration syntax, not AWS service-level validation rules.

**Fix Applied:**

Two changes were required:

1. Added `public_subnet_b_id` to `modules/vpc/output.tf`:

```hcl
output "public_subnet_b_id" {
  description = "ID of second public subnet (AZ-b) — required for ALB HA"
  value       = aws_subnet.public_b.id
}
```

2. Updated `ha-aws-architecture/main.tf` to pass both subnets to the ALB:

```hcl
resource "aws_lb" "main" {
  subnets = [
    module.vpc.public_subnet_a_id,
    module.vpc.public_subnet_b_id,    # ← this was missing
  ]
}
```

**Business Impact:**

Without the second AZ, the ALB is a single-AZ resource. If `us-east-2a` has an outage (AWS has had AZ-level failures — most recently `us-east-1f` in 2023), 100% of traffic is dropped. A genuine multi-AZ architecture is the minimum requirement for any application with an SLA above 99.5%. This failure also demonstrates a critical limitation of `terraform plan`: it validates HCL syntax and state, but it cannot validate AWS service-level constraints until the API call is made.

---

## Problem 2 — IMDSv1 Enabled by Default: SSRF Credential Theft Vector

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Security |
| **Time Lost** | Caught during security review |
| **Discovered** | Security review of EC2 launch template configuration |

**Symptom:**

The launch template for EC2 instances in the Auto Scaling Group did not specify `metadata_options`. This means every instance was deployed with IMDSv1 enabled by default — the AWS default until account-level IMDSv2 enforcement is explicitly configured.

There was no error. The instances started. The ASG scaled correctly. The problem was invisible.

**Root Cause:**

AWS EC2 has two versions of its Instance Metadata Service (IMDS):

- **IMDSv1:** Any process on the instance can issue an HTTP GET to `http://169.254.169.254/latest/meta-data/iam/security-credentials/` and retrieve the instance's IAM role credentials without authentication.
- **IMDSv2:** Requires a PUT request to obtain a session token first (a form of CSRF protection). The hop limit of 1 blocks container-to-host metadata escalation.

The SSRF attack pattern is documented: a vulnerable web application running on the EC2 instance can be exploited to make a server-side request to `169.254.169.254`, retrieve IAM credentials, and use them to perform lateral movement across the AWS account.

The Capital One breach (2019, $80M fine) used exactly this SSRF → IMDSv1 → IAM credential theft path.

**Fix Applied:**

```hcl
resource "aws_launch_template" "app" {
  # ...
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"     # IMDSv2 mandatory
    http_put_response_hop_limit = 1              # Blocks container-to-host escalation
  }
}
```

**Business Impact:**

IMDSv1 is the primary enabler of the most common AWS account takeover pattern. An EC2 instance running a web application with any SSRF vulnerability (URL fetch, webhook, PDF renderer, image converter) exposes its IAM credentials to unauthenticated attackers. A single compromised instance credential can lead to full account compromise if the IAM role is over-privileged. This is not theoretical — it is the documented root cause of multiple major cloud breaches.

---

## Problem 3 — Unrestricted Egress on Security Groups

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Security / Compliance |
| **Time Lost** | ~30 minutes investigating CI failures |
| **Discovered** | Checkov CKV_AWS_382 flagged both `alb_sg` and `instance_sg` in CI |

**Symptom:**

Both security groups were initially configured with a blanket egress rule:

```hcl
egress {
  from_port   = 0
  to_port     = 0
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]
}
```

Checkov's CI scan flagged both with `CKV_AWS_382: Ensure no security groups allow unrestricted egress`.

**Root Cause:**

The unrestricted egress rule is the default in many Terraform examples and is often cargo-culted without consideration. The rationale is "you control inbound, so outbound doesn't matter." This reasoning is wrong for two reasons:

1. **Data exfiltration:** A compromised EC2 instance can beacon to any external command-and-control server on any port. Unrestricted egress makes this trivial.
2. **ALB specifically:** An ALB needs to reach its targets (the EC2 instances) on a specific port. It does not need to reach arbitrary internet addresses. Granting it `protocol = "-1"` to `0.0.0.0/0` is significantly over-privileged.

**Fix Applied:**

Replaced the blanket egress rule with explicit, justified rules on each security group:

```hcl
# ALB SG: only needs to reach backend instances on port 80 within the VPC
egress {
  description = "Allow ALB to reach backend EC2 instances on port 80 within VPC"
  from_port   = 80
  to_port     = 80
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/16"]
}

# EC2 instance SG: needs HTTPS for AWS API calls and HTTP for package repos via NAT
egress {
  description = "HTTPS for AWS APIs and package repos (via NAT)"
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}
egress {
  description = "HTTP for package repositories via NAT"
  from_port   = 80
  to_port     = 80
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
}
```

**Business Impact:**

Unrestricted egress is the second component required for successful data exfiltration (after an initial breach). An attacker who compromises an EC2 instance needs unrestricted egress to beacon home, exfiltrate data, and download additional tooling. Restricting egress to only the ports and destinations required for legitimate operations reduces the attacker's options even after a successful breach — this is the defence-in-depth principle applied to network egress.

---

## Problem 4 — ALB Missing Deletion Protection

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Operational Safety |
| **Time Lost** | ~15 minutes |
| **Discovered** | Checkov CKV_AWS_150 in CI scan output |

**Symptom:**

Checkov flagged the ALB resource with:

```
Check: CKV_AWS_150: "Ensure that Load Balancer has deletion protection enabled"
FAILED for resource: aws_lb.main
```

The ALB was functional and healthy. The issue was a missing safety attribute.

**Root Cause:**

By default, AWS ALBs can be deleted by any IAM principal with `elasticloadbalancing:DeleteLoadBalancer` permission. In production, an ALB is the single point of entry for all traffic. Accidentally deleting it — via a mistaken `terraform destroy`, a misconfigured CI/CD pipeline, or a compromised IAM credential — takes the application down immediately.

The `enable_deletion_protection` attribute is a single boolean that prevents deletion via the AWS API until protection is explicitly disabled. It has no performance or cost impact.

**Fix Applied:**

```hcl
resource "aws_lb" "main" {
  name                       = "ha-load-balancer"
  internal                   = false
  load_balancer_type         = "application"
  drop_invalid_header_fields = true
  enable_deletion_protection = true    # Prevent accidental ALB deletion
  # ...
}
```

**Business Impact:**

In a production environment, an accidentally deleted ALB results in a total application outage. Even if the Terraform state still has the configuration, recreating an ALB takes 3–5 minutes and requires DNS propagation time. For a high-traffic application, this translates to direct revenue loss and potential SLA breach. Deletion protection is a one-line addition that eliminates the entire class of "accidental deletion" incidents.

---

## What These Failures Prove

The HA architecture project demonstrated four production failure patterns in a single project:

1. **Plan ≠ Apply** — `terraform plan` succeeds on a configuration that the AWS API will reject. Service-level validation (ALB requires 2 AZs) is not detectable by Terraform's planning phase.
2. **Default-insecure AWS behaviour** — IMDSv1 is the default. The secure configuration must be explicitly specified.
3. **Copy-paste security groups** — unrestricted egress is the first thing every tutorial copies and the last thing anyone examines.
4. **Operational safety controls are not optional** — deletion protection is a one-line addition with zero operational cost. Not having it is a continuous accident waiting to happen.
