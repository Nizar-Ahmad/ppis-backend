from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PPIS API"
    app_version: str = "1.0.0"

    database_url: str

    secret_key: str
    access_token_expire_minutes: int = 1440

    google_web_client_id: str
    google_web_client_secret: str

    google_calendar_redirect_uri_local: str
    google_calendar_redirect_uri_server: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()