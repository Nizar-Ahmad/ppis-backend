from datetime import date, datetime, time, timedelta, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    ActivityStat,
    CalendarEvent,
    DailyInput,
    DailyScore,
    ScreenTimeStat,
    User,
)
from app.schemas import (
    DailyScoreResponse,
    WeeklyAnalyticsResponse,
)


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


def clamp(value: float) -> int:
    return round(
        max(0, min(100, value))
    )


def calculate_sleep_score(
    sleep_hours: float
) -> int:

    if 7 <= sleep_hours <= 9:
        return 100

    if (
        6 <= sleep_hours < 7
        or 9 < sleep_hours <= 10
    ):
        return 80

    if (
        5 <= sleep_hours < 6
        or 10 < sleep_hours <= 11
    ):
        return 60

    if (
        4 <= sleep_hours < 5
        or 11 < sleep_hours <= 12
    ):
        return 40

    return 20


def calculate_activity_score(
    steps: int,
    activity_minutes: int
) -> int:

    step_score = min(
        steps / 8000,
        1
    ) * 70

    minutes_score = min(
        activity_minutes / 30,
        1
    ) * 30

    return clamp(
        step_score + minutes_score
    )


def calculate_meeting_load(
    meeting_minutes: int
) -> int:

    if meeting_minutes == 0:
        return 0

    if meeting_minutes <= 60:
        return 20

    if meeting_minutes <= 180:
        return 50

    if meeting_minutes <= 300:
        return 75

    return 100


def calculate_distraction_score(
    total_minutes: int,
    night_minutes: int
) -> int:

    total_score = min(
        total_minutes / 480,
        1
    ) * 70

    night_score = min(
        night_minutes / 120,
        1
    ) * 30

    return clamp(
        total_score + night_score
    )


def get_meeting_minutes_for_day(
    user_id,
    entry_date: date,
    db: Session
) -> int:

    day_start = datetime.combine(
        entry_date,
        time.min,
        tzinfo=timezone.utc
    )

    day_end = day_start + timedelta(
        days=1
    )

    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time >= day_start,
            CalendarEvent.start_time < day_end,
        )
    ).all()

    return sum(
        event.duration_minutes
        for event in events
    )


def calculate_and_save_daily_score(
    entry_date: date,
    current_user: User,
    db: Session
) -> DailyScore:

    daily_input = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date == entry_date,
        )
    )

    if not daily_input:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily input is required to calculate scores",
        )

    activity = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date == entry_date,
        )
    )

    screen_time = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date == entry_date,
        )
    )

    meeting_minutes = get_meeting_minutes_for_day(
        current_user.id,
        entry_date,
        db
    )

    steps = (
        activity.steps
        if activity
        else 0
    )

    activity_minutes = (
        activity.activity_minutes
        if activity
        else 0
    )

    total_screen_minutes = (
        screen_time.total_minutes
        if screen_time
        else 0
    )

    night_screen_minutes = (
        screen_time.night_minutes
        if screen_time
        else 0
    )

    sleep_score = calculate_sleep_score(
        daily_input.sleep_hours
    )

    activity_score = calculate_activity_score(
        steps,
        activity_minutes
    )

    meeting_load_score = calculate_meeting_load(
        meeting_minutes
    )

    distraction_score = calculate_distraction_score(
        total_screen_minutes,
        night_screen_minutes
    )

    focus_score = clamp(
        daily_input.focused_work_hours / 6 * 100
    )

    energy_score = clamp(
        daily_input.energy_level / 5 * 100
    )

    mood_score = clamp(
        daily_input.mood / 5 * 100
    )

    productivity_score = clamp(
        (focus_score * 0.30)
        + (energy_score * 0.20)
        + (mood_score * 0.15)
        + (sleep_score * 0.15)
        + (activity_score * 0.10)
        + ((100 - distraction_score) * 0.05)
        + ((100 - meeting_load_score) * 0.05)
    )

    stress_index = clamp(
        ((100 - sleep_score) * 0.25)
        + ((100 - energy_score) * 0.20)
        + ((100 - mood_score) * 0.15)
        + (meeting_load_score * 0.20)
        + (distraction_score * 0.20)
    )

    score = db.scalar(
        select(DailyScore).where(
            DailyScore.user_id == current_user.id,
            DailyScore.entry_date == entry_date,
        )
    )

    if score:
        score.productivity_score = (
            productivity_score
        )

        score.stress_index = (
            stress_index
        )

        score.sleep_score = (
            sleep_score
        )

        score.meeting_load_score = (
            meeting_load_score
        )

        score.distraction_score = (
            distraction_score
        )

        score.activity_score = (
            activity_score
        )

    else:
        score = DailyScore(
            user_id=current_user.id,
            entry_date=entry_date,
            productivity_score=productivity_score,
            stress_index=stress_index,
            sleep_score=sleep_score,
            meeting_load_score=meeting_load_score,
            distraction_score=distraction_score,
            activity_score=activity_score,
        )

        db.add(score)

    db.commit()
    db.refresh(score)

    return score


@router.get(
    "/daily/{entry_date}",
    response_model=DailyScoreResponse,
)
def get_daily_analytics(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    return calculate_and_save_daily_score(
        entry_date,
        current_user,
        db
    )


@router.get(
    "/weekly",
    response_model=WeeklyAnalyticsResponse,
)
def get_weekly_analytics(
    start_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

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