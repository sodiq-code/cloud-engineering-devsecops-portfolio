# IAM Role for EC2 instances
# Allows EC2 service to assume this role
resource "aws_iam_role" "ec2_role" {
  name = "${var.environment}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# S3 Read-Only Policy
# Grants read access to specified S3 bucket
resource "aws_iam_policy" "s3_read_only" {
  name        = "${var.environment}-s3-read-policy"
  description = "Allow EC2 to read from specific S3 bucket"

  # Handle wildcard "*" separately to avoid MalformedPolicyDocument error
  # When "*" is passed, use it directly; otherwise, include bucket and object ARNs
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:ListBucket", # Required for listing bucket contents
          "s3:GetObject"   # Required for reading objects
        ]
        Effect = "Allow"
        Resource = var.target_bucket_arn == "*" ? ["*"] : [
          var.target_bucket_arn,       # Bucket-level permissions
          "${var.target_bucket_arn}/*" # Object-level permissions
        ]
      }
    ]
  })
}

# Attach S3 policy to the EC2 role
resource "aws_iam_role_policy_attachment" "attach_s3" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_read_only.arn
}

# Instance profile to associate the IAM role with EC2 instances
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.environment}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}