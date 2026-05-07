from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import boto3
import os


@dataclass(frozen=True)
class AwsInstanceSummary:
    instance_id: str
    state: str
    instance_type: str
    memory_mib: Optional[int]
    name: Optional[str]
    private_ip: Optional[str]
    public_ip: Optional[str]


def _session(region: str, profile: Optional[str]) -> boto3.Session:
    # If explicit env credentials are present, prefer them over named profiles.
    # This enables server-side STS temporary creds without fighting AWS_PROFILE.
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return boto3.Session(region_name=region)
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def list_ec2_instances(*, region: str, profile: Optional[str] = None) -> list[dict[str, Any]]:
    ec2 = _session(region, profile).client("ec2")
    paginator = ec2.get_paginator("describe_instances")

    out: list[dict[str, Any]] = []
    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                name = None
                for tag in inst.get("Tags", []) or []:
                    if tag.get("Key") == "Name":
                        name = tag.get("Value")
                        break

                out.append(
                    AwsInstanceSummary(
                        instance_id=inst["InstanceId"],
                        state=((inst.get("State") or {}).get("Name") or "unknown"),
                        instance_type=inst.get("InstanceType") or "unknown",
                        memory_mib=None,
                        name=name,
                        private_ip=inst.get("PrivateIpAddress"),
                        public_ip=inst.get("PublicIpAddress"),
                    ).__dict__
                )
    return out


def _describe_instance_type_memory_mib(
    *, ec2: Any, instance_types: list[str]
) -> dict[str, Optional[int]]:
    """
    Returns map of instance_type -> memory_mib.

    Uses EC2 `DescribeInstanceTypes` which returns `MemoryInfo.SizeInMiB`.
    """
    memory_by_type: dict[str, Optional[int]] = {}
    if not instance_types:
        return memory_by_type

    # API limit is 100 instance types per call.
    chunk_size = 100
    for i in range(0, len(instance_types), chunk_size):
        chunk = instance_types[i : i + chunk_size]
        resp = ec2.describe_instance_types(InstanceTypes=chunk)
        for it in resp.get("InstanceTypes", []) or []:
            t = it.get("InstanceType")
            mem = ((it.get("MemoryInfo") or {}).get("SizeInMiB"))
            if isinstance(t, str):
                memory_by_type[t] = int(mem) if isinstance(mem, (int, float)) else None

    # Ensure every requested type has a key (even if missing from response).
    for t in instance_types:
        memory_by_type.setdefault(t, None)
    return memory_by_type


