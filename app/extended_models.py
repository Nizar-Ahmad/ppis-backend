import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    birth_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    occupation: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        nullable=False,
    )

    login_otp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    weekly_report_email: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    monthly_report_email: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    new_login_email: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    last_weekly_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_monthly_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    __table_args__ = (
        Index(
            "ix_auth_sessions_user_active",
            "user_id",
            "revoked_at",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    token_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    client_type: Mapped[str] = mapped_column(
        String(30),
        default="unknown",
        nullable=False,
        index=True,
    )

    device_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    app_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    revoked_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


class OtpCode(Base):
    __tablename__ = "otp_codes"

    __table_args__ = (
        Index(
            "ix_otp_email_purpose_created",
            "target_email",
            "purpose",
            "created_at",
        ),
        Index(
            "ix_otp_valid_expires",
            "is_valid",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    target_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    purpose: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invalid_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class EmailLog(Base):
    __tablename__ = "email_logs"

    __table_args__ = (
        Index(
            "ix_email_logs_status_created",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    target_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    email_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        default="resend",
        nullable=False,
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index(
            "ix_audit_logs_event_created",
            "event_type",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "auth_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    request_method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    request_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class ApiUsageStat(Base):
    __tablename__ = "api_usage_stats"

    __table_args__ = (
        UniqueConstraint(
            "usage_date",
            "method",
            "route_path",
            name="uq_api_usage_day_method_route",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    usage_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    route_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    success_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    client_error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    server_error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_duration_ms: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
    )

    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    feedback_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    report_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    report_end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    insight_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "insights.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )