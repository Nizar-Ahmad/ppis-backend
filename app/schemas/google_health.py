from datetime import datetime

from pydantic import BaseModel


class GoogleHealthConnectResponse(
    BaseModel
):
    authorization_url: str


class GoogleHealthStatusResponse(
    BaseModel
):
    connected: bool

    provider: str | None = None
    scope: str | None = None

    expires_at: datetime | None = None
    last_sync_at: datetime | None = None


class GoogleHealthDailyResponse(
    BaseModel
):
    metric: str
    data_type: str
    days: int
    raw: dict


class GoogleHealthDataPointsResponse(
    BaseModel
):
    data_type: str
    count: int
    data_points: list[dict]


class GoogleHealthSyncResponse(
    BaseModel
):
    days_requested: int

    days_imported: int
    days_skipped: int
    days_without_data: int
