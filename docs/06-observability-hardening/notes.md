# Week 6: Project A — Observability, Hardening & Engineering Challenges

## 1. Project Objective
**Goal:** Refactor the Week 5 skeleton into a production-grade, monitored environment using Modular Architecture.
**Deliverables:**
* **Observability:** Implemented CloudTrail (Audit Logs) and GuardDuty (Threat Detection).
* **Secure Storage:** Created an encrypted, private S3 bucket (`modules/logging`) for audit trails.
* **Modular Refactor:** Decoupled the monolithic design into reusable Terraform modules (`logging`, `security`, `vpc`, `iam`).

---

## 2. Security Remediation (DevSecOps)
*Adhering to "Shift Left" principles, I resolved critical security debt identified during the build.*

* **IAM Least Privilege:**
    * *Risk:* The EC2 role originally had `Resource: "*"` permission, violating least privilege.
    * *Fix:* Updated `modules/iam` to accept a `target_bucket_arn` variable. The EC2 instance is now strictly scoped to read *only* from the specific logging bucket.
* **Instance Hardening (Trivy Findings):**
    * *Risk:* Trivy flagged `AVD-AWS-0028` (IMDSv1 enabled) and unencrypted root volumes.
    * *Fix:* Enforced `metadata_options { http_tokens = "required" }` to prevent SSRF attacks and enabled `root_block_device { encrypted = true }`.
* **Traffic Restriction:**
    * *Fix:* Tightened Security Group egress rules from `0.0.0.0/0` to `10.0.0.0/16` to prevent data exfiltration to the public internet.

---

## 3. Engineering Challenges & Resolutions (Technical Diary)
*During the deployment to LocalStack, I encountered and resolved 7 specific technical hurdles. These resolutions verify my ability to troubleshoot across the Terraform, Docker, and OS layers.*

### 🔧 1. The "Hanging EC2" (Docker-in-Docker)
* **Problem:** Terraform hung indefinitely on `aws_instance.web: Creating...`.
* **Root Cause:** LocalStack runs inside Docker. To spawn "sibling containers" (EC2), it needs access to the host Docker Engine.
* **Resolution:** Configured `privileged: true` and mounted the Docker socket (`/var/run/docker.sock`) in `docker-compose.yml`.

### 🔧 2. Provider v6.0 API Conflict
* **Problem:** `Error reading EC2 Instance ... credit specification: couldn't find resource`.
* **Root Cause:** The AWS Terraform Provider v6.x introduced strict API validation for T2 instance credit specifications that the LocalStack emulator does not yet fully support.
* **Resolution:** Pinned the AWS Provider version to `~> 5.0` in the `required_providers` block to ensure compatibility.

### 🔧 3. Module Scope & Undeclared Resources
* **Problem:** `modules/logging` failed because it could not see the KMS key defined in `modules/security`.
* **Root Cause:** Terraform modules are isolated scopes; resources are not global by default.
* **Resolution:** Refactored `modules/logging/main.tf` to self-declare its own KMS key, ensuring the module is self-contained and encapsulated.

### 🔧 4. Variable Passthrough Errors
* **Problem:** `Error: An argument named "environment" is not expected here`.
* **Root Cause:** The root `main.tf` tried to pass variables to modules that had not declared them in their own `variables.tf`.
* **Resolution:** Explicitly defined input variables (`environment`, `log_bucket_name`, `target_bucket_arn`) in each module's `variables.tf` to create the necessary "mailboxes" for data.

### 🔧 5. Windows/Git Bash Path Conflict
* **Problem:** LocalStack could not connect to Docker despite the socket mount (`1 container running instead of 2`).
* **Root Cause:** Git Bash on Windows attempts to translate Linux paths (like `/var/run/docker.sock`) into Windows paths (e.g., `C:\Program Files...`), breaking the mount.
* **Resolution:** Switched execution to **PowerShell** to pass the raw socket path correctly to the Docker Engine.

### 🔧 6. "Resource Busy" Crash
* **Problem:** LocalStack container crashed with `[Errno 16] Device or resource busy: '/tmp/localstack'`.
* **Root Cause:** Windows file locking conflicts when mapping volumes to `/tmp`.
* **Resolution:** Changed the volume map in `docker-compose.yml` to `/var/lib/localstack`, which avoids the Windows temporary file lock.

---

## 4. Evidence of Success
* **Full Stack Deployment:** `screenshots/full-stack-success.png` (Verifies VPC, IAM, S3, and CloudTrail deployed successfully).
* **Trivy Scan:** Passing (Green pipeline).