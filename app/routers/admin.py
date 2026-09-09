from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.admin_auth import get_current_admin
from app.admin_schemas import (
    AdminRoleUpdate,
    AdminStatisticsResponse,
    AdminUserDataResponse,
    AdminUserResponse,
)
from app.database import get_db
from app.models import (
    ActivityStat,
    CalendarEvent,
    DailyInput,
    DailyScore,
    GoogleCalendarConnection,
    Insight,
    Role,
    ScreenTimeStat,
    User,
)
from app.roles import (
    ROLE_ADMIN,
    ROLE_USER,
    get_role,
)


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)


def get_user_or_404(
    user_id: UUID,
    db: Session,
) -> User:

    user = db.get(
        User,
        user_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.get(
    "/statistics",
    response_model=AdminStatisticsResponse,
)
def get_statistics(
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    total_users = (
        db.scalar(
            select(
                func.count(User.id)
            )
        )
        or 0
    )

    normal_users = (
        db.scalar(
            select(
                func.count(User.id)
            )
            .join(Role)
            .where(
                Role.name == ROLE_USER
            )
        )
        or 0
    )

    admin_users = (
        db.scalar(
            select(
                func.count(User.id)
            )
            .join(Role)
            .where(
                Role.name == ROLE_ADMIN
            )
        )
        or 0
    )

    google_users = (
        db.scalar(
            select(
                func.count(User.id)
            ).where(
                User.google_sub.is_not(None)
            )
        )
        or 0
    )

    password_users = (
        db.scalar(
            select(
                func.count(User.id)
            ).where(
                User.password_hash.is_not(None)
            )
        )
        or 0
    )

    google_calendar_connections = (
        db.scalar(
            select(
                func.count(
                    GoogleCalendarConnection.id
                )
            )
        )
        or 0
    )

    total_daily_inputs = (
        db.scalar(
            select(
                func.count(
                    DailyInput.id
                )
            )
        )
        or 0
    )

    total_activity_records = (
        db.scalar(
            select(
                func.count(
                    ActivityStat.id
                )
            )
        )
        or 0
    )

    total_calendar_events = (
        db.scalar(
            select(
                func.count(
                    CalendarEvent.id
                )
            )
        )
        or 0
    )

    total_screen_time_records = (
        db.scalar(
            select(
                func.count(
                    ScreenTimeStat.id
                )
            )
        )
        or 0
    )

    total_daily_scores = (
        db.scalar(
            select(
                func.count(
                    DailyScore.id
                )
            )
        )
        or 0
    )

    total_insights = (
        db.scalar(
            select(
                func.count(
                    Insight.id
                )
            )
        )
        or 0
    )

    average_productivity = (
        db.scalar(
            select(
                func.avg(
                    DailyScore.productivity_score
                )
            )
        )
        or 0
    )

    average_stress = (
        db.scalar(
            select(
                func.avg(
                    DailyScore.stress_index
                )
            )
        )
        or 0
    )

    return AdminStatisticsResponse(
        total_users=total_users,

        normal_users=normal_users,
        admin_users=admin_users,

        google_users=google_users,
        password_users=password_users,

        google_calendar_connections=
            google_calendar_connections,

        total_daily_inputs=
            total_daily_inputs,

        total_activity_records=
            total_activity_records,

        total_calendar_events=
            total_calendar_events,

        total_screen_time_records=
            total_screen_time_records,

        total_daily_scores=
            total_daily_scores,

        total_insights=
            total_insights,

        average_productivity_score=round(
            float(
                average_productivity
            ),
            2
        ),

        average_stress_index=round(
            float(
                average_stress
            ),
            2
        ),
    )


@router.get(
    "/users",
    response_model=list[
        AdminUserResponse
    ],
)
def get_users(
    limit: int = Query(
        default=100,
        ge=1,
        le=500
    ),
    offset: int = Query(
        default=0,
        ge=0
    ),
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    users = db.scalars(
        select(User)
        .order_by(
            User.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return users


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
def get_user(
    user_id: UUID,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    return get_user_or_404(
        user_id,
        db
    )


@router.get(
    "/users/{user_id}/data",
    response_model=AdminUserDataResponse,
)
def get_user_data(
    user_id: UUID,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    user = get_user_or_404(
        user_id,
        db
    )

    daily_inputs = db.scalars(
        select(DailyInput)
        .where(
            DailyInput.user_id
            == user.id
        )
        .order_by(
            DailyInput.entry_date.desc()
        )
    ).all()

    activity = db.scalars(
        select(ActivityStat)
        .where(
            ActivityStat.user_id
            == user.id
        )
        .order_by(
            ActivityStat.entry_date.desc()
        )
    ).all()

    calendar_events = db.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id
            == user.id
        )
        .order_by(
            CalendarEvent.start_time.desc()
        )
    ).all()

    screen_time = db.scalars(
        select(ScreenTimeStat)
        .where(
            ScreenTimeStat.user_id
            == user.id
        )
        .order_by(
            ScreenTimeStat.entry_date.desc()
        )
    ).all()

    daily_scores = db.scalars(
        select(DailyScore)
        .where(
            DailyScore.user_id
            == user.id
        )
        .order_by(
            DailyScore.entry_date.desc()
        )
    ).all()

    insights = db.scalars(
        select(Insight)
        .where(
            Insight.user_id
            == user.id
        )
        .order_by(
            Insight.created_at.desc()
        )
    ).all()

    google_calendar_connection = (
        db.scalar(
            select(
                GoogleCalendarConnection
            ).where(
                GoogleCalendarConnection
                .user_id
                == user.id
            )
        )
    )

    return AdminUserDataResponse(
        user=user,

        google_calendar_connected=(
            google_calendar_connection
            is not None
        ),

        daily_inputs=
            daily_inputs,

        activity=
            activity,

        calendar_events=
            calendar_events,

        screen_time=
            screen_time,

        daily_scores=
            daily_scores,

        insights=
            insights,
    )


@router.put(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
)
def update_user_role(
    user_id: UUID,
    data: AdminRoleUpdate,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    user = get_user_or_404(
        user_id,
        db
    )

    new_role = get_role(
        db,
        data.role
    )

    if (
        user.id == current_admin.id
        and data.role != ROLE_ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You cannot remove your "
                "own admin role"
            ),
        )

    user.role_id = new_role.id

    db.commit()
    db.refresh(user)

    return user


@router.delete(
    "/users/{user_id}",
    status_code=
        status.HTTP_204_NO_CONTENT,
)
def delete_user(
    user_id: UUID,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):

    user = get_user_or_404(
        user_id,
        db
    )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You cannot delete "
                "your own admin account"
            ),
        )

    db.delete(
        user
    )

    db.commit()

    return None