"""Initial schema

Revision ID: 0001_init_schema
Revises: 
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", mysql.CHAR(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("idp_subject", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_idp_subject", "users", ["idp_subject"], unique=True)

    op.create_table(
        "conversations",
        sa.Column("id", mysql.CHAR(length=36), primary_key=True),
        sa.Column("user_id", mysql.CHAR(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", mysql.CHAR(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            mysql.CHAR(length=36),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content_json", mysql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "tool_audit",
        sa.Column("id", mysql.CHAR(length=36), primary_key=True),
        sa.Column("user_id", mysql.CHAR(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("args_json", mysql.JSON(), nullable=False),
        sa.Column("result_meta_json", mysql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_tool_audit_user_id", "tool_audit", ["user_id"])

    op.create_table(
        "auth_nonces",
        sa.Column("state", sa.String(length=128), primary_key=True),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redirect_path", sa.Text(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("auth_nonces")
    op.drop_index("ix_tool_audit_user_id", table_name="tool_audit")
    op.drop_table("tool_audit")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_users_idp_subject", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

