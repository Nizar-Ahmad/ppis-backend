from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import ensure_utc
from app.models import (
    ActivityStat,
    CalendarEvent,
    DailyInput,
    DailyScore,
    ScreenTimeStat,
    User,
    UserProfile,
)


PRODUCTIVITY_WEIGHTS = {
    "focus": 0.30,
    "energy": 0.20,
    "mood": 0.15,
    "sleep": 0.15,
    "activity": 0.10,
    "distraction": 0.05,
    "meeting": 0.05,
}

STRESS_WEIGHTS = {
    "sleep": 0.25,
    "energy": 0.20,
    "mood": 0.15,
    "meeting": 0.20,
    "distraction": 0.20,
}


def clamp(value: float) -> int:
    return round(
        max(0, min(100, value))
    )


def calculate_sleep_score(
    sleep_hours: float,
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
    activity_minutes: int,
) -> int:
    step_score = min(
        steps / 8000,
        1,
    ) * 70

    minutes_score = min(
        activity_minutes / 30,
        1,
    ) * 30

    return clamp(
        step_score + minutes_score
    )


def calculate_meeting_load(
    meeting_minutes: int,
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
    night_minutes: int,
) -> int:
    total_score = min(
        total_minutes / 480,
        1,
    ) * 70

    night_score = min(
        night_minutes / 120,
        1,
    ) * 30

    return clamp(
        total_score + night_score
    )


def _safe_timezone(
    timezone_name: str | None,
) -> ZoneInfo:
    try:
        return ZoneInfo(
            timezone_name or "UTC"
        )
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def get_user_timezone(
    user_id,
    db: Session,
) -> ZoneInfo:
    timezone_name = db.scalar(
        select(UserProfile.timezone).where(
            UserProfile.user_id == user_id
        )
    )

    return _safe_timezone(
        timezone_name
    )


def get_local_day_utc_bounds(
    user_id,
    entry_date: date,
    db: Session,
) -> tuple[datetime, datetime]:
    timezone_info = get_user_timezone(
        user_id,
        db,
    )

    local_start = datetime.combine(
        entry_date,
        time.min,
        tzinfo=timezone_info,
    )

    local_end = local_start + timedelta(
        days=1
    )

    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
    )


def get_calendar_metrics_for_day(
    user_id,
    entry_date: date,
    db: Session,
) -> tuple[int, bool]:
    day_start, day_end = (
        get_local_day_utc_bounds(
            user_id,
            entry_date,
            db,
        )
    )

    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time < day_end,
            CalendarEvent.end_time > day_start,
        )
    ).all()

    meeting_minutes = 0

    for event in events:
        event_start = ensure_utc(
            event.start_time
        )
        event_end = ensure_utc(
            event.end_time
        )

        overlap_start = max(
            event_start,
            day_start,
        )
        overlap_end = min(
            event_end,
            day_end,
        )

        if overlap_end <= overlap_start:
            continue

        meeting_minutes += int(
            (
                overlap_end
                - overlap_start
            ).total_seconds()
            / 60
        )

    return (
        meeting_minutes,
        bool(events),
    )


def get_meeting_minutes_for_day(
    user_id,
    entry_date: date,
    db: Session,
) -> int:
    meeting_minutes, _ = (
        get_calendar_metrics_for_day(
            user_id,
            entry_date,
            db,
        )
    )

    return meeting_minutes


def get_available_dates_between(
    *,
    user_id,
    start_date: date,
    end_date: date,
    db: Session,
) -> list[date]:
    dates: set[date] = set()

    for model in (
        DailyInput,
        ActivityStat,
        ScreenTimeStat,
    ):
        dates.update(
            db.scalars(
                select(model.entry_date).where(
                    model.user_id == user_id,
                    model.entry_date >= start_date,
                    model.entry_date <= end_date,
                )
            ).all()
        )

    timezone_info = get_user_timezone(
        user_id,
        db,
    )

    period_start_local = datetime.combine(
        start_date,
        time.min,
        tzinfo=timezone_info,
    )
    period_end_local = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone_info,
    )

    period_start_utc = (
        period_start_local
        .astimezone(timezone.utc)
    )
    period_end_utc = (
        period_end_local
        .astimezone(timezone.utc)
    )

    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_time
            < period_end_utc,
            CalendarEvent.end_time
            > period_start_utc,
        )
    ).all()

    for event in events:
        local_start = ensure_utc(
            event.start_time
        ).astimezone(timezone_info)

        # End is exclusive for day attribution. An event ending exactly
        # at local midnight belongs to the previous local day only.
        local_end = (
            ensure_utc(event.end_time)
            .astimezone(timezone_info)
            - timedelta(microseconds=1)
        )

        cursor = max(
            local_start.date(),
            start_date,
        )
        last_date = min(
            local_end.date(),
            end_date,
        )

        while cursor <= last_date:
            dates.add(cursor)
            cursor += timedelta(days=1)

    return sorted(dates)


