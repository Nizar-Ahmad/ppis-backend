from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models import ScreenTimeStat, User
from app.schemas import (
    ScreenTimeCreate,
    ScreenTimeResponse,
    ScreenTimeUpdate,
)


router = APIRouter(
    prefix="/screen-time",
    tags=["Screen Time"],
)


@router.post(
    "",
    response_model=ScreenTimeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_screen_time(
    data: ScreenTimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date == data.entry_date,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Screen time data already exists for this date",
        )

    screen_time = ScreenTimeStat(
        user_id=current_user.id,
        **data.model_dump(),
    )

    db.add(screen_time)
    db.commit()
    db.refresh(screen_time)

    return screen_time


@router.get(
    "",
    response_model=list[ScreenTimeResponse],
)
def get_screen_time_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = db.scalars(
        select(ScreenTimeStat)
        .where(
            ScreenTimeStat.user_id == current_user.id
        )
        .order_by(
            ScreenTimeStat.entry_date.desc()
        )
    ).all()

    return records


@router.get(
    "/{entry_date}",
    response_model=ScreenTimeResponse,
)
def get_screen_time(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date == entry_date,
        )
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screen time data not found",
        )

    return record


@router.put(
    "/{entry_date}",
    response_model=ScreenTimeResponse,
)
def update_screen_time(
    entry_date: date,
    data: ScreenTimeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date == entry_date,
        )
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screen time data not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    new_total_minutes = update_data.get(
        "total_minutes",
        record.total_minutes
    )

    new_night_minutes = update_data.get(
        "night_minutes",
        record.night_minutes
    )

    if new_night_minutes > new_total_minutes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="night_minutes cannot be greater than total_minutes",
        )

    for field, value in update_data.items():
        setattr(
            record,
            field,
            value
        )

    db.commit()
    db.refresh(record)

    return record


@router.delete(
    "/{entry_date}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_screen_time(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(ScreenTimeStat).where(
            ScreenTimeStat.user_id == current_user.id,
            ScreenTimeStat.entry_date == entry_date,
        )
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screen time data not found",
        )

    db.delete(record)
    db.commit()
