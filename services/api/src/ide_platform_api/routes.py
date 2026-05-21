from __future__ import annotations

import json
import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from ide_platform_api.aws_policy import assert_role_allowed
from ide_platform_api.aws_sts import assume_role
from ide_platform_api.aws_topology import describe_infra_topology
from ide_platform_api.config import settings
from ide_platform_api.db import get_db
from ide_platform_api.deps import get_current_user
from ide_platform_api.mcp_client import McpEnv
from ide_platform_api.models import Conversation, Message, ToolAudit, User
from ide_platform_api.mcp_client import with_mcp_session
from ide_platform_api.openai_orchestrator import PendingActionRequired, run_openai_mcp_chat

router = APIRouter()

_EC2_INSTANCE_ID_RE = re.compile(r"\bi-[0-9a-f]{8,17}\b", re.IGNORECASE)


def _extract_instance_ids(text: str) -> list[str]:
    ids = _EC2_INSTANCE_ID_RE.findall(text or "")
    # Normalize to lowercase (AWS instance ids are hex)
    return [i.lower() for i in ids]


def _looks_like_terminate_intent(text: str) -> bool:
    t = (text or "").lower()
    return ("terminate" in t or "delete" in t) and ("ec2" in t or "instance" in t or "instances" in t)


def _pending_terminate_action(*, instance_ids: list[str], region: str) -> dict[str, Any]:
    return {
        "tool_name": "aws_terminate_ec2_instances",
        "args": {"instance_ids": instance_ids, "region": region, "dry_run": False},
        "explanation": {
            "why": ["You requested EC2 termination. This is destructive, so we require explicit approval."],
            "impact": ["Instance will be permanently terminated.", "This may delete the root EBS volume depending on settings."],
            "checks": ["Confirm this is not production.", "Confirm backups/snapshots exist if needed."],
        },
    }

def _require_role_arn(raw: str) -> str:
    role_arn = (raw or "").strip()
    if not role_arn:
        raise HTTPException(status_code=400, detail="aws_role_arn is required")
    if ":role/" not in role_arn:
        raise HTTPException(status_code=400, detail="aws_role_arn must be an IAM Role ARN (contains ':role/')")
    return role_arn


def _assume_role_or_400(*, role_arn: str, user_id: str) -> dict[str, Any]:
    try:
        return assume_role(
            role_arn=role_arn,
            session_name=f"ide-{user_id[:16]}",
            external_id=settings.aws_role_external_id,
        )
    except ClientError as e:
        code = (e.response.get("Error") or {}).get("Code") or "ClientError"
        msg = (e.response.get("Error") or {}).get("Message") or str(e)
        raise HTTPException(status_code=400, detail=f"AWS STS AssumeRole failed ({code}): {msg}") from e


class MeResponse(BaseModel):
    id: str
    email: str
    name: str | None = None


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(id=user.id, email=user.email, name=user.name)


class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: dict[str, Any]
    created_at: str


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    body: CreateConversationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = Conversation(user_id=user.id, title=body.title or "New chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse(id=conv.id, title=conv.title)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).all()
    return [ConversationResponse(id=r.id, title=r.title) for r in rows]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    out: list[MessageResponse] = []
    for m in rows:
        out.append(
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content_json,
                created_at=m.created_at.isoformat(),
            )
        )
    return out

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    aws_role_arn: str = Field(min_length=1, description="Required. IAM Role ARN to assume for every request.")
    aws_region: str | None = Field(default="ap-south-1")


class ChatResponse(BaseModel):
    reply: str
    trace: list[dict[str, Any]]


class ActionRunRequest(BaseModel):
    conversation_id: str | None = None
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    aws_role_arn: str = Field(min_length=1)
    aws_region: str | None = Field(default="ap-south-1")