def list_ec2_instances_max_memory(
    *,
    region: str,
    max_memory_mib: int = 2048,
    profile: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    List EC2 instances in a region whose instance-type memory is <= max_memory_mib.

    Note: EC2 instance memory is derived from `DescribeInstanceTypes` (per instance type),
    not from the running VM itself.
    """
    ec2 = _session(region, profile).client("ec2")
    paginator = ec2.get_paginator("describe_instances")

    raw_instances: list[dict[str, Any]] = []
    instance_types: set[str] = set()

    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                raw_instances.append(inst)
                t = inst.get("InstanceType")
                if isinstance(t, str) and t:
                    instance_types.add(t)

    memory_by_type = _describe_instance_type_memory_mib(
        ec2=ec2, instance_types=sorted(instance_types)
    )

    out: list[dict[str, Any]] = []
    for inst in raw_instances:
        t = inst.get("InstanceType") or "unknown"
        mem = memory_by_type.get(t) if isinstance(t, str) else None
        if mem is None:
            continue
        if mem > max_memory_mib:
            continue

        name = None
        for tag in inst.get("Tags", []) or []:
            if tag.get("Key") == "Name":
                name = tag.get("Value")
                break

        out.append(
            AwsInstanceSummary(
                instance_id=inst["InstanceId"],
                state=((inst.get("State") or {}).get("Name") or "unknown"),
                instance_type=t if isinstance(t, str) else "unknown",
                memory_mib=mem,
                name=name,
                private_ip=inst.get("PrivateIpAddress"),
                public_ip=inst.get("PublicIpAddress"),
            ).__dict__
        )

    # Smallest instances first.
    out.sort(key=lambda x: (x.get("memory_mib") or 10**9, x.get("instance_type") or "", x.get("instance_id") or ""))
    return out


def start_ec2_instances(
    *, instance_ids: list[str], region: str, profile: Optional[str] = None
) -> dict[str, Any]:
    ec2 = _session(region, profile).client("ec2")
    resp = ec2.start_instances(InstanceIds=instance_ids)
    return {"starting_instances": resp.get("StartingInstances", [])}


def stop_ec2_instances(
    *, instance_ids: list[str], region: str, profile: Optional[str] = None
) -> dict[str, Any]:
    ec2 = _session(region, profile).client("ec2")
    resp = ec2.stop_instances(InstanceIds=instance_ids)
    return {"stopping_instances": resp.get("StoppingInstances", [])}


def terminate_ec2_instances(
    *, instance_ids: list[str], region: str, profile: Optional[str] = None, dry_run: bool = False
) -> dict[str, Any]:
    ec2 = _session(region, profile).client("ec2")
    resp = ec2.terminate_instances(InstanceIds=instance_ids, DryRun=dry_run)
    return {"terminating_instances": resp.get("TerminatingInstances", [])}


def _extract_name_from_tags(tags: Any) -> Optional[str]:
    for tag in tags or []:
        if (tag or {}).get("Key") == "Name":
            return (tag or {}).get("Value")
    return None


def _instance_summary_from_instance(inst: dict[str, Any], *, memory_mib: Optional[int]) -> dict[str, Any]:
    return AwsInstanceSummary(
        instance_id=inst["InstanceId"],
        state=((inst.get("State") or {}).get("Name") or "unknown"),
        instance_type=inst.get("InstanceType") or "unknown",
        memory_mib=memory_mib,
        name=_extract_name_from_tags(inst.get("Tags")),
        private_ip=inst.get("PrivateIpAddress"),
        public_ip=inst.get("PublicIpAddress"),
    ).__dict__


Comparator = Literal["gt", "gte", "lt", "lte"]


def list_ec2_instances_by_cpu_utilization(
    *,
    region: str,
    threshold_percent: float,
    comparator: Comparator = "gt",
    lookback_minutes: int = 15,
    period_seconds: int = 300,
    statistic: Literal["Average", "Maximum", "Minimum"] = "Average",
    profile: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    List EC2 instances filtered by CloudWatch CPUUtilization.

    - Uses CloudWatch `GetMetricData` for AWS/EC2 CPUUtilization per InstanceId.
    - Filters by comparator vs threshold_percent (e.g., gt 50.0, lt 70.0).
    - `lookback_minutes` controls the time window; we take the most recent datapoint.
    """
    if lookback_minutes <= 0:
        raise ValueError("lookback_minutes must be > 0")
    if period_seconds <= 0:
        raise ValueError("period_seconds must be > 0")

    ec2 = _session(region, profile).client("ec2")
    cw = _session(region, profile).client("cloudwatch")

    # 1) Gather instances (and names) first.
    paginator = ec2.get_paginator("describe_instances")
    instances: list[dict[str, Any]] = []
    instance_ids: list[str] = []
    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                iid = inst.get("InstanceId")
                if not isinstance(iid, str) or not iid:
                    continue
                instances.append(inst)
                instance_ids.append(iid)

    if not instance_ids:
        return []

    # 2) Query CPUUtilization in chunks (CloudWatch max 500 MetricDataQueries/request).
    start = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    end = datetime.now(timezone.utc)

    def match(value: float) -> bool:
        if comparator == "gt":
            return value > threshold_percent
        if comparator == "gte":
            return value >= threshold_percent
        if comparator == "lt":
            return value < threshold_percent
        if comparator == "lte":
            return value <= threshold_percent
        raise ValueError(f"Unsupported comparator: {comparator}")

    cpu_by_instance: dict[str, dict[str, Any]] = {}
    chunk_size = 200
    for i in range(0, len(instance_ids), chunk_size):
        chunk = instance_ids[i : i + chunk_size]
        queries = []
        for iid in chunk:
            queries.append(
                {
                    "Id": f"i{abs(hash(iid)) % 10_000_000}".replace("-", ""),
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EC2",
                            "MetricName": "CPUUtilization",
                            "Dimensions": [{"Name": "InstanceId", "Value": iid}],
                        },
                        "Period": period_seconds,
                        "Stat": statistic,
                    },
                    "ReturnData": True,
                    "Label": iid,
                }
            )

        resp = cw.get_metric_data(MetricDataQueries=queries, StartTime=start, EndTime=end, ScanBy="TimestampDescending")
        for r in resp.get("MetricDataResults", []) or []:
            iid = r.get("Label")
            if not isinstance(iid, str) or not iid:
                continue
            values = r.get("Values") or []
            timestamps = r.get("Timestamps") or []
            if not values:
                continue
            cpu_by_instance[iid] = {
                "cpu_percent": float(values[0]),
                "cpu_timestamp": (timestamps[0].isoformat() if timestamps else None),
                "cpu_statistic": statistic,
                "cpu_lookback_minutes": lookback_minutes,
                "cpu_period_seconds": period_seconds,
            }

    # 3) Filter instances.
    out: list[dict[str, Any]] = []
    for inst in instances:
        iid = inst.get("InstanceId")
        if not isinstance(iid, str) or iid not in cpu_by_instance:
            continue
        cpu = cpu_by_instance[iid]["cpu_percent"]
        if not match(cpu):
            continue

        item = _instance_summary_from_instance(inst, memory_mib=None)
        item.update(cpu_by_instance[iid])
        out.append(item)

    out.sort(key=lambda x: -(x.get("cpu_percent") or 0.0))
    return out


