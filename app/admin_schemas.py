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