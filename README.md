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

### Azure

Recommended:

```bash
az login
```

Then `DefaultAzureCredential` will typically pick it up.

### GCP

Recommended:

```bash
gcloud auth application-default login
```

## Tools exposed

- `aws_list_ec2_instances(region="ap-south-1", profile="dc")`
- `aws_list_ec2_instances_memory_lt_2gb(region="ap-south-1", profile="dc")`
- `list_aws_ec2_instances_less_than_2gb_memory(region="ap-south-1", profile="dc")` (friendly alias)
- `aws_list_ec2_instances_max_memory(region="ap-south-1", max_memory_mib=2048, profile="dc")`
- `aws_list_ec2_instances_cpu_utilization_filter(threshold_percent, comparator="gt|gte|lt|lte", region="ap-south-1", profile="dc", lookback_minutes=15)`
- `list_aws_ec2_instances_cpu_greater_than(threshold_percent=50, region="ap-south-1", profile="dc", lookback_minutes=15)`
- `list_aws_ec2_instances_cpu_less_than(threshold_percent=70, region="ap-south-1", profile="dc", lookback_minutes=15)`
- `aws_start_ec2_instances(instance_ids, region="ap-south-1", profile="dc")`
- `aws_stop_ec2_instances(instance_ids, region="ap-south-1", profile="dc")`

## Next steps

- Add “create instance” and “terminate instance” flows behind explicit allow-lists.
- Add policy guardrails (approved regions, instance types, tags).
- Add audit logging + request IDs.
