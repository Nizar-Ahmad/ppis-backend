from google.auth.exceptions import (
    GoogleAuthError,
)
from google.auth.transport import (
    requests as google_requests,
)
from google.oauth2 import (
    id_token as google_id_token,
)
from sqlalchemy.orm import Session

from app.account_schemas import (
    LoginResponseV2,
    TokenResponseV2,
)
from app.config import settings
from app.email_service import (
    send_new_login_email,
)
from app.extended_models import (
    AuthSession,
)
from app.models import User
from app.otp import normalize_email
from app.user_defaults import (
    get_or_create_notification_preferences,
)


def verify_google_token(
    raw_id_token: str,
) -> dict:
    try:
        google_request = (
            google_requests.Request()
        )

        google_user = (
            google_id_token
            .verify_oauth2_token(
                raw_id_token,
                google_request,
                settings.google_web_client_id,
            )
        )

    except (
        ValueError,
        GoogleAuthError,
    ):
        from fastapi import (
            HTTPException,
            status,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid Google ID token"
            ),
        )

    google_sub = google_user.get(
        "sub"
    )

    email = google_user.get(
        "email"
    )

    email_verified = google_user.get(
        "email_verified"
    )

    if (
        not google_sub
        or not email
        or email_verified is not True
    ):
        from fastapi import (
            HTTPException,
            status,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Google account could not "
                "be verified"
            ),
        )

    google_user["email"] = (
        normalize_email(email)
    )

    return google_user


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