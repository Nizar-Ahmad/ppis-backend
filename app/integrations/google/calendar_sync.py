"""Reusable Google Calendar synchronization service."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.google.calendar import (
    google_calendar_get,
    refresh_google_access_token,
)
from app.models import (
    CalendarEvent,
    GoogleCalendarConnection,
    User,
)
from app.schemas import GoogleCalendarSyncResponse


def parse_google_datetime(
    value: str,
) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    return datetime.fromisoformat(value)


def sync_google_calendar_for_user(
    *,
    user: User,
    db: Session,
    days_back: int = 7,
    days_forward: int = 30,
) -> GoogleCalendarSyncResponse:
    if (
        days_back < 0
        or days_back > 365
        or days_forward < 0
        or days_forward > 365
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "days_back and days_forward "
                "must be between 0 and 365"
            ),
        )

    connection = db.scalar(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.user_id
            == user.id
        )
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google Calendar is not connected",
        )

    access_token = refresh_google_access_token(
        connection,
        db,
    )

    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=days_back)
    time_max = now + timedelta(days=days_forward)

    calendars_data = google_calendar_get(
        "/users/me/calendarList",
        access_token,
        params={
            "maxResults": 250,
            "showHidden": "false",
        },
    )

    calendars = calendars_data.get("items", [])
    events_created = 0
    events_updated = 0
    events_skipped = 0

    for calendar_info in calendars:
        calendar_id = calendar_info.get("id")
        if not calendar_id:
            continue

        encoded_calendar_id = quote(
            calendar_id,
            safe="",
        )
        page_token = None

        while True:
            params = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500,
            }

            if page_token:
                params["pageToken"] = page_token

            events_data = google_calendar_get(
                (
                    "/calendars/"
                    f"{encoded_calendar_id}/events"
                ),
                access_token,
                params=params,
            )

            for item in events_data.get("items", []):
                event_id = item.get("id")
                if not event_id:
                    events_skipped += 1
                    continue

                external_id = f"{calendar_id}:{event_id}"

                existing = db.scalar(
                    select(CalendarEvent).where(
                        CalendarEvent.user_id
                        == user.id,
                        CalendarEvent.source
                        == "google",
                        CalendarEvent.external_id
                        == external_id,
                    )
                )

                if item.get("status") == "cancelled":
                    if existing:
                        db.delete(existing)
                    events_skipped += 1
                    continue

                start_data = item.get("start", {})
                end_data = item.get("end", {})
                start_value = start_data.get("dateTime")
                end_value = end_data.get("dateTime")

                if not start_value or not end_value:
                    events_skipped += 1
                    continue

                try:
                    start_time = parse_google_datetime(
                        start_value
                    )
                    end_time = parse_google_datetime(
                        end_value
                    )
                except ValueError:
                    events_skipped += 1
                    continue

                if end_time <= start_time:
                    events_skipped += 1
                    continue

                duration_minutes = int(
                    (
                        end_time - start_time
                    ).total_seconds()
                    / 60
                )
                title = item.get("summary")

                if existing:
                    existing.title = title
                    existing.start_time = start_time
                    existing.end_time = end_time
                    existing.duration_minutes = (
                        duration_minutes
                    )
                    events_updated += 1
                else:
                    duplicate = db.scalar(
                        select(CalendarEvent).where(
                            CalendarEvent.user_id
                            == user.id,
                            CalendarEvent.start_time
                            == start_time,
                            CalendarEvent.end_time
                            == end_time,
                            CalendarEvent.title
                            == title,
                        )
                    )

                    if duplicate:
                        events_skipped += 1
                        continue

                    db.add(
                        CalendarEvent(
                            user_id=user.id,
                            external_id=external_id,
                            source="google",
                            title=title,
                            start_time=start_time,
                            end_time=end_time,
                            duration_minutes=(
                                duration_minutes
                            ),
                        )
                    )
                    events_created += 1

            page_token = events_data.get(
                "nextPageToken"
            )
            if not page_token:
                break

    db.commit()

    return GoogleCalendarSyncResponse(
        calendars_checked=len(calendars),
        events_created=events_created,
        events_updated=events_updated,
        events_skipped=events_skipped,
    )
