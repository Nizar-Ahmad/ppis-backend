from pydantic import BaseModel, Field


class ClientInfo(BaseModel):
    client_type: str = Field(default="unknown", min_length=1, max_length=30)
    device_id: str | None = Field(default=None, max_length=255)
    device_name: str | None = Field(default=None, max_length=255)
    app_version: str | None = Field(default=None, max_length=50)


class MessageResponse(BaseModel):
    message: str
