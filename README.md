# cloud-mcp-agent (Python MCP server)

This is a Python **MCP server** (using `fastmcp`) that lets operators authenticate via standard cloud SDK mechanisms and run tools like:

- List AWS EC2 instances
- Start/stop AWS EC2 instances
- List Azure VMs
- List GCP Compute Engine instances

## Prerequisites

- Python 3.10+
- Cloud CLIs (recommended):
  - AWS CLI (`aws`)
  - Azure CLI (`az`)
  - gcloud (`gcloud`)

## Install

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
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

- `aws_list_ec2_instances(region, profile=None)`
- `aws_start_ec2_instances(instance_ids, region, profile=None)`
- `aws_stop_ec2_instances(instance_ids, region, profile=None)`
- `azure_list_vms(subscription_id)`
- `gcp_list_instances(project, zone)`

## Next steps

- Add “create instance” and “terminate instance” flows behind explicit allow-lists.
- Add policy guardrails (approved regions, instance types, tags).
- Add audit logging + request IDs.
