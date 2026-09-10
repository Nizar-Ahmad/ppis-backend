from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.schemas import UserResponse


OtpPurpose = Literal[
    "login",
    "signup",
    "reset_password",
    "change_password",
]

FeedbackType = Literal[
    "app",
    "weekly_report",
    "monthly_report",
    "insight",
]


class ClientInfo(BaseModel):
    client_type: str = Field(
        default="unknown",
        min_length=1,
        max_length=30,
    )

    device_id: str | None = Field(
        default=None,
        max_length=255,
    )

    device_name: str | None = Field(
        default=None,
        max_length=255,
    )

    app_version: str | None = Field(
        default=None,
        max_length=50,
    )


class SignupData(BaseModel):
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
    def validate_password_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError(
                "password and confirm_password do not match"
            )

        return self


class LoginRequestV2(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    client: ClientInfo | None = None


class GoogleLoginRequestV2(BaseModel):
    id_token: str = Field(
        min_length=20,
    )

    client: ClientInfo | None = None


class SetPasswordRequestV2(BaseModel):
    password: str = Field(
        min_length=8,
        max_length=128,
    )

    confirm_password: str = Field(
        min_length=8,
        max_length=128,
    )

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password:
            raise ValueError(
                "password and confirm_password do not match"
            )

        return self


class TokenResponseV2(BaseModel):
    access_token: str
    refresh_token: str

    token_type: str = "bearer"

    expires_in: int
    refresh_expires_in: int

    session_id: UUID


class LoginResponseV2(BaseModel):
    requires_otp: bool

    challenge_id: UUID | None = None
    purpose: OtpPurpose | None = None
    otp_expires_in: int | None = None

    access_token: str | None = None
    refresh_token: str | None = None

    token_type: str | None = None

    expires_in: int | None = None
    refresh_expires_in: int | None = None

    session_id: UUID | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        min_length=20,
    )

    client: ClientInfo | None = None


class MessageResponse(BaseModel):
    message: str


class OtpSendRequest(BaseModel):
    purpose: Literal[
        "signup",
        "reset_password",
        "change_password",
    ]

    email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_email_requirement(self):
        if (
            self.purpose
            in {
                "signup",
                "reset_password",
            }
            and self.email is None
        ):
            raise ValueError(
                "email is required for this OTP purpose"
            )

        return self


class OtpResendRequest(BaseModel):
    challenge_id: UUID


class OtpChallengeResponse(BaseModel):
    challenge_id: UUID
    purpose: OtpPurpose
    expires_in: int


class OtpVerifyRequest(BaseModel):
    challenge_id: UUID
    purpose: OtpPurpose

    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )

    signup_data: SignupData | None = None

    current_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    new_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    confirm_new_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    client: ClientInfo | None = None

    @model_validator(mode="after")
    def validate_payload_for_purpose(self):
        if (
            self.purpose == "signup"
            and self.signup_data is None
        ):
            raise ValueError(
                "signup_data is required for signup verification"
            )

        if self.purpose == "reset_password":
            if (
                self.new_password is None
                or self.confirm_new_password is None
            ):
                raise ValueError(
                    "new_password and confirm_new_password "
                    "are required for password reset"
                )

            if (
                self.new_password
                != self.confirm_new_password
            ):
                raise ValueError(
                    "new_password and confirm_new_password "
                    "do not match"
                )

        if self.purpose == "change_password":
            if self.current_password is None:
                raise ValueError(
                    "current_password is required for password change"
                )

            if (
                self.new_password is None
                or self.confirm_new_password is None
            ):
                raise ValueError(
                    "new_password and confirm_new_password "
                    "are required for password change"
                )

            if (
                self.new_password
                != self.confirm_new_password
            ):
                raise ValueError(
                    "new_password and confirm_new_password "
                    "do not match"
                )

        return self


