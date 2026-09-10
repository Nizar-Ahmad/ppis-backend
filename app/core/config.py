from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_name: str = "PPIS API"
    app_version: str = "1.0.0"

    database_url: str

    secret_key: str

    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    session_touch_interval_minutes: int = 5
    session_retention_days: int = 90

    otp_secret_key: str
    otp_expire_minutes: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5
    otp_max_sends_per_hour: int = 5
    otp_retention_days: int = 90

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_app_password: str
    email_from: str

    email_log_retention_days: int = 365

    audit_log_retention_days: int = 365
    api_usage_retention_days: int = 365

    report_reminder_hour_local: int = 18

    google_web_client_id: str
    google_web_client_secret: str

    google_calendar_redirect_uri_local: str
    google_calendar_redirect_uri_server: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()