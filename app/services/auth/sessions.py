"""Auth-session lifecycle, rotation, and revocation."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.request import get_request_ip, get_user_agent
from app.core.time import ensure_utc
from app.models import User
from app.models.auth import AuthSession
from app.schemas.auth import TokenResponseV2
from app.schemas.common import ClientInfo
from app.services.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


def _apply_client_info(session: AuthSession, client: ClientInfo | None) -> None:
    if not client:
        return
    session.client_type = client.client_type
    session.device_id = client.device_id
    session.device_name = client.device_name
    session.app_version = client.app_version


def _token_response(access_token: str, refresh_token: str, session_id: UUID) -> TokenResponseV2:
    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_in=settings.refresh_token_expire_days * 24 * 60 * 60,
        session_id=session_id,
    )


def create_session_and_tokens(user: User, db: Session, request: Request, client: ClientInfo | None = None) -> TokenResponseV2:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="",
        token_version=1,
        client_type=client.client_type if client else "unknown",
        device_id=client.device_id if client else None,
        device_name=client.device_name if client else None,
        app_version=client.app_version if client else None,
        ip_address=get_request_ip(request),
        user_agent=get_user_agent(request),
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    refresh_token = create_refresh_token(user.id, session.id, expires_at)
    session.refresh_token_hash = hash_refresh_token(refresh_token)
    access_token = create_access_token(user.id, session.id, session.token_version)
    return _token_response(access_token, refresh_token, session.id)


def renew_session_tokens(user: User, session: AuthSession, db: Session, request: Request) -> TokenResponseV2:
    now = datetime.now(timezone.utc)
    session.token_version += 1
    new_expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    session.expires_at = new_expires_at
    session.last_seen_at = now
    session.ip_address = get_request_ip(request)
    session.user_agent = get_user_agent(request)
    refresh_token = create_refresh_token(user.id, session.id, new_expires_at)
    session.refresh_token_hash = hash_refresh_token(refresh_token)
    access_token = create_access_token(user.id, session.id, session.token_version)
    db.flush()
    return _token_response(access_token, refresh_token, session.id)


def rotate_refresh_tokens(refresh_token: str, db: Session, request: Request, client: ClientInfo | None = None) -> tuple[User, AuthSession, TokenResponseV2]:
    payload = decode_token(refresh_token, "refresh")
    try:
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
        .with_for_update()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")
    now = datetime.now(timezone.utc)
    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")
    if ensure_utc(session.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")
    if hash_refresh_token(refresh_token) != session.refresh_token_hash:
        session.revoked_at = now
        session.revoked_reason = "refresh_token_mismatch"
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is no longer valid")
    user = db.get(User, user_id)
    if not user:
        session.revoked_at = now
        session.revoked_reason = "user_not_found"
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    new_expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    session.expires_at = new_expires_at
    session.last_seen_at = now
    session.ip_address = get_request_ip(request)
    session.user_agent = get_user_agent(request)
    _apply_client_info(session, client)
    new_refresh_token = create_refresh_token(user.id, session.id, new_expires_at)
    session.refresh_token_hash = hash_refresh_token(new_refresh_token)
    access_token = create_access_token(user.id, session.id, session.token_version)
    tokens = _token_response(access_token, new_refresh_token, session.id)
    db.commit()
    db.refresh(session)
    return user, session, tokens


def revoke_session(session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason


def revoke_all_user_sessions(user_id: UUID, db: Session, reason: str, exclude_session_id: UUID | None = None) -> int:
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ).all()
    count = 0
    for session in sessions:
        if exclude_session_id is not None and session.id == exclude_session_id:
            continue
        revoke_session(session, reason)
        count += 1
    return count
