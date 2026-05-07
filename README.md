# cloud-mcp-agent (Python MCP server)

This is a Python **MCP server** (using `fastmcp`) for **AWS EC2** that lets operators authenticate via standard AWS SDK mechanisms and run tools like:

- List AWS EC2 instances
- List AWS EC2 instances with **instance-type memory < 2GB**
- Start/stop AWS EC2 instances

## Prerequisites

- Python 3.10+
- Cloud CLIs (recommended):
  - AWS CLI (`aws`)

## Install

From the repo root:

```bash
python3 -m venv mcp-env
source mcp-env/bin/activate
pip install -U pip
pip install -e .
```

## Run the MCP server

```bash
cloud-mcp-agent
```

## Authentication model (no secrets stored by this server)

This server **does not store credentials**. It relies on each provider’s standard SDK auth chain.

### AWS

Any of these work:

- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_SESSION_TOKEN`)
- Named profile in `~/.aws/credentials` / `~/.aws/config`
- AWS SSO profiles (after `aws sso login --profile <name>`)

## Tools exposed

- `aws_list_ec2_instances(region="ap-south-1", profile="dc")`
- `aws_list_ec2_instances_memory_lt_2gb(region="ap-south-1", profile="dc")`
- `list_aws_ec2_instances_less_than_2gb_memory(region="ap-south-1", profile="dc")` (friendly alias)
- `aws_list_ec2_instances_max_memory(region="ap-south-1", max_memory_mib=2048, profile="dc")`
- `aws_list_ec2_instances_cpu_utilization_filter(threshold_percent, comparator="gt|gte|lt|lte", region="ap-south-1", profile="dc", lookback_minutes=15)`
- `list_aws_ec2_instances_cpu_greater_than(threshold_percent=50, region="ap-south-1", profile="dc", lookback_minutes=15)`
- `list_aws_ec2_instances_cpu_less_than(threshold_percent=70, region="ap-south-1", profile="dc", lookback_minutes=15)`
- `aws_list_amis(region="ap-south-1", profile="dc", name_contains="al2023", owners=["amazon"], limit=20)`
- `aws_create_ec2_instance(ami_id, instance_type, region="ap-south-1", profile="dc", security_group_ids=None, vpc_id=None, subnet_id=None, ...)`
- `aws_start_ec2_instances(instance_ids, region="ap-south-1", profile="dc")`
- `aws_stop_ec2_instances(instance_ids, region="ap-south-1", profile="dc")`
- `aws_terminate_ec2_instances(instance_ids, region="ap-south-1", profile="dc", dry_run=false)`

## Next steps

- Add “create instance” and “terminate instance” flows behind explicit allow-lists.
- Add policy guardrails (approved regions, instance types, tags).
- Add audit logging + request IDs.

## Team Web IDE (Next.js + FastAPI)

This repo also contains a **team-hosted** “Cursor-like” web UI:

- `apps/web`: Next.js frontend
- `services/api`: FastAPI backend (OpenAI tool loop + MCP stdio client + MySQL + OIDC)
- `infra/terraform`: starter AWS deploy (VPC/RDS/ECS/ALB)

### Local dev (high level)

1) Run API:

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ../../
pip install -e .
uvicorn ide_platform_api.main:app --reload --port 8000
```

2) Run Web:

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

3) Configure OIDC in `services/api/.env` (or set `AUTH_DISABLED=true` for local dev only).

### Docker build contexts

- API image build context is the **repo root** (see `services/api/Dockerfile`).

### AWS deployment notes

- Use `infra/terraform` as a starting point; you still need TLS, secrets, and IAM hardening for production.
