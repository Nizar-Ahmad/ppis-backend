from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from urllib.parse import quote, urlencode
from uuid import UUID

import jwt
import requests
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.google_calendar import (
    GOOGLE_REVOKE_URL,
    google_calendar_get,
    refresh_google_access_token,
)
from app.models import (
    CalendarEvent,
    GoogleCalendarConnection,
    User,
)
from app.schemas import (
    GoogleCalendarConnectResponse,
    GoogleCalendarStatusResponse,
    GoogleCalendarSyncResponse,
)


router = APIRouter(
    prefix="/auth/google/calendar",
    tags=["Google Calendar"],
)


GOOGLE_AUTH_URL = (
    "https://accounts.google.com/o/oauth2/v2/auth"
)

GOOGLE_TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

GOOGLE_SCOPES = [
    (
        "https://www.googleapis.com/auth/"
        "calendar.events.readonly"
    ),
    (
        "https://www.googleapis.com/auth/"
        "calendar.calendarlist.readonly"
    ),
]


def get_redirect_uri(
    mode: str
) -> str:

    if mode == "local":
        return (
            settings
            .google_calendar_redirect_uri_local
        )

    if mode == "server":
        return (
            settings
            .google_calendar_redirect_uri_server
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="mode must be local or server",
    )


def create_oauth_state(
    user_id: UUID,
    redirect_uri: str
) -> str:

    payload = {
        "sub": str(user_id),
        "purpose":
            "google_calendar_connect",
        "redirect_uri":
            redirect_uri,
        "exp":
            datetime.now(timezone.utc)
            + timedelta(minutes=10),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def decode_oauth_state(
    state_token: str
) -> dict:

    try:
        payload = jwt.decode(
            state_token,
            settings.secret_key,
            algorithms=["HS256"],
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    if (
        payload.get("purpose")
        != "google_calendar_connect"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    return payload


@router.get(
    "/connect",
    response_model=GoogleCalendarConnectResponse,
)
def connect_google_calendar(
    mode: str = Query(
        default="local",
        pattern="^(local|server)$",
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    redirect_uri = get_redirect_uri(
        mode
    )

    state_token = create_oauth_state(
        current_user.id,
        redirect_uri
    )

    query = urlencode({
        "client_id":
            settings.google_web_client_id,

        "redirect_uri":
            redirect_uri,

        "response_type":
            "code",

        "scope":
            " ".join(GOOGLE_SCOPES),

        "access_type":
            "offline",

        "prompt":
            "consent",

        "include_granted_scopes":
            "true",

        "state":
            state_token,
    })

    authorization_url = (
        f"{GOOGLE_AUTH_URL}?{query}"
    )

    return GoogleCalendarConnectResponse(
        authorization_url=
            authorization_url
    )


@router.get(
    "/callback",
)
def google_calendar_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authorization failed: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google authorization code or state",
        )

    state_data = decode_oauth_state(
        state
    )

    try:
        user_id = UUID(
            state_data["sub"]
        )

    except (
        KeyError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    redirect_uri = state_data.get(
        "redirect_uri"
    )

    if redirect_uri not in {
        settings.google_calendar_redirect_uri_local,
        settings.google_calendar_redirect_uri_server,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI",
        )

    user = db.get(
        User,
        user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id":
                    settings.google_web_client_id,

                "client_secret":
                    settings.google_web_client_secret,

                "code":
                    code,

                "grant_type":
                    "authorization_code",

                "redirect_uri":
                    redirect_uri,
            },
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google authentication service "
                "is currently unavailable"
            ),
        )


    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to exchange "
                "Google authorization code"
            ),
        )


    try:
        token_data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
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
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google did not return "
                "an access token"
            ),
        )


    refresh_token = token_data.get(
        "refresh_token"
    )

    expires_in = token_data.get(
        "expires_in",
        3600
    )

    existing = db.scalar(
        select(
            GoogleCalendarConnection
        ).where(
            GoogleCalendarConnection
            .user_id
            == user.id
        )
    )

    if existing:

        existing.access_token = (
            access_token
        )

        if refresh_token:
            existing.refresh_token = (
                refresh_token
            )

        existing.token_type = (
            token_data.get(
                "token_type",
                "Bearer"
            )
        )

        existing.scope = (
            token_data.get("scope")
        )

        existing.expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=expires_in
            )
        )

        connection = existing

    else:

        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Google did not return a refresh token. "
                    "Reconnect and grant calendar access again."
                ),
            )

        connection = (
            GoogleCalendarConnection(
                user_id=user.id,
                access_token=
                    access_token,

                refresh_token=
                    refresh_token,

                token_type=
                    token_data.get(
                        "token_type",
                        "Bearer"
                    ),

                scope=
                    token_data.get(
                        "scope"
                    ),

                expires_at=
                    datetime.now(
                        timezone.utc
                    )
                    + timedelta(
                        seconds=expires_in
                    ),
            )
        )

        db.add(
            connection
        )

    db.commit()

    return {
        "status": "success",
        "message":
            "Google Calendar connected successfully",
    }


