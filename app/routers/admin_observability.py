from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.schemas.admin import (
    AdminObservabilitySummaryResponse,
    ApiUsageResponse,
    AuditLogResponse,
)
from app.services.auth.admin import (
    get_current_admin,
)
from app.core.database import get_db
from app.models.auth import AuthSession, OtpCode
from app.models.feedback import Feedback
from app.models.observability import ApiUsageStat, AuditLog, EmailLog
from app.models import User


router = APIRouter(
    prefix="/api/admin/observability",
    tags=["Admin Observability"],
)


@router.get(
    "/summary",
    response_model=(
        AdminObservabilitySummaryResponse
    ),
)
def get_observability_summary(
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    now = datetime.now(
        timezone.utc
    )

    last_24h = (
        now
        - timedelta(hours=24)
    )

    today = now.date()

    active_sessions = (
        db.scalar(
            select(
                func.count(
                    AuthSession.id
                )
            ).where(
                AuthSession.revoked_at
                .is_(None),

                AuthSession.expires_at
                > now,
            )
        )
        or 0
    )

    sessions_created_last_24h = (
        db.scalar(
            select(
                func.count(
                    AuthSession.id
                )
            ).where(
                AuthSession.created_at
                >= last_24h
            )
        )
        or 0
    )

    otp_requests_last_24h = (
        db.scalar(
            select(
                func.count(
                    OtpCode.id
                )
            ).where(
                OtpCode.created_at
                >= last_24h
            )
        )
        or 0
    )

    otp_failures_last_24h = (
        db.scalar(
            select(
                func.count(
                    AuditLog.id
                )
            ).where(
                AuditLog.created_at
                >= last_24h,

                AuditLog.event_type
                == "otp_verification_failed",
            )
        )
        or 0
    )

    emails_sent_last_24h = (
        db.scalar(
            select(
                func.count(
                    EmailLog.id
                )
            ).where(
                EmailLog.created_at
                >= last_24h,

                EmailLog.status
                == "sent",
            )
        )
        or 0
    )

    email_failures_last_24h = (
        db.scalar(
            select(
                func.count(
                    EmailLog.id
                )
            ).where(
                EmailLog.created_at
                >= last_24h,

                EmailLog.status
                == "failed",
            )
        )
        or 0
    )

    audit_events_last_24h = (
        db.scalar(
            select(
                func.count(
                    AuditLog.id
                )
            ).where(
                AuditLog.created_at
                >= last_24h
            )
        )
        or 0
    )

    feedback_total = (
        db.scalar(
            select(
                func.count(
                    Feedback.id
                )
            )
        )
        or 0
    )

    feedback_average_rating = (
        db.scalar(
            select(
                func.avg(
                    Feedback.rating
                )
            )
        )
        or 0
    )

    api_requests_today = (
        db.scalar(
            select(
                func.sum(
                    ApiUsageStat.request_count
                )
            ).where(
                ApiUsageStat.usage_date
                == today
            )
        )
        or 0
    )

    api_client_errors_today = (
        db.scalar(
            select(
                func.sum(
                    ApiUsageStat
                    .client_error_count
                )
            ).where(
                ApiUsageStat.usage_date
                == today
            )
        )
        or 0
    )

    api_server_errors_today = (
        db.scalar(
            select(
                func.sum(
                    ApiUsageStat
                    .server_error_count
                )
            ).where(
                ApiUsageStat.usage_date
                == today
            )
        )
        or 0
    )

    return (
        AdminObservabilitySummaryResponse(
            active_sessions=int(
                active_sessions
            ),
            sessions_created_last_24h=int(
                sessions_created_last_24h
            ),
            otp_requests_last_24h=int(
                otp_requests_last_24h
            ),
            otp_failures_last_24h=int(
                otp_failures_last_24h
            ),
            emails_sent_last_24h=int(
                emails_sent_last_24h
            ),
            email_failures_last_24h=int(
                email_failures_last_24h
            ),
            audit_events_last_24h=int(
                audit_events_last_24h
            ),
            feedback_total=int(
                feedback_total
            ),
            feedback_average_rating=round(
                float(
                    feedback_average_rating
                ),
                2,
            ),
            api_requests_today=int(
                api_requests_today
            ),
            api_client_errors_today=int(
                api_client_errors_today
            ),
            api_server_errors_today=int(
                api_server_errors_today
            ),
        )
    )


@router.get(
    "/api-usage",
    response_model=list[
        ApiUsageResponse
    ],
)
def get_api_usage(
    days: int = Query(
        default=7,
        ge=1,
        le=365,
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=1000,
    ),
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    start_date = (
        datetime.now(
            timezone.utc
        ).date()
        - timedelta(
            days=days - 1
        )
    )

    rows = db.scalars(
        select(ApiUsageStat)
        .where(
            ApiUsageStat.usage_date
            >= start_date
        )
        .order_by(
            ApiUsageStat
            .usage_date
            .desc(),

            ApiUsageStat
            .request_count
            .desc(),
        )
        .limit(limit)
    ).all()

    result = []

    for row in rows:
        average_duration_ms = (
            row.total_duration_ms
            / row.request_count
            if row.request_count
            else 0
        )

        result.append(
            ApiUsageResponse(
                usage_date=(
                    row.usage_date
                ),
                method=row.method,
                route_path=(
                    row.route_path
                ),
                request_count=(
                    row.request_count
                ),
                success_count=(
                    row.success_count
                ),
                client_error_count=(
                    row.client_error_count
                ),
                server_error_count=(
                    row.server_error_count
                ),
                average_duration_ms=round(
                    average_duration_ms,
                    2,
                ),
                last_accessed_at=(
                    row.last_accessed_at
                ),
            )
        )

    return result


@router.get(
    "/audit-logs",
    response_model=list[
        AuditLogResponse
    ],
)
def get_audit_logs(
    event_type: str | None = Query(
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
        AuditLog
    )

    if event_type:
        query = query.where(
            AuditLog.event_type
            == event_type
        )

    return db.scalars(
        query
        .order_by(
            AuditLog
            .created_at
            .desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()
