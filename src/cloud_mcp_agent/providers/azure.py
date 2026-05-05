from __future__ import annotations

from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient


def list_vms(*, subscription_id: str) -> list[dict[str, Any]]:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    client = ComputeManagementClient(credential, subscription_id)

    out: list[dict[str, Any]] = []
    for vm in client.virtual_machines.list_all():
        out.append(
            {
                "id": vm.id,
                "name": vm.name,
                "location": vm.location,
                "vm_size": (vm.hardware_profile.vm_size if vm.hardware_profile else None),
            }
        )
    return out