def _default_vpc_id(*, ec2: Any) -> str:
    resp = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    vpcs = resp.get("Vpcs", []) or []
    if vpcs:
        return vpcs[0]["VpcId"]
    # Fallback: pick first VPC if no default exists
    resp2 = ec2.describe_vpcs()
    vpcs2 = resp2.get("Vpcs", []) or []
    if not vpcs2:
        raise RuntimeError("No VPCs found in this region.")
    return vpcs2[0]["VpcId"]


def _default_subnet_id(*, ec2: Any, vpc_id: str) -> str:
    # Prefer default subnets (one per AZ) if present.
    resp = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnets = resp.get("Subnets", []) or []
    if not subnets:
        raise RuntimeError(f"No subnets found for vpc_id={vpc_id}.")

    default_subnets = [s for s in subnets if s.get("DefaultForAz") is True]
    pick_from = default_subnets or subnets
    # Deterministic selection
    pick_from.sort(key=lambda s: (s.get("AvailabilityZone") or "", s.get("SubnetId") or ""))
    return pick_from[0]["SubnetId"]


def _default_security_group_id(*, ec2: Any, vpc_id: str) -> str:
    resp = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": ["default"]},
        ]
    )
    groups = resp.get("SecurityGroups", []) or []
    if groups:
        return groups[0]["GroupId"]
    raise RuntimeError(f"Default security group not found for vpc_id={vpc_id}.")


