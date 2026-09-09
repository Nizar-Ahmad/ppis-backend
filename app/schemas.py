from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class UserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=2,
        max_length=150
    )

    password: str = Field(
        min_length=8,
        max_length=128
    )


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(
        min_length=20
    )


class SetPasswordRequest(BaseModel):
    password: str = Field(
        min_length=8,
        max_length=128
    )


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None

    model_config = ConfigDict(
        from_attributes=True
    )


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str

    role: str

    has_password: bool
    google_connected: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------
# Daily Input
# --------------------------------------------------

class DailyInputCreate(BaseModel):
    entry_date: date

    mood: int = Field(
        ge=1,
        le=5
    )

    sleep_hours: float = Field(
        ge=0,
        le=24
    )

    energy_level: int = Field(
        ge=1,
        le=5
    )

    focused_work_hours: float = Field(
        ge=0,
        le=24
    )

    notes: str | None = Field(
        default=None,
        max_length=1000
    )


class DailyInputUpdate(BaseModel):
    mood: int | None = Field(
        default=None,
        ge=1,
        le=5
    )

    sleep_hours: float | None = Field(
        default=None,
        ge=0,
        le=24
    )

    energy_level: int | None = Field(
        default=None,
        ge=1,
        le=5
    )

    focused_work_hours: float | None = Field(
        default=None,
        ge=0,
        le=24
    )

    notes: str | None = Field(
        default=None,
        max_length=1000
    )

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        required_fields = (
            "mood",
            "sleep_hours",
            "energy_level",
            "focused_work_hours",
        )

        for field in required_fields:
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class DailyInputResponse(BaseModel):
    id: UUID
    entry_date: date

    mood: int
    sleep_hours: float
    energy_level: int
    focused_work_hours: float
    notes: str | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# Activity
# --------------------------------------------------

class ActivityCreate(BaseModel):
    entry_date: date

    steps: int = Field(
        default=0,
        ge=0
    )

    activity_minutes: int = Field(
        default=0,
        ge=0,
        le=1440
    )

    source: Literal[
        "manual",
        "health_connect"
    ] = "manual"


class ActivityUpdate(BaseModel):
    steps: int | None = Field(
        default=None,
        ge=0
    )

    activity_minutes: int | None = Field(
        default=None,
        ge=0,
        le=1440
    )

    source: Literal[
        "manual",
        "health_connect"
    ] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        required_fields = (
            "steps",
            "activity_minutes",
            "source",
        )

        for field in required_fields:
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class ActivityResponse(BaseModel):
    id: UUID
    entry_date: date

    steps: int
    activity_minutes: int
    source: str

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# Calendar
# --------------------------------------------------

class CalendarEventCreate(BaseModel):
    external_id: str | None = Field(
        default=None,
        max_length=255
    )

    source: Literal[
        "manual",
        "google",
        "local"
    ]

    title: str | None = Field(
        default=None,
        max_length=255
    )

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError(
                "end_time must be after start_time"
            )

        return self


class CalendarEventUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=255
    )

    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def reject_null_times(self):
        for field in (
            "start_time",
            "end_time",
        ):
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class CalendarEventResponse(BaseModel):
    id: UUID

    external_id: str | None
    source: str
    title: str | None

    start_time: datetime
    end_time: datetime
    duration_minutes: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# Screen Time
# --------------------------------------------------

class ScreenTimeCreate(BaseModel):
    entry_date: date

    total_minutes: int = Field(
        ge=0,
        le=1440
    )

    night_minutes: int = Field(
        default=0,
        ge=0,
        le=1440
    )

    @model_validator(mode="after")
    def validate_screen_time(self):
        if self.night_minutes > self.total_minutes:
            raise ValueError(
                "night_minutes cannot be greater than total_minutes"
            )

        return self


class ScreenTimeUpdate(BaseModel):
    total_minutes: int | None = Field(
        default=None,
        ge=0,
        le=1440
    )

    night_minutes: int | None = Field(
        default=None,
        ge=0,
        le=1440
    )

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in (
            "total_minutes",
            "night_minutes",
        ):
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class ScreenTimeResponse(BaseModel):
    id: UUID
    entry_date: date

    total_minutes: int
    night_minutes: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# Analytics
# --------------------------------------------------

class DailyScoreResponse(BaseModel):
    id: UUID
    entry_date: date

    productivity_score: int
    stress_index: int
    sleep_score: int
    meeting_load_score: int
    distraction_score: int
    activity_score: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class WeeklyAnalyticsResponse(BaseModel):
    start_date: date
    end_date: date

    days_analyzed: int

    average_sleep_hours: float
    average_mood: float
    average_energy_level: float
    total_focused_work_hours: float

    total_meeting_minutes: int
    total_screen_minutes: int

    average_productivity_score: float
    average_stress_index: float

    best_day: date | None
    worst_day: date | None


# --------------------------------------------------
# Insights
# --------------------------------------------------

class InsightResponse(BaseModel):
    id: UUID

    start_date: date
    end_date: date

    insight_type: str
    message: str

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# --------------------------------------------------
# Google Calendar
# --------------------------------------------------

class GoogleCalendarConnectResponse(BaseModel):
    authorization_url: str


class GoogleCalendarStatusResponse(BaseModel):
    connected: bool
    scope: str | None = None
    expires_at: datetime | None = None


class GoogleCalendarSyncResponse(BaseModel):
    calendars_checked: int
    events_created: int
    events_updated: int
    events_skipped: int