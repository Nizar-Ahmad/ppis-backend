from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.services.auth.admin import (
    get_current_admin,
)
from app.schemas.admin import (
    AdminRoleUpdate,
    AdminStatisticsResponse,
    AdminUserDataResponse,
    AdminUserResponse,
)
from app.services.observability.audit import write_audit_log
from app.core.database import get_db
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
from app.core.roles import (
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
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="User not found",
        )

    return user


def scalar_count(
    db: Session,
    statement,
) -> int:
    return int(
        db.scalar(statement)
        or 0
    )


@router.get(
    "/statistics",
    response_model=(
        AdminStatisticsResponse
    ),
)
def get_statistics(
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    total_users = scalar_count(
        db,
        select(
            func.count(User.id)
        ),
    )

    normal_users = scalar_count(
        db,
        select(
            func.count(User.id)
        )
        .join(Role)
        .where(
            Role.name == ROLE_USER
        ),
    )

    admin_users = scalar_count(
        db,
        select(
            func.count(User.id)
        )
        .join(Role)
        .where(
            Role.name == ROLE_ADMIN
        ),
    )

    google_users = scalar_count(
        db,
        select(
            func.count(User.id)
        ).where(
            User.google_sub
            .is_not(None)
        ),
    )

    password_users = scalar_count(
        db,
        select(
            func.count(User.id)
        ).where(
            User.password_hash
            .is_not(None)
        ),
    )

    google_calendar_connections = (
        scalar_count(
            db,
            select(
                func.count(
                    GoogleCalendarConnection.id
                )
            ),
        )
    )

    total_daily_inputs = scalar_count(
        db,
        select(
            func.count(
                DailyInput.id
            )
        ),
    )

    total_activity_records = (
        scalar_count(
            db,
            select(
                func.count(
                    ActivityStat.id
                )
            ),
        )
    )

    total_calendar_events = (
        scalar_count(
            db,
            select(
                func.count(
                    CalendarEvent.id
                )
            ),
        )
    )

    total_screen_time_records = (
        scalar_count(
            db,
            select(
                func.count(
                    ScreenTimeStat.id
                )
            ),
        )
    )

    total_daily_scores = (
        scalar_count(
            db,
            select(
                func.count(
                    DailyScore.id
                )
            ),
        )
    )

    total_insights = (
        scalar_count(
            db,
            select(
                func.count(
                    Insight.id
                )
            ),
        )
    )

    average_productivity = (
        db.scalar(
            select(
                func.avg(
                    DailyScore
                    .productivity_score
                )
            )
        )
        or 0
    )

    average_stress = (
        db.scalar(
            select(
                func.avg(
                    DailyScore
                    .stress_index
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
        google_calendar_connections=(
            google_calendar_connections
        ),
        total_daily_inputs=(
            total_daily_inputs
        ),
        total_activity_records=(
            total_activity_records
        ),
        total_calendar_events=(
            total_calendar_events
        ),
        total_screen_time_records=(
            total_screen_time_records
        ),
        total_daily_scores=(
            total_daily_scores
        ),
        total_insights=(
            total_insights
        ),
        average_productivity_score=round(
            float(
                average_productivity
            ),
            2,
        ),
        average_stress_index=round(
            float(
                average_stress
            ),
            2,
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
    return db.scalars(
        select(User)
        .order_by(
            User.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()


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
        db,
    )


@router.get(
    "/users/{user_id}/data",
    response_model=(
        AdminUserDataResponse
    ),
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
        db,
    )

    daily_inputs = db.scalars(
        select(DailyInput)
        .where(
            DailyInput.user_id
            == user.id
        )
        .order_by(
            DailyInput
            .entry_date
            .desc()
        )
    ).all()

    activity = db.scalars(
        select(ActivityStat)
        .where(
            ActivityStat.user_id
            == user.id
        )
        .order_by(
            ActivityStat
            .entry_date
            .desc()
        )
    ).all()

    calendar_events = db.scalars(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id
            == user.id
        )
        .order_by(
            CalendarEvent
            .start_time
            .desc()
        )
    ).all()

    screen_time = db.scalars(
        select(ScreenTimeStat)
        .where(
            ScreenTimeStat.user_id
            == user.id
        )
        .order_by(
            ScreenTimeStat
            .entry_date
            .desc()
        )
    ).all()

    daily_scores = db.scalars(
        select(DailyScore)
        .where(
            DailyScore.user_id
            == user.id
        )
        .order_by(
            DailyScore
            .entry_date
            .desc()
        )
    ).all()

    insights = db.scalars(
        select(Insight)
        .where(
            Insight.user_id
            == user.id
        )
        .order_by(
            Insight
            .created_at
            .desc()
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
        daily_inputs=daily_inputs,
        activity=activity,
        calendar_events=(
            calendar_events
        ),
        screen_time=screen_time,
        daily_scores=daily_scores,
        insights=insights,
    )


@router.put(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
)
def update_user_role(
    user_id: UUID,
    data: AdminRoleUpdate,
    request: Request,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        user_id,
        db,
    )

    previous_role = (
        user.role
    )

    new_role = get_role(
        db,
        data.role,
    )

    if (
        user.id == current_admin.id
        and data.role != ROLE_ADMIN
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "You cannot remove your "
                "own admin role"
            ),
        )

    user.role_id = (
        new_role.id
    )

    db.commit()
    db.refresh(user)

    write_audit_log(
        event_type=(
            "admin_role_changed"
        ),
        request=request,
        user_id=user.id,
        actor_user_id=(
            current_admin.id
        ),
        entity_type="user",
        entity_id=str(
            user.id
        ),
        details={
            "previous_role":
                previous_role,

            "new_role":
                data.role,
        },
    )

    return user


@router.delete(
    "/users/{user_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def delete_user(
    user_id: UUID,
    request: Request,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(
        user_id,
        db,
    )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "You cannot delete your "
                "own admin account"
            ),
        )

    deleted_user_id = (
        user.id
    )

    deleted_user_email = (
        user.email
    )

    db.delete(user)
    db.commit()

    write_audit_log(
        event_type=(
            "admin_user_deleted"
        ),
        request=request,
        actor_user_id=(
            current_admin.id
        ),
        entity_type="user",
        entity_id=str(
            deleted_user_id
        ),
        details={
            "email":
                deleted_user_email
        },
    )

    return None


# ============================================================
# ADMIN USER CREATE + PASSWORD RESET V2
# ============================================================

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy.exc import IntegrityError

from app.schemas.admin import (
    AdminPasswordReset,
    AdminPasswordResetResponse,
    AdminUserCreate,
)

from app.services.auth import (
    hash_password,
    revoke_all_user_sessions,
)

from app.notifications.email.service import (
    send_welcome_email,
)

from app.models.auth import (
    OtpCode,
)

from app.services.otp.service import (
    normalize_email,
)

from app.services.users.defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


def _invalidate_active_user_otps(
    *,
    email: str,
    db: Session,
    reason: str,
) -> int:
    now = datetime.now(
        timezone.utc
    )

    challenges = db.scalars(
        select(OtpCode).where(
            OtpCode.target_email
            == email,

            OtpCode.is_valid
            .is_(True),
        )
    ).all()

    for challenge in challenges:
        challenge.is_valid = False
        challenge.invalidated_at = now
        challenge.invalid_reason = (
            reason
        )

    return len(
        challenges
    )


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_user_by_admin(
    data: AdminUserCreate,
    request: Request,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(
        get_db
    ),
):
    email = normalize_email(
        str(data.email)
    )

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Email already registered"
            ),
        )

    role = get_role(
        db,
        data.role,
    )

    user = User(
        email=email,
        full_name=(
            data.full_name.strip()
        ),
        password_hash=(
            hash_password(
                data.password
            )
        ),
        role_id=role.id,
    )

    db.add(
        user
    )

    try:
        # Obtain user UUID before
        # creating dependent rows.
        db.flush()

        profile = (
            get_or_create_profile(
                user,
                db,
            )
        )

        profile.birth_date = (
            data.birth_date
        )

        profile.country = (
            data.country
        )

        profile.occupation = (
            data.occupation
        )

        profile.timezone = (
            data.timezone
        )

        profile.preferred_language = (
            data.preferred_language
        )

        profile.login_otp_enabled = (
            data.login_otp_enabled
        )

        get_or_create_notification_preferences(
            user,
            db,
        )

        invalidated_otp_count = (
            _invalidate_active_user_otps(
                email=email,
                db=db,
                reason=(
                    "admin_account_created"
                ),
            )
        )

        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Email already registered"
            ),
        )

    except Exception:
        db.rollback()
        raise

    db.refresh(
        user
    )

    write_audit_log(
        event_type=(
            "admin_user_created"
        ),
        request=request,
        user_id=user.id,
        actor_user_id=(
            current_admin.id
        ),
        entity_type="user",
        entity_id=str(
            user.id
        ),
        details={
            "email":
                user.email,

            "role":
                user.role,

            "otp_bypassed":
                True,

            "invalidated_otp_count":
                invalidated_otp_count,
        },
    )

    if data.send_welcome_email:
        send_welcome_email(
            target_email=user.email,
            full_name=user.full_name,
            user_id=user.id,
        )

    return user


@router.put(
    "/users/{user_id}/password",
    response_model=(
        AdminPasswordResetResponse
    ),
)
def reset_user_password_by_admin(
    user_id: UUID,
    data: AdminPasswordReset,
    request: Request,
    current_admin: User = Depends(
        get_current_admin
    ),
    db: Session = Depends(
        get_db
    ),
):
    user = get_user_or_404(
        user_id,
        db,
    )

    user.password_hash = (
        hash_password(
            data.new_password
        )
    )

    revoked_sessions = (
        revoke_all_user_sessions(
            user_id=user.id,
            db=db,
            reason=(
                "admin_password_reset"
            ),
        )
    )

    invalidated_otp_count = (
        _invalidate_active_user_otps(
            email=user.email,
            db=db,
            reason=(
                "admin_password_reset"
            ),
        )
    )

    db.commit()
    db.refresh(
        user
    )

    write_audit_log(
        event_type=(
            "admin_password_reset"
        ),
        request=request,
        user_id=user.id,
        actor_user_id=(
            current_admin.id
        ),
        entity_type="user",
        entity_id=str(
            user.id
        ),
        details={
            "revoked_sessions":
                revoked_sessions,

            "invalidated_otp_count":
                invalidated_otp_count,

            "otp_bypassed":
                True,
        },
    )

    return (
        AdminPasswordResetResponse(
            message=(
                "Password reset "
                "successfully"
            ),
            revoked_sessions=(
                revoked_sessions
            ),
        )
    )
