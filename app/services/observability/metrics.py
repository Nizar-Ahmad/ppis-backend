from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models.observability import ApiUsageStat


EXCLUDED_METRIC_PATHS = {
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


def record_api_usage(
    *,
    method: str,
    route_path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    if route_path in EXCLUDED_METRIC_PATHS:
        return

    now = datetime.now(
        timezone.utc
    )

    today = now.date()

    success = (
        1
        if 200 <= status_code < 400
        else 0
    )

    client_error = (
        1
        if 400 <= status_code < 500
        else 0
    )

    server_error = (
        1
        if status_code >= 500
        else 0
    )

    try:
        with SessionLocal() as db:
            statement = insert(
                ApiUsageStat
            ).values(
                usage_date=today,
                method=method,
                route_path=route_path,
                request_count=1,
                success_count=success,
                client_error_count=client_error,
                server_error_count=server_error,
                total_duration_ms=duration_ms,
                last_accessed_at=now,
            )

            statement = (
                statement
                .on_conflict_do_update(
                    index_elements=[
                        ApiUsageStat.usage_date,
                        ApiUsageStat.method,
                        ApiUsageStat.route_path,
                    ],
                    set_={
                        "request_count": (
                            ApiUsageStat.request_count
                            + 1
                        ),
                        "success_count": (
                            ApiUsageStat.success_count
                            + success
                        ),
                        "client_error_count": (
                            ApiUsageStat.client_error_count
                            + client_error
                        ),
                        "server_error_count": (
                            ApiUsageStat.server_error_count
                            + server_error
                        ),
                        "total_duration_ms": (
                            ApiUsageStat.total_duration_ms
                            + duration_ms
                        ),
                        "last_accessed_at": now,
                    },
                )
            )

            db.execute(statement)
            db.commit()

    except Exception:
        # Metrics must never break
        # the API request.
        return
