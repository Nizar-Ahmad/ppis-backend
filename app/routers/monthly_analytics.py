from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.schemas.analytics import MonthlyAnalyticsResponse
from app.services.analytics.monthly import get_monthly_analytics as build_monthly_analytics
from app.services.auth.dependencies import get_current_user


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
    return build_monthly_analytics(
        year,
        month,
        current_user,
        db,
    )
