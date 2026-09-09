from fastapi import FastAPI
from sqlalchemy import select

from app import models
from app.config import settings
from app.database import (
    Base,
    SessionLocal,
    engine,
)
from app.models import Role
from app.roles import (
    ROLE_ADMIN,
    ROLE_USER,
)
from app.routers import (
    activity,
    admin,
    analytics,
    auth,
    calendar,
    daily_inputs,
    google_calendar,
    health,
    insights,
    screen_time,
)


def seed_roles():
    with SessionLocal() as db:

        existing_roles = set(
            db.scalars(
                select(Role.name)
            ).all()
        )

        if ROLE_USER not in existing_roles:
            db.add(
                Role(
                    name=ROLE_USER,
                    description=(
                        "Normal application user"
                    ),
                )
            )

        if ROLE_ADMIN not in existing_roles:
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
    version=settings.app_version
)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(daily_inputs.router)
app.include_router(activity.router)
app.include_router(calendar.router)
app.include_router(screen_time.router)
app.include_router(analytics.router)
app.include_router(insights.router)
app.include_router(google_calendar.router)
app.include_router(admin.router)