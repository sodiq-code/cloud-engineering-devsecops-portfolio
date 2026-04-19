# Week 8: High Availability Architecture (Project A+)

## 1. Project Objective
**Goal:** Upgrade the Project A single-server architecture to a **High Availability (HA)**, self-healing system using Load Balancing and Auto Scaling.
**Key Deliverables:**
* **Application Load Balancer (ALB):** Single entry point for all user traffic.
* **Auto Scaling Group (ASG):** Automatically maintains 2 healthy instances.
* **Web Application Firewall (WAF):** Layer 7 defense attached to the ALB to block SQLi/XSS.

## 2. Engineering Challenges & Resolutions (The v4.67 Fix)
*During the upgrade, I encountered a critical compatibility issue between Terraform AWS Provider v5 and the LocalStack S3 emulator.*

### 🔧 The "S3 Control" API Conflict
* **Problem:** `terraform apply` failed with `S3 Control: ListTagsForResource... endpoint rule error`.
* **Root Cause:** The AWS Provider v5.x attempts to use the newer `S3 Control` API for tagging, which isn't fully implemented in the current LocalStack community image.
* **Resolution:**
    1.  **Dependency Pinning:** Explicitly pinned the AWS Provider to `~> 4.67.0` in `main.tf` to force the use of the legacy S3 API logic.
    2.  **Service Configuration:** Updated `docker-compose.yml` to explicitly expose the `s3control` endpoint as a fail-safe.
    3.  **State Reset:** Performed a full volume wipe (`docker compose down -v`) to clear corrupted state before re-applying.

## 3. Architecture Changes
* **Traffic Flow:** `Internet -> WAF -> ALB -> Security Group -> EC2`.
* **Security Groups:**
    * `alb_sg`: Open to world (Port 80).
    * `instance_sg`: Locked down. **Only** accepts traffic from `alb_sg`. Direct access blocked.

## 4. Evidence of Success
* **Deployment:** Successfully created **26 Resources** (including ALB, WAF, ASG, and Launch Templates).
* **Verification:** `aws autoscaling describe-auto-scaling-groups` shows `DesiredCapacity: 2`.