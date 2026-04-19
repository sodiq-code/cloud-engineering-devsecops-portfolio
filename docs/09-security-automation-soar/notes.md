# Week 9: Security Automation & SOAR

## 1. Project Objective
**Goal:** Implement "Self-Healing Security" by automating threat remediation using Python (Boto3).
**The Problem:** Manual response to threats (e.g., blocking an IP) is too slow for modern attacks.
**The Solution:** A Python script that programmatically interacts with the AWS Network ACL to block attackers instantly.

## 2. The Logic (`auto_remediate_nacl.py`)
I wrote a script that performs the following logic chain:
1.  **Authentication:** Connects to the AWS environment (LocalStack) via the Boto3 SDK.
2.  **Discovery:** Dynamically queries the VPC API to find the active Network ACL (NACL) ID.
3.  **Remediation:** Injects a `Rule #1` (Highest Priority) DENY entry for the malicious IP.

## 3. Key Technical Concepts
* **Infrastructure as Code vs. Automation:** Terraform builds the network (Static), but Python defends the network (Dynamic).
* **AWS SDK (Boto3):** Used `ec2.create_network_acl_entry` to modify infrastructure state via API.

## 4. Evidence
* **Execution Log:** `screenshots/python-success.png` (Shows successful API calls and rule creation).

## Production Architecture (Planned)
While this lab runs the script locally, in a production environment, the workflow would be automated:
1.  **GuardDuty** detects a threat (Finding).
2.  **EventBridge** filters for "High Severity" findings.
3.  **Lambda** triggers this Python script, passing the Malicious IP as an input variable.
4.  **NACL** is updated to block the IP.