from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.account_schemas import (
    FeedbackResponse,
    FeedbackStatisticsResponse,
)
from app.admin_auth import (
    get_current_admin,
)
from app.database import get_db
from app.extended_models import Feedback
from app.models import User


router = APIRouter(
    prefix="/api/admin/feedback",
    tags=["Admin Feedback"],
)


@router.get(
    "",
    response_model=list[
        FeedbackResponse
    ],
)
def get_feedback(
    feedback_type: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    query = select(
        Feedback
    )

    if feedback_type:
        query = query.where(
            Feedback.feedback_type
            == feedback_type
        )

    return db.scalars(
        query
        .order_by(
            Feedback
            .created_at
            .desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()


@router.get(
    "/statistics",
    response_model=(
        FeedbackStatisticsResponse
    ),
)
def get_feedback_statistics(
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    total = (
        db.scalar(
            select(
                func.count(
                    Feedback.id
                )
            )
        )
        or 0
    )

    average_rating = (
        db.scalar(
            select(
                func.avg(
                    Feedback.rating
                )
            )
        )
        or 0
    )

    def count_type(
        value: str,
    ) -> int:
        return (
            db.scalar(
                select(
                    func.count(
                        Feedback.id
                    )
                ).where(
                    Feedback.feedback_type
                    == value
                )
            )
            or 0
        )

    def count_rating(
        value: int,
    ) -> int:
        return (
            db.scalar(
                select(
                    func.count(
                        Feedback.id
                    )
                ).where(
                    Feedback.rating
                    == value
                )
            )
            or 0
        )

    return FeedbackStatisticsResponse(
        total_feedback=total,
        average_rating=round(
            float(
                average_rating
            ),
            2,
        ),
        app_feedback_count=(
            count_type("app")
        ),
        weekly_report_feedback_count=(
            count_type(
                "weekly_report"
            )
        ),
        monthly_report_feedback_count=(
            count_type(
                "monthly_report"
            )
        ),
        insight_feedback_count=(
            count_type("insight")
        ),
        rating_1=count_rating(1),
        rating_2=count_rating(2),
        rating_3=count_rating(3),
        rating_4=count_rating(4),
        rating_5=count_rating(5),
    )