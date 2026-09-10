from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityStat, DailyInput, Insight, ScreenTimeStat, User
from app.services.analytics.daily import (
    calculate_and_save_daily_score,
    get_meeting_minutes_for_day,
)


def average(values: list[float]) -> float:
    if not values:
        return 0

    return sum(values) / len(values)


def get_weekly_insights(
    start_date: date,
    current_user: User,
    db: Session,
) -> list[Insight]:
    end_date = start_date + timedelta(days=6)

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

    # Calculate or refresh scores for every available day.
    scores = {}

    for daily_input in daily_inputs:
        score = calculate_and_save_daily_score(
            daily_input.entry_date,
            current_user,
            db,
        )

        scores[daily_input.entry_date] = score

    generated_insights = []

    # --------------------------------------------------
    # Weekly summary
    # --------------------------------------------------

    productivity_values = [
        score.productivity_score
        for score in scores.values()
    ]

    stress_values = [
        score.stress_index
        for score in scores.values()
    ]

    best_score = max(
        scores.values(),
        key=lambda item: item.productivity_score
    )

    worst_score = min(
        scores.values(),
        key=lambda item: item.productivity_score
    )

    average_productivity = round(
        average(productivity_values),
        1
    )

    average_stress = round(
        average(stress_values),
        1
    )

    generated_insights.append(
        (
            "weekly_summary",
            (
                f"Average productivity was "
                f"{average_productivity}/100 and average "
                f"stress was {average_stress}/100. "
                f"The best productivity day was "
                f"{best_score.entry_date} and the lowest "
                f"productivity day was {worst_score.entry_date}."
            ),
        )
    )

    # --------------------------------------------------
    # Sleep vs productivity
    # --------------------------------------------------

    good_sleep_productivity = []
    low_sleep_productivity = []

    for daily_input in daily_inputs:
        productivity = (
            scores[daily_input.entry_date]
            .productivity_score
        )

        if daily_input.sleep_hours >= 7:
            good_sleep_productivity.append(
                productivity
            )
        else:
            low_sleep_productivity.append(
                productivity
            )

    if (
        good_sleep_productivity
        and low_sleep_productivity
    ):
        good_sleep_average = average(
            good_sleep_productivity
        )

        low_sleep_average = average(
            low_sleep_productivity
        )

        difference = (
            good_sleep_average
            - low_sleep_average
        )

        if difference >= 5:
            generated_insights.append(
                (
                    "sleep_productivity",
                    (
                        "During this week, days with at least "
                        "7 hours of sleep coincided with a "
                        f"productivity score about "
                        f"{round(difference, 1)} points higher "
                        "on average."
                    ),
                )
            )

        elif difference <= -5:
            generated_insights.append(
                (
                    "sleep_productivity",
                    (
                        "This week's data did not show higher "
                        "productivity on days with at least "
                        "7 hours of sleep. More data is needed "
                        "to identify a stable sleep pattern."
                    ),
                )
            )

    # --------------------------------------------------
    # Screen time vs productivity
    # --------------------------------------------------

    screen_records = db.scalars(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date >= start_date,
            ScreenTimeStat.entry_date <= end_date,
        )
    ).all()

    high_screen_productivity = []
    low_screen_productivity = []

    for record in screen_records:
        score = scores.get(
            record.entry_date
        )

        if not score:
            continue

        if record.total_minutes >= 240:
            high_screen_productivity.append(
                score.productivity_score
            )
        else:
            low_screen_productivity.append(
                score.productivity_score
            )

    if (
        high_screen_productivity
        and low_screen_productivity
    ):
        high_screen_average = average(
            high_screen_productivity
        )

        low_screen_average = average(
            low_screen_productivity
        )

        difference = (
            low_screen_average
            - high_screen_average
        )

        if difference >= 5:
            generated_insights.append(
                (
                    "screen_time_productivity",
                    (
                        "Days with 4 or more hours of screen "
                        "time coincided with a productivity "
                        f"score about {round(difference, 1)} "
                        "points lower on average."
                    ),
                )
            )

    # --------------------------------------------------
    # Activity vs productivity
    # --------------------------------------------------

    activity_records = db.scalars(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date >= start_date,
            ActivityStat.entry_date <= end_date,
        )
    ).all()

    active_productivity = []
    low_activity_productivity = []

    for record in activity_records:
        score = scores.get(
            record.entry_date
        )

        if not score:
            continue

        is_active_day = (
            record.steps >= 8000
            or record.activity_minutes >= 30
        )

        if is_active_day:
            active_productivity.append(
                score.productivity_score
            )
        else:
            low_activity_productivity.append(
                score.productivity_score
            )

    if (
        active_productivity
        and low_activity_productivity
    ):
        active_average = average(
            active_productivity
        )

        low_activity_average = average(
            low_activity_productivity
        )

        difference = (
            active_average
            - low_activity_average
        )

        if difference >= 5:
            generated_insights.append(
            (
                "activity_productivity",
                (
                    "More active days coincided with a "
                    f"productivity score about "
                    f"{round(difference, 1)} points higher "
                    "on average."
                ),
            )
            )

    # --------------------------------------------------
    # Meeting load vs productivity
    # --------------------------------------------------

    high_meeting_productivity = []
    low_meeting_productivity = []

    for daily_input in daily_inputs:

        meeting_minutes = (
            get_meeting_minutes_for_day(
                current_user.id,
                daily_input.entry_date,
                db,
            )
        )

        productivity = (
            scores[daily_input.entry_date]
            .productivity_score
        )

        if meeting_minutes >= 180:
            high_meeting_productivity.append(
                productivity
            )
        else:
            low_meeting_productivity.append(
                productivity
            )

    if (
        high_meeting_productivity
        and low_meeting_productivity
    ):
        high_meeting_average = average(
            high_meeting_productivity
        )

        low_meeting_average = average(
            low_meeting_productivity
        )

        difference = (
            low_meeting_average
            - high_meeting_average
        )

        if difference >= 5:
            generated_insights.append(
                (
                    "meeting_productivity",
                    (
                        "Days with 3 or more hours of meetings "
                        "coincided with a productivity score "
                        f"about {round(difference, 1)} points "
                        "lower on average."
                    ),
                )
            )

    # --------------------------------------------------
    # Replace previously generated insights for this week
    # --------------------------------------------------

    existing_insights = db.scalars(
        select(Insight).where(
            Insight.user_id == current_user.id,
            Insight.start_date == start_date,
            Insight.end_date == end_date,
        )
    ).all()

    for insight in existing_insights:
        db.delete(insight)

    new_insights = []

    for insight_type, message in generated_insights:

        insight = Insight(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            insight_type=insight_type,
            message=message,
        )

        db.add(insight)

        new_insights.append(
            insight
        )

    db.commit()

    for insight in new_insights:
        db.refresh(insight)

    return new_insights
