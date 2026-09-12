from datetime import datetime

from pydantic import BaseModel, Field


class GoogleFitConnectResponse(BaseModel):
    authorization_url: str


class GoogleFitStatusResponse(BaseModel):
    connected: bool
    provider: str | None = None
    scope: str | None = None
    expires_at: datetime | None = None
    last_sync_at: datetime | None = None


class GoogleFitSyncResponse(BaseModel):
    days_requested: int
    days_imported: int
    days_skipped: int
    days_without_data: int
    source: str = "google_fit"


class GoogleFitAggregateResponse(BaseModel):
    data_type_name: str
    days: int = Field(ge=1, le=90)
    raw: dict
    simplified: list[dict]


class GoogleFitDataSourcesResponse(BaseModel):
    count: int
    data_sources: list[dict]


class GoogleFitSessionsResponse(BaseModel):
    count: int
    sessions: list[dict]
