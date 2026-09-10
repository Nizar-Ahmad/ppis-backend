import hashlib
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import (
    UUID,
    uuid4,
)

import jwt
from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import (
    ClientInfo,
    TokenResponseV2,
)
from app.config import settings
from app.database import get_db
from app.extended_models import AuthSession
from app.models import User
from app.request_utils import (
    get_request_ip,
    get_user_agent,
)
from app.time_utils import ensure_utc


password_hasher = (
    PasswordHash.recommended()
)

security = HTTPBearer()

optional_security = HTTPBearer(
    auto_error=False
)


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def hash_password(
    password: str,
) -> str:
    return password_hasher.hash(
        password
    )


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return password_hasher.verify(
        password,
        password_hash,
    )


def hash_refresh_token(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_access_token(
    user_id: UUID,
    session_id: UUID,
    token_version: int,
) -> str:
    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=(
                settings
                .access_token_expire_minutes
            )
        )
    )

    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "ver": token_version,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def create_refresh_token(
    user_id: UUID,
    session_id: UUID,
    expires_at: datetime,
) -> str:
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid4()),
        "type": "refresh",
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def decode_token(
    token: str,
    expected_type: str,
) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid or expired token"
            ),
        )

    if (
        payload.get("type")
        != expected_type
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                f"Invalid {expected_type} "
                f"token"
            ),
        )

    if (
        not payload.get("sub")
        or not payload.get("sid")
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Invalid token",
        )

    return payload


def _apply_client_info(
    session: AuthSession,
    client: ClientInfo | None,
) -> None:
    if not client:
        return

    session.client_type = (
        client.client_type
    )

    session.device_id = (
        client.device_id
    )

    session.device_name = (
        client.device_name
    )

    session.app_version = (
        client.app_version
    )


def create_session_and_tokens(
    user: User,
    db: Session,
    request: Request,
    client: ClientInfo | None = None,
) -> TokenResponseV2:
    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now
        + timedelta(
            days=(
                settings
                .refresh_token_expire_days
            )
        )
    )

    session = AuthSession(
        user_id=user.id,
        refresh_token_hash="",
        token_version=1,
        client_type=(
            client.client_type
            if client
            else "unknown"
        ),
        device_id=(
            client.device_id
            if client
            else None
        ),
        device_name=(
            client.device_name
            if client
            else None
        ),
        app_version=(
            client.app_version
            if client
            else None
        ),
        ip_address=(
            get_request_ip(request)
        ),
        user_agent=(
            get_user_agent(request)
        ),
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
    )

    db.add(session)
    db.flush()

    refresh_token = (
        create_refresh_token(
            user.id,
            session.id,
            expires_at,
        )
    )

    session.refresh_token_hash = (
        hash_refresh_token(
            refresh_token
        )
    )

    access_token = (
        create_access_token(
            user.id,
            session.id,
            session.token_version,
        )
    )

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=(
            settings
            .access_token_expire_minutes
            * 60
        ),
        refresh_expires_in=(
            settings
            .refresh_token_expire_days
            * 24
            * 60
            * 60
        ),
        session_id=session.id,
    )


def renew_session_tokens(
    user: User,
    session: AuthSession,
    db: Session,
    request: Request,
) -> TokenResponseV2:
    now = datetime.now(
        timezone.utc
    )

    # Invalidate all previously issued access
    # tokens for this same session.
    session.token_version += 1

    new_expires_at = (
        now
        + timedelta(
            days=(
                settings
                .refresh_token_expire_days
            )
        )
    )

    session.expires_at = (
        new_expires_at
    )

    session.last_seen_at = now

    session.ip_address = (
        get_request_ip(request)
    )

    session.user_agent = (
        get_user_agent(request)
    )

    refresh_token = (
        create_refresh_token(
            user.id,
            session.id,
            new_expires_at,
        )
    )

    session.refresh_token_hash = (
        hash_refresh_token(
            refresh_token
        )
    )

    access_token = (
        create_access_token(
            user.id,
            session.id,
            session.token_version,
        )
    )

    db.flush()

    return TokenResponseV2(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=(
            settings
            .access_token_expire_minutes
            * 60
        ),
        refresh_expires_in=(
            settings
            .refresh_token_expire_days
            * 24
            * 60
            * 60
        ),
        session_id=session.id,
    )


