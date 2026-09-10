from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models import DailyInput, User
from app.schemas import (
    DailyInputCreate,
    DailyInputResponse,
    DailyInputUpdate
)


router = APIRouter(
    prefix="/daily-inputs",
    tags=["Daily Inputs"]
)


@router.post(
    "",
    response_model=DailyInputResponse,
    status_code=status.HTTP_201_CREATED
)
def create_daily_input(
    data: DailyInputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date == data.entry_date
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Daily input already exists for this date"
        )

    daily_input = DailyInput(
        user_id=current_user.id,
        **data.model_dump()
    )

    db.add(daily_input)
    db.commit()
    db.refresh(daily_input)

    return daily_input


@router.get(
    "",
    response_model=list[DailyInputResponse]
)
def get_daily_inputs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = db.scalars(
        select(DailyInput)
        .where(
            DailyInput.user_id == current_user.id
        )
        .order_by(
            DailyInput.entry_date.desc()
        )
    ).all()

    return result


@router.get(
    "/{entry_date}",
    response_model=DailyInputResponse
)
def get_daily_input(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    daily_input = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date == entry_date
        )
    )

    if not daily_input:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily input not found"
        )

    return daily_input


@router.put(
    "/{entry_date}",
    response_model=DailyInputResponse
)
def update_daily_input(
    entry_date: date,
    data: DailyInputUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    daily_input = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date == entry_date
        )
    )

    if not daily_input:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily input not found"
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            daily_input,
            field,
            value
        )

    db.commit()
    db.refresh(daily_input)

    return daily_input


@router.delete(
    "/{entry_date}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_daily_input(
    entry_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    daily_input = db.scalar(
        select(DailyInput).where(
            DailyInput.user_id == current_user.id,
            DailyInput.entry_date == entry_date
        )
    )

    if not daily_input:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily input not found"
        )

    db.delete(daily_input)
    db.commit()

    return None
