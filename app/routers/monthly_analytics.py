from calendar import monthrange
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import (
    MonthlyAnalyticsResponse,
)
from app.auth import get_current_user
from app.database import get_db
from app.models import (
    DailyInput,
    ScreenTimeStat,
    User,
)
from app.routers.analytics import (
    calculate_and_save_daily_score,
    get_meeting_minutes_for_day,
)


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get(
    "/monthly",
    response_model=(
        MonthlyAnalyticsResponse
    ),
)
def get_monthly_analytics(
    year: int = Query(
        ...,
        ge=2000,
        le=2100,
    ),
    month: int = Query(
        ...,
        ge=1,
        le=12,
    ),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
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
            DailyInput
            .entry_date
            .asc()
        )
    ).all()

    if not daily_inputs:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "No daily inputs found "
                "for this month"
            ),
        )

    scores = []

    total_meeting_minutes = 0
    total_screen_minutes = 0

    for daily_input in daily_inputs:
        score = (
            calculate_and_save_daily_score(
                daily_input.entry_date,
                current_user,
                db,
            )
        )

        scores.append(score)

        total_meeting_minutes += (
            get_meeting_minutes_for_day(
                current_user.id,
                daily_input.entry_date,
                db,
            )
        )

        screen_time = db.scalar(
            select(
                ScreenTimeStat
            ).where(
                ScreenTimeStat.user_id
                == current_user.id,

                ScreenTimeStat.entry_date
                == daily_input.entry_date,
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
            for item
            in daily_inputs
        )
        / days_analyzed,
        2,
    )

    average_mood = round(
        sum(
            item.mood
            for item
            in daily_inputs
        )
        / days_analyzed,
        2,
    )

    average_energy_level = round(
        sum(
            item.energy_level
            for item
            in daily_inputs
        )
        / days_analyzed,
        2,
    )

    total_focused_work_hours = round(
        sum(
            item.focused_work_hours
            for item
            in daily_inputs
        ),
        2,
    )

    average_productivity_score = round(
        sum(
            score.productivity_score
            for score
            in scores
        )
        / len(scores),
        2,
    )

    average_stress_index = round(
        sum(
            score.stress_index
            for score
            in scores
        )
        / len(scores),
        2,
    )

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
        days_analyzed=(
            days_analyzed
        ),
        average_sleep_hours=(
            average_sleep_hours
        ),
        average_mood=(
            average_mood
        ),
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
        best_day=(
            best_score.entry_date
        ),
        worst_day=(
            worst_score.entry_date
        ),
    )