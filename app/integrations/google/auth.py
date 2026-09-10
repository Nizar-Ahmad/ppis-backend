"""Google identity-token verification."""

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.services.otp.service import normalize_email


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


__all__ = ["verify_google_token"]
