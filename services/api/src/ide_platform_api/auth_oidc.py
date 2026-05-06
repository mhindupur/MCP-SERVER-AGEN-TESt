from __future__ import annotations

import datetime as dt
import secrets
import urllib.parse
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy.orm import Session

from ide_platform_api.config import settings
from ide_platform_api.db import get_db
from ide_platform_api.models import AuthNonce, User
from ide_platform_api.security import SessionPayload, sign_session, verify_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_oidc_config() -> None:
    if settings.auth_disabled:
        return
    missing = [
        k
        for k, v in {
            "OIDC_ISSUER": settings.oidc_issuer,
            "OIDC_CLIENT_ID": settings.oidc_client_id,
            "OIDC_CLIENT_SECRET": settings.oidc_client_secret,
            "OIDC_REDIRECT_URI": settings.oidc_redirect_uri,
        }.items()
        if not v
    ]
    if missing:
        raise HTTPException(status_code=500, detail=f"OIDC is not configured: missing {', '.join(missing)}")


async def _oidc_metadata(issuer: str) -> dict[str, Any]:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


@router.get("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    if settings.auth_disabled:
        raise HTTPException(status_code=400, detail="AUTH_DISABLED=true (dev mode)")

    _require_oidc_config()
    issuer = settings.oidc_issuer or ""
    md = await _oidc_metadata(issuer)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    db.add(AuthNonce(state=state, nonce=nonce, redirect_path=request.query_params.get("next")))
    db.commit()

    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.oidc_redirect_uri,
        "state": state,
        "nonce": nonce,
    }
    auth_ep = md["authorization_endpoint"]
    url = auth_ep + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    if settings.auth_disabled:
        raise HTTPException(status_code=400, detail="AUTH_DISABLED=true (dev mode)")

    _require_oidc_config()
    q = request.query_params
    if q.get("error"):
        raise HTTPException(status_code=400, detail=q.get("error_description") or q.get("error"))

    code = q.get("code")
    state = q.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")

    nonce_row = db.get(AuthNonce, state)
    if not nonce_row:
        raise HTTPException(status_code=400, detail="Invalid state")
    redirect_target = nonce_row.redirect_path or settings.post_login_redirect

    issuer = settings.oidc_issuer or ""
    md = await _oidc_metadata(issuer)
    token_ep = md["token_endpoint"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            token_ep,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret or "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {r.text}")
        token = r.json()

    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token returned")

    # Validate signature + nonce using provider JWKS (minimal validation)
    jwks_uri = md["jwks_uri"]
    async with httpx.AsyncClient(timeout=30) as client:
        jwks = (await client.get(jwks_uri)).json()

    try:
        headers = jwt.get_unverified_header(id_token)
        alg = str(headers.get("alg") or "RS256")
    except Exception:
        alg = "RS256"

    claims = jwt.decode(
        id_token,
        jwks,
        algorithms=[alg],
        audience=settings.oidc_client_id,
        issuer=str(md.get("issuer") or issuer),
        options={"verify_at_hash": False},
    )

    if claims.get("nonce") != nonce_row.nonce:
        raise HTTPException(status_code=400, detail="Invalid nonce")

    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or claims.get("preferred_username") or "")
    name = claims.get("name")
    if not sub or not email:
        raise HTTPException(status_code=400, detail="Missing subject/email in id_token")

    user = db.query(User).filter(User.idp_subject == sub).one_or_none()
    if not user:
        user = User(idp_subject=sub, email=email, name=str(name) if name else None)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if name and user.name != str(name):
            user.name = str(name)
            changed = True
        if changed:
            db.commit()

    db.delete(nonce_row)
    db.commit()

    session_token = sign_session(SessionPayload(user_id=user.id))
    resp = RedirectResponse(redirect_target)
    # NOTE: For cross-site cookies between API and web, prefer a first-party proxy path on the web domain.
    resp.set_cookie(
        key="ide_session",
        value=session_token,
        httponly=True,
        secure=settings.app_env != "dev",
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return resp


@router.post("/logout")
async def logout(response: Response):
    response = Response(status_code=204)
    response.delete_cookie("ide_session")
    return response
