from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import CalendarEvent, User
from app.schemas import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarEventUpdate,
)


router = APIRouter(
    prefix="/calendar",
    tags=["Calendar"],
)


def calculate_duration_minutes(
    start_time,
    end_time
) -> int:
    duration = end_time - start_time

    return int(
        duration.total_seconds() / 60
    )


@router.post(
    "/events",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_calendar_event(
    data: CalendarEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # First check external ID when available.
    if data.external_id:
        existing_external = db.scalar(
            select(CalendarEvent).where(
                CalendarEvent.user_id == current_user.id,
                CalendarEvent.source == data.source,
                CalendarEvent.external_id == data.external_id,
            )
        )

        if existing_external:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Calendar event already exists",
            )

    # Simple cross-source deduplication.
    existing_event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.user_id == current_user.id,
            CalendarEvent.start_time == data.start_time,
            CalendarEvent.end_time == data.end_time,
            CalendarEvent.title == data.title,
        )
    )

    if existing_event:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calendar event already exists",
        )

    duration_minutes = calculate_duration_minutes(
        data.start_time,
        data.end_time,
    )

    event = CalendarEvent(
        user_id=current_user.id,
        external_id=data.external_id,
        source=data.source,
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=duration_minutes,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get(
    "/events",
    response_model=list[CalendarEventResponse],
)
def get_calendar_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == current_user.id
        )
        .order_by(
            CalendarEvent.start_time.desc()
        )
    ).all()

    return events


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
)
def get_calendar_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == current_user.id,
        )
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )

    return event


@router.put(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
)
def update_calendar_event(
    event_id: UUID,
    data: CalendarEventUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == current_user.id,
        )
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    new_start_time = update_data.get(
        "start_time",
        event.start_time
    )

    new_end_time = update_data.get(
        "end_time",
        event.end_time
    )

    new_title = update_data.get(
        "title",
        event.title
    )

    duplicate = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.user_id
            == current_user.id,

            CalendarEvent.id
            != event.id,

            CalendarEvent.start_time
            == new_start_time,

            CalendarEvent.end_time
            == new_end_time,

            CalendarEvent.title
            == new_title,
        )
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calendar event already exists",
        )

    if new_end_time <= new_start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )

    for field, value in update_data.items():
        setattr(
            event,
            field,
            value
        )

    event.duration_minutes = calculate_duration_minutes(
        event.start_time,
        event.end_time,
    )

    db.commit()
    db.refresh(event)

    return event


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_calendar_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == current_user.id,
        )
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar event not found",
        )

    db.delete(event)
    db.commit()