class ActionRunResponse(BaseModel):
    ok: bool
    result: dict[str, Any] | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.get(Conversation, body.conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.add(Message(conversation_id=conv.id, role="user", content_json={"text": body.message}))
    db.commit()

    role_arn = _require_role_arn(body.aws_role_arn)

    # Always use the provided Role ARN for every request.
    # In auth-disabled/dev mode we skip allow-list enforcement, but still AssumeRole.
    if not settings.auth_disabled:
        assert_role_allowed(role_arn)

    creds = _assume_role_or_400(role_arn=role_arn, user_id=user.id)

    mcp_env = McpEnv(aws=creds, aws_region=body.aws_region)

    async def audit(name: str, args: dict[str, Any], payload: dict[str, Any]):
        db.add(
            ToolAudit(
                user_id=user.id,
                tool_name=name,
                args_json=args,
                result_meta_json={"result": payload},
            )
        )
        db.commit()

    system_prompt = (
        "You are an internal cloud operations assistant. "
        "Prefer using tools for AWS facts. "
        "Be concise and operational."
    )

    # Deterministic Cursor-style approval for termination requests.
    if _looks_like_terminate_intent(body.message):
        ids = _extract_instance_ids(body.message)
        if ids:
            pending_action = _pending_terminate_action(instance_ids=ids, region=body.aws_region or "ap-south-1")
            trace_steps = [{"type": "pending_action", "pending_action": pending_action}]
            reply = (
                "Approval required. I prepared the termination action but did not execute it. "
                "Click 'Approve & Run' to execute, or 'Copy' to edit before running."
            )
            db.add(Message(conversation_id=conv.id, role="assistant", content_json={"text": reply, "trace": trace_steps}))
            db.commit()
            return ChatResponse(reply=reply, trace=trace_steps)

    try:
        reply, trace = await run_openai_mcp_chat(
            user_text=body.message,
            mcp_env=mcp_env,
            system_prompt=system_prompt,
            on_tool_result=audit,
        )
    except PendingActionRequired as e:
        args = e.args if isinstance(e.args, dict) else {"_raw": e.args}
        if e.tool_name == "aws_terminate_ec2_instances":
            instance_ids = args.get("instance_ids")
            if not isinstance(instance_ids, list) or not instance_ids:
                reply = (
                    "I couldn't prepare a termination approval because `instance_ids` was missing. "
                    "Please include the instance id(s), e.g. `Terminate EC2 instance i-... in ap-south-1`."
                )
                trace_steps = [{"type": "tool_result", "name": e.tool_name, "result": {"error": "missing_instance_ids", "got": args}, "isError": True}]
                db.add(Message(conversation_id=conv.id, role="assistant", content_json={"text": reply, "trace": trace_steps}))
                db.commit()
                return ChatResponse(reply=reply, trace=trace_steps)

        pending_action = {
            "tool_name": e.tool_name,
            "args": args,
            "explanation": {
                "why": ["Termination is destructive and requires explicit user approval."],
                "impact": ["Instance will be permanently terminated.", "This may delete the root EBS volume depending on AMI settings."],
                "checks": ["Confirm this is not a production instance.", "Confirm you have snapshots/backups if needed."],
            },
        }
        trace_steps = [{"type": "pending_action", "pending_action": pending_action}]
        reply = (
            "Approval required. I prepared the termination action but did not execute it. "
            "Review the details and click 'Approve & Run' or use 'Copy' to edit the command."
        )
        db.add(Message(conversation_id=conv.id, role="assistant", content_json={"text": reply, "trace": trace_steps}))
        db.commit()
        return ChatResponse(reply=reply, trace=trace_steps)

    db.add(Message(conversation_id=conv.id, role="assistant", content_json={"text": reply, "trace": trace.steps}))
    db.commit()

    return ChatResponse(reply=reply, trace=trace.steps)


def _format_sse(event: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = db.get(Conversation, body.conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.add(Message(conversation_id=conv.id, role="user", content_json={"text": body.message}))
    db.commit()

    role_arn = _require_role_arn(body.aws_role_arn)

    if not settings.auth_disabled:
        assert_role_allowed(role_arn)

    creds = _assume_role_or_400(role_arn=role_arn, user_id=user.id)
    mcp_env = McpEnv(aws=creds, aws_region=body.aws_region)

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def audit(name: str, args: dict[str, Any], payload: dict[str, Any]):
        db.add(
            ToolAudit(
                user_id=user.id,
                tool_name=name,
                args_json=args,
                result_meta_json={"result": payload},
            )
        )
        db.commit()

    async def on_trace_step(step: dict[str, Any]):
        await queue.put({"type": "trace", "step": step})

    system_prompt = (
        "You are an internal cloud operations assistant. "
        "Prefer using tools for AWS facts. "
        "Be concise and operational."
    )

    async def runner():
        try:
            # Deterministic Cursor-style approval for termination requests.
            if _looks_like_terminate_intent(body.message):
                ids = _extract_instance_ids(body.message)
                if ids:
                    pending_action = _pending_terminate_action(instance_ids=ids, region=body.aws_region or "ap-south-1")
                    step = {"type": "pending_action", "pending_action": pending_action}
                    await queue.put({"type": "trace", "step": step})
                    await queue.put(
                        {
                            "type": "final",
                            "reply": (
                                "Approval required. I prepared the termination action but did not execute it. "
                                "Click 'Approve & Run' to execute, or 'Copy' to edit."
                            ),
                            "trace": [step],
                            "pending_action": pending_action,
                        }
                    )
                    return

            reply, trace = await run_openai_mcp_chat(
                user_text=body.message,
                mcp_env=mcp_env,
                system_prompt=system_prompt,
                on_tool_result=audit,
                on_trace_step=on_trace_step,
            )
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content_json={"text": reply, "trace": trace.steps},
                )
            )
            db.commit()
            await queue.put({"type": "final", "reply": reply, "trace": trace.steps})
        except PendingActionRequired as e:
            args = e.args if isinstance(e.args, dict) else {"_raw": e.args}
            if e.tool_name == "aws_terminate_ec2_instances":
                instance_ids = args.get("instance_ids")
                if not isinstance(instance_ids, list) or not instance_ids:
                    step = {"type": "tool_result", "name": e.tool_name, "result": {"error": "missing_instance_ids", "got": args}, "isError": True}
                    await queue.put({"type": "trace", "step": step})
                    await queue.put(
                        {
                            "type": "final",
                            "reply": (
                                "I couldn't prepare a termination approval because `instance_ids` was missing. "
                                "Please include the instance id(s), e.g. `Terminate EC2 instance i-... in ap-south-1`."
                            ),
                            "trace": [step],
                            "pending_action": None,
                        }
                    )
                    return

            pending_action = {
                "tool_name": e.tool_name,
                "args": args,
                "explanation": {
                    "why": ["Termination is destructive and requires explicit user approval."],
                    "impact": ["Instance will be permanently terminated.", "This may delete the root EBS volume depending on AMI settings."],
                    "checks": ["Confirm this is not a production instance.", "Confirm you have snapshots/backups if needed."],
                },
            }
            step = {"type": "pending_action", "pending_action": pending_action}
            await queue.put({"type": "trace", "step": step})
            await queue.put(
                {
                    "type": "final",
                    "reply": (
                        "Approval required. I prepared the termination action but did not execute it. "
                        "Click 'Approve & Run' to execute, or 'Copy' to edit."
                    ),
                    "trace": [step],
                    "pending_action": pending_action,
                }
            )
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def event_gen():
        yield _format_sse("ready", {"ok": True})
        while True:
            item = await queue.get()
            if item is None:
                break
            if item.get("type") == "trace":
                yield _format_sse("trace", item)
            elif item.get("type") == "final":
                yield _format_sse("final", item)
            elif item.get("type") == "error":
                yield _format_sse("error", item)
        await task

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/actions/run", response_model=ActionRunResponse)
async def actions_run(
    body: ActionRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv: Conversation | None = None
    if body.conversation_id:
        conv = db.get(Conversation, body.conversation_id)
        if not conv or conv.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversation not found")

    role_arn = _require_role_arn(body.aws_role_arn)
    if not settings.auth_disabled:
        assert_role_allowed(role_arn)
    creds = _assume_role_or_400(role_arn=role_arn, user_id=user.id)
    mcp_env = McpEnv(aws=creds, aws_region=body.aws_region or "ap-south-1")

    if not isinstance(body.args, dict):
        raise HTTPException(status_code=400, detail="Action args are invalid; must be a dictionary.")
    if body.tool_name == "aws_terminate_ec2_instances":
        instance_ids = body.args.get("instance_ids")
        if not isinstance(instance_ids, list) or not instance_ids:
            raise HTTPException(status_code=400, detail="Missing or invalid 'instance_ids' for termination.")

    async def _run(session):
        return await session.call_tool(body.tool_name, body.args)

    result = await with_mcp_session(mcp_env=mcp_env, fn=_run)
    payload: dict[str, Any]
    try:
        payload = result.model_dump()
    except Exception:
        payload = {"repr": repr(result)}

    if conv is not None:
        trace_steps = [
            {"type": "tool_call", "name": body.tool_name, "args": body.args},
            {"type": "tool_result", "name": body.tool_name, "result": payload, "isError": False},
        ]
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content_json={
                    "text": f"Approved & executed `{body.tool_name}`.",
                    "trace": trace_steps,
                },
            )
        )

    db.add(
        ToolAudit(
            user_id=user.id,
            tool_name=body.tool_name,
            args_json=body.args,
            result_meta_json={"approved": True, "result": payload},
        )
    )
    db.commit()
    return ActionRunResponse(ok=True, result=payload)


@router.get("/aws/infra/topology")
def aws_infra_topology(
    aws_role_arn: str,
    aws_region: str = "ap-south-1",
    user: User = Depends(get_current_user),
):
    role_arn = _require_role_arn(aws_role_arn)
    if not settings.auth_disabled:
        assert_role_allowed(role_arn)

    creds = _assume_role_or_400(role_arn=role_arn, user_id=user.id)

    try:
        return describe_infra_topology(
            region=aws_region or "ap-south-1",
            access_key_id=creds.access_key_id,
            secret_access_key=creds.secret_access_key,
            session_token=creds.session_token,
        )
    except ClientError as e:
        code = (e.response.get("Error") or {}).get("Code") or "ClientError"
        msg = (e.response.get("Error") or {}).get("Message") or str(e)
        raise HTTPException(status_code=400, detail=f"AWS API failed ({code}): {msg}") from e
