from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import boto3


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
