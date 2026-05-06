from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ide_platform_api.aws_sts import AwsTemporaryCredentials
from ide_platform_api.config import settings

T = TypeVar("T")


@dataclass(frozen=True)
class McpEnv:
    aws: AwsTemporaryCredentials | None = None
    aws_region: str | None = None


def _merged_process_env(extra: dict[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update(extra)
    return env


def _aws_env(mcp_env: McpEnv) -> dict[str, str]:
    out: dict[str, str] = {}
    if mcp_env.aws_region:
        out["AWS_REGION"] = mcp_env.aws_region
        out["AWS_DEFAULT_REGION"] = mcp_env.aws_region
    if mcp_env.aws:
        # Ensure boto3 uses env credentials, not profiles.
        out["AWS_ACCESS_KEY_ID"] = mcp_env.aws.access_key_id
        out["AWS_SECRET_ACCESS_KEY"] = mcp_env.aws.secret_access_key
        out["AWS_SESSION_TOKEN"] = mcp_env.aws.session_token
        out.pop("AWS_PROFILE", None)
    return out


async def with_mcp_session(
    *,
    mcp_env: McpEnv,
    fn: Callable[[ClientSession], Awaitable[T]],
) -> T:
    extra_env = _aws_env(mcp_env)
    params = StdioServerParameters(
        command=settings.mcp_command,
        args=settings.mcp_args,
        cwd=settings.mcp_cwd,
        env=_merged_process_env(extra_env),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def run_mcp_sync(mcp_env: McpEnv, fn: Callable[[ClientSession], Awaitable[T]]) -> T:
    return anyio.run(with_mcp_session, mcp_env=mcp_env, fn=fn)
