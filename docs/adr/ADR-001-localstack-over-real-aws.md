# ADR-001: Use LocalStack for Development-Lifecycle Cost Avoidance

**Date:** 2025-10-01  
**Status:** Accepted  
**Deciders:** Jimoh Sodiq Bolaji  
**Category:** FinOps / Development Environment

---

## Context

Developing and iterating on an 11-service microservices platform with full AWS dependencies (EKS, ALB, WAF, S3, SQS) on a live AWS account would cost approximately:

| Service | Monthly Cost |
| :--- | :--- |
| EKS Control Plane | ~$72 |
| NAT Gateways (2x) | ~$64 |
| ALB | ~$18 |
| WAFv2 | ~$10+ |
| KMS, CloudWatch, etc. | ~$30 |
| **Total** | **~$194–$500/month** |

This cost is prohibitive for a portfolio-level project with no revenue.

## Decision

Use **LocalStack Pro** to emulate all AWS service APIs locally during development and testing. LocalStack provides HTTPS-compatible endpoints on `http://localhost:4566` that implement the full AWS API surface, including IAM, S3, EC2, EKS, VPC, WAFv2, KMS, and SQS.

All Terraform providers are configured with `endpoint` overrides pointing to LocalStack instead of real AWS endpoints.

## Consequences

### Positive
- ✅ **$0 development spend** — unlimited architectural iterations at zero cost
- ✅ **Offline capability** — no internet required for development
- ✅ **Full API parity** — LocalStack Pro supports 80+ AWS services
- ✅ **Fast feedback loops** — `terraform apply` in seconds vs. minutes on real AWS
- ✅ **Reproduciblility** — environment reset with `docker-compose down && docker-compose up`

### Negative / Trade-offs
- ⚠️ **LocalStack Pro required** — `LS_TOKEN` environment variable must be set; free tier has limitations
- ⚠️ **Not production** — deployment screenshots are LocalStack-based, not live AWS
- ⚠️ **Some service behaviours differ** — edge cases in IAM evaluation and Lambda cold starts may differ

### Mitigations
- Provider pinning (`version = "~> 4.67"`) prevents incompatibility between Terraform provider versions and LocalStack API implementations
- Production deployment would simply remove `endpoint` overrides and use real AWS credentials via IAM roles

## Alternatives Considered

| Option | Reason Rejected |
| :--- | :--- |
| Real AWS Free Tier | Too many services exceed free-tier limits (EKS, WAFv2, NAT GW) |
| AWS CDK with mocking | Less realistic than actual Terraform provider calls |
| Terraform mock provider | Too synthetic — does not exercise real API paths |