def create_ec2_instance(
    *,
    region: str,
    ami_id: str,
    instance_type: str,
    profile: Optional[str] = None,
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
) -> dict[str, Any]:
    """
    Create (RunInstances) an EC2 instance with sensible defaults.

    If vpc_id/subnet_id/security_group_ids are not provided:
    - picks the default VPC (or first VPC)
    - picks a default subnet in that VPC (or first subnet)
    - uses the default security group in that VPC
    """
    if count < 1 or count > 20:
        raise ValueError("count must be between 1 and 20")

    ec2 = _session(region, profile).client("ec2")

    resolved_vpc_id = vpc_id or _default_vpc_id(ec2=ec2)
    resolved_subnet_id = subnet_id or _default_subnet_id(ec2=ec2, vpc_id=resolved_vpc_id)
    resolved_sg_ids = security_group_ids or [_default_security_group_id(ec2=ec2, vpc_id=resolved_vpc_id)]

    # Tags
    merged_tags: dict[str, str] = {}
    if tags:
        merged_tags.update({str(k): str(v) for k, v in tags.items()})
    if name:
        merged_tags.setdefault("Name", name)

    tag_specifications = []
    if merged_tags:
        tag_specifications = [
            {
                "ResourceType": "instance",
                "Tags": [{"Key": k, "Value": v} for k, v in merged_tags.items()],
            }
        ]

    # Public IP behavior is only controllable via NetworkInterfaces.
    network_interfaces = [
        {
            "DeviceIndex": 0,
            "SubnetId": resolved_subnet_id,
            "Groups": resolved_sg_ids,
        }
    ]
    if assign_public_ip is not None:
        network_interfaces[0]["AssociatePublicIpAddress"] = bool(assign_public_ip)

    kwargs: dict[str, Any] = {
        "ImageId": ami_id,
        "InstanceType": instance_type,
        "MinCount": count,
        "MaxCount": count,
        "NetworkInterfaces": network_interfaces,
        "DryRun": dry_run,
    }
    if key_name:
        kwargs["KeyName"] = key_name
    if iam_instance_profile_arn:
        kwargs["IamInstanceProfile"] = {"Arn": iam_instance_profile_arn}
    if user_data_b64:
        # Caller should base64-encode if needed; boto3 expects plain string UserData.
        kwargs["UserData"] = user_data_b64
    if tag_specifications:
        kwargs["TagSpecifications"] = tag_specifications

    resp = ec2.run_instances(**kwargs)
    instances = resp.get("Instances", []) or []
    instance_ids = [i.get("InstanceId") for i in instances if isinstance(i.get("InstanceId"), str)]

    return {
        "instance_ids": instance_ids,
        "resolved": {
            "region": region,
            "vpc_id": resolved_vpc_id,
            "subnet_id": resolved_subnet_id,
            "security_group_ids": resolved_sg_ids,
            "assign_public_ip": assign_public_ip,
        },
    }


def list_amis(
    *,
    region: str,
    profile: Optional[str] = None,
    owners: Optional[list[str]] = None,
    name_contains: Optional[str] = None,
    architecture: Optional[str] = None,
    root_device_type: Optional[str] = "ebs",
    virtualization_type: Optional[str] = "hvm",
    most_recent: bool = True,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    List AMIs in a region (for selecting a valid ImageId).

    Defaults are tuned for common modern Linux AMIs:
    - root_device_type=ebs
    - virtualization_type=hvm
    - owners defaults to ['amazon'] if not provided
    """
    if limit < 1 or limit > 200:
        raise ValueError("limit must be between 1 and 200")

    ec2 = _session(region, profile).client("ec2")

    filters: list[dict[str, Any]] = []
    if name_contains:
        filters.append({"Name": "name", "Values": [f"*{name_contains}*"]})
    if architecture:
        filters.append({"Name": "architecture", "Values": [architecture]})
    if root_device_type:
        filters.append({"Name": "root-device-type", "Values": [root_device_type]})
    if virtualization_type:
        filters.append({"Name": "virtualization-type", "Values": [virtualization_type]})

    use_owners = owners or ["amazon"]

    resp = ec2.describe_images(Owners=use_owners, Filters=filters)
    images = resp.get("Images", []) or []

    def created(img: dict[str, Any]) -> str:
        return str(img.get("CreationDate") or "")

    images.sort(key=created, reverse=most_recent)
    images = images[:limit]

    out: list[dict[str, Any]] = []
    for img in images:
        out.append(
            {
                "image_id": img.get("ImageId"),
                "name": img.get("Name"),
                "description": img.get("Description"),
                "creation_date": img.get("CreationDate"),
                "architecture": img.get("Architecture"),
                "state": img.get("State"),
                "owner_id": img.get("OwnerId"),
                "platform_details": img.get("PlatformDetails"),
                "root_device_type": img.get("RootDeviceType"),
                "virtualization_type": img.get("VirtualizationType"),
            }
        )
    return out