def rotate_refresh_tokens(
    refresh_token: str,
    db: Session,
    request: Request,
    client: ClientInfo | None = None,
) -> tuple[
    User,
    AuthSession,
    TokenResponseV2,
]:
    payload = decode_token(
        refresh_token,
        "refresh",
    )

    try:
        user_id = UUID(
            payload["sub"]
        )

        session_id = UUID(
            payload["sid"]
        )

    except (
        ValueError,
        KeyError,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid refresh token"
            ),
        )

    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.id
            == session_id,

            AuthSession.user_id
            == user_id,
        )
        .with_for_update()
    )

    if not session:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Session not found",
        )

    now = datetime.now(
        timezone.utc
    )

    if session.revoked_at is not None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Session has been revoked"
            ),
        )

    if (
        ensure_utc(
            session.expires_at
        )
        <= now
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Session has expired",
        )

    supplied_hash = (
        hash_refresh_token(
            refresh_token
        )
    )

    if (
        supplied_hash
        != session.refresh_token_hash
    ):
        session.revoked_at = now

        session.revoked_reason = (
            "refresh_token_mismatch"
        )

        db.commit()

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Refresh token is no "
                "longer valid"
            ),
        )

    user = db.get(
        User,
        user_id,
    )

    if not user:
        session.revoked_at = now

        session.revoked_reason = (
            "user_not_found"
        )

        db.commit()

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="User not found",
        )

    new_expires_at = (
        now
        + timedelta(
            days=(
                settings
                .refresh_token_expire_days
            )
        )
    )

    session.expires_at = (
        new_expires_at
    )

    session.last_seen_at = now

    session.ip_address = (
        get_request_ip(request)
    )

    session.user_agent = (
        get_user_agent(request)
    )

    _apply_client_info(
        session,
        client,
    )

    new_refresh_token = (
        create_refresh_token(
            user.id,
            session.id,
            new_expires_at,
        )
    )

    session.refresh_token_hash = (
        hash_refresh_token(
            new_refresh_token
        )
    )

    access_token = (
        create_access_token(
            user.id,
            session.id,
            session.token_version,
        )
    )

    tokens = TokenResponseV2(
        access_token=access_token,
        refresh_token=(
            new_refresh_token
        ),
        token_type="bearer",
        expires_in=(
            settings
            .access_token_expire_minutes
            * 60
        ),
        refresh_expires_in=(
            settings
            .refresh_token_expire_days
            * 24
            * 60
            * 60
        ),
        session_id=session.id,
    )

    db.commit()
    db.refresh(session)

    return (
        user,
        session,
        tokens,
    )


def revoke_session(
    session: AuthSession,
    reason: str,
) -> None:
    if session.revoked_at is None:
        session.revoked_at = (
            datetime.now(
                timezone.utc
            )
        )

        session.revoked_reason = (
            reason
        )


def revoke_all_user_sessions(
    user_id: UUID,
    db: Session,
    reason: str,
    exclude_session_id: UUID | None = None,
) -> int:
    sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id
            == user_id,

            AuthSession.revoked_at
            .is_(None),
        )
    ).all()

    count = 0

    for session in sessions:
        if (
            exclude_session_id
            is not None
            and session.id
            == exclude_session_id
        ):
            continue

        revoke_session(
            session,
            reason,
        )

        count += 1

    return count


def get_current_auth_context(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials
    ) = Depends(security),
    db: Session = Depends(get_db),
) -> AuthContext:
    payload = decode_token(
        credentials.credentials,
        "access",
    )

    try:
        user_id = UUID(
            payload["sub"]
        )

        session_id = UUID(
            payload["sid"]
        )

        token_version = int(
            payload["ver"]
        )

    except (
        ValueError,
        TypeError,
        KeyError,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid access token"
            ),
        )

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id
            == session_id,

            AuthSession.user_id
            == user_id,
        )
    )

    if not session:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Session not found",
        )

    now = datetime.now(
        timezone.utc
    )

    if (
        token_version
        != session.token_version
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Access token is no "
                "longer valid"
            ),
        )

    if session.revoked_at is not None:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Session has been revoked"
            ),
        )

    if (
        ensure_utc(
            session.expires_at
        )
        <= now
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="Session has expired",
        )

    user = db.get(
        User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail="User not found",
        )

    touch_interval = timedelta(
        minutes=(
            settings
            .session_touch_interval_minutes
        )
    )

    if (
        now
        - ensure_utc(
            session.last_seen_at
        )
        >= touch_interval
    ):
        session.last_seen_at = now

        session.ip_address = (
            get_request_ip(request)
        )

        session.user_agent = (
            get_user_agent(request)
        )

        db.commit()
        db.refresh(session)

    request.state.user_id = (
        user.id
    )

    request.state.session_id = (
        session.id
    )

    return AuthContext(
        user=user,
        session=session,
    )


def get_current_user(
    context: AuthContext = Depends(
        get_current_auth_context
    ),
) -> User:
    return context.user


def get_optional_auth_context(
    request: Request,
    credentials: (
        HTTPAuthorizationCredentials
        | None
    ) = Depends(
        optional_security
    ),
    db: Session = Depends(get_db),
) -> AuthContext | None:
    if credentials is None:
        return None

    # This dependency is intentionally optional.
    #
    # Public OTP flows such as signup and
    # reset_password must still work if a client
    # accidentally sends an expired/stale access token.
    try:
        payload = decode_token(
            credentials.credentials,
            "access",
        )

        user_id = UUID(
            payload["sub"]
        )

        session_id = UUID(
            payload["sid"]
        )

        token_version = int(
            payload["ver"]
        )

    except (
        HTTPException,
        ValueError,
        TypeError,
        KeyError,
    ):
        return None

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id
            == session_id,

            AuthSession.user_id
            == user_id,
        )
    )

    if not session:
        return None

    now = datetime.now(
        timezone.utc
    )

    if (
        token_version
        != session.token_version
    ):
        return None

    if session.revoked_at is not None:
        return None

    if (
        ensure_utc(
            session.expires_at
        )
        <= now
    ):
        return None

    user = db.get(
        User,
        user_id,
    )

    if not user:
        return None

    request.state.user_id = (
        user.id
    )

    request.state.session_id = (
        session.id
    )

    return AuthContext(
        user=user,
        session=session,
    )