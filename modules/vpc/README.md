# VPC Module — Multi-AZ Network Foundation

Creates a production-grade VPC with dual-AZ public and private subnets, Internet Gateway, NAT Gateway, and route tables. Used by all compute projects in this portfolio.

## Architecture
```
VPC 10.0.0.0/16
├── Public Subnet A (AZ-a) 10.0.1.0/24  ← ALB, NAT GW, bastion
├── Public Subnet B (AZ-b) 10.0.3.0/24  ← ALB second AZ (required for HA)
├── Private Subnet A (AZ-a) 10.0.2.0/24 ← EC2 instances
├── Private Subnet B (AZ-b) 10.0.4.0/24 ← EC2 second AZ
├── Internet Gateway                      ← Public subnet internet access
└── NAT Gateway (in Public A)            ← Private subnet outbound only
```

## Key Security Decisions
- `map_public_ip_on_launch = false` — no automatic public IPs
- Private subnets have no IGW route — only NAT Gateway (no inbound internet)
- CIDR variables include `validation` blocks to prevent typos

## Inputs
All inputs have validation blocks and defaults safe for local development.

## Outputs
`vpc_id`, `public_subnet_id`, `public_subnet_b_id`, `private_subnet_id`, `private_subnet_b_id`, `nat_gateway_id`
