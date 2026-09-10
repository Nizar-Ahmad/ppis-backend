from datetime import (
    datetime,
    timezone,
)
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import (
    MessageResponse,
    SessionResponse,
)
from app.admin_auth import (
    get_current_admin,
)
from app.audit import write_audit_log
from app.auth import revoke_session
from app.database import get_db
from app.extended_models import (
    AuthSession,
)
from app.models import User


router = APIRouter(
    prefix="/api/admin/sessions",
    tags=["Admin Sessions"],
)


@router.get(
    "",
    response_model=list[
        SessionResponse
    ],
)
def get_sessions(
    active_only: bool = Query(
        default=True
    ),
    user_id: UUID | None = Query(
        default=None
    ),
    client_type: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    query = select(
        AuthSession
    )

    if active_only:
        now = datetime.now(
            timezone.utc
        )

        query = query.where(
            AuthSession.revoked_at
            .is_(None),

            AuthSession.expires_at
            > now,
        )

    if user_id:
        query = query.where(
            AuthSession.user_id
            == user_id
        )

    if client_type:
        query = query.where(
            AuthSession.client_type
            == client_type
        )

    sessions = db.scalars(
        query
        .order_by(
            AuthSession
            .last_seen_at
            .desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        SessionResponse(
            id=item.id,
            user_id=item.user_id,
            client_type=(
                item.client_type
            ),
            device_id=(
                item.device_id
            ),
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
            is_current=False,
        )
        for item in sessions
    ]


@router.delete(
    "/{session_id}",
    response_model=MessageResponse,
)
def revoke_user_session(
    session_id: UUID,
    request: Request,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    session = db.get(
        AuthSession,
        session_id,
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
        "admin_revoked",
    )

    db.commit()

    write_audit_log(
        event_type=(
            "admin_session_revoked"
        ),
        request=request,
        user_id=(
            session.user_id
        ),
        actor_user_id=(
            current_admin.id
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