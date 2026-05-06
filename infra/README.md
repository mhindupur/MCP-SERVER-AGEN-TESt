# infra/

This folder contains **AWS deployment scaffolding** for the team platform:

- `terraform/`: VPC + RDS MySQL + ECS Fargate + ALB (starter)

## Notes

- This is intentionally a **starter** Terraform layout. You will still need to:
  - Choose instance sizes
  - Configure TLS on the ALB
  - Wire Secrets Manager values (OpenAI key, OIDC client secret)
  - Tighten security groups
