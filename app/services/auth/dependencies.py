"""FastAPI authentication dependencies."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.request import get_request_ip, get_user_agent
from app.core.time import ensure_utc
from app.models import User
from app.models.auth import AuthSession
from app.services.auth.tokens import decode_token


security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def get_current_auth_context(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> AuthContext:
    payload = decode_token(credentials.credentials, "access")
    try:
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
        token_version = int(payload["ver"])
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")
    now = datetime.now(timezone.utc)
    if token_version != session.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token is no longer valid")
    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")
    if ensure_utc(session.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    touch_interval = timedelta(minutes=settings.session_touch_interval_minutes)
    if now - ensure_utc(session.last_seen_at) >= touch_interval:
        session.last_seen_at = now
        session.ip_address = get_request_ip(request)
        session.user_agent = get_user_agent(request)
        db.commit()
        db.refresh(session)
    request.state.user_id = user.id
    request.state.session_id = session.id
    return AuthContext(user=user, session=session)


def get_current_user(context: AuthContext = Depends(get_current_auth_context)) -> User:
    return context.user


def get_optional_auth_context(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(optional_security), db: Session = Depends(get_db)) -> AuthContext | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
        token_version = int(payload["ver"])
    except (HTTPException, ValueError, TypeError, KeyError):
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id))
    if not session:
        return None
    now = datetime.now(timezone.utc)
    if token_version != session.token_version or session.revoked_at is not None or ensure_utc(session.expires_at) <= now:
        return None
    user = db.get(User, user_id)
    if not user:
        return None
    request.state.user_id = user.id
    request.state.session_id = session.id
    return AuthContext(user=user, session=session)
