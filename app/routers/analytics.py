from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.schemas.analytics import DailyScoreResponse, WeeklyAnalyticsResponse
from app.services.analytics.daily import calculate_and_save_daily_score
from app.services.analytics.weekly import get_weekly_analytics as build_weekly_analytics
from app.services.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


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
    return build_weekly_analytics(
        start_date,
        current_user,
        db,
    )
