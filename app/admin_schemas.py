from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas import (
    ActivityResponse,
    CalendarEventResponse,
    DailyInputResponse,
    DailyScoreResponse,
    InsightResponse,
    ScreenTimeResponse,
)


class AdminUserResponse(BaseModel):
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


class AdminRoleUpdate(BaseModel):
    role: Literal[
        "USER",
        "ADMIN"
    ]


class AdminStatisticsResponse(BaseModel):
    total_users: int

    normal_users: int
    admin_users: int

    google_users: int
    password_users: int

    google_calendar_connections: int

    total_daily_inputs: int
    total_activity_records: int
    total_calendar_events: int
    total_screen_time_records: int

    total_daily_scores: int
    total_insights: int

    average_productivity_score: float
    average_stress_index: float


class AdminUserDataResponse(BaseModel):
    user: AdminUserResponse

    google_calendar_connected: bool

    daily_inputs: list[
        DailyInputResponse
    ]

    activity: list[
        ActivityResponse
    ]

    calendar_events: list[
        CalendarEventResponse
    ]

    screen_time: list[
        ScreenTimeResponse
    ]

    daily_scores: list[
        DailyScoreResponse
    ]

    insights: list[
        InsightResponse
    ]


# ============================================================
# ADMIN USER MANAGEMENT V2
# ============================================================

from datetime import date
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from pydantic import (
    Field,
    field_validator,
    model_validator,
)


class AdminUserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=2,
        max_length=150,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    confirm_password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: Literal[
        "USER",
        "ADMIN",
    ] = "USER"

    birth_date: date | None = None

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    occupation: str | None = Field(
        default=None,
        max_length=150,
    )

    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=100,
    )

    preferred_language: str = Field(
        default="en",
        min_length=2,
        max_length=20,
    )

    login_otp_enabled: bool = False

    send_welcome_email: bool = True

    @field_validator("timezone")
    @classmethod
    def validate_timezone(
        cls,
        value: str,
    ) -> str:
        try:
            ZoneInfo(value)

        except ZoneInfoNotFoundError:
            raise ValueError(
                "Invalid timezone"
            )

        return value

    @model_validator(mode="after")
    def validate_passwords(self):
        if (
            self.password
            != self.confirm_password
        ):
            raise ValueError(
                "password and "
                "confirm_password "
                "do not match"
            )

        return self


class AdminPasswordReset(BaseModel):
    new_password: str = Field(
        min_length=8,
        max_length=128,
    )

    confirm_new_password: str = Field(
        min_length=8,
        max_length=128,
    )

    @model_validator(mode="after")
    def validate_passwords(self):
        if (
            self.new_password
            != self.confirm_new_password
        ):
            raise ValueError(
                "new_password and "
                "confirm_new_password "
                "do not match"
            )

        return self


class AdminPasswordResetResponse(BaseModel):
    message: str
    revoked_sessions: int
