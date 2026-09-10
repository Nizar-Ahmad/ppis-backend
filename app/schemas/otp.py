from typing import TYPE_CHECKING, Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, model_validator
from app.schemas.common import ClientInfo
from app.schemas.productivity import UserResponse

if TYPE_CHECKING:
    from app.schemas.auth import SignupData


OtpPurpose = Literal[
    "login",
    "signup",
    "reset_password",
    "change_password",
]
class OtpSendRequest(BaseModel):
    purpose: Literal["signup", "reset_password", "change_password"]
    email: EmailStr | None = None
    @model_validator(mode="after")
    def validate_email_requirement(self):
        if self.purpose in {"signup", "reset_password"} and self.email is None: raise ValueError("email is required for this OTP purpose")
        return self
class OtpResendRequest(BaseModel): challenge_id: UUID
class OtpChallengeResponse(BaseModel):
    challenge_id: UUID
    purpose: OtpPurpose
    expires_in: int
class OtpVerifyRequest(BaseModel):
    challenge_id: UUID
    purpose: OtpPurpose
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    signup_data: "SignupData | None" = None
    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    confirm_new_password: str | None = Field(default=None, min_length=8, max_length=128)
    client: ClientInfo | None = None
    @model_validator(mode="after")
    def validate_payload_for_purpose(self):
        if self.purpose == "signup" and self.signup_data is None: raise ValueError("signup_data is required for signup verification")
        if self.purpose == "reset_password":
            if self.new_password is None or self.confirm_new_password is None: raise ValueError("new_password and confirm_new_password are required for password reset")
            if self.new_password != self.confirm_new_password: raise ValueError("new_password and confirm_new_password do not match")
        if self.purpose == "change_password":
            if self.current_password is None: raise ValueError("current_password is required for password change")
            if self.new_password is None or self.confirm_new_password is None: raise ValueError("new_password and confirm_new_password are required for password change")
            if self.new_password != self.confirm_new_password: raise ValueError("new_password and confirm_new_password do not match")
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
