from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import CHAR, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ide_platform_api.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idp_subject: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ToolAudit(Base):
    __tablename__ = "tool_audit"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(200))
    args_json: Mapped[dict] = mapped_column(JSON)
    result_meta_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


class AuthNonce(Base):
    """
    Minimal OIDC state/nonce store (dev-friendly).
    For production, prefer Redis or encrypted cookies only.
    """

    __tablename__ = "auth_nonces"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))
    redirect_path: Mapped[str | None] = mapped_column(Text, nullable=True)
