# Week 3 — Terraform fundamentals

## HashiCorp Learn followed:
- **Intro: `terraform init` / `plan` / `apply`**  
    - `terraform init` – Downloads providers, initializes the backend, and prepares the working directory.  
    - `terraform plan` – Shows what Terraform will create, change, or destroy without making any actual changes.  
    - `terraform apply` – Executes the planned changes to reach the desired infrastructure state.
- **State: local state vs remote state (S3 + DynamoDB lock)**  
    - Local state: `terraform.tfstate` file stored locally, simple but not suitable for teams.  
    - Remote state: Stored in a shared, persistent, and versioned location (e.g., S3 bucket).  
    - State locking: Prevents concurrent modifications (e.g., DynamoDB for S3 backend).
- **Providers: AWS provider configuration and credentials lookup**  
    - Providers: Plugins that allow Terraform to interact with cloud platforms and other services.  
    - Configuration: `provider "aws" { region = "us-east-1" }` block.  
    - Authentication: AWS credentials lookup order (environment variables, shared credentials file, IAM roles).
- **Resources: basic aws_s3_bucket example**  
    - Resources: The most important element in Terraform, representing infrastructure objects (e.g., EC2 instances, S3 buckets).  
    - Syntax: `resource "type" "name" { ... }`  
    - Example: `aws_s3_bucket` for creating an S3 bucket.

- **Execution: `terraform destroy` to clean up**  
    - `terraform destroy`: Terminates all resources managed by the current Terraform configuration.  
    - Important: Always review the plan before destroying to avoid accidental data loss.
- Files: main.tf, variables.tf, outputs.tf, terraform.tfvars

## Workspaces
- Purpose: Manage multiple distinct states for a single Terraform configuration (e.g., dev, staging, prod).
- Commands: `terraform workspace new <name>`, `terraform workspace select <name>`, `terraform workspace list`.
-   Files: main.tf, variables.tf, outputs.tf, terraform.tfvars
    - `main.tf`: Main configuration file, contains resource definitions.  
    - `variables.tf`: Defines input variables for the configuration.  
    - `outputs.tf`: Defines output values to be displayed after `apply`.  
    - `terraform.tfvars`: Assigns values to variables, typically not committed to version control.

- **Variables**  
    Definition: Inputs that parameterize Terraform configurations so you avoid hard‑coding values.  
    Example:
    ```hcl
    variable "environment" {
        type        = string
        description = "Deployment environment"
        default     = "dev"
    }
    ```

- **Outputs**  
    Definition: Named values exported from a Terraform configuration so other people, tools, or modules can use them.  
    Example:
    ```hcl
    output "bucket_arn" {
        value       = aws_s3_bucket.app_bucket.arn
        description = "ARN of the app S3 bucket"
    }
    ```

## Goals this week
- Run a small S3 example locally with LocalStack
- Understand terraform plan output

### provider.tf
- Sets required provider (aws).
- Configures provider to talk to LocalStack by setting endpoints.s3 to http://localhost:4566
- skip_credentials_validation and test keys allow LocalStack to accept calls without real AWS creds.

### main.tf
- Declares an aws_s3_bucket resource with bucket name from variable.
- ACL = private and tags are set.

### variables.tf
- region and bucket_name variables so code is reusable.

### outputs.tf
- Exposes bucket_name after apply so we can reference it elsewhere.

### Commands run
- terraform init → downloads providers & sets up .terraform
- terraform validate → checks syntax
- terraform plan → shows what Terraform will change
- terraform apply → executes changes (we used LocalStack)
- terraform destroy → removes created test resources
