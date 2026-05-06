from __future__ import annotations

from dataclasses import dataclass

from itsdangerous import BadSignature, URLSafeSerializer

from ide_platform_api.config import settings


@dataclass(frozen=True)
class SessionPayload:
    user_id: str


def session_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret, salt="ide-session-v1")


def sign_session(payload: SessionPayload) -> str:
    return session_serializer().dumps({"user_id": payload.user_id})


def verify_session(token: str) -> SessionPayload | None:
    try:
        data = session_serializer().loads(token)
        user_id = data.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            return None
        return SessionPayload(user_id=user_id)
    except BadSignature:
        return None
