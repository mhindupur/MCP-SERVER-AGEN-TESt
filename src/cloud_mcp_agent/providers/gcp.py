from __future__ import annotations

from typing import Any

from google.cloud import compute_v1


def list_instances(*, project: str, zone: str) -> list[dict[str, Any]]:
    client = compute_v1.InstancesClient()
    out: list[dict[str, Any]] = []

    for inst in client.list(project=project, zone=zone):
        out.append(
            {
                "id": str(inst.id) if inst.id is not None else None,
                "name": inst.name,
                "machine_type": inst.machine_type,
                "status": inst.status,
                "zone": zone,
            }
        )
    return out
