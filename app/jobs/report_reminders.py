from calendar import monthrange
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.email_service import (
    send_report_reminder_email,
)
from app.models import (
    DailyInput,
    User,
)
from app.user_defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


def safe_timezone(
    value: str,
) -> ZoneInfo:
    try:
        return ZoneInfo(value)

    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def already_sent_this_week(
    sent_at: datetime | None,
    local_now: datetime,
) -> bool:
    if not sent_at:
        return False

    sent_local = sent_at.astimezone(
        local_now.tzinfo
    )

    return (
        sent_local.isocalendar()[:2]
        == local_now.isocalendar()[:2]
    )


def already_sent_this_month(
    sent_at: datetime | None,
    local_now: datetime,
) -> bool:
    if not sent_at:
        return False

    sent_local = sent_at.astimezone(
        local_now.tzinfo
    )

    return (
        sent_local.year == local_now.year
        and sent_local.month
        == local_now.month
    )


def get_previous_month_range(
    current_date: date,
) -> tuple[date, date]:
    if current_date.month == 1:
        year = current_date.year - 1
        month = 12

    else:
        year = current_date.year
        month = current_date.month - 1

    start_date = date(
        year,
        month,
        1,
    )

    end_date = date(
        year,
        month,
        monthrange(
            year,
            month,
        )[1],
    )

    return (
        start_date,
        end_date,
    )


def user_has_data_between(
    *,
    db,
    user_id,
    start_date: date,
    end_date: date,
) -> bool:
    record = db.scalar(
        select(
            DailyInput.id
        )
        .where(
            DailyInput.user_id
            == user_id,

            DailyInput.entry_date
            >= start_date,

            DailyInput.entry_date
            <= end_date,
        )
        .limit(1)
    )

    return record is not None


def run_report_reminders() -> None:
    now_utc = datetime.now(
        timezone.utc
    )

    with SessionLocal() as db:
        users = db.scalars(
            select(User)
        ).all()

        for user in users:
            profile = (
                get_or_create_profile(
                    user,
                    db,
                )
            )

            preferences = (
                get_or_create_notification_preferences(
                    user,
                    db,
                )
            )

            db.commit()

            db.refresh(profile)
            db.refresh(preferences)

            timezone_info = safe_timezone(
                profile.timezone
            )

            local_now = (
                now_utc.astimezone(
                    timezone_info
                )
            )

            # Respect the user's local timezone.
            if (
                local_now.hour
                < settings.report_reminder_hour_local
            ):
                continue

            # ==================================================
            # Weekly report reminder
            #
            # Monday = 0
            # Send Monday for the previous Mon-Sun week.
            # ==================================================

            if (
                preferences.weekly_report_email
                and local_now.weekday() == 0
                and not already_sent_this_week(
                    preferences.last_weekly_sent_at,
                    local_now,
                )
            ):
                weekly_end_date = (
                    local_now.date()
                    - timedelta(days=1)
                )

                weekly_start_date = (
                    weekly_end_date
                    - timedelta(days=6)
                )

                has_weekly_data = (
                    user_has_data_between(
                        db=db,
                        user_id=user.id,
                        start_date=weekly_start_date,
                        end_date=weekly_end_date,
                    )
                )

                if has_weekly_data:
                    sent = (
                        send_report_reminder_email(
                            target_email=user.email,
                            full_name=user.full_name,
                            user_id=user.id,
                            report_type="weekly",
                            start_date=weekly_start_date,
                            end_date=weekly_end_date,
                        )
                    )

                    if sent:
                        preferences.last_weekly_sent_at = (
                            now_utc
                        )

                        db.commit()

            # ==================================================
            # Monthly report reminder
            #
            # On the first day of a new month,
            # notify about the previous complete month.
            # ==================================================

            if (
                preferences.monthly_report_email
                and local_now.day == 1
                and not already_sent_this_month(
                    preferences.last_monthly_sent_at,
                    local_now,
                )
            ):
                (
                    monthly_start_date,
                    monthly_end_date,
                ) = get_previous_month_range(
                    local_now.date()
                )

                has_monthly_data = (
                    user_has_data_between(
                        db=db,
                        user_id=user.id,
                        start_date=monthly_start_date,
                        end_date=monthly_end_date,
                    )
                )

                if has_monthly_data:
                    sent = (
                        send_report_reminder_email(
                            target_email=user.email,
                            full_name=user.full_name,
                            user_id=user.id,
                            report_type="monthly",
                            start_date=monthly_start_date,
                            end_date=monthly_end_date,
                        )
                    )

                    if sent:
                        preferences.last_monthly_sent_at = (
                            now_utc
                        )

                        db.commit()


if __name__ == "__main__":
    run_report_reminders()