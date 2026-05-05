from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import boto3


@dataclass(frozen=True)
class AwsInstanceSummary:
    instance_id: str
    state: str
    instance_type: str
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
                        name=name,
                        private_ip=inst.get("PrivateIpAddress"),
                        public_ip=inst.get("PublicIpAddress"),
                    ).__dict__
                )
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
