from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ide_platform_api.config import settings
from ide_platform_api.db import get_db
from ide_platform_api.models import User
from ide_platform_api.security import SessionPayload, verify_session


def get_session_payload(request: Request) -> SessionPayload:
    if settings.auth_disabled:
        # Dev-only fixed user
        return SessionPayload(user_id="00000000-0000-0000-0000-000000000001")

    token = request.cookies.get("ide_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_session(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid session")
    return payload


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    session: SessionPayload = Depends(get_session_payload),
) -> User:
    if settings.auth_disabled:
        user = db.get(User, session.user_id)
        if not user:
            user = User(
                id=session.user_id,
                email="dev@example.com",
                name="Dev User",
                idp_subject="dev",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
