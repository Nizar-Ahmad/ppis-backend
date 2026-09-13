from datetime import (
    date,
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

from app.core.config import settings
from app.models import GoogleHealthConnection


GOOGLE_HEALTH_BASE_URL = (
    "https://health.googleapis.com/v4/users/me"
)

GOOGLE_TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

GOOGLE_REVOKE_URL = (
    "https://oauth2.googleapis.com/revoke"
)


def refresh_google_health_access_token(
    connection: GoogleHealthConnection,
    db: Session,
) -> str:
    now = datetime.now(timezone.utc)

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
                "Google Health access token"
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

    connection.access_token = (
        access_token
    )

    connection.expires_at = (
        now
        + timedelta(
            seconds=token_data.get(
                "expires_in",
                3600,
            )
        )
    )

    if token_data.get("scope"):
        connection.scope = (
            token_data["scope"]
        )

    db.commit()
    db.refresh(connection)

    return access_token


def _parse_google_health_response(
    response: requests.Response,
) -> dict:
    try:
        body = response.json()

    except ValueError:
        body = {
            "raw": response.text
        }

    if response.status_code >= 400:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail={
                "message":
                    "Google Health request failed",

                "google_status":
                    response.status_code,

                "google_response":
                    body,
            },
        )

    return body


def google_health_get(
    path: str,
    access_token: str,
    params: dict | None = None,
) -> dict:
    try:
        response = requests.get(
            (
                f"{GOOGLE_HEALTH_BASE_URL}"
                f"{path}"
            ),
            headers={
                "Authorization":
                    f"Bearer {access_token}",

                "Accept":
                    "application/json",
            },
            params=params,
            timeout=30,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google Health service "
                "is currently unavailable"
            ),
        )

    return _parse_google_health_response(
        response
    )


def google_health_post(
    path: str,
    access_token: str,
    json_body: dict | None = None,
) -> dict:
    try:
        response = requests.post(
            (
                f"{GOOGLE_HEALTH_BASE_URL}"
                f"{path}"
            ),
            headers={
                "Authorization":
                    f"Bearer {access_token}",

                "Accept":
                    "application/json",

                "Content-Type":
                    "application/json",
            },
            json=json_body,
            timeout=30,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=
                status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google Health service "
                "is currently unavailable"
            ),
        )

    return _parse_google_health_response(
        response
    )


def civil_datetime(
    value: date,
) -> dict:
    return {
        "date": {
            "year": value.year,
            "month": value.month,
            "day": value.day,
        },
        "time": {
            "hours": 0,
            "minutes": 0,
            "seconds": 0,
            "nanos": 0,
        },
    }


def daily_rollup(
    *,
    data_type: str,
    start_date: date,
    end_date_exclusive: date,
    access_token: str,
) -> dict:
    if (
        end_date_exclusive
        <= start_date
    ):
        raise ValueError(
            "end_date_exclusive must "
            "be after start_date"
        )

    requested_days = (
        end_date_exclusive
        - start_date
    ).days

    body = {
        "range": {
            "start":
                civil_datetime(
                    start_date
                ),

            "end":
                civil_datetime(
                    end_date_exclusive
                ),
        },

        "windowSizeDays":
            1,

        # dailyRollUp limits the product of
        # windowSizeDays * pageSize by data type.
        #
        # PPIS requests one daily bucket per requested
        # local date, so asking for exactly that many
        # buckets avoids artificial 90/14-day violations
        # and also avoids pagination for our <= 14-day
        # application windows.
        "pageSize":
            requested_days,

        "dataSourceFamily":
            (
                "users/me/"
                "dataSourceFamilies/"
                "all-sources"
            ),
    }

    return google_health_post(
        (
            f"/dataTypes/{data_type}/"
            "dataPoints:dailyRollUp"
        ),
        access_token,
        body,
    )


def list_data_points(
    *,
    data_type: str,
    access_token: str,
    filter_expression: str | None = None,
    page_size: int = 25,
) -> dict:
    points: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict = {
            "pageSize":
                page_size,
        }

        if filter_expression:
            params["filter"] = (
                filter_expression
            )

        if page_token:
            params["pageToken"] = (
                page_token
            )

        data = google_health_get(
            (
                f"/dataTypes/{data_type}/"
                "dataPoints"
            ),
            access_token,
            params=params,
        )

        points.extend(
            data.get(
                "dataPoints",
                [],
            )
        )

        page_token = data.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return {
        "dataPoints":
            points,

        "nextPageToken":
            "",
    }


def civil_date_from_rollup(
    item: dict,
) -> date | None:
    value = (
        item
        .get(
            "civilStartTime",
            {},
        )
        .get(
            "date",
            {},
        )
    )

    try:
        return date(
            int(value["year"]),
            int(value["month"]),
            int(value["day"]),
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


def steps_by_date(
    data: dict,
) -> dict[date, int]:
    result: dict[date, int] = {}

    for item in data.get(
        "rollupDataPoints",
        [],
    ):
        if "steps" not in item:
            continue

        entry_date = (
            civil_date_from_rollup(
                item
            )
        )

        if entry_date is None:
            continue

        raw_count = (
            item
            .get("steps", {})
            .get(
                "countSum",
                0,
            )
        )

        try:
            result[entry_date] = (
                max(
                    0,
                    int(raw_count),
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            result[entry_date] = 0

    return result


def active_minutes_by_date(
    data: dict,
) -> dict[date, int]:
    result: dict[date, int] = {}

    for item in data.get(
        "rollupDataPoints",
        [],
    ):
        active_value = item.get(
            "activeMinutes"
        )

        if not active_value:
            continue

        entry_date = (
            civil_date_from_rollup(
                item
            )
        )

        if entry_date is None:
            continue

        total = 0

        included_levels = {
            "MODERATELY_ACTIVE",
            "VERY_ACTIVE",
        }

        for level in (
            active_value.get(
                (
                    "activeMinutes"
                    "RollupByActivityLevel"
                ),
                [],
            )
        ):
            if (
                level.get("activityLevel")
                not in included_levels
            ):
                continue

            try:
                total += int(
                    level.get(
                        "activeMinutesSum",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        result[entry_date] = max(
            0,
            min(
                1440,
                total,
            ),
        )

    return result
