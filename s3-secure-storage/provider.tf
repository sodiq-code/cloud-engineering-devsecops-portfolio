terraform {                     # Root Terraform block configuring settings for this module
  required_providers {          # Declare which providers this module depends on
    aws = {                     # Configuration for the AWS provider
      source  = "hashicorp/aws" # Provider source location on the Terraform Registry
      version = "~> 4.0"        # Use any 4.x version, but not 5.x or higher
    }
  }
  required_version = ">= 1.4.0" # Require Terraform CLI version 1.4.0 or newer
}

provider "aws" {                           # Configure the AWS provider instance
  region                      = var.region # AWS region, taken from a Terraform variable
  access_key                  = "test"     # Dummy AWS access key (used for LocalStack)
  secret_key                  = "test"     # Dummy AWS secret key (used for LocalStack)
  s3_use_path_style           = true       # use path-style S3 URLs (required by LocalStack for S3)
  skip_credentials_validation = true       # Skip checking if credentials are valid (for local testing)
  skip_requesting_account_id  = true       # Skip retrieving AWS account ID (not needed for LocalStack)

  endpoints {                    # Override default AWS service endpoints
    s3 = "http://localhost:4566" # Point S3 API calls to LocalStack running on localhost:4566
    kms = "http://localhost:4566"
  }
}
