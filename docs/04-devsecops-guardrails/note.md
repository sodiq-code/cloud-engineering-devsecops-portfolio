# Week 4: Automated Security Remediation & CI/CD Pipeline Debugging

## Objective
To implement **"Shift Left"** security by scanning Terraform code for vulnerabilities before deployment and ensuring the CI/CD pipeline is robust enough to enforce these security gates.

## Tools Used
- **Terraform:** Infrastructure as Code (IaC).
- **LocalStack:** For local AWS cloud simulation.
- **GitHub Actions:** Automates the CI/CD workflow.
- **Trivy:** The security scanner (by Aqua Security).
- **AWS KMS:** Customer Managed Keys for encryption.

## Security Challenges & Remediation
The initial pipeline scan detected **6 High-Severity Vulnerabilities** in the S3 bucket configuration.

1. **Public Access Vulnerabilities (AVD-AWS-0086 to 0093):**
   - **Issue:** The bucket lacked a Public Access Block, exposing it to potential public leaks.
   - **Fix:** Implemented `aws_s3_bucket_public_access_block` resource with all blocks set to `true`.

2. **Encryption Vulnerabilities (AVD-AWS-0088 & 0132):**
   - **Issue:** Data was unencrypted, lacking a Customer Managed Key (CMK).
   - **Fix:** Defined an `aws_kms_key` with rotation enabled and enforced `sse_algorithm = "aws:kms"` on the bucket.

## DevSecOps Learning: Pipeline Debugging
A critical operational challenge occurred where the pipeline kept reporting old vulnerabilities despite the code fixes.

- **The Problem:** The GitHub Actions runner was using a shallow clone or stale cache, ignoring the latest security commits.
- **The Fix:** I updated the workflow YAML to use `fetch-depth: 0` in the checkout step.
  ```yaml
  - name: Checkout code
    uses: actions/checkout@v4
    with:
      fetch-depth: 0  # Forces deep clone to ensure latest code is scanned

- Evidence: `screenshots/trivy-fail.png`
- Evidence: `screenshots/trivy-success.png`

## Key Learning
By catching this in the pipeline, I prevented a potential data breach without needing to deploy any resources to AWS.