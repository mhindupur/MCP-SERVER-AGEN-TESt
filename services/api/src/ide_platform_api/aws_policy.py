from __future__ import annotations

from ide_platform_api.config import settings


def _normalize_groups(claims: dict) -> list[str]:
    # Keycloak often uses: realm_access.roles, resource_access.*.roles, or "groups"
    groups: list[str] = []
    if isinstance(claims.get("groups"), list):
        groups.extend([str(x) for x in claims["groups"]])
    ra = claims.get("realm_access") or {}
    if isinstance(ra, dict) and isinstance(ra.get("roles"), list):
        groups.extend([str(x) for x in ra["roles"]])
    return [g for g in groups if g]


def pick_role_arn_for_user(claims: dict) -> str | None:
    """
    Minimal mapping strategy (intentionally simple for scaffolding):
    - If only one role is allow-listed, use it.
    - Else if AWS_DEFAULT_ROLE_ARN is set and allow-listed, use it.
    - Else return None (caller must handle).
    """
    allowed = set(settings.aws_allowed_role_arns)
    if settings.aws_default_role_arn:
        allowed.add(settings.aws_default_role_arn)

    allowed_list = sorted([a for a in allowed if a])
    if not allowed_list:
        return None

    # Future: map group -> role via DB or env JSON. For now, use defaults.
    _ = _normalize_groups(claims)  # reserved for future mapping

    if len(allowed_list) == 1:
        return allowed_list[0]

    if settings.aws_default_role_arn and settings.aws_default_role_arn in allowed_list:
        return settings.aws_default_role_arn

    return None


def assert_role_allowed(role_arn: str) -> None:
    allowed = set(settings.aws_allowed_role_arns)
    if settings.aws_default_role_arn:
        allowed.add(settings.aws_default_role_arn)
    if role_arn not in allowed:
        raise PermissionError("Requested AWS role is not allow-listed for this deployment.")
