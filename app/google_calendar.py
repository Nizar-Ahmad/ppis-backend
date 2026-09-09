from datetime import (
    datetime,
    timedelta,
    timezone,
)

import requests
from fastapi import (
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    GoogleCalendarConnection,
)


GOOGLE_TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

GOOGLE_REVOKE_URL = (
    "https://oauth2.googleapis.com/revoke"
)

GOOGLE_CALENDAR_BASE_URL = (
    "https://www.googleapis.com/calendar/v3"
)


def refresh_google_access_token(
    connection: GoogleCalendarConnection,
    db: Session
) -> str:

    now = datetime.now(
        timezone.utc
    )

    if (
        connection.access_token
        and connection.expires_at
        and connection.expires_at
        > now + timedelta(minutes=1)
    ):
        return connection.access_token

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id":
                    settings.google_web_client_id,

                "client_secret":
                    settings.google_web_client_secret,

                "refresh_token":
                    connection.refresh_token,

                "grant_type":
                    "refresh_token",
            },
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google authentication service "
                "is currently unavailable"
            ),
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to refresh "
                "Google access token"
            ),
        )

    try:
        token_data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Invalid response from "
                "Google authentication service"
            ),
        )

    access_token = token_data.get(
        "access_token"
    )

    if not access_token:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google did not return "
                "an access token"
            ),
        )

    expires_in = token_data.get(
        "expires_in",
        3600
    )

    connection.access_token = (
        access_token
    )

    connection.expires_at = (
        now
        + timedelta(
            seconds=expires_in
        )
    )

    if token_data.get("scope"):
        connection.scope = (
            token_data["scope"]
        )

    db.commit()
    db.refresh(connection)

    return access_token


def google_calendar_get(
    path: str,
    access_token: str,
    params: dict | None = None
):

    try:
        response = requests.get(
            (
                f"{GOOGLE_CALENDAR_BASE_URL}"
                f"{path}"
            ),
            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },
            params=params,
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google Calendar service "
                "is currently unavailable"
            ),
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google Calendar request failed"
            ),
        )

    try:
        return response.json()

    except ValueError:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Invalid response from "
                "Google Calendar"
            ),
        )