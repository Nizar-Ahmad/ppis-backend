import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="role_record"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    google_sub: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id"),
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    role_record: Mapped["Role"] = relationship(
        back_populates="users"
    )

    daily_inputs: Mapped[list["DailyInput"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    activity_stats: Mapped[list["ActivityStat"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    calendar_events: Mapped[list["CalendarEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    screen_time_stats: Mapped[list["ScreenTimeStat"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    daily_scores: Mapped[list["DailyScore"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    insights: Mapped[list["Insight"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    google_calendar_connection: Mapped[
        "GoogleCalendarConnection | None"
    ] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def google_connected(self) -> bool:
        return self.google_sub is not None

    @property
    def role(self) -> str:
        return self.role_record.name


class DailyInput(Base):
    __tablename__ = "daily_inputs"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entry_date",
            name="uq_daily_input_user_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    mood: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    sleep_hours: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    energy_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    focused_work_hours: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="daily_inputs"
    )


class ActivityStat(Base):
    __tablename__ = "activity_stats"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entry_date",
            name="uq_activity_user_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    steps: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    activity_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    source: Mapped[str] = mapped_column(
        String(30),
        default="manual",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="activity_stats"
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="calendar_events"
    )


class ScreenTimeStat(Base):
    __tablename__ = "screen_time_stats"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entry_date",
            name="uq_screen_time_user_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    total_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    night_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="screen_time_stats"
    )


class DailyScore(Base):
    __tablename__ = "daily_scores"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entry_date",
            name="uq_daily_score_user_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    entry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    productivity_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    stress_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    sleep_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    meeting_load_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    distraction_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    activity_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="daily_scores"
    )


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    insight_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="insights"
    )


class GoogleCalendarConnection(Base):
    __tablename__ = "google_calendar_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    access_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    token_type: Mapped[str] = mapped_column(
        String(30),
        default="Bearer",
        nullable=False
    )

    scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="google_calendar_connection"
    )