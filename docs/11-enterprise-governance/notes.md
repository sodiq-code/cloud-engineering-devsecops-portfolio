# Week 11: Enterprise Governance (Project B)

## 1. Project Objective
**Goal:** Move from single-account security to Multi-Account Governance.
**The Tool:** AWS Organizations & Service Control Policies (SCPs).
**The Business Value:** Ensuring compliance and security baselines are enforced automatically across the entire company, preventing "Shadow IT."

## 2. Policies Implemented (The "Guardrails")
| Policy Name | Function | Security Domain |
| :--- | :--- | :--- |
| **Deny-CloudTrail-Tampering** | Blocks `StopLogging` and `DeleteTrail`. | **Log Integrity / Non-Repudiation** |
| **Restrict-Regions-US** | Blocks API calls to regions outside US-East. | **Data Sovereignty / Cost Control** |

## 3. Architecture
* **Root:** The Management Account.
* **OU (Workloads-Prod):** Where the application accounts live. The SCPs are attached here to restrict developers.
* **OU (Security-Prod):** Where the log archive lives. Less restrictive to allow security tools to operate.

## 4. Evidence
* **Terraform Deployment:** `screenshots/org-success.png`