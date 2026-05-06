from __future__ import annotations

import json
import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ide_platform_api.aws_policy import assert_role_allowed, pick_role_arn_for_user
from ide_platform_api.aws_sts import assume_role
from ide_platform_api.config import settings
from ide_platform_api.db import get_db
from ide_platform_api.deps import get_current_user
from ide_platform_api.mcp_client import McpEnv
from ide_platform_api.models import Conversation, Message, ToolAudit, User
from ide_platform_api.openai_orchestrator import run_openai_mcp_chat

router = APIRouter()


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


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    aws_role_arn: str | None = None
    aws_region: str | None = Field(default="ap-south-1")


class ChatResponse(BaseModel):
    reply: str
    trace: list[dict[str, Any]]


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

    # Minimal claims for future group->role mapping (stored later if needed)
    claims: dict[str, Any] = {"email": user.email, "sub": user.idp_subject}

    # Local dev: skip STS AssumeRole + allow-list enforcement.
    # Let the MCP server use its own default AWS profile (server-side tool args default to profile="dc").
    if settings.auth_disabled:
        mcp_env = McpEnv(aws=None, aws_region=body.aws_region)
    else:
        role_arn = body.aws_role_arn or pick_role_arn_for_user(claims)
        if not role_arn:
            raise HTTPException(status_code=400, detail="No AWS role configured/mapped for this user")
        assert_role_allowed(role_arn)

        creds = assume_role(
            role_arn=role_arn,
            session_name=f"ide-{user.id[:16]}",
            external_id=settings.aws_role_external_id,
        )

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

    reply, trace = await run_openai_mcp_chat(
        user_text=body.message,
        mcp_env=mcp_env,
        system_prompt=system_prompt,
        on_tool_result=audit,
    )

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

    claims: dict[str, Any] = {"email": user.email, "sub": user.idp_subject}
    if settings.auth_disabled:
        mcp_env = McpEnv(aws=None, aws_region=body.aws_region)
    else:
        role_arn = body.aws_role_arn or pick_role_arn_for_user(claims)
        if not role_arn:
            raise HTTPException(status_code=400, detail="No AWS role configured/mapped for this user")
        assert_role_allowed(role_arn)

        creds = assume_role(
            role_arn=role_arn,
            session_name=f"ide-{user.id[:16]}",
            external_id=settings.aws_role_external_id,
        )
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
