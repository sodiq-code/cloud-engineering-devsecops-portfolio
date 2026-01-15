#  Project A+: High Availability & Auto-Scaling
**Status:** ✅ Deployed & Verified on LocalStack

## 1. Overview
This project is an architectural upgrade to [Project A](../week6-deploy). While Project A focused on security segmentation, **Project A+** focuses on **Resilience, Scalability, and Layer 7 Defense**.

It transforms a single-server architecture into a **Self-Healing Fleet** using Application Load Balancers (ALB) and Auto Scaling Groups (ASG), protected by a Web Application Firewall (WAF).

## 2. Architecture & Traffic Flow
![Project A+ Final Architecture](../docs/week6/architecture_diagram_final.png)

## 2. Traffic Flow
`Internet` -> **`WAF`** (SQLi Block) -> **`ALB`** (Traffic Dist.) -> **`Security Group`** (Port 80) -> **`EC2 Instances`** (Private)

## 3. Key Features Implemented
| Component | Function | Why it matters (DevOps) |
| :--- | :--- | :--- |
| **Application Load Balancer** | Distributes traffic | Removes the "Single Point of Failure" of a single server. |
| **Auto Scaling Group** | `min=2`, `max=3` | **Self-Healing:** If a server crashes, ASG replaces it instantly. |
| **Web Application Firewall** | AWS Managed Rules | **AppSec:** Blocks SQL Injection and XSS attacks at the edge. |
| **Dynamic AMI** | Launch Template | Defines the "Blueprint" for all new servers (Hardened config). |

## 4. Engineering Challenges (Solved)
* **Provider Conflict:** Pinned AWS Provider to `v4.67.0` to resolve a compatibility bug between Terraform `v5.x` and LocalStack's S3 API.
* **Lab Constraints:** Configured `.trivyignore` to accept HTTP (Port 80) and Open Egress risks specifically for the local simulation environment.


## 5. Artifacts
* **Infrastructure Code:** [main.tf](./main.tf)

### **Evidence of Scale**
*(Verifying Auto Scaling Group capacity = 2)*

<p align="center">
  <img src="./screenshot/auto-scaling.png" alt="Auto Scaling" width="700"/>
  <br>
  <em>Figure 1: Auto Scaling Complete</em>
</p>

<p align="center">
  <img src="./screenshot/ha-success.png" alt="ASG Success" width="700"/>
  <br>
  <em>Figure 2: Terraform Apply Complete</em>
</p>

<p align="center">
  <img src="./screenshot/ha-success_1.png" alt="Terminal Success" width="700"/>
  <br>
  <em>Figure 3: ASG Scaling Events</em>
</p>

## 6. Deployment Verification
To deploy this stack locally:
```bash
terraform init
terraform apply --auto-approve
