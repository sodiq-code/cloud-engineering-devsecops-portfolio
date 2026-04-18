variable "region" { # Declare a Terraform input variable named "region"
  description = "AWS region (LocalStack uses a fake region)"
  type        = string      # Enforce that the variable value must be a string
  default     = "us-east-1" # Default value for the region if none is provided
}

variable "bucket_name" { # Declare a Terraform input variable named "bucket_name"
  description = "S3 bucket name"
  type        = string                     # Enforce that the variable value must be a string
  default     = "afsod-week3-bucket-12345" # Default S3 bucket name if none is provided
}
