from __future__ import annotations

from typing import Optional

from fastmcp import FastMCP

from cloud_mcp_agent.providers.aws import (
    create_ec2_instance,
    list_amis,
    list_ec2_instances,
    list_ec2_instances_max_memory as _list_ec2_instances_max_memory,
    list_ec2_instances_by_cpu_utilization,
    start_ec2_instances,
    stop_ec2_instances,
    terminate_ec2_instances,
)
from cloud_mcp_agent.providers.aws_topology import describe_infra_topology

mcp = FastMCP("cloud-mcp-agent")


@mcp.tool
def aws_list_ec2_instances(region: str = "ap-south-1", profile: str = "dc"):
    """List EC2 instances in a region (defaults: ap-south-1, profile=dc)."""
    return list_ec2_instances(region=region, profile=profile)


@mcp.tool
def aws_start_ec2_instances(
    instance_ids: list[str], region: str = "ap-south-1", profile: str = "dc"
):
    """Start one or more EC2 instances by instance id (defaults: ap-south-1, profile=dc)."""
    return start_ec2_instances(instance_ids=instance_ids, region=region, profile=profile)


@mcp.tool
def aws_stop_ec2_instances(
    instance_ids: list[str], region: str = "ap-south-1", profile: str = "dc"
):
    """Stop one or more EC2 instances by instance id (defaults: ap-south-1, profile=dc)."""
    return stop_ec2_instances(instance_ids=instance_ids, region=region, profile=profile)


@mcp.tool
def aws_terminate_ec2_instances(
    instance_ids: list[str],
    region: str = "ap-south-1",
    profile: str = "dc",
    dry_run: bool = False,
):
    """
    Terminate one or more EC2 instances by instance id.

    Use `dry_run=true` first if you want to validate permissions before terminating.
    """
    return terminate_ec2_instances(instance_ids=instance_ids, region=region, profile=profile, dry_run=dry_run)


@mcp.tool
def aws_list_ec2_instances_memory_lt_2gb(region: str = "ap-south-1", profile: str = "dc"):
    """
    List AWS EC2 instances with LESS THAN 2 GB memory (instance-type memory <= 2048 MiB).

    If the user asks in plain English like:
    - "List out aws instance which has less than 2 GB Memory"
    - "Show EC2 instances under 2GB RAM"
    this is the tool to use.

    Defaults: region=ap-south-1, profile=dc.
    """
    return _list_ec2_instances_max_memory(region=region, max_memory_mib=2048, profile=profile)


@mcp.tool
def list_aws_ec2_instances_less_than_2gb_memory(region: str = "ap-south-1", profile: str = "dc"):
    """
    Friendly alias for `aws_list_ec2_instances_memory_lt_2gb`.

    Meaning: "List out AWS EC2 instances which has less than 2 GB memory".
    Defaults: region=ap-south-1, profile=dc.
    """
    return _list_ec2_instances_max_memory(region=region, max_memory_mib=2048, profile=profile)


@mcp.tool
def aws_list_ec2_instances_max_memory(
    region: str = "ap-south-1", max_memory_mib: int = 2048, profile: str = "dc"
):
    """List EC2 instances whose instance-type memory is <= max_memory_mib (defaults: ap-south-1, profile=dc)."""
    return _list_ec2_instances_max_memory(region=region, max_memory_mib=max_memory_mib, profile=profile)


@mcp.tool
def aws_list_ec2_instances_cpu_utilization_filter(
    threshold_percent: float,
    comparator: str = "gt",
    region: str = "ap-south-1",
    profile: str = "dc",
    lookback_minutes: int = 15,
):
    """
    Filter EC2 instances by CloudWatch CPUUtilization.

    Semantic examples this tool should match:
    - "fetch servers which CPU is greater than 50%"
    - "CPU > 80%"
    - "CPU utilization < 70%"

    Args:
      comparator: one of "gt", "gte", "lt", "lte"
      threshold_percent: CPU utilization threshold in percent (0-100+)
      lookback_minutes: how far back to look (we return the most recent datapoint)
      region/profile default to ap-south-1 / dc
    """
    return list_ec2_instances_by_cpu_utilization(
        region=region,
        threshold_percent=threshold_percent,
        comparator=comparator,  # type: ignore[arg-type]
        lookback_minutes=lookback_minutes,
        profile=profile,
    )


