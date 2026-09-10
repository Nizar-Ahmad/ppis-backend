import logging
import time

from fastapi import (
    FastAPI,
    Request,
)
from sqlalchemy import select
from starlette.concurrency import (
    run_in_threadpool,
)

from app import (
    extended_models,
    models,
)
from app.config import settings
from app.database import (
    Base,
    SessionLocal,
    engine,
)
from app.metrics import (
    record_api_usage,
)
from app.models import Role
from app.roles import (
    ROLE_ADMIN,
    ROLE_USER,
)
from app.routers import (
    activity,
    admin,
    admin_feedback,
    admin_observability,
    admin_sessions,
    analytics,
    auth,
    calendar,
    daily_inputs,
    feedback,
    google_calendar,
    health,
    insights,
    monthly_analytics,
    otp,
    profile,
    screen_time,
    sessions,
)


logger = logging.getLogger(
    "ppis.api"
)


def seed_roles():
    with SessionLocal() as db:
        existing_roles = set(
            db.scalars(
                select(Role.name)
            ).all()
        )

        if (
            ROLE_USER
            not in existing_roles
        ):
            db.add(
                Role(
                    name=ROLE_USER,
                    description=(
                        "Normal application user"
                    ),
                )
            )

        if (
            ROLE_ADMIN
            not in existing_roles
        ):
            db.add(
                Role(
                    name=ROLE_ADMIN,
                    description=(
                        "Application administrator"
                    ),
                )
            )

        db.commit()


Base.metadata.create_all(
    bind=engine
)

seed_roles()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.middleware("http")
async def request_metrics_middleware(
    request: Request,
    call_next,
):
    started = time.perf_counter()

    status_code = 500

    try:
        response = await call_next(
            request
        )

        status_code = (
            response.status_code
        )

        return response

    finally:
        duration_ms = (
            time.perf_counter()
            - started
        ) * 1000

        route = request.scope.get(
            "route"
        )

        route_path = getattr(
            route,
            "path",
            request.url.path,
        )

        logger.info(
            "%s %s -> %s %.2fms",
            request.method,
            route_path,
            status_code,
            duration_ms,
        )

        await run_in_threadpool(
            record_api_usage,
            method=request.method,
            route_path=route_path,
            status_code=status_code,
            duration_ms=duration_ms,
        )


app.include_router(
    health.router
)

app.include_router(
    auth.router
)

app.include_router(
    otp.router
)

app.include_router(
    sessions.router
)

app.include_router(
    profile.router
)

app.include_router(
    feedback.router
)

app.include_router(
    daily_inputs.router
)

app.include_router(
    activity.router
)

app.include_router(
    calendar.router
)

app.include_router(
    screen_time.router
)

app.include_router(
    analytics.router
)

app.include_router(
    monthly_analytics.router
)

app.include_router(
    insights.router
)

app.include_router(
    google_calendar.router
)

app.include_router(
    admin.router
)

app.include_router(
    admin_sessions.router
)

app.include_router(
    admin_feedback.router
)

app.include_router(
    admin_observability.router
)