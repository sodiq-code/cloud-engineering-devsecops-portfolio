# IAM Module — Least-Privilege EC2 Instance Role

Creates an IAM Role and Instance Profile for EC2 instances, granting read-only access to a specific S3 bucket. Implements the Principle of Least Privilege: instances can only access what they need.

## Resources
- `aws_iam_role.ec2_role` — EC2 service assume role
- `aws_iam_policy.s3_read_only` — S3 ListBucket + GetObject on target bucket only  
- `aws_iam_role_policy_attachment.attach_s3` — attaches policy to role
- `aws_iam_instance_profile.ec2_profile` — associates role with EC2

## Inputs
| Variable | Type | Description |
|---|---|---|
| `environment` | string | Prefix for resource naming |
| `target_bucket_arn` | string | ARN of the S3 bucket to grant access |

## Outputs
| Output | Description |
|---|---|
| `instance_profile_name` | Name of the instance profile — pass to `aws_instance.iam_instance_profile` |
