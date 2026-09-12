from datetime import datetime, timedelta, timezone

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import GoogleFitnessConnection


FIT_BASE_URL = "https://www.googleapis.com/fitness/v1/users/me"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def refresh_google_fit_access_token(
    connection: GoogleFitnessConnection,
    db: Session,
) -> str:
    now = datetime.now(timezone.utc)

    if (
        connection.access_token
        and connection.expires_at
        and connection.expires_at > now + timedelta(minutes=1)
    ):
        return connection.access_token

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_web_client_id,
                "client_secret": settings.google_web_client_secret,
                "refresh_token": connection.refresh_token,
                "grant_type": "refresh_token",
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
            detail="Failed to refresh Google Fit access token",
        )

    try:
        token_data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Google authentication service",
        )

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google did not return an access token",
        )

    connection.access_token = access_token
    connection.expires_at = now + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if token_data.get("scope"):
        connection.scope = token_data["scope"]

    db.commit()
    db.refresh(connection)
    return access_token


def google_fit_get(
    path: str,
    access_token: str,
    params: dict | None = None,
) -> dict:
    try:
        response = requests.get(
            f"{FIT_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Fit service is currently unavailable",
        )

    return _parse_google_response(response)


def google_fit_post(
    path: str,
    access_token: str,
    json_body: dict | None = None,
) -> dict:
    try:
        response = requests.post(
            f"{FIT_BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=json_body,
            timeout=30,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Fit service is currently unavailable",
        )

    return _parse_google_response(response)


def _parse_google_response(response: requests.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Google Fit request failed",
                "google_status": response.status_code,
                "google_response": body,
            },
        )

    return body


def milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def aggregate_data_type(
    *,
    data_type_name: str,
    start: datetime,
    end: datetime,
    access_token: str,
    bucket_millis: int = 86_400_000,
    bucket_period: dict | None = None,
) -> dict:
    body: dict = {
        "aggregateBy": [{"dataTypeName": data_type_name}],
        "startTimeMillis": milliseconds(start),
        "endTimeMillis": milliseconds(end),
    }

    if bucket_period is not None:
        body["bucketByTime"] = {
            "period": bucket_period,
        }
    else:
        body["bucketByTime"] = {
            "durationMillis": bucket_millis,
        }

    return google_fit_post(
        "/dataset:aggregate",
        access_token,
        body,
    )


def simplify_aggregate_response(data: dict) -> list[dict]:
    result: list[dict] = []

    for bucket in data.get("bucket", []):
        bucket_item = {
            "startTimeMillis": bucket.get("startTimeMillis"),
            "endTimeMillis": bucket.get("endTimeMillis"),
            "datasets": [],
        }

        for dataset in bucket.get("dataset", []):
            dataset_item = {
                "dataSourceId": dataset.get("dataSourceId"),
                "points": [],
            }

            for point in dataset.get("point", []):
                values = []
                for value in point.get("value", []):
                    values.append(
                        {
                            "intVal": value.get("intVal"),
                            "fpVal": value.get("fpVal"),
                            "stringVal": value.get("stringVal"),
                            "mapVal": value.get("mapVal"),
                        }
                    )

                dataset_item["points"].append(
                    {
                        "startTimeNanos": point.get("startTimeNanos"),
                        "endTimeNanos": point.get("endTimeNanos"),
                        "dataTypeName": point.get("dataTypeName"),
                        "originDataSourceId": point.get("originDataSourceId"),
                        "values": values,
                    }
                )

            bucket_item["datasets"].append(dataset_item)

        result.append(bucket_item)

    return result


def aggregate_numeric_total(data: dict) -> float:
    total = 0.0

    for bucket in data.get("bucket", []):
        for dataset in bucket.get("dataset", []):
            for point in dataset.get("point", []):
                for value in point.get("value", []):
                    if value.get("intVal") is not None:
                        total += float(value["intVal"])
                    elif value.get("fpVal") is not None:
                        total += float(value["fpVal"])

    return total


def move_minutes_from_aggregate(data: dict) -> int:
    duration_millis = aggregate_numeric_total(data)
    return max(0, round(duration_millis / 60_000))
