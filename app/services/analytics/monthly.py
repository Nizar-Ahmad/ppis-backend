from calendar import monthrange
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyInput, ScreenTimeStat, User
from app.schemas.analytics import MonthlyAnalyticsResponse
from app.services.analytics.daily import (
    calculate_and_save_daily_score,
    get_available_dates_between,
    get_meeting_minutes_for_day,
)


def _average(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return round(
        sum(values) / len(values),
        2,
    )


def get_monthly_analytics(
    year: int,
    month: int,
    current_user: User,
    db: Session,
) -> MonthlyAnalyticsResponse:
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

    analysis_dates = (
        get_available_dates_between(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            db=db,
        )
    )

    if not analysis_dates:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "No analytics data found "
                "for this month"
            ),
        )

    daily_inputs = db.scalars(
        select(DailyInput)
        .where(
            DailyInput.user_id
            == current_user.id,
            DailyInput.entry_date
            >= start_date,
            DailyInput.entry_date
            <= end_date,
        )
        .order_by(
            DailyInput.entry_date.asc()
        )
    ).all()

    screen_records = {
        item.entry_date: item
        for item in db.scalars(
            select(ScreenTimeStat).where(
                ScreenTimeStat.user_id
                == current_user.id,
                ScreenTimeStat.entry_date
                >= start_date,
                ScreenTimeStat.entry_date
                <= end_date,
            )
        ).all()
    }

    scores = []
    total_meeting_minutes = 0
    total_screen_minutes = 0

    for analysis_date in analysis_dates:
        score = calculate_and_save_daily_score(
            analysis_date,
            current_user,
            db,
        )
        scores.append(score)

        total_meeting_minutes += (
            get_meeting_minutes_for_day(
                current_user.id,
                analysis_date,
                db,
            )
        )

        screen_time = screen_records.get(
            analysis_date
        )

        if screen_time:
            total_screen_minutes += (
                screen_time.total_minutes
            )

    subjective_days = len(
        daily_inputs
    )

    average_sleep_hours = _average([
        item.sleep_hours
        for item in daily_inputs
    ])

    average_mood = _average([
        float(item.mood)
        for item in daily_inputs
    ])

    average_energy_level = _average([
        float(item.energy_level)
        for item in daily_inputs
    ])

    total_focused_work_hours = round(
        sum(
            item.focused_work_hours
            for item in daily_inputs
        ),
        2,
    )

    average_productivity_score = _average([
        float(score.productivity_score)
        for score in scores
    ])

    average_stress_index = _average([
        float(score.stress_index)
        for score in scores
        if score.stress_data_coverage > 0
    ])

    average_data_coverage = _average([
        float(score.data_coverage)
        for score in scores
    ])

    average_stress_data_coverage = _average([
        float(score.stress_data_coverage)
        for score in scores
    ])

    best_score = max(
        scores,
        key=lambda item:
            item.productivity_score,
    )

    worst_score = min(
        scores,
        key=lambda item:
            item.productivity_score,
    )

    return MonthlyAnalyticsResponse(
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        days_analyzed=len(analysis_dates),
        subjective_days=subjective_days,
        average_sleep_hours=(
            average_sleep_hours
        ),
        average_mood=average_mood,
        average_energy_level=(
            average_energy_level
        ),
        total_focused_work_hours=(
            total_focused_work_hours
        ),
        total_meeting_minutes=(
            total_meeting_minutes
        ),
        total_screen_minutes=(
            total_screen_minutes
        ),
        average_productivity_score=(
            average_productivity_score
        ),
        average_stress_index=(
            average_stress_index
        ),
        average_data_coverage=(
            average_data_coverage
        ),
        average_stress_data_coverage=(
            average_stress_data_coverage
        ),
        best_day=best_score.entry_date,
        worst_day=worst_score.entry_date,
    )