@mcp.tool
def list_aws_ec2_instances_cpu_greater_than(
    threshold_percent: float = 50.0,
    region: str = "ap-south-1",
    profile: str = "dc",
    lookback_minutes: int = 15,
):
    """
    Friendly alias for: "fetch servers which CPU utilization is greater than X%".

    Examples:
    - CPU > 80%  => threshold_percent=80
    - CPU > 50%  => threshold_percent=50
    """
    return list_ec2_instances_by_cpu_utilization(
        region=region,
        threshold_percent=threshold_percent,
        comparator="gt",
        lookback_minutes=lookback_minutes,
        profile=profile,
    )


@mcp.tool
def list_aws_ec2_instances_cpu_less_than(
    threshold_percent: float = 70.0,
    region: str = "ap-south-1",
    profile: str = "dc",
    lookback_minutes: int = 15,
):
    """
    Friendly alias for: "fetch servers which CPU utilization is less than X%".

    Example:
    - CPU utilization < 70% => threshold_percent=70
    """
    return list_ec2_instances_by_cpu_utilization(
        region=region,
        threshold_percent=threshold_percent,
        comparator="lt",
        lookback_minutes=lookback_minutes,
        profile=profile,
    )


@mcp.tool
def aws_create_ec2_instance(
    ami_id: str,
    instance_type: str,
    region: str = "ap-south-1",
    profile: str = "dc",
    key_name: Optional[str] = None,
    name: Optional[str] = None,
    security_group_ids: Optional[list[str]] = None,
    vpc_id: Optional[str] = None,
    subnet_id: Optional[str] = None,
    assign_public_ip: Optional[bool] = None,
    iam_instance_profile_arn: Optional[str] = None,
    user_data_b64: Optional[str] = None,
    tags: Optional[dict[str, str]] = None,
    count: int = 1,
    dry_run: bool = False,
):
    """
    Spin up (create) a new EC2 instance.

    Required:
    - ami_id
    - instance_type

    Common optional inputs:
    - region/profile (default ap-south-1/dc)
    - security_group_ids
    - vpc_id / subnet_id
    - key_name (SSH key pair name)
    - name / tags

    Defaults if not provided:
    - Uses **default VPC**, a **default subnet**, and the **default security group**.
    """
    return create_ec2_instance(
        region=region,
        ami_id=ami_id,
        instance_type=instance_type,
        profile=profile,
        key_name=key_name,
        name=name,
        security_group_ids=security_group_ids,
        vpc_id=vpc_id,
        subnet_id=subnet_id,
        assign_public_ip=assign_public_ip,
        iam_instance_profile_arn=iam_instance_profile_arn,
        user_data_b64=user_data_b64,
        tags=tags,
        count=count,
        dry_run=dry_run,
    )


@mcp.tool
def aws_list_amis(
    region: str = "ap-south-1",
    profile: str = "dc",
    owners: Optional[list[str]] = None,
    name_contains: Optional[str] = "al2023",
    architecture: Optional[str] = "x86_64",
    most_recent: bool = True,
    limit: int = 20,
):
    """
    List available AMIs in a region so users can pick a valid `ami_id`.

    Example user intent:
    - "Show me available AMIs for ap-south-1"
    - "List Amazon Linux 2023 AMIs"

    Defaults:
    - name_contains='al2023' (Amazon Linux 2023)
    - owners defaults to ['amazon'] (official images)
    """
    return list_amis(
        region=region,
        profile=profile,
        owners=owners,
        name_contains=name_contains,
        architecture=architecture,
        most_recent=most_recent,
        limit=limit,
    )


@mcp.tool
def aws_describe_infra_topology(region: str = "ap-south-1", profile: str = "dc"):
    """
    Describe EC2 instances with VPC, subnets, and security groups for infrastructure visualization.

    Returns a topology graph: vpcs, subnets, security_groups, instances, edges, and summary counts.
    """
    return describe_infra_topology(region=region, profile=profile)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
