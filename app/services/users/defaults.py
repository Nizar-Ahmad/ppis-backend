from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import (
    NotificationPreference,
    UserProfile,
)
from app.models import User


def get_or_create_profile(
    user: User,
    db: Session,
) -> UserProfile:
    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.user_id == user.id
        )
    )

    if profile:
        return profile

    profile = UserProfile(
        user_id=user.id,
        timezone="UTC",
        preferred_language="en",
        login_otp_enabled=False,
    )

    db.add(profile)
    db.flush()

    return profile


def get_or_create_notification_preferences(
    user: User,
    db: Session,
) -> NotificationPreference:
    preferences = db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id
            == user.id
        )
    )

    if preferences:
        return preferences

    preferences = NotificationPreference(
        user_id=user.id,
        daily_report_email=True,
        weekly_report_email=True,
        monthly_report_email=True,
        new_login_email=True,
    )

    db.add(preferences)
    db.flush()

    return preferences