@router.get(
    "/status",
    response_model=
        GoogleCalendarStatusResponse,
)
def google_calendar_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    connection = db.scalar(
        select(
            GoogleCalendarConnection
        ).where(
            GoogleCalendarConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        return (
            GoogleCalendarStatusResponse(
                connected=False
            )
        )

    return (
        GoogleCalendarStatusResponse(
            connected=True,
            scope=connection.scope,
            expires_at=
                connection.expires_at,
        )
    )


@router.delete(
    "/disconnect",
    status_code=
        status.HTTP_204_NO_CONTENT,
)
def disconnect_google_calendar(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    connection = db.scalar(
        select(
            GoogleCalendarConnection
        ).where(
            GoogleCalendarConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        return None

    try:
        requests.post(
            GOOGLE_REVOKE_URL,
            params={
                "token":
                    connection.refresh_token
            },
            timeout=10,
        )
    except requests.RequestException:
        pass

    db.delete(
        connection
    )

    db.commit()

    return None

def parse_google_datetime(
    value: str
) -> datetime:

    if value.endswith("Z"):
        value = (
            value[:-1]
            + "+00:00"
        )

    return datetime.fromisoformat(
        value
    )


@router.post(
    "/sync",
    response_model=GoogleCalendarSyncResponse,
)
def sync_google_calendar(
    days_back: int = 7,
    days_forward: int = 30,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    if (
        days_back < 0
        or days_back > 365
        or days_forward < 0
        or days_forward > 365
    ):
        raise HTTPException(
            status_code=
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "days_back and days_forward "
                "must be between 0 and 365"
            ),
        )

    connection = db.scalar(
        select(
            GoogleCalendarConnection
        ).where(
            GoogleCalendarConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Google Calendar is not connected"
            ),
        )

    access_token = (
        refresh_google_access_token(
            connection,
            db
        )
    )

    now = datetime.now(
        timezone.utc
    )

    time_min = (
        now
        - timedelta(
            days=days_back
        )
    )

    time_max = (
        now
        + timedelta(
            days=days_forward
        )
    )

    calendars_data = (
        google_calendar_get(
            "/users/me/calendarList",
            access_token,
            params={
                "maxResults": 250,
                "showHidden": "false",
            },
        )
    )

    calendars = calendars_data.get(
        "items",
        []
    )

    events_created = 0
    events_updated = 0
    events_skipped = 0

    for calendar_info in calendars:

        calendar_id = (
            calendar_info.get("id")
        )

        if not calendar_id:
            continue

        encoded_calendar_id = quote(
            calendar_id,
            safe=""
        )

        page_token = None

        while True:

            params = {
                "timeMin":
                    time_min.isoformat(),

                "timeMax":
                    time_max.isoformat(),

                "singleEvents":
                    "true",

                "orderBy":
                    "startTime",

                "maxResults":
                    2500,
            }

            if page_token:
                params["pageToken"] = (
                    page_token
                )

            events_data = (
                google_calendar_get(
                    (
                        "/calendars/"
                        f"{encoded_calendar_id}/events"
                    ),
                    access_token,
                    params=params,
                )
            )

            for item in (
                events_data.get(
                    "items",
                    []
                )
            ):
                event_id = item.get(
                    "id"
                )

                if not event_id:
                    events_skipped += 1
                    continue

                external_id = (
                    f"{calendar_id}:"
                    f"{event_id}"
                )

                existing = db.scalar(
                    select(
                        CalendarEvent
                    ).where(
                        CalendarEvent
                        .user_id
                        == current_user.id,

                        CalendarEvent
                        .source
                        == "google",

                        CalendarEvent
                        .external_id
                        == external_id,
                    )
                )

                if (
                    item.get("status")
                    == "cancelled"
                ):
                    if existing:
                        db.delete(
                            existing
                        )

                    events_skipped += 1
                    continue

                start_data = item.get(
                    "start",
                    {}
                )

                end_data = item.get(
                    "end",
                    {}
                )

                start_value = (
                    start_data.get(
                        "dateTime"
                    )
                )

                end_value = (
                    end_data.get(
                        "dateTime"
                    )
                )

                # Ignore all-day events.
                # They should not count as meetings.
                if (
                    not start_value
                    or not end_value
                ):
                    events_skipped += 1
                    continue

                try:
                    start_time = (
                        parse_google_datetime(
                            start_value
                        )
                    )

                    end_time = (
                        parse_google_datetime(
                            end_value
                        )
                    )

                except ValueError:
                    events_skipped += 1
                    continue

                if (
                    end_time
                    <= start_time
                ):
                    events_skipped += 1
                    continue

                duration_minutes = int(
                    (
                        end_time
                        - start_time
                    ).total_seconds()
                    / 60
                )

                title = item.get(
                    "summary"
                )

                if existing:

                    existing.title = (
                        title
                    )

                    existing.start_time = (
                        start_time
                    )

                    existing.end_time = (
                        end_time
                    )

                    existing.duration_minutes = (
                        duration_minutes
                    )

                    events_updated += 1

                else:

                    duplicate = db.scalar(
                        select(
                            CalendarEvent
                        ).where(
                            CalendarEvent
                            .user_id
                            == current_user.id,

                            CalendarEvent
                            .start_time
                            == start_time,

                            CalendarEvent
                            .end_time
                            == end_time,

                            CalendarEvent
                            .title
                            == title,
                        )
                    )

                    if duplicate:
                        events_skipped += 1
                        continue

                    event = CalendarEvent(
                        user_id=
                            current_user.id,

                        external_id=
                            external_id,

                        source=
                            "google",

                        title=
                            title,

                        start_time=
                            start_time,

                        end_time=
                            end_time,

                        duration_minutes=
                            duration_minutes,
                    )

                    db.add(
                        event
                    )

                    events_created += 1

            page_token = (
                events_data.get(
                    "nextPageToken"
                )
            )

            if not page_token:
                break

    db.commit()

    return (
        GoogleCalendarSyncResponse(
            calendars_checked=
                len(calendars),

            events_created=
                events_created,

            events_updated=
                events_updated,

            events_skipped=
                events_skipped,
        )
    )