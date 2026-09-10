from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
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
