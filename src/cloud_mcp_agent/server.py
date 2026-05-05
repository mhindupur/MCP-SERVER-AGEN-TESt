from __future__ import annotations

from typing import Optional

from fastmcp import FastMCP

from cloud_mcp_agent.providers.aws import list_ec2_instances, start_ec2_instances, stop_ec2_instances
from cloud_mcp_agent.providers.azure import list_vms
from cloud_mcp_agent.providers.gcp import list_instances

mcp = FastMCP("cloud-mcp-agent")


@mcp.tool
def aws_list_ec2_instances(region: str, profile: Optional[str] = None):
    """List EC2 instances in a region."""
    return list_ec2_instances(region=region, profile=profile)


@mcp.tool
def aws_start_ec2_instances(instance_ids: list[str], region: str, profile: Optional[str] = None):
    """Start one or more EC2 instances by instance id."""
    return start_ec2_instances(instance_ids=instance_ids, region=region, profile=profile)


@mcp.tool
def aws_stop_ec2_instances(instance_ids: list[str], region: str, profile: Optional[str] = None):
    """Stop one or more EC2 instances by instance id."""
    return stop_ec2_instances(instance_ids=instance_ids, region=region, profile=profile)


@mcp.tool
def azure_list_vms(subscription_id: str):
    """List Azure VMs in a subscription."""
    return list_vms(subscription_id=subscription_id)


@mcp.tool
def gcp_list_instances(project: str, zone: str):
    """List GCP Compute Engine instances in a zone."""
    return list_instances(project=project, zone=zone)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
