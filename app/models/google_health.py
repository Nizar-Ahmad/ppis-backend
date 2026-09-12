import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.core.database import Base


class GoogleHealthConnection(Base):
    __tablename__ = "google_health_connections"

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

    provider: Mapped[str] = mapped_column(
        String(30),
        default="google_health",
        nullable=False,
    )

    access_token: Mapped[str | None] = (
        mapped_column(
            Text,
            nullable=True,
        )
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_type: Mapped[str] = mapped_column(
        String(30),
        default="Bearer",
        nullable=False,
    )

    scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    last_sync_at: Mapped[datetime | None] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(
            timezone.utc
        ),
        onupdate=lambda: datetime.now(
            timezone.utc
        ),
        nullable=False,
    )