class OtpVerifyResponse(BaseModel):
    success: bool = True
    message: str

    access_token: str | None = None
    refresh_token: str | None = None

    token_type: str | None = None

    expires_in: int | None = None
    refresh_expires_in: int | None = None

    session_id: UUID | None = None

    user: UserResponse | None = None


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID

    client_type: str

    device_id: str | None
    device_name: str | None
    app_version: str | None

    ip_address: str | None
    user_agent: str | None

    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime

    revoked_at: datetime | None
    revoked_reason: str | None

    is_current: bool = False


class ProfileResponse(BaseModel):
    id: UUID

    email: EmailStr
    full_name: str
    role: str

    has_password: bool
    google_connected: bool

    birth_date: date | None
    country: str | None
    occupation: str | None

    timezone: str
    preferred_language: str

    login_otp_enabled: bool

    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    birth_date: date | None = None

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    occupation: str | None = Field(
        default=None,
        max_length=150,
    )

    timezone: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    preferred_language: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )

    login_otp_enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return value

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError(
                "Invalid timezone"
            )

        return value

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in (
            "full_name",
            "timezone",
            "preferred_language",
            "login_otp_enabled",
        ):
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class NotificationPreferenceResponse(BaseModel):
    weekly_report_email: bool
    monthly_report_email: bool
    new_login_email: bool


class NotificationPreferenceUpdate(BaseModel):
    weekly_report_email: bool | None = None
    monthly_report_email: bool | None = None
    new_login_email: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in (
            "weekly_report_email",
            "monthly_report_email",
            "new_login_email",
        ):
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(
                    f"{field} cannot be null"
                )

        return self


class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType

    rating: int = Field(
        ge=1,
        le=5,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )

    report_start_date: date | None = None
    report_end_date: date | None = None

    insight_id: UUID | None = None

    @model_validator(mode="after")
    def validate_context(self):
        if self.feedback_type in {
            "weekly_report",
            "monthly_report",
        }:
            if (
                self.report_start_date is None
                or self.report_end_date is None
            ):
                raise ValueError(
                    "report_start_date and report_end_date "
                    "are required for report feedback"
                )

            if (
                self.report_end_date
                < self.report_start_date
            ):
                raise ValueError(
                    "report_end_date cannot be before "
                    "report_start_date"
                )

        if (
            self.feedback_type == "insight"
            and self.insight_id is None
        ):
            raise ValueError(
                "insight_id is required for insight feedback"
            )

        return self


class FeedbackUpdate(BaseModel):
    rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )

    @model_validator(mode="after")
    def reject_rating_null(self):
        if (
            "rating" in self.model_fields_set
            and self.rating is None
        ):
            raise ValueError(
                "rating cannot be null"
            )

        return self


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID

    feedback_type: str
    rating: int
    comment: str | None

    report_start_date: date | None
    report_end_date: date | None

    insight_id: UUID | None

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class FeedbackStatisticsResponse(BaseModel):
    total_feedback: int
    average_rating: float

    app_feedback_count: int
    weekly_report_feedback_count: int
    monthly_report_feedback_count: int
    insight_feedback_count: int

    rating_1: int
    rating_2: int
    rating_3: int
    rating_4: int
    rating_5: int


class AdminObservabilitySummaryResponse(BaseModel):
    active_sessions: int
    sessions_created_last_24h: int

    otp_requests_last_24h: int
    otp_failures_last_24h: int

    emails_sent_last_24h: int
    email_failures_last_24h: int

    audit_events_last_24h: int

    feedback_total: int
    feedback_average_rating: float

    api_requests_today: int
    api_client_errors_today: int
    api_server_errors_today: int


class ApiUsageResponse(BaseModel):
    usage_date: date

    method: str
    route_path: str

    request_count: int
    success_count: int
    client_error_count: int
    server_error_count: int

    average_duration_ms: float

    last_accessed_at: datetime


class AuditLogResponse(BaseModel):
    id: UUID

    user_id: UUID | None
    actor_user_id: UUID | None
    session_id: UUID | None

    event_type: str

    entity_type: str | None
    entity_id: str | None

    request_method: str | None
    request_path: str | None

    ip_address: str | None
    user_agent: str | None

    details: dict | None

    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class MonthlyAnalyticsResponse(BaseModel):
    year: int
    month: int

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