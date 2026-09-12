from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.schemas.profile import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    ProfileResponse,
    ProfileUpdate,
)
from app.services.observability.audit import write_audit_log
from app.services.auth import (
    get_current_auth_context,
)
from app.core.database import get_db
from app.services.users.defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


def build_profile_response(
    user,
    profile,
) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        has_password=(
            user.has_password
        ),
        google_connected=(
            user.google_connected
        ),
        birth_date=(
            profile.birth_date
        ),
        country=profile.country,
        occupation=(
            profile.occupation
        ),
        timezone=(
            profile.timezone
        ),
        preferred_language=(
            profile.preferred_language
        ),
        login_otp_enabled=(
            profile.login_otp_enabled
        ),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get(
    "",
    response_model=ProfileResponse,
)
def get_profile(
    context=Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    profile = (
        get_or_create_profile(
            context.user,
            db,
        )
    )

    db.commit()
    db.refresh(profile)

    return build_profile_response(
        context.user,
        profile,
    )


@router.put(
    "",
    response_model=ProfileResponse,
)
def update_profile(
    data: ProfileUpdate,
    request: Request,
    context=Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    user = context.user

    profile = (
        get_or_create_profile(
            user,
            db,
        )
    )

    update_data = (
        data.model_dump(
            exclude_unset=True
        )
    )

    if (
        update_data.get(
            "login_otp_enabled"
        ) is True
        and not user.password_hash
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Set a password before "
                "enabling OTP for "
                "email/password login"
            ),
        )

    if "full_name" in update_data:
        user.full_name = (
            update_data
            .pop("full_name")
            .strip()
        )

    for field, value in (
        update_data.items()
    ):
        setattr(
            profile,
            field,
            value,
        )

    db.commit()

    db.refresh(user)
    db.refresh(profile)

    write_audit_log(
        event_type="profile_updated",
        request=request,
        user_id=user.id,
        session_id=(
            context.session.id
        ),
        entity_type="user_profile",
        entity_id=str(
            profile.id
        ),
        details={
            "updated_fields": list(
                data.model_fields_set
            )
        },
    )

    return build_profile_response(
        user,
        profile,
    )


@router.get(
    "/notifications",
    response_model=(
        NotificationPreferenceResponse
    ),
)
def get_notification_preferences(
    context=Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    preferences = (
        get_or_create_notification_preferences(
            context.user,
            db,
        )
    )

    db.commit()
    db.refresh(preferences)

    return NotificationPreferenceResponse(
        daily_report_email=(
            preferences
            .daily_report_email
        ),
        weekly_report_email=(
            preferences
            .weekly_report_email
        ),
        monthly_report_email=(
            preferences
            .monthly_report_email
        ),
        new_login_email=(
            preferences
            .new_login_email
        ),
    )


@router.put(
    "/notifications",
    response_model=(
        NotificationPreferenceResponse
    ),
)
def update_notification_preferences(
    data: NotificationPreferenceUpdate,
    request: Request,
    context=Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    preferences = (
        get_or_create_notification_preferences(
            context.user,
            db,
        )
    )

    update_data = (
        data.model_dump(
            exclude_unset=True
        )
    )

    for field, value in (
        update_data.items()
    ):
        setattr(
            preferences,
            field,
            value,
        )

    db.commit()
    db.refresh(preferences)

    write_audit_log(
        event_type=(
            "notification_preferences_updated"
        ),
        request=request,
        user_id=context.user.id,
        session_id=(
            context.session.id
        ),
        entity_type=(
            "notification_preferences"
        ),
        entity_id=str(
            preferences.id
        ),
        details={
            "updated_fields": list(
                data.model_fields_set
            )
        },
    )

    return NotificationPreferenceResponse(
        daily_report_email=(
            preferences
            .daily_report_email
        ),
        weekly_report_email=(
            preferences
            .weekly_report_email
        ),
        monthly_report_email=(
            preferences
            .monthly_report_email
        ),
        new_login_email=(
            preferences
            .new_login_email
        ),
    )
