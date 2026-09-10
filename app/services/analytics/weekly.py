from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyInput, ScreenTimeStat, User
from app.schemas.analytics import WeeklyAnalyticsResponse
from app.services.analytics.daily import (
    calculate_and_save_daily_score,
    get_meeting_minutes_for_day,
)


def get_weekly_analytics(
    start_date: date,
    current_user: User,
    db: Session,
) -> WeeklyAnalyticsResponse:
    end_date = start_date + timedelta(
        days=6
    )

    daily_inputs = db.scalars(
        select(DailyInput)
        .where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date >= start_date,
            DailyInput.entry_date <= end_date,
        )
        .order_by(
            DailyInput.entry_date.asc()
        )
    ).all()

    if not daily_inputs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No daily inputs found for this week",
        )

    scores = []

    total_meeting_minutes = 0
    total_screen_minutes = 0

    for daily_input in daily_inputs:

        score = calculate_and_save_daily_score(
            daily_input.entry_date,
            current_user,
            db
        )

        scores.append(score)

        total_meeting_minutes += (
            get_meeting_minutes_for_day(
                current_user.id,
                daily_input.entry_date,
                db
            )
        )

        screen_time = db.scalar(
            select(ScreenTimeStat).where(
                ScreenTimeStat.user_id == current_user.id,
                ScreenTimeStat.entry_date == daily_input.entry_date,
            )
        )

        if screen_time:
            total_screen_minutes += (
                screen_time.total_minutes
            )

    days_analyzed = len(
        daily_inputs
    )

    average_sleep_hours = round(
        sum(
            item.sleep_hours
            for item in daily_inputs
        ) / days_analyzed,
        2
    )

    average_mood = round(
        sum(
            item.mood
            for item in daily_inputs
        ) / days_analyzed,
        2
    )

    average_energy_level = round(
        sum(
            item.energy_level
            for item in daily_inputs
        ) / days_analyzed,
        2
    )

    total_focused_work_hours = round(
        sum(
            item.focused_work_hours
            for item in daily_inputs
        ),
        2
    )

    average_productivity_score = round(
        sum(
            score.productivity_score
            for score in scores
        ) / len(scores),
        2
    )

    average_stress_index = round(
        sum(
            score.stress_index
            for score in scores
        ) / len(scores),
        2
    )

    best_score = max(
        scores,
        key=lambda score: score.productivity_score
    )

    worst_score = min(
        scores,
        key=lambda score: score.productivity_score
    )

    return WeeklyAnalyticsResponse(
        start_date=start_date,
        end_date=end_date,
        days_analyzed=days_analyzed,
        average_sleep_hours=average_sleep_hours,
        average_mood=average_mood,
        average_energy_level=average_energy_level,
        total_focused_work_hours=total_focused_work_hours,
        total_meeting_minutes=total_meeting_minutes,
        total_screen_minutes=total_screen_minutes,
        average_productivity_score=average_productivity_score,
        average_stress_index=average_stress_index,
        best_day=best_score.entry_date,
        worst_day=worst_score.entry_date,
    )
