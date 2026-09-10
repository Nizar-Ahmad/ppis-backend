from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import (
    MessageResponse,
    RefreshTokenRequest,
    SessionResponse,
    TokenResponseV2,
)
from app.audit import write_audit_log
from app.auth import (
    AuthContext,
    get_current_auth_context,
    revoke_all_user_sessions,
    revoke_session,
    rotate_refresh_tokens,
)
from app.database import get_db
from app.extended_models import (
    AuthSession,
)


router = APIRouter(
    prefix="/auth",
    tags=["Sessions"],
)


@router.post(
    "/refresh",
    response_model=TokenResponseV2,
)
def refresh_tokens(
    data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _, _, tokens = (
        rotate_refresh_tokens(
            refresh_token=(
                data.refresh_token
            ),
            db=db,
            request=request,
            client=data.client,
        )
    )

    return tokens


@router.post(
    "/logout",
    response_model=MessageResponse,
)
def logout(
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    revoke_session(
        context.session,
        "logout",
    )

    db.commit()

    write_audit_log(
        event_type="logout",
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type="auth_session",
        entity_id=str(
            context.session.id
        ),
    )

    return MessageResponse(
        message=(
            "Logged out successfully"
        )
    )


@router.post(
    "/logout-all",
    response_model=MessageResponse,
)
def logout_all(
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    revoke_all_user_sessions(
        user_id=context.user.id,
        db=db,
        reason="logout_all",
    )

    db.commit()

    write_audit_log(
        event_type="logout_all",
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
    )

    return MessageResponse(
        message=(
            "All sessions have been logged out"
        )
    )


@router.get(
    "/sessions",
    response_model=list[
        SessionResponse
    ],
)
def get_sessions(
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    sessions = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id
            == context.user.id
        )
        .order_by(
            AuthSession
            .last_seen_at
            .desc()
        )
    ).all()

    return [
        SessionResponse(
            id=item.id,
            user_id=item.user_id,
            client_type=(
                item.client_type
            ),
            device_id=item.device_id,
            device_name=(
                item.device_name
            ),
            app_version=(
                item.app_version
            ),
            ip_address=(
                item.ip_address
            ),
            user_agent=(
                item.user_agent
            ),
            created_at=(
                item.created_at
            ),
            last_seen_at=(
                item.last_seen_at
            ),
            expires_at=(
                item.expires_at
            ),
            revoked_at=(
                item.revoked_at
            ),
            revoked_reason=(
                item.revoked_reason
            ),
            is_current=(
                item.id
                == context.session.id
            ),
        )
        for item in sessions
    ]


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
)
def revoke_own_session(
    session_id: UUID,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id
            == session_id,

            AuthSession.user_id
            == context.user.id,
        )
    )

    if not session:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    revoke_session(
        session,
        "user_revoked",
    )

    db.commit()

    write_audit_log(
        event_type="session_revoked",
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type="auth_session",
        entity_id=str(
            session.id
        ),
    )

    return MessageResponse(
        message=(
            "Session revoked successfully"
        )
    )


@router.post(
    "/sessions/revoke-others",
    response_model=MessageResponse,
)
def revoke_other_sessions(
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    count = (
        revoke_all_user_sessions(
            user_id=context.user.id,
            db=db,
            reason=(
                "user_revoked_others"
            ),
            exclude_session_id=(
                context.session.id
            ),
        )
    )

    db.commit()

    write_audit_log(
        event_type=(
            "other_sessions_revoked"
        ),
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        details={
            "revoked_count": count
        },
    )

    return MessageResponse(
        message=(
            f"Revoked {count} "
            f"other session(s)"
        )
    )