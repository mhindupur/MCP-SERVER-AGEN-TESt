from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", validation_alias="APP_ENV")

    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="CORS_ORIGINS",
    )

    # Dev-only
    auth_disabled: bool = Field(default=False, validation_alias="AUTH_DISABLED")

    session_secret: str = Field(default="dev-insecure-change-me", validation_alias="SESSION_SECRET")

    database_url: str = Field(
        default="mysql+pymysql://user:pass@127.0.0.1:3306/ide_platform",
        validation_alias="DATABASE_URL",
    )

    oidc_issuer: str | None = Field(default=None, validation_alias="OIDC_ISSUER")
    oidc_client_id: str | None = Field(default=None, validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, validation_alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str | None = Field(default=None, validation_alias="OIDC_REDIRECT_URI")
    post_login_redirect: str = Field(default="http://localhost:3000/", validation_alias="POST_LOGIN_REDIRECT")

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    mcp_command: str = Field(default="python3", validation_alias="MCP_COMMAND")
    mcp_args: List[str] = Field(default_factory=lambda: ["-m", "cloud_mcp_agent.server"], validation_alias="MCP_ARGS")
    mcp_cwd: str | None = Field(default=None, validation_alias="MCP_CWD")

    aws_allowed_role_arns: List[str] = Field(default_factory=list, validation_alias="AWS_ALLOWED_ROLE_ARNS")
    aws_default_role_arn: str | None = Field(default=None, validation_alias="AWS_DEFAULT_ROLE_ARN")
    aws_role_external_id: str | None = Field(default=None, validation_alias="AWS_ROLE_EXTERNAL_ID")

    @field_validator("mcp_cwd", mode="before")
    @classmethod
    def _empty_to_none(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return ["http://localhost:3000"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",")]
            return [p for p in parts if p]
        return v

    @field_validator("aws_allowed_role_arns", mode="before")
    @classmethod
    def _split_csv_roles(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",")]
            return [p for p in parts if p]
        return v


settings = Settings()
