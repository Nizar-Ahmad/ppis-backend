from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.schemas.analytics import InsightResponse
from app.services.analytics.insights import get_weekly_insights as build_weekly_insights
from app.services.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/insights",
    tags=["Insights"],
)


@router.get(
    "/weekly",
    response_model=list[InsightResponse],
)
def get_weekly_insights(
    start_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_weekly_insights(
        start_date,
        current_user,
        db,
    )
