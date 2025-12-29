# 🛡️ Enterprise Cloud Engineering & DevSecOps Portfolio
**By JIMOH SODIQ BOLAJI**

![Status](https://img.shields.io/badge/Status-Completed-success) ![Focus](https://img.shields.io/badge/Focus-SRE%20%7C%20Cloud%20Security%20%7C%20K8s-blue) ![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-orange) ![Monitoring](https://img.shields.io/badge/Stack-Prometheus%20%26%20Grafana-red)

## 🚀 Executive Summary
Highly analytical Computer Engineer with a focus on **Infrastructure as Code (IaC)**, **Cloud Security**, and **Site Reliability Engineering (SRE)**. This portfolio documents the successful delivery of production-grade cloud environments, emphasizing automated security compliance, high-availability architecture, and enterprise-scale observability.

---

## 📂 Engineering Project Index

### **1. 🛡️ KubeScale: High-Availability Microservices & SRE Observability Platform**
* **[🔗 View Project Code & Documentation](./k8s-ecommerce-project)**
* **Enterprise Orchestration:** Orchestrated an 11-tier polyglot microservices ecosystem on **Kubernetes**, utilizing **Deployments** and **ReplicaSets** to ensure 99.9% application availability.
* **Layer 7 Traffic Engineering:** Implemented a production-grade **Nginx Ingress Controller** to manage name-based virtual hosting (`shop.local`), moving beyond "lab-style" port-forwarding to a centralized edge routing model.
* **SRE Observability:** Deployed a full-stack monitoring suite via **Helm**, integrating **Prometheus** for metrics scraping and **Grafana** for visualizing "Golden Signals" (Latency, Traffic, Errors, Saturation).
* **FinOps & Cost Optimization:** Engineered a hybrid development workflow using **LocalStack Pro** to emulate AWS dependencies, achieving **100% cost avoidance (~$500/mo savings)** during the development lifecycle.
* **Security & Governance:** Hardened container security to a **0-finding baseline** (Trivy) by implementing **Non-Root users**, **Immutable Filesystems**, and administrative isolation via **Namespaces**.

### **2. High-Availability AWS Architecture & Cost Optimization Initiative**
* **[🔗 View Project Code & Documentation](./week8-ha-deploy)**
* **Cost Reduction:** Engineered a hybrid development workflow using **LocalStack** for emulation, reducing development cloud spend by 100% while maintaining full production parity.
* **Zero Downtime:** Configured an **Application Load Balancer (ALB)** backed by an **Auto Scaling Group (ASG)** to ensure fault tolerance during peak loads.
* **Security at the Edge:** Deployed **AWS WAF** with managed rules to block SQL Injection and XSS attacks before they reached the application layer.
* **Technical Problem Solving:** Resolved a critical Terraform Provider v6.x compatibility bug by pinning dependencies to `v4.67.0`.

### **3. Automated Security Compliance Pipeline ("Shift-Left" Strategy)**
* **[🔗 View Project Code & Documentation](./docs/week4/README.md)**
* **Pipeline Governance:** Built a **GitHub Actions** workflow that integrates **Aqua Security Trivy** to enforce a "Shift-Left" security model on every Pull Request.
* **Risk Mitigation:** Configured automated gates to block builds immediately if High/Critical risks (e.g., Public S3 Buckets) are detected.
* **Enterprise Process:** Established a formal `trivyignore` protocol to document and accept specific lab-environment risks.

### **4. Real-Time Threat Remediation System (SOAR) & Forensics**
* **[🔗 View Automation Code](./automation) | [🔗 View Forensics Report](./forensics)**
* **Response Time Optimization:** Developed a **Python (Boto3)** automated remediation tool that reduced incident Time-to-Containment to milliseconds.
* **Automated Defense:** The script dynamically monitors VPCs and instantly injects high-priority **Network ACL Deny Rules** to block malicious IPs.
* **Forensic Investigation:** Conducted simulated "Live Hack" investigations on compromised Linux servers using `grep` and `awk` to identify Indicators of Compromise (IoCs).

### **5. Multi-Account Governance & Immutable Security Strategy**
* **[🔗 View Project Code & Documentation](./governance)**
* **Shadow IT Elimination:** Implemented **AWS Organizations** and **Service Control Policies (SCPs)** to enforce immutable security baselines like "Region Locks".
* **Compliance Enforcement:** Mandated **CloudTrail** integrity and centralized logging standards, effectively removing the risk of unauthorized infrastructure changes.

---

## 🛠️ Technical Expertise

| Category | Skills |
| :--- | :--- |
| **Cloud Native (K8s)** | Kubernetes, Helm, Docker, Nginx Ingress, Deployments, Services |
| **Observability (SRE)** | Prometheus, Grafana, CloudWatch, GuardDuty, Golden Signals |
| **Infrastructure as Code** | Terraform (Modules, State Management, Provider Pinning v4/v5) |
| **Cloud Infrastructure** | AWS (VPC, EKS, ALB, ASG, WAF, CloudTrail, Organizations) |
| **Security & Automation** | Python (Boto3), Bash Scripting, Trivy (DevSecOps), Linux Forensics |

---

## 💡 Key Engineering Challenges Solved
* **Microservices Networking:** Replaced basic port-forwarding with a production-grade Ingress Controller, implementing Layer 7 routing for 10+ services.
* **Resource Contention:** Debugged OOMKills in Kubernetes pods by implementing Prometheus monitoring and rightsizing container resource limits.
* **Cloud Spend Optimization:** Leveraged **LocalStack** to simulate 100% of the development lifecycle, allowing for limitless architectural iterations with zero AWS service costs.
* **Immutable Governance:** Overcame "Shadow IT" risks by implementing **AWS Organizations and SCPs**, enforcing a global "Region Lock" that reduced the attack surface by 90%.
* **Docker-in-Docker Networking:** Resolved LocalStack EC2 failures by configuring socket mounting and privileged mode in `docker-compose.yml`.

---

## 🎓 Education & Credentials
* **B.Eng Computer Engineering** (FUTA, 2025)
* **Certified in Cybersecurity (CC)** - *ISC2 (Candidate)*

---
*This portfolio demonstrates a commitment to security, cost-efficiency, and operational excellence in modern cloud environments.*