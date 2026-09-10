from sqlalchemy.orm import Session

from app.schemas.auth import (
    LoginResponseV2,
    TokenResponseV2,
)
from app.integrations.google.auth import verify_google_token
from app.notifications.email.service import (
    send_new_login_email,
)
from app.models.auth import (
    AuthSession,
)
from app.models import User
from app.services.users.defaults import (
    get_or_create_notification_preferences,
)


def build_login_response(
    tokens: TokenResponseV2,
) -> LoginResponseV2:
    return LoginResponseV2(
        requires_otp=False,
        access_token=(
            tokens.access_token
        ),
        refresh_token=(
            tokens.refresh_token
        ),
        token_type=(
            tokens.token_type
        ),
        expires_in=(
            tokens.expires_in
        ),
        refresh_expires_in=(
            tokens.refresh_expires_in
        ),
        session_id=(
            tokens.session_id
        ),
    )


def maybe_send_new_login_notification(
    *,
    user: User,
    session: AuthSession,
    db: Session,
) -> None:
    preferences = (
        get_or_create_notification_preferences(
            user,
            db,
        )
    )

    db.commit()

    if not preferences.new_login_email:
        return

    send_new_login_email(
        target_email=user.email,
        full_name=user.full_name,
        user_id=user.id,
        device_name=session.device_name,
        client_type=session.client_type,
        ip_address=session.ip_address,
        occurred_at=session.created_at,
    )
