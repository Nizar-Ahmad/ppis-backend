"""Scheduled Google Calendar synchronization for connected users."""

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.google.calendar_sync import (
    sync_google_calendar_for_user,
)
from app.models import (
    GoogleCalendarConnection,
    User,
)


logger = logging.getLogger(
    "ppis.jobs.google_calendar_sync"
)


def run_google_calendar_sync() -> None:
    with SessionLocal() as db:
        user_ids = db.scalars(
            select(
                GoogleCalendarConnection.user_id
            )
        ).all()

        for user_id in user_ids:
            user = db.get(User, user_id)
            if not user:
                continue

            try:
                result = sync_google_calendar_for_user(
                    user=user,
                    db=db,
                    days_back=(
                        settings
                        .google_calendar_sync_days_back
                    ),
                    days_forward=(
                        settings
                        .google_calendar_sync_days_forward
                    ),
                )

                logger.info(
                    (
                        "Google Calendar sync user=%s "
                        "calendars=%s created=%s "
                        "updated=%s skipped=%s"
                    ),
                    user.id,
                    result.calendars_checked,
                    result.events_created,
                    result.events_updated,
                    result.events_skipped,
                )
            except Exception:
                db.rollback()
                logger.exception(
                    "Google Calendar sync failed user=%s",
                    user.id,
                )


if __name__ == "__main__":
    run_google_calendar_sync()
