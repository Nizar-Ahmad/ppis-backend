from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.integrations.google.fit import (
    GOOGLE_REVOKE_URL,
    GOOGLE_TOKEN_URL,
    aggregate_data_type,
    aggregate_numeric_total,
    google_fit_get,
    move_minutes_from_aggregate,
    refresh_google_fit_access_token,
    simplify_aggregate_response,
)
from app.models import ActivityStat, GoogleFitnessConnection, User, UserProfile
from app.schemas.google_fit import (
    GoogleFitAggregateResponse,
    GoogleFitConnectResponse,
    GoogleFitDataSourcesResponse,
    GoogleFitSessionsResponse,
    GoogleFitStatusResponse,
    GoogleFitSyncResponse,
)
from app.services.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/auth/google/fit",
    tags=["Google Fit"],
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

GOOGLE_FIT_SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
]

FIT_DATA_TYPES = {
    "steps": "com.google.step_count.delta",
    "calories": "com.google.calories.expended",
    "distance": "com.google.distance.delta",
    "heart-rate": "com.google.heart_rate.bpm",
    "sleep": "com.google.sleep.segment",
    "active-minutes": "com.google.active_minutes",
}


def get_redirect_uri(mode: str) -> str:
    if mode == "local":
        return settings.google_fit_redirect_uri_local
    if mode == "server":
        return settings.google_fit_redirect_uri_server
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="mode must be local or server",
    )


def create_oauth_state(user_id: UUID, redirect_uri: str) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "purpose": "google_fit_connect",
            "redirect_uri": redirect_uri,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def decode_oauth_state(state_token: str) -> dict:
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
    if payload.get("purpose") != "google_fit_connect":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    return payload


def _get_connection(current_user: User, db: Session) -> GoogleFitnessConnection:
    connection = db.scalar(
        select(GoogleFitnessConnection).where(
            GoogleFitnessConnection.user_id == current_user.id
        )
    )
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google Fit is not connected",
        )
    return connection


def _safe_timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _user_timezone(user_id: UUID, db: Session) -> ZoneInfo:
    name = db.scalar(
        select(UserProfile.timezone).where(UserProfile.user_id == user_id)
    )
    return _safe_timezone(name)


def _date_bounds(
    entry_date: date,
    timezone_info: ZoneInfo,
) -> tuple[datetime, datetime]:
    start_local = datetime.combine(
        entry_date,
        time.min,
        tzinfo=timezone_info,
    )
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


def _aggregate_response(
    *,
    data_type_name: str,
    days: int,
    access_token: str,
) -> GoogleFitAggregateResponse:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    data = aggregate_data_type(
        data_type_name=data_type_name,
        start=start,
        end=now,
        access_token=access_token,
    )
    return GoogleFitAggregateResponse(
        data_type_name=data_type_name,
        days=days,
        raw=data,
        simplified=simplify_aggregate_response(data),
    )


@router.get("/connect", response_model=GoogleFitConnectResponse)
def connect_google_fit(
    mode: str = Query(default="server", pattern="^(local|server)$"),
    current_user: User = Depends(get_current_user),
):
    redirect_uri = get_redirect_uri(mode)
    state_token = create_oauth_state(current_user.id, redirect_uri)
    query = urlencode(
        {
            "client_id": settings.google_web_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_FIT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state_token,
        }
    )
    return GoogleFitConnectResponse(
        authorization_url=f"{GOOGLE_AUTH_URL}?{query}"
    )


@router.get("/callback")
def google_fit_callback(
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

    state_data = decode_oauth_state(state)
    try:
        user_id = UUID(state_data["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    redirect_uri = state_data.get("redirect_uri")
    if redirect_uri not in {
        settings.google_fit_redirect_uri_local,
        settings.google_fit_redirect_uri_server,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URI",
        )

    if not db.get(User, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_web_client_id,
                "client_secret": settings.google_web_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=20,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google authentication service is currently unavailable",
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Google authorization code",
        )
    try:
        token_data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Google authentication service",
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google did not return an access token",
        )

    existing = db.scalar(
        select(GoogleFitnessConnection).where(
            GoogleFitnessConnection.user_id == user_id
        )
    )
    if existing:
        existing.access_token = access_token
        if refresh_token:
            existing.refresh_token = refresh_token
        existing.token_type = token_data.get("token_type", "Bearer")
        existing.scope = token_data.get("scope")
        existing.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_data.get("expires_in", 3600)
        )
    else:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Google did not return a refresh token. "
                    "Reconnect and grant Google Fit access again."
                ),
            )
        db.add(
            GoogleFitnessConnection(
                user_id=user_id,
                provider="google_fit",
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_data.get("token_type", "Bearer"),
                scope=token_data.get("scope"),
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=token_data.get("expires_in", 3600)),
            )
        )

    db.commit()
    return {
        "status": "success",
        "message": "Google Fit connected successfully",
    }


