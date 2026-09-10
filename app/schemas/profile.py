from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
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
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    birth_date: date | None = None
    country: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=150)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=20)
    login_otp_enabled: bool | None = None
    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None: return value
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Invalid timezone")
        return value
    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in ("full_name", "timezone", "preferred_language", "login_otp_enabled"):
            if field in self.model_fields_set and getattr(self, field) is None: raise ValueError(f"{field} cannot be null")
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
        for field in ("weekly_report_email", "monthly_report_email", "new_login_email"):
            if field in self.model_fields_set and getattr(self, field) is None: raise ValueError(f"{field} cannot be null")
        return self
