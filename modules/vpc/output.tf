# modules/vpc/output.tf

output "vpc_id" {
  description = "Unique ID of the VPC — used by other modules to attach resources"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID of public subnet A (AZ-a) — used by ALB, NAT Gateway, bastion hosts"
  value       = aws_subnet.public_a.id
}

output "public_subnet_b_id" {
  description = "ID of public subnet B (AZ-b) — required second AZ for ALB high availability"
  value       = aws_subnet.public_b.id
}

output "private_subnet_id" {
  description = "ID of private subnet A (AZ-a) — for application servers behind NAT"
  value       = aws_subnet.private_a.id
}

output "private_subnet_b_id" {
  description = "ID of private subnet B (AZ-b) — for HA application server placement"
  value       = aws_subnet.private_b.id
}

output "nat_gateway_id" {
  description = "ID of the NAT Gateway — allows private subnet internet egress"
  value       = aws_nat_gateway.nat.id
}
