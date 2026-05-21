from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional

import boto3


def _ec2_client(
    *,
    region: str,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    session_token: Optional[str] = None,
    profile: Optional[str] = None,
):
    if access_key_id and secret_access_key:
        return boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
        )
    if profile:
        return boto3.Session(profile_name=profile, region_name=region).client("ec2")
    return boto3.client("ec2", region_name=region)


def _tags(inst: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in inst.get("Tags") or []:
        key = tag.get("Key")
        val = tag.get("Value")
        if isinstance(key, str):
            out[key] = str(val) if val is not None else ""
    return out


def _sg_rules(permissions: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for perm in permissions or []:
        for r in perm.get("IpRanges") or []:
            rules.append(
                {
                    "protocol": perm.get("IpProtocol"),
                    "from_port": perm.get("FromPort"),
                    "to_port": perm.get("ToPort"),
                    "cidr": r.get("CidrIp"),
                    "description": r.get("Description"),
                }
            )
        for r in perm.get("Ipv6Ranges") or []:
            rules.append(
                {
                    "protocol": perm.get("IpProtocol"),
                    "from_port": perm.get("FromPort"),
                    "to_port": perm.get("ToPort"),
                    "cidr": r.get("CidrIpv6"),
                    "description": r.get("Description"),
                }
            )
        for r in perm.get("UserIdGroupPairs") or []:
            rules.append(
                {
                    "protocol": perm.get("IpProtocol"),
                    "from_port": perm.get("FromPort"),
                    "to_port": perm.get("ToPort"),
                    "source_sg": r.get("GroupId"),
                    "description": r.get("Description"),
                }
            )
    return rules


def describe_infra_topology(
    *,
    region: str,
    profile: Optional[str] = None,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    session_token: Optional[str] = None,
) -> dict[str, Any]:
    """
    Aggregate EC2 instances and related VPC networking for visualization.
    """
    ec2 = _ec2_client(
        region=region,
        profile=profile,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
    )

    def fetch_vpcs():
        vpcs: list[dict[str, Any]] = []
        for page in ec2.get_paginator("describe_vpcs").paginate():
            for vpc in page.get("Vpcs") or []:
                tags = _tags(vpc)
                vpcs.append(
                    {
                        "id": vpc.get("VpcId"),
                        "cidr": vpc.get("CidrBlock"),
                        "name": tags.get("Name"),
                        "is_default": bool(vpc.get("IsDefault")),
                        "state": vpc.get("State"),
                    }
                )
        return vpcs

    def fetch_subnets():
        subnets: list[dict[str, Any]] = []
        for page in ec2.get_paginator("describe_subnets").paginate():
            for sn in page.get("Subnets") or []:
                tags = _tags(sn)
                subnets.append(
                    {
                        "id": sn.get("SubnetId"),
                        "vpc_id": sn.get("VpcId"),
                        "cidr": sn.get("CidrBlock"),
                        "az": sn.get("AvailabilityZone"),
                        "name": tags.get("Name"),
                        "public": bool(sn.get("MapPublicIpOnLaunch")),
                    }
                )
        return subnets

    def fetch_security_groups():
        sgs: list[dict[str, Any]] = []
        for page in ec2.get_paginator("describe_security_groups").paginate():
            for sg in page.get("SecurityGroups") or []:
                tags = _tags(sg)
                sgs.append(
                    {
                        "id": sg.get("GroupId"),
                        "vpc_id": sg.get("VpcId"),
                        "name": sg.get("GroupName") or tags.get("Name"),
                        "description": sg.get("Description"),
                        "inbound": _sg_rules(sg.get("IpPermissions")),
                        "outbound": _sg_rules(sg.get("IpPermissionsEgress")),
                    }
                )
        return sgs

    def fetch_instances():
        instances: list[dict[str, Any]] = []
        for page in ec2.get_paginator("describe_instances").paginate():
            for reservation in page.get("Reservations") or []:
                for inst in reservation.get("Instances") or []:
                    tags = _tags(inst)
                    sg_ids = [
                        g.get("GroupId")
                        for g in inst.get("SecurityGroups") or []
                        if g.get("GroupId")
                    ]
                    instances.append(
                        {
                            "instance_id": inst.get("InstanceId"),
                            "name": tags.get("Name"),
                            "state": (inst.get("State") or {}).get("Name"),
                            "instance_type": inst.get("InstanceType"),
                            "vpc_id": inst.get("VpcId"),
                            "subnet_id": inst.get("SubnetId"),
                            "az": inst.get("Placement", {}).get("AvailabilityZone"),
                            "private_ip": inst.get("PrivateIpAddress"),
                            "public_ip": inst.get("PublicIpAddress"),
                            "security_group_ids": sg_ids,
                            "eni_ids": [
                                eni.get("NetworkInterfaceId")
                                for eni in inst.get("NetworkInterfaces") or []
                                if eni.get("NetworkInterfaceId")
                            ],
                        }
                    )
        return instances

    vpcs: list[dict[str, Any]] = []
    subnets: list[dict[str, Any]] = []
    security_groups: list[dict[str, Any]] = []
    instances: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fetch_vpcs): "vpcs",
            pool.submit(fetch_subnets): "subnets",
            pool.submit(fetch_security_groups): "security_groups",
            pool.submit(fetch_instances): "instances",
        }
        for fut in as_completed(futures):
            key = futures[fut]
            result = fut.result()
            if key == "vpcs":
                vpcs = result
            elif key == "subnets":
                subnets = result
            elif key == "security_groups":
                security_groups = result
            else:
                instances = result

    sg_usage: dict[str, int] = {}
    for inst in instances:
        for sg_id in inst.get("security_group_ids") or []:
            sg_usage[sg_id] = sg_usage.get(sg_id, 0) + 1

    for sg in security_groups:
        sg["used_by_instances"] = sg_usage.get(sg["id"], 0)

    edges: list[dict[str, str]] = []
    vpc_ids = {v["id"] for v in vpcs if v.get("id")}
    subnet_ids = {s["id"] for s in subnets if s.get("id")}

    for sn in subnets:
        if sn.get("id") and sn.get("vpc_id"):
            edges.append({"from": f"subnet/{sn['id']}", "to": f"vpc/{sn['vpc_id']}", "type": "in_vpc"})

    for inst in instances:
        iid = inst.get("instance_id")
        if not iid:
            continue
        node = f"instance/{iid}"
        if inst.get("subnet_id"):
            edges.append({"from": node, "to": f"subnet/{inst['subnet_id']}", "type": "in_subnet"})
        elif inst.get("vpc_id"):
            edges.append({"from": node, "to": f"vpc/{inst['vpc_id']}", "type": "in_vpc"})
        for sg_id in inst.get("security_group_ids") or []:
            edges.append({"from": node, "to": f"sg/{sg_id}", "type": "uses_sg"})

    summary = {
        "instance_count": len(instances),
        "running_count": sum(1 for i in instances if i.get("state") == "running"),
        "vpc_count": len(vpcs),
        "subnet_count": len(subnets),
        "security_group_count": len(security_groups),
        "open_inbound_0_0_0_0": sum(
            1
            for sg in security_groups
            for rule in sg.get("inbound") or []
            if rule.get("cidr") in ("0.0.0.0/0", "::/0")
        ),
    }

    return {
        "region": region,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "vpcs": sorted(vpcs, key=lambda x: (x.get("name") or "", x.get("id") or "")),
        "subnets": sorted(subnets, key=lambda x: (x.get("vpc_id") or "", x.get("name") or "")),
        "security_groups": sorted(security_groups, key=lambda x: (-(x.get("used_by_instances") or 0), x.get("name") or "")),
        "instances": sorted(instances, key=lambda x: (x.get("name") or "", x.get("instance_id") or "")),
        "edges": edges,
    }
