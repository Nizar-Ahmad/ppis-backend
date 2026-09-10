from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_schemas import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackUpdate,
    MessageResponse,
)
from app.audit import write_audit_log
from app.auth import (
    AuthContext,
    get_current_auth_context,
)
from app.database import get_db
from app.extended_models import Feedback
from app.models import Insight


router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
)


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_feedback(
    data: FeedbackCreate,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    if (
        data.feedback_type
        == "insight"
    ):
        insight = db.scalar(
            select(Insight).where(
                Insight.id
                == data.insight_id,

                Insight.user_id
                == context.user.id,
            )
        )

        if not insight:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="Insight not found",
            )

    feedback = Feedback(
        user_id=context.user.id,
        feedback_type=(
            data.feedback_type
        ),
        rating=data.rating,
        comment=(
            data.comment.strip()
            if data.comment
            else None
        ),
        report_start_date=(
            data.report_start_date
        ),
        report_end_date=(
            data.report_end_date
        ),
        insight_id=(
            data.insight_id
        ),
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    write_audit_log(
        event_type=(
            "feedback_submitted"
        ),
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type="feedback",
        entity_id=str(
            feedback.id
        ),
        details={
            "feedback_type":
                feedback.feedback_type,

            "rating":
                feedback.rating,
        },
    )

    return feedback


@router.get(
    "/mine",
    response_model=list[
        FeedbackResponse
    ],
)
def get_my_feedback(
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Feedback)
        .where(
            Feedback.user_id
            == context.user.id
        )
        .order_by(
            Feedback
            .created_at
            .desc()
        )
    ).all()


@router.put(
    "/{feedback_id}",
    response_model=FeedbackResponse,
)
def update_feedback(
    feedback_id: UUID,
    data: FeedbackUpdate,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    feedback = db.scalar(
        select(Feedback).where(
            Feedback.id
            == feedback_id,

            Feedback.user_id
            == context.user.id,
        )
    )

    if not feedback:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Feedback not found",
        )

    update_data = (
        data.model_dump(
            exclude_unset=True
        )
    )

    if "comment" in update_data:
        comment = (
            update_data["comment"]
        )

        update_data["comment"] = (
            comment.strip()
            if comment
            else None
        )

    for field, value in (
        update_data.items()
    ):
        setattr(
            feedback,
            field,
            value,
        )

    db.commit()
    db.refresh(feedback)

    write_audit_log(
        event_type="feedback_updated",
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type="feedback",
        entity_id=str(
            feedback.id
        ),
    )

    return feedback


@router.delete(
    "/{feedback_id}",
    response_model=MessageResponse,
)
def delete_feedback(
    feedback_id: UUID,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    feedback = db.scalar(
        select(Feedback).where(
            Feedback.id
            == feedback_id,

            Feedback.user_id
            == context.user.id,
        )
    )

    if not feedback:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Feedback not found",
        )

    db.delete(feedback)
    db.commit()

    write_audit_log(
        event_type="feedback_deleted",
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type="feedback",
        entity_id=str(
            feedback_id
        ),
    )

    return MessageResponse(
        message=(
            "Feedback deleted successfully"
        )
    )