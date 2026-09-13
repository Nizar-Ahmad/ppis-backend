from datetime import (
    datetime,
    timedelta,
    timezone,
)
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

import jwt
import requests
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from jwt.exceptions import (
    InvalidTokenError,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.integrations.google.health import (
    GOOGLE_TOKEN_URL,
    active_minutes_by_date,
    daily_rollup,
    list_data_points,
    refresh_google_health_access_token,
    steps_by_date,
)
from app.models import (
    ActivityStat,
    GoogleHealthConnection,
    User,
    UserProfile,
)
from app.schemas.google_health import (
    GoogleHealthConnectResponse,
    GoogleHealthDailyResponse,
    GoogleHealthDataPointsResponse,
    GoogleHealthStatusResponse,
    GoogleHealthSyncResponse,
)
from app.services.auth.dependencies import (
    get_current_user,
)


router = APIRouter(
    prefix="/auth/google/health",
    tags=["Google Health"],
)


GOOGLE_AUTH_URL = (
    "https://accounts.google.com/o/oauth2/v2/auth"
)


GOOGLE_HEALTH_SCOPES = [
    (
        "https://www.googleapis.com/auth/"
        "googlehealth.activity_and_fitness."
        "readonly"
    ),
    (
        "https://www.googleapis.com/auth/"
        "googlehealth."
        "health_metrics_and_measurements."
        "readonly"
    ),
    (
        "https://www.googleapis.com/auth/"
        "googlehealth.sleep.readonly"
    ),
]


DAILY_METRICS = {
    "steps":
        "steps",

    "active-minutes":
        "active-minutes",

    "distance":
        "distance",

    "calories":
        "active-energy-burned",

    "heart-rate":
        "heart-rate",
}


def get_redirect_uri(
    mode: str,
) -> str:
    if mode == "local":
        return (
            settings
            .google_health_redirect_uri_local
        )

    if mode == "server":
        return (
            settings
            .google_health_redirect_uri_server
        )

    raise HTTPException(
        status_code=
            status.HTTP_400_BAD_REQUEST,
        detail=(
            "mode must be local or server"
        ),
    )


def create_oauth_state(
    user_id: UUID,
    redirect_uri: str,
) -> str:
    payload = {
        "sub":
            str(user_id),

        "purpose":
            "google_health_connect",

        "redirect_uri":
            redirect_uri,

        "exp":
            (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    minutes=10
                )
            ),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def decode_oauth_state(
    state_token: str,
) -> dict:
    try:
        payload = jwt.decode(
            state_token,
            settings.secret_key,
            algorithms=["HS256"],
        )

    except InvalidTokenError:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid or expired "
                "OAuth state"
            ),
        )

    if (
        payload.get("purpose")
        != "google_health_connect"
    ):
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    return payload


def _get_connection(
    current_user: User,
    db: Session,
) -> GoogleHealthConnection:
    connection = db.scalar(
        select(
            GoogleHealthConnection
        ).where(
            GoogleHealthConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Google Health "
                "is not connected"
            ),
        )

    return connection


def _safe_timezone(
    name: str | None,
) -> ZoneInfo:
    try:
        return ZoneInfo(
            name or "UTC"
        )

    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _user_timezone(
    user_id: UUID,
    db: Session,
) -> ZoneInfo:
    timezone_name = db.scalar(
        select(
            UserProfile.timezone
        ).where(
            UserProfile.user_id
            == user_id
        )
    )

    return _safe_timezone(
        timezone_name
    )


