import hashlib
import hmac
import secrets
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import UUID

from fastapi import (
    HTTPException,
    status,
)
from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.email_service import send_otp_email
from app.extended_models import OtpCode
from app.time_utils import ensure_utc


OTP_PURPOSE_LOGIN = "login"
OTP_PURPOSE_SIGNUP = "signup"

OTP_PURPOSE_RESET_PASSWORD = (
    "reset_password"
)

OTP_PURPOSE_CHANGE_PASSWORD = (
    "change_password"
)

OTP_PURPOSES = {
    OTP_PURPOSE_LOGIN,
    OTP_PURPOSE_SIGNUP,
    OTP_PURPOSE_RESET_PASSWORD,
    OTP_PURPOSE_CHANGE_PASSWORD,
}


def normalize_email(
    email: str,
) -> str:
    return email.lower().strip()


def generate_otp_code() -> str:
    return (
        f"{secrets.randbelow(1_000_000):06d}"
    )


def hash_otp_code(
    challenge_id: UUID,
    otp_code: str,
) -> str:
    message = (
        f"otp:{challenge_id}:{otp_code}"
    )

    return hmac.new(
        settings.otp_secret_key.encode(
            "utf-8"
        ),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def invalidate_expired_otps(
    db: Session,
) -> int:
    now = datetime.now(
        timezone.utc
    )

    expired = db.scalars(
        select(OtpCode).where(
            OtpCode.is_valid.is_(True),
            OtpCode.expires_at <= now,
        )
    ).all()

    for item in expired:
        item.is_valid = False
        item.invalidated_at = now
        item.invalid_reason = "expired"

    if expired:
        db.commit()

    return len(expired)


def invalidate_active_otps(
    *,
    db: Session,
    email: str,
    purpose: str,
    reason: str,
) -> int:
    now = datetime.now(
        timezone.utc
    )

    records = db.scalars(
        select(OtpCode).where(
            OtpCode.target_email == email,
            OtpCode.purpose == purpose,
            OtpCode.is_valid.is_(True),
        )
    ).all()

    for record in records:
        record.is_valid = False
        record.invalidated_at = now
        record.invalid_reason = reason

    return len(records)


def create_otp(
    *,
    db: Session,
    email: str,
    purpose: str,
    user_id: UUID | None = None,
) -> OtpCode:
    if purpose not in OTP_PURPOSES:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Invalid OTP purpose",
        )

    email = normalize_email(
        email
    )

    now = datetime.now(
        timezone.utc
    )

    sent_last_hour = (
        db.scalar(
            select(
                func.count(OtpCode.id)
            ).where(
                OtpCode.target_email
                == email,

                OtpCode.purpose
                == purpose,

                OtpCode.created_at
                >= (
                    now
                    - timedelta(hours=1)
                ),
            )
        )
        or 0
    )

    if (
        sent_last_hour
        >= settings.otp_max_sends_per_hour
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Too many OTP requests. "
                "Try again later."
            ),
        )

    latest = db.scalar(
        select(OtpCode)
        .where(
            OtpCode.target_email
            == email,

            OtpCode.purpose
            == purpose,
        )
        .order_by(
            OtpCode.created_at.desc()
        )
    )

    if latest:
        elapsed = (
            now
            - ensure_utc(
                latest.created_at
            )
        ).total_seconds()

        if (
            elapsed
            < settings
            .otp_resend_cooldown_seconds
        ):
            retry_after = int(
                settings
                .otp_resend_cooldown_seconds
                - elapsed
            )

            raise HTTPException(
                status_code=(
                    status
                    .HTTP_429_TOO_MANY_REQUESTS
                ),
                detail=(
                    "Please wait "
                    f"{max(retry_after, 1)} "
                    "seconds before requesting "
                    "another code"
                ),
            )

    # Keep OTP history, but only one
    # active OTP for the same email
    # and purpose.
    invalidate_active_otps(
        db=db,
        email=email,
        purpose=purpose,
        reason="replaced",
    )

    challenge = OtpCode(
        user_id=user_id,
        target_email=email,
        purpose=purpose,
        code_hash="",
        is_valid=True,
        attempt_count=0,
        expires_at=(
            now
            + timedelta(
                minutes=(
                    settings
                    .otp_expire_minutes
                )
            )
        ),
    )

    db.add(challenge)
    db.flush()

    otp_code = generate_otp_code()

    challenge.code_hash = (
        hash_otp_code(
            challenge.id,
            otp_code,
        )
    )

    # Persist the OTP record before
    # contacting the external provider,
    # so failures can also be recorded.
    db.commit()
    db.refresh(challenge)

    try:
        send_otp_email(
            target_email=email,
            otp_code=otp_code,
            purpose=purpose,
            user_id=user_id,
        )

    except HTTPException:
        challenge.is_valid = False

        challenge.invalidated_at = (
            datetime.now(timezone.utc)
        )

        challenge.invalid_reason = (
            "email_failed"
        )

        db.commit()

        raise

    return challenge


def get_otp_challenge(
    db: Session,
    challenge_id: UUID,
) -> OtpCode:
    challenge = db.get(
        OtpCode,
        challenge_id,
    )

    if not challenge:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Invalid OTP challenge",
        )

    return challenge


def verify_otp_code(
    *,
    db: Session,
    challenge: OtpCode,
    purpose: str,
    otp_code: str,
) -> None:
    now = datetime.now(
        timezone.utc
    )

    if challenge.purpose != purpose:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "OTP purpose does not match "
                "challenge"
            ),
        )

    if not challenge.is_valid:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="OTP is not valid",
        )

    if (
        ensure_utc(
            challenge.expires_at
        )
        <= now
    ):
        challenge.is_valid = False
        challenge.invalidated_at = now
        challenge.invalid_reason = (
            "expired"
        )

        db.commit()

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="OTP has expired",
        )

    if (
        challenge.attempt_count
        >= settings.otp_max_attempts
    ):
        challenge.is_valid = False
        challenge.invalidated_at = now
        challenge.invalid_reason = (
            "max_attempts"
        )

        db.commit()

        raise HTTPException(
            status_code=(
                status
                .HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Maximum OTP attempts exceeded"
            ),
        )

    expected_hash = hash_otp_code(
        challenge.id,
        otp_code,
    )

    if not hmac.compare_digest(
        expected_hash,
        challenge.code_hash,
    ):
        challenge.attempt_count += 1

        if (
            challenge.attempt_count
            >= settings.otp_max_attempts
        ):
            challenge.is_valid = False
            challenge.invalidated_at = now
            challenge.invalid_reason = (
                "max_attempts"
            )

        db.commit()

        if not challenge.is_valid:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_429_TOO_MANY_REQUESTS
                ),
                detail=(
                    "Maximum OTP attempts "
                    "exceeded"
                ),
            )

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Invalid OTP",
        )


def consume_otp(
    challenge: OtpCode,
) -> None:
    now = datetime.now(
        timezone.utc
    )

    challenge.is_valid = False
    challenge.used_at = now
    challenge.invalidated_at = now
    challenge.invalid_reason = "used"