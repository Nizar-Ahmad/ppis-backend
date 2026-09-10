from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.schemas.common import ClientInfo
from app.schemas.otp import OtpPurpose, OtpVerifyRequest

class SignupData(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    birth_date: date | None = None
    country: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=150)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    preferred_language: str = Field(default="en", min_length=2, max_length=20)
    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Invalid timezone")
        return value
    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password: raise ValueError("password and confirm_password do not match")
        return self

class LoginRequestV2(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    client: ClientInfo | None = None
class GoogleLoginRequestV2(BaseModel):
    id_token: str = Field(min_length=20)
    client: ClientInfo | None = None
class SetPasswordRequestV2(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.confirm_password: raise ValueError("password and confirm_password do not match")
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
    refresh_token: str = Field(min_length=20)
    client: ClientInfo | None = None


OtpVerifyRequest.model_rebuild(
    _types_namespace={"SignupData": SignupData},
)
