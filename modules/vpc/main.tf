# modules/vpc/main.tf
# Production-grade VPC module with:
# - Dual-AZ public and private subnets for true high availability
# - NAT Gateway for secure private subnet egress
# - Consistent tagging strategy

# =============================================================================
# CORE VPC
# =============================================================================
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.environment}-vpc"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# =============================================================================
# INTERNET GATEWAY — Enables outbound internet access for public subnets
# =============================================================================
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.environment}-igw"
    Environment = var.environment
  }
}

# =============================================================================
# PUBLIC SUBNETS — Two AZs for ALB and NAT Gateway placement
# ALB requires subnets in at least two AZs for production deployments
# =============================================================================
resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  map_public_ip_on_launch = false # Explicit control; assign EIPs only where needed
  availability_zone       = "${var.region}a"

  tags = {
    Name        = "${var.environment}-public-subnet-a"
    Environment = var.environment
    Tier        = "public"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_b_cidr
  map_public_ip_on_launch = false
  availability_zone       = "${var.region}b"

  tags = {
    Name        = "${var.environment}-public-subnet-b"
    Environment = var.environment
    Tier        = "public"
  }
}

# =============================================================================
# PRIVATE SUBNETS — Two AZs for application servers (no direct internet access)
# =============================================================================
resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = "${var.region}a"

  tags = {
    Name        = "${var.environment}-private-subnet-a"
    Environment = var.environment
    Tier        = "private"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_b_cidr
  availability_zone = "${var.region}b"

  tags = {
    Name        = "${var.environment}-private-subnet-b"
    Environment = var.environment
    Tier        = "private"
  }
}

# =============================================================================
# NAT GATEWAY — Allows private subnets outbound internet access
# without exposing them to inbound internet traffic (one-way firewall)
# =============================================================================
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name        = "${var.environment}-nat-eip"
    Environment = var.environment
  }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_a.id # NAT Gateway lives in the public subnet

  depends_on = [aws_internet_gateway.igw]

  tags = {
    Name        = "${var.environment}-nat-gw"
    Environment = var.environment
  }
}

# =============================================================================
# ROUTE TABLES
# =============================================================================

# Public route table — all internet traffic goes through the IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name        = "${var.environment}-public-rt"
    Environment = var.environment
  }
}

# Private route table — outbound internet routes through NAT Gateway (no inbound)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = {
    Name        = "${var.environment}-private-rt"
    Environment = var.environment
  }
}

# Associate public subnets with the public route table
resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# Associate private subnets with the private route table (NAT-egress only)
resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}