def _rfc3339(
    value: datetime,
) -> str:
    return (
        value
        .astimezone(timezone.utc)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


@router.get(
    "/connect",
    response_model=
        GoogleHealthConnectResponse,
)
def connect_google_health(
    mode: str = Query(
        default="server",
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
        redirect_uri,
    )

    query = urlencode({
        "client_id":
            settings.google_web_client_id,

        "redirect_uri":
            redirect_uri,

        "response_type":
            "code",

        "scope":
            " ".join(
                GOOGLE_HEALTH_SCOPES
            ),

        "access_type":
            "offline",

        "prompt":
            "consent",

        "include_granted_scopes":
            "false",

        "state":
            state_token,
    })

    return (
        GoogleHealthConnectResponse(
            authorization_url=(
                f"{GOOGLE_AUTH_URL}"
                f"?{query}"
            )
        )
    )


@router.get(
    "/callback",
)
def google_health_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(
        get_db
    ),
):
    if error:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Google authorization "
                f"failed: {error}"
            ),
        )

    if not code or not state:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail=(
                "Missing Google "
                "authorization code or state"
            ),
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
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    redirect_uri = state_data.get(
        "redirect_uri"
    )

    if redirect_uri not in {
        settings
        .google_health_redirect_uri_local,

        settings
        .google_health_redirect_uri_server,
    }:
        raise HTTPException(
            status_code=
                status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI",
        )

    user = db.get(
        User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id":
                    settings
                    .google_web_client_id,

                "client_secret":
                    settings
                    .google_web_client_secret,

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
                "Failed to exchange "
                "Google authorization code"
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

    refresh_token = token_data.get(
        "refresh_token"
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

    existing = db.scalar(
        select(
            GoogleHealthConnection
        ).where(
            GoogleHealthConnection
            .user_id
            == user.id
        )
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            seconds=token_data.get(
                "expires_in",
                3600,
            )
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

        existing.provider = (
            "google_health"
        )

        existing.token_type = (
            token_data.get(
                "token_type",
                "Bearer",
            )
        )

        existing.scope = (
            token_data.get("scope")
        )

        existing.expires_at = (
            expires_at
        )

    else:
        if not refresh_token:
            raise HTTPException(
                status_code=
                    status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Google did not return "
                    "a refresh token. "
                    "Reconnect and grant "
                    "Google Health access again."
                ),
            )

        db.add(
            GoogleHealthConnection(
                user_id=
                    user.id,

                provider=
                    "google_health",

                access_token=
                    access_token,

                refresh_token=
                    refresh_token,

                token_type=
                    token_data.get(
                        "token_type",
                        "Bearer",
                    ),

                scope=
                    token_data.get(
                        "scope"
                    ),

                expires_at=
                    expires_at,
            )
        )

    db.commit()

    return {
        "status": "success",
        "message": (
            "Google Health "
            "connected successfully"
        ),
    }


@router.get(
    "/status",
    response_model=
        GoogleHealthStatusResponse,
)
def google_health_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    connection = db.scalar(
        select(
            GoogleHealthConnection
        ).where(
            GoogleHealthConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        return (
            GoogleHealthStatusResponse(
                connected=False
            )
        )

    return (
        GoogleHealthStatusResponse(
            connected=True,

            provider=
                connection.provider,

            scope=
                connection.scope,

            expires_at=
                connection.expires_at,

            last_sync_at=
                connection.last_sync_at,
        )
    )


@router.delete(
    "/disconnect",
    status_code=
        status.HTTP_204_NO_CONTENT,
)
def disconnect_google_health(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    connection = db.scalar(
        select(
            GoogleHealthConnection
        ).where(
            GoogleHealthConnection
            .user_id
            == current_user.id
        )
    )

    if not connection:
        return None

    db.delete(
        connection
    )

    db.commit()

    return None


@router.get(
    "/daily/{metric}",
    response_model=
        GoogleHealthDailyResponse,
)
def google_health_daily(
    metric: str,
    days: int = Query(
        default=7,
        ge=1,
        le=14,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    data_type = DAILY_METRICS.get(
        metric
    )

    if not data_type:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "Unsupported Google "
                f"Health metric: {metric}"
            ),
        )

    connection = _get_connection(
        current_user,
        db,
    )

    access_token = (
        refresh_google_health_access_token(
            connection,
            db,
        )
    )

    timezone_info = _user_timezone(
        current_user.id,
        db,
    )

    today = datetime.now(
        timezone_info
    ).date()

    start_date = (
        today
        - timedelta(
            days=days - 1
        )
    )

    data = daily_rollup(
        data_type=data_type,
        start_date=start_date,
        end_date_exclusive=(
            today
            + timedelta(days=1)
        ),
        access_token=access_token,
    )

    return GoogleHealthDailyResponse(
        metric=metric,
        data_type=data_type,
        days=days,
        raw=data,
    )


@router.get(
    "/sleep",
    response_model=
        GoogleHealthDataPointsResponse,
)
def google_health_sleep(
    days: int = Query(
        default=30,
        ge=1,
        le=90,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    connection = _get_connection(
        current_user,
        db,
    )

    access_token = (
        refresh_google_health_access_token(
            connection,
            db,
        )
    )

    timezone_info = _user_timezone(
        current_user.id,
        db,
    )

    today = datetime.now(
        timezone_info
    ).date()

    start_date = (
        today
        - timedelta(
            days=days - 1
        )
    )

    end_date = (
        today
        + timedelta(days=1)
    )

    filter_expression = (
        "sleep.interval.civil_end_time "
        f'>= "{start_date.isoformat()}" '
        "AND "
        "sleep.interval.civil_end_time "
        f'< "{end_date.isoformat()}"'
    )

    data = list_data_points(
        data_type="sleep",
        access_token=access_token,
        filter_expression=
            filter_expression,
        page_size=25,
    )

    points = data.get(
        "dataPoints",
        [],
    )

    return (
        GoogleHealthDataPointsResponse(
            data_type="sleep",
            count=len(points),
            data_points=points,
        )
    )


@router.get(
    "/exercise",
    response_model=
        GoogleHealthDataPointsResponse,
)
def google_health_exercise(
    days: int = Query(
        default=30,
        ge=1,
        le=90,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    connection = _get_connection(
        current_user,
        db,
    )

    access_token = (
        refresh_google_health_access_token(
            connection,
            db,
        )
    )

    timezone_info = _user_timezone(
        current_user.id,
        db,
    )

    today = datetime.now(
        timezone_info
    ).date()

    start_date = (
        today
        - timedelta(
            days=days - 1
        )
    )

    end_date_exclusive = (
        today
        + timedelta(days=1)
    )

    filter_expression = (
        "exercise.interval.civil_start_time "
        f'>= "{start_date.isoformat()}" '
        "AND "
        "exercise.interval.civil_start_time "
        f'< "{end_date_exclusive.isoformat()}"'
    )

    data = list_data_points(
        data_type="exercise",
        access_token=access_token,
        filter_expression=
            filter_expression,
        page_size=25,
    )

    points = data.get(
        "dataPoints",
        [],
    )

    return (
        GoogleHealthDataPointsResponse(
            data_type="exercise",
            count=len(points),
            data_points=points,
        )
    )


@router.post(
    "/sync",
    response_model=
        GoogleHealthSyncResponse,
)
def sync_google_health_activity(
    days_back: int = Query(
        default=7,
        ge=0,
        le=13,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    connection = _get_connection(
        current_user,
        db,
    )

    access_token = (
        refresh_google_health_access_token(
            connection,
            db,
        )
    )

    timezone_info = _user_timezone(
        current_user.id,
        db,
    )

    today = datetime.now(
        timezone_info
    ).date()

    start_date = (
        today
        - timedelta(
            days=days_back
        )
    )

    end_date_exclusive = (
        today
        + timedelta(days=1)
    )

    steps_data = daily_rollup(
        data_type="steps",
        start_date=start_date,
        end_date_exclusive=
            end_date_exclusive,
        access_token=access_token,
    )

    minutes_data = daily_rollup(
        data_type="active-minutes",
        start_date=start_date,
        end_date_exclusive=
            end_date_exclusive,
        access_token=access_token,
    )

    steps_map = steps_by_date(
        steps_data
    )

    minutes_map = (
        active_minutes_by_date(
            minutes_data
        )
    )

    imported = 0
    skipped = 0
    no_data = 0

    for offset in range(
        days_back + 1
    ):
        entry_date = (
            today
            - timedelta(days=offset)
        )

        has_steps = (
            entry_date
            in steps_map
        )

        has_minutes = (
            entry_date
            in minutes_map
        )

        if (
            not has_steps
            and not has_minutes
        ):
            no_data += 1
            continue

        steps = steps_map.get(
            entry_date,
            0,
        )

        activity_minutes = (
            minutes_map.get(
                entry_date,
                0,
            )
        )

        existing = db.scalar(
            select(
                ActivityStat
            ).where(
                ActivityStat.user_id
                == current_user.id,

                ActivityStat.entry_date
                == entry_date,
            )
        )

        # Health Connect remains the
        # authoritative mobile/device source.
        if (
            existing
            and existing.source
            == "health_connect"
        ):
            skipped += 1
            continue

        if existing:
            existing.steps = (
                steps
            )

            existing.activity_minutes = (
                activity_minutes
            )

            existing.source = (
                "google_health"
            )

        else:
            db.add(
                ActivityStat(
                    user_id=
                        current_user.id,

                    entry_date=
                        entry_date,

                    steps=
                        steps,

                    activity_minutes=
                        activity_minutes,

                    source=
                        "google_health",
                )
            )

        imported += 1

    connection.last_sync_at = (
        datetime.now(
            timezone.utc
        )
    )

    db.commit()

    return GoogleHealthSyncResponse(
        days_requested=
            days_back + 1,

        days_imported=
            imported,

        days_skipped=
            skipped,

        days_without_data=
            no_data,
    )
