from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import (
    and_,
    delete,
    or_,
)

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.auth import AuthSession, OtpCode
from app.models.observability import ApiUsageStat, AuditLog, EmailLog
from app.services.otp.service import (
    invalidate_expired_otps,
)


def run_maintenance() -> None:
    now = datetime.now(
        timezone.utc
    )

    otp_cutoff = (
        now
        - timedelta(
            days=settings.otp_retention_days
        )
    )

    session_cutoff = (
        now
        - timedelta(
            days=settings.session_retention_days
        )
    )

    email_cutoff = (
        now
        - timedelta(
            days=settings.email_log_retention_days
        )
    )

    audit_cutoff = (
        now
        - timedelta(
            days=settings.audit_log_retention_days
        )
    )

    api_usage_cutoff = (
        now.date()
        - timedelta(
            days=settings.api_usage_retention_days
        )
    )

    with SessionLocal() as db:
        # --------------------------------------------------
        # OTP
        # --------------------------------------------------

        # Any OTP whose duration ended becomes invalid.
        invalidate_expired_otps(
            db
        )

        # Keep invalid OTP history for the configured
        # retention period, then delete it.
        db.execute(
            delete(OtpCode).where(
                OtpCode.created_at
                < otp_cutoff,

                OtpCode.is_valid
                .is_(False),
            )
        )

        # --------------------------------------------------
        # Auth Sessions
        # --------------------------------------------------

        # Active sessions are never removed.
        #
        # Remove:
        # 1. revoked sessions whose revoke date is old
        # 2. expired sessions that have been expired
        #    longer than the retention period
        db.execute(
            delete(AuthSession).where(
                or_(
                    and_(
                        AuthSession.revoked_at
                        .is_not(None),

                        AuthSession.revoked_at
                        < session_cutoff,
                    ),
                    and_(
                        AuthSession.expires_at
                        < session_cutoff,
                    ),
                )
            )
        )

        # --------------------------------------------------
        # Email Logs
        # --------------------------------------------------

        db.execute(
            delete(EmailLog).where(
                EmailLog.created_at
                < email_cutoff
            )
        )

        # --------------------------------------------------
        # Audit Logs
        # --------------------------------------------------

        db.execute(
            delete(AuditLog).where(
                AuditLog.created_at
                < audit_cutoff
            )
        )

        # --------------------------------------------------
        # API Usage Statistics
        # --------------------------------------------------

        db.execute(
            delete(ApiUsageStat).where(
                ApiUsageStat.usage_date
                < api_usage_cutoff
            )
        )

        db.commit()


if __name__ == "__main__":
    run_maintenance()
