from datetime import date

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
from app.models import ActivityStat, User
from app.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
)


router = APIRouter(
    prefix="/activity",
    tags=["Activity"],
)


@router.post(
    "",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    data: ActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date == data.entry_date,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Activity data already exists for this date",
        )

    activity = ActivityStat(
        user_id=current_user.id,
        **data.model_dump(),
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


@router.get(
    "",
    response_model=list[ActivityResponse],
)
def get_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activities = db.scalars(
        select(ActivityStat)
        .where(
            ActivityStat.user_id == current_user.id
        )
        .order_by(
            ActivityStat.entry_date.desc()
        )
    ).all()

    return activities


@router.get(
    "/{entry_date}",
    response_model=ActivityResponse,
)
def get_activity(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date == entry_date,
        )
    )

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity data not found",
        )

    return activity


@router.put(
    "/{entry_date}",
    response_model=ActivityResponse,
)
def update_activity(
    entry_date: date,
    data: ActivityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date == entry_date,
        )
    )

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity data not found",
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            activity,
            field,
            value
        )

    db.commit()
    db.refresh(activity)

    return activity


@router.delete(
    "/{entry_date}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_activity(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = db.scalar(
        select(ActivityStat).where(
            ActivityStat.user_id == current_user.id,
            ActivityStat.entry_date == entry_date,
        )
    )

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity data not found",
        )

    db.delete(activity)
    db.commit()