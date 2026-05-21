from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from mcp import ClientSession
from openai import OpenAI

from ide_platform_api.config import settings
from ide_platform_api.mcp_client import McpEnv, with_mcp_session


@dataclass(frozen=True)
class ChatTrace:
    steps: list[dict[str, Any]]


@dataclass(frozen=True)
class PendingActionRequired(Exception):
    tool_name: str
    args: dict[str, Any]
    reason: str = "pending_action_required"


def _openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)


def _to_openai_tools(mcp_tools) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for t in mcp_tools:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


async def run_openai_mcp_chat(
    *,
    user_text: str,
    mcp_env: McpEnv,
    system_prompt: str | None = None,
    model: str | None = None,
    on_tool_result: Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]] | None = None,
    on_trace_step: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> tuple[str, ChatTrace]:
    """
    Single request multi-step tool loop:
    - Pull MCP tool schemas once
    - Call OpenAI with tools
    - Execute tool calls via MCP
    """
    client = _openai_client()
    use_model = model or settings.openai_model
    trace_steps: list[dict[str, Any]] = []

    async def _list_tools(session: ClientSession):
        return (await session.list_tools()).tools

    mcp_tools = await with_mcp_session(mcp_env=mcp_env, fn=_list_tools)
    openai_tools = _to_openai_tools(mcp_tools)

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    async def _call_tool(session: ClientSession, name: str, arguments: dict[str, Any]):
        return await session.call_tool(name, arguments)

    for _ in range(12):
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model=use_model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = completion.choices[0].message
        tool_calls = choice.tool_calls or []

        # Append assistant message (including tool calls if present)
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if choice.content:
            assistant_msg["content"] = choice.content
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        if not tool_calls:
            final = choice.content or ""
            return final, ChatTrace(steps=trace_steps)

        for tc in tool_calls:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args) if raw_args else {}
                if not isinstance(args, dict):
                    args = {"_raw": args, "_raw_text": raw_args}
            except json.JSONDecodeError:
                args = {"_raw": raw_args}

            step = {"type": "tool_call", "name": name, "args": args}
            trace_steps.append(step)
            if on_trace_step is not None:
                await on_trace_step(step)

            # Cursor-like gating for destructive tool calls: do not execute until user approves.
            if name == "aws_terminate_ec2_instances" and not bool(args.get("dry_run", False)):
                instance_ids = args.get("instance_ids")
                if not isinstance(instance_ids, list) or not instance_ids:
                    payload = {
                        "error": "Invalid tool arguments for aws_terminate_ec2_instances. Expected {instance_ids:[...]}",
                        "got": args,
                    }
                    step = {"type": "tool_result", "name": name, "result": payload, "isError": True}
                    trace_steps.append(step)
                    if on_trace_step is not None:
                        await on_trace_step(step)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(payload),
                        }
                    )
                    continue

                raise PendingActionRequired(tool_name=name, args=args)

            async def _run_one(session: ClientSession, name=name, args=args):
                return await _call_tool(session, name, args)

            result = await with_mcp_session(mcp_env=mcp_env, fn=_run_one)

            # `CallToolResult` is pydantic; keep a compact representation
            payload: dict[str, Any]
            try:
                payload = result.model_dump()
            except Exception:
                payload = {"repr": repr(result)}

            step = {"type": "tool_result", "name": name, "result": payload}
            trace_steps.append(step)
            if on_trace_step is not None:
                await on_trace_step(step)

            if on_tool_result is not None:
                await on_tool_result(name, args, payload)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(payload)[:200000],
                }
            )

    raise RuntimeError("Tool loop exceeded max steps")