def _normalized_weighted_score(
    components: dict[
        str,
        tuple[int, float] | None,
    ],
) -> tuple[int, float]:
    weighted_total = 0.0
    available_weight = 0.0

    for component in components.values():
        if component is None:
            continue

        value, weight = component
        weighted_total += value * weight
        available_weight += weight

    if available_weight <= 0:
        return 0, 0.0

    return (
        clamp(
            weighted_total
            / available_weight
        ),
        round(
            available_weight * 100,
            2,
        ),
    )


def calculate_and_save_daily_score(
    entry_date: date,
    current_user: User,
    db: Session,
) -> DailyScore:
    daily_input = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id
            == current_user.id,
            DailyInput.entry_date
            == entry_date,
        )
    )

    activity = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id
            == current_user.id,
            ActivityStat.entry_date
            == entry_date,
        )
    )

    screen_time = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id
            == current_user.id,
            ScreenTimeStat.entry_date
            == entry_date,
        )
    )

    (
        meeting_minutes,
        has_calendar_data,
    ) = get_calendar_metrics_for_day(
        current_user.id,
        entry_date,
        db,
    )

    if not any((
        daily_input,
        activity,
        screen_time,
        has_calendar_data,
    )):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "No analytics data available "
                "for this date"
            ),
        )

    sleep_score = (
        calculate_sleep_score(
            daily_input.sleep_hours
        )
        if daily_input
        else 0
    )

    activity_score = (
        calculate_activity_score(
            activity.steps,
            activity.activity_minutes,
        )
        if activity
        else 0
    )

    meeting_load_score = (
        calculate_meeting_load(
            meeting_minutes
        )
        if has_calendar_data
        else 0
    )

    distraction_score = (
        calculate_distraction_score(
            screen_time.total_minutes,
            screen_time.night_minutes,
        )
        if screen_time
        else 0
    )

    focus_score = (
        clamp(
            daily_input.focused_work_hours
            / 6
            * 100
        )
        if daily_input
        else 0
    )

    energy_score = (
        clamp(
            daily_input.energy_level
            / 5
            * 100
        )
        if daily_input
        else 0
    )

    mood_score = (
        clamp(
            daily_input.mood
            / 5
            * 100
        )
        if daily_input
        else 0
    )

    productivity_components = {
        "focus": (
            focus_score,
            PRODUCTIVITY_WEIGHTS["focus"],
        ) if daily_input else None,
        "energy": (
            energy_score,
            PRODUCTIVITY_WEIGHTS["energy"],
        ) if daily_input else None,
        "mood": (
            mood_score,
            PRODUCTIVITY_WEIGHTS["mood"],
        ) if daily_input else None,
        "sleep": (
            sleep_score,
            PRODUCTIVITY_WEIGHTS["sleep"],
        ) if daily_input else None,
        "activity": (
            activity_score,
            PRODUCTIVITY_WEIGHTS["activity"],
        ) if activity else None,
        "distraction": (
            100 - distraction_score,
            PRODUCTIVITY_WEIGHTS["distraction"],
        ) if screen_time else None,
        "meeting": (
            100 - meeting_load_score,
            PRODUCTIVITY_WEIGHTS["meeting"],
        ) if has_calendar_data else None,
    }

    (
        productivity_score,
        data_coverage,
    ) = _normalized_weighted_score(
        productivity_components
    )

    stress_components = {
        "sleep": (
            100 - sleep_score,
            STRESS_WEIGHTS["sleep"],
        ) if daily_input else None,
        "energy": (
            100 - energy_score,
            STRESS_WEIGHTS["energy"],
        ) if daily_input else None,
        "mood": (
            100 - mood_score,
            STRESS_WEIGHTS["mood"],
        ) if daily_input else None,
        "meeting": (
            meeting_load_score,
            STRESS_WEIGHTS["meeting"],
        ) if has_calendar_data else None,
        "distraction": (
            distraction_score,
            STRESS_WEIGHTS["distraction"],
        ) if screen_time else None,
    }

    (
        stress_index,
        stress_data_coverage,
    ) = _normalized_weighted_score(
        stress_components
    )

    score = db.scalar(
        select(DailyScore).where(
            DailyScore.user_id
            == current_user.id,
            DailyScore.entry_date
            == entry_date,
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
        score.data_coverage = (
            data_coverage
        )
        score.stress_data_coverage = (
            stress_data_coverage
        )

    else:
        score = DailyScore(
            user_id=current_user.id,
            entry_date=entry_date,
            productivity_score=(
                productivity_score
            ),
            stress_index=stress_index,
            sleep_score=sleep_score,
            meeting_load_score=(
                meeting_load_score
            ),
            distraction_score=(
                distraction_score
            ),
            activity_score=activity_score,
            data_coverage=data_coverage,
            stress_data_coverage=(
                stress_data_coverage
            ),
        )

        db.add(score)

    db.commit()
    db.refresh(score)

    return score
