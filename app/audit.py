from uuid import UUID

from fastapi import Request

from app.database import SessionLocal
from app.extended_models import AuditLog
from app.request_utils import (
    get_request_ip,
    get_user_agent,
)


def write_audit_log(
    event_type: str,
    request: Request | None = None,
    user_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    session_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            log = AuditLog(
                user_id=user_id,
                actor_user_id=actor_user_id,
                session_id=session_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                request_method=(
                    request.method
                    if request
                    else None
                ),
                request_path=(
                    request.url.path
                    if request
                    else None
                ),
                ip_address=(
                    get_request_ip(request)
                    if request
                    else None
                ),
                user_agent=(
                    get_user_agent(request)
                    if request
                    else None
                ),
                details=details,
            )

            db.add(log)
            db.commit()

    except Exception:
        # Audit logging must never
        # break the user request.
        return