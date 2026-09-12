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

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.notifications.email.service import (
    send_daily_report_email,
    send_report_reminder_email,
)
from app.services.analytics.daily import (
    calculate_and_save_daily_score,
    get_available_dates_between,
)
from app.services.users.defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


def safe_timezone(value: str) -> ZoneInfo:
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
        and sent_local.month == local_now.month
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

    start_date = date(year, month, 1)
    end_date = date(
        year,
        month,
        monthrange(year, month)[1],
    )
    return start_date, end_date


def user_has_data_between(
    *,
    db,
    user_id,
    start_date: date,
    end_date: date,
) -> bool:
    return bool(
        get_available_dates_between(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            db=db,
        )
    )


def run_report_reminders(
    now_utc: datetime | None = None,
) -> None:
    now_utc = (
        now_utc
        or datetime.now(timezone.utc)
    )

    with SessionLocal() as db:
        users = db.scalars(
            select(User)
        ).all()

        for user in users:
            profile = get_or_create_profile(
                user,
                db,
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
            local_now = now_utc.astimezone(
                timezone_info
            )

            if (
                preferences.daily_report_email
                and local_now.hour
                >= settings.daily_report_hour_local
            ):
                report_date = (
                    local_now.date()
                    - timedelta(days=1)
                )

                if (
                    preferences.last_daily_report_date
                    != report_date
                    and user_has_data_between(
                        db=db,
                        user_id=user.id,
                        start_date=report_date,
                        end_date=report_date,
                    )
                ):
                    score = (
                        calculate_and_save_daily_score(
                            report_date,
                            user,
                            db,
                        )
                    )

                    sent = send_daily_report_email(
                        target_email=user.email,
                        full_name=user.full_name,
                        user_id=user.id,
                        report_date=report_date,
                        productivity_score=(
                            score.productivity_score
                        ),
                        stress_index=score.stress_index,
                        data_coverage=score.data_coverage,
                        stress_data_coverage=(
                            score.stress_data_coverage
                        ),
                    )

                    if sent:
                        preferences.last_daily_report_date = report_date
                        db.commit()

            if (
                local_now.hour
                < settings.report_reminder_hour_local
            ):
                continue

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

                if user_has_data_between(
                    db=db,
                    user_id=user.id,
                    start_date=weekly_start_date,
                    end_date=weekly_end_date,
                ):
                    sent = send_report_reminder_email(
                        target_email=user.email,
                        full_name=user.full_name,
                        user_id=user.id,
                        report_type="weekly",
                        start_date=weekly_start_date,
                        end_date=weekly_end_date,
                    )
                    if sent:
                        preferences.last_weekly_sent_at = now_utc
                        db.commit()

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

                if user_has_data_between(
                    db=db,
                    user_id=user.id,
                    start_date=monthly_start_date,
                    end_date=monthly_end_date,
                ):
                    sent = send_report_reminder_email(
                        target_email=user.email,
                        full_name=user.full_name,
                        user_id=user.id,
                        report_type="monthly",
                        start_date=monthly_start_date,
                        end_date=monthly_end_date,
                    )
                    if sent:
                        preferences.last_monthly_sent_at = now_utc
                        db.commit()


if __name__ == "__main__":
    run_report_reminders()