@router.get("/status", response_model=GoogleFitStatusResponse)
def google_fit_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = db.scalar(
        select(GoogleFitnessConnection).where(
            GoogleFitnessConnection.user_id == current_user.id
        )
    )
    if not connection:
        return GoogleFitStatusResponse(connected=False)
    return GoogleFitStatusResponse(
        connected=True,
        provider=connection.provider,
        scope=connection.scope,
        expires_at=connection.expires_at,
        last_sync_at=connection.last_sync_at,
    )


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_google_fit(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = db.scalar(
        select(GoogleFitnessConnection).where(
            GoogleFitnessConnection.user_id == current_user.id
        )
    )
    if not connection:
        return None
    try:
        requests.post(
            GOOGLE_REVOKE_URL,
            params={"token": connection.refresh_token},
            timeout=10,
        )
    except requests.RequestException:
        pass
    db.delete(connection)
    db.commit()
    return None


@router.get("/data-sources", response_model=GoogleFitDataSourcesResponse)
def fit_data_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = _get_connection(current_user, db)
    access_token = refresh_google_fit_access_token(connection, db)
    data = google_fit_get("/dataSources", access_token)
    sources = [
        {
            "dataStreamId": item.get("dataStreamId"),
            "dataStreamName": item.get("dataStreamName"),
            "type": item.get("type"),
            "dataType": item.get("dataType"),
            "application": item.get("application"),
            "device": item.get("device"),
        }
        for item in data.get("dataSource", [])
    ]
    return GoogleFitDataSourcesResponse(count=len(sources), data_sources=sources)


@router.get("/aggregate/{metric}", response_model=GoogleFitAggregateResponse)
def fit_aggregate(
    metric: str,
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data_type_name = FIT_DATA_TYPES.get(metric)
    if not data_type_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unsupported Google Fit metric: {metric}",
        )
    connection = _get_connection(current_user, db)
    access_token = refresh_google_fit_access_token(connection, db)
    return _aggregate_response(
        data_type_name=data_type_name,
        days=days,
        access_token=access_token,
    )


@router.get("/sessions", response_model=GoogleFitSessionsResponse)
def fit_sessions(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = _get_connection(current_user, db)
    access_token = refresh_google_fit_access_token(connection, db)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    data = google_fit_get(
        "/sessions",
        access_token,
        params={
            "startTime": start.isoformat(),
            "endTime": now.isoformat(),
        },
    )
    sessions = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "activityType": item.get("activityType"),
            "startTimeMillis": item.get("startTimeMillis"),
            "endTimeMillis": item.get("endTimeMillis"),
            "application": item.get("application"),
        }
        for item in data.get("session", [])
    ]
    return GoogleFitSessionsResponse(count=len(sessions), sessions=sessions)


@router.post("/sync", response_model=GoogleFitSyncResponse)
def sync_google_fit_activity(
    days_back: int = Query(default=7, ge=0, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = _get_connection(current_user, db)
    access_token = refresh_google_fit_access_token(connection, db)
    timezone_info = _user_timezone(current_user.id, db)
    today = datetime.now(timezone_info).date()

    imported = 0
    skipped = 0
    no_data = 0

    period = {
        "type": "day",
        "value": 1,
        "timeZoneId": str(timezone_info),
    }

    for offset in range(days_back + 1):
        entry_date = today - timedelta(days=offset)
        start, end = _date_bounds(entry_date, timezone_info)

        steps_data = aggregate_data_type(
            data_type_name=FIT_DATA_TYPES["steps"],
            start=start,
            end=end,
            access_token=access_token,
            bucket_period=period,
        )
        minutes_data = aggregate_data_type(
            data_type_name=FIT_DATA_TYPES["active-minutes"],
            start=start,
            end=end,
            access_token=access_token,
            bucket_period=period,
        )

        steps = max(0, round(aggregate_numeric_total(steps_data)))
        activity_minutes = min(
            1440,
            move_minutes_from_aggregate(minutes_data),
        )

        if steps == 0 and activity_minutes == 0:
            no_data += 1
            continue

        existing = db.scalar(
            select(ActivityStat).where(
                ActivityStat.user_id == current_user.id,
                ActivityStat.entry_date == entry_date,
            )
        )
        if existing and existing.source == "health_connect":
            skipped += 1
            continue

        if existing:
            existing.steps = steps
            existing.activity_minutes = activity_minutes
            existing.source = "google_fit"
        else:
            db.add(
                ActivityStat(
                    user_id=current_user.id,
                    entry_date=entry_date,
                    steps=steps,
                    activity_minutes=activity_minutes,
                    source="google_fit",
                )
            )
        imported += 1

    connection.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    return GoogleFitSyncResponse(
        days_requested=days_back + 1,
        days_imported=imported,
        days_skipped=skipped,
        days_without_data=no_data,
    )
