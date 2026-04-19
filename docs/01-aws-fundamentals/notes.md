# Week 1 — AWS & Networking Basics

# Week 1 — AWS Fundamentals Notes

### IAM (Source: AWS Foundations – Pluralsight)
1) IAM Users vs Roles  
    - Users = long‑term identities for people or apps with credentials.  
    - Roles = temporary access, assumed by users/services, easier to rotate and limit permissions.  

2) Policy document = Effect / Action / Resource  
    - Effect: allow or deny.  
    - Action: which API calls are permitted.  
    - Resource: which AWS resources those actions apply to.  

3) Never attach policies to users, use roles  
    - Attach policies to roles or groups, then assign users to them for easier, safer permission management.  

### VPC (Source: AWS Foundations – Pluralsight)
4) Public vs Private Subnet + NAT Gateway  
    - Public subnet: has route to Internet Gateway, resources are internet‑reachable.  
    - Private subnet: no direct internet route; use NAT Gateway in a public subnet for outbound‑only access.  

5) Route Table determines traffic flow  
    - Routes decide where traffic goes (local, internet, peering, VPN); each subnet is associated with exactly one route table.  

6) Internet Gateway allows outbound internet  
    - IGW enables resources in public subnets to send/receive traffic from the internet when routes and security rules allow it.  

### KMS (Source: Intro to AWS Security – Pluralsight)
7) Customer Managed CMKs = full control  
    - You create/manage keys, control rotation, permissions, and can disable or delete them.  

8) Envelope encryption  
    - Data is encrypted with a data key; that data key is encrypted with a KMS CMK, reducing KMS calls and improving performance.  

### Logging (Source: Intro to Security & Architecture – Pluralsight)
9) CloudTrail = API logging  
    - Records who did what, when, and from where in your AWS account for auditing and incident investigation.  

10) CloudWatch = metrics + alarms  
    - Collects metrics and logs from services, lets you create alarms and dashboards to monitor health and performance. 

## Lab Summaries

### Lab 1: IAM Role for S3 Read‑Only

- **Created:** IAM role `S3ReadOnlyRole` with `AmazonS3ReadOnlyAccess`.
- **Path:** IAM → Roles → Create role → EC2 → Attach policy → Name role.
- **Key point:** Prefer roles with temporary credentials over user‑attached policies.
Screenshot: ./img/iam-lab.png  

### Lab 2: KMS Symmetric Key

- **Created:** Symmetric customer managed key with annual rotation for S3 encryption.
- **Path:** KMS → Customer managed keys → Create key → Symmetric → Configure admins/usage.
- **Key point:** KMS access is controlled by key policies; permissions must be explicitly granted.
Screenshot: ./img/kms-lab.png
### Lab 3: VPC Flow Logs

- **Enabled:** VPC Flow Logs for the main VPC, capturing ACCEPT and REJECT traffic.
- **Destination:** Sent logs to CloudWatch Logs group `vpc-flow-logs-main`.
- **Path:** VPC → Your VPCs → Select VPC → Create flow log → Choose IAM role & destination.
- **Key point:** Flow logs help troubleshoot connectivity and monitor for suspicious network activity.
Screenshot: ./img/vpc-lab.png
