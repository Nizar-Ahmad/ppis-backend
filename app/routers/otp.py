from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.otp import (
    OtpChallengeResponse,
    OtpResendRequest,
    OtpSendRequest,
    OtpVerifyRequest,
    OtpVerifyResponse,
)
from app.services.auth.accounts import (
    maybe_send_new_login_notification,
)
from app.services.observability.audit import write_audit_log
from app.services.auth import (
    AuthContext,
    create_session_and_tokens,
    get_optional_auth_context,
    hash_password,
    renew_session_tokens,
    revoke_all_user_sessions,
    verify_password,
)
from app.core.config import settings
from app.core.database import get_db
from app.notifications.email.service import (
    send_welcome_email,
)
from app.models.auth import AuthSession
from app.models.user import UserProfile
from app.models import User
from app.services.otp.service import (
    OTP_PURPOSE_CHANGE_PASSWORD,
    OTP_PURPOSE_LOGIN,
    OTP_PURPOSE_RESET_PASSWORD,
    OTP_PURPOSE_SIGNUP,
    consume_otp,
    create_otp,
    get_otp_challenge,
    normalize_email,
    verify_otp_code,
)
from app.core.roles import (
    get_default_user_role,
)
from app.core.time import ensure_utc
from app.services.users.defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


router = APIRouter(
    prefix="/auth",
    tags=["OTP"],
)


@router.post(
    "/otp/send",
    response_model=OtpChallengeResponse,
)
def send_otp(
    data: OtpSendRequest,
    request: Request,
    context: AuthContext | None = Depends(
        get_optional_auth_context
    ),
    db: Session = Depends(get_db),
):
    if (
        data.purpose
        == OTP_PURPOSE_SIGNUP
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

        challenge = create_otp(
            db=db,
            email=email,
            purpose=(
                OTP_PURPOSE_SIGNUP
            ),
            user_id=None,
        )

    elif (
        data.purpose
        == OTP_PURPOSE_RESET_PASSWORD
    ):
        email = normalize_email(
            str(data.email)
        )

        user = db.scalar(
            select(User).where(
                User.email == email
            )
        )

        if not user:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="User not found",
            )

        if not user.password_hash:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "This account does not "
                    "have a password"
                ),
            )

        challenge = create_otp(
            db=db,
            email=user.email,
            purpose=(
                OTP_PURPOSE_RESET_PASSWORD
            ),
            user_id=user.id,
        )

    elif (
        data.purpose
        == OTP_PURPOSE_CHANGE_PASSWORD
    ):
        if not context:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Authentication required"
                ),
            )

        if not context.user.password_hash:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "This account does not "
                    "have a password"
                ),
            )

        challenge = create_otp(
            db=db,
            email=context.user.email,
            purpose=(
                OTP_PURPOSE_CHANGE_PASSWORD
            ),
            user_id=context.user.id,
        )

    else:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Invalid OTP purpose",
        )

    write_audit_log(
        event_type="otp_requested",
        request=request,
        user_id=(
            challenge.user_id
        ),
        session_id=(
            context.session.id
            if context
            else None
        ),
        entity_type="otp_code",
        entity_id=str(
            challenge.id
        ),
        details={
            "purpose":
                challenge.purpose
        },
    )

    return OtpChallengeResponse(
        challenge_id=challenge.id,
        purpose=challenge.purpose,
        expires_in=(
            settings.otp_expire_minutes
            * 60
        ),
    )


@router.post(
    "/otp/resend",
    response_model=OtpChallengeResponse,
)
def resend_otp(
    data: OtpResendRequest,
    request: Request,
    context: AuthContext | None = Depends(
        get_optional_auth_context
    ),
    db: Session = Depends(get_db),
):
    previous = get_otp_challenge(
        db,
        data.challenge_id,
    )

    now = datetime.now(
        timezone.utc
    )

    if (
        not previous.is_valid
        or ensure_utc(
            previous.expires_at
        ) <= now
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "OTP challenge is no longer "
                "active. Start the action again."
            ),
        )

    if (
        previous.purpose
        == OTP_PURPOSE_LOGIN
    ):
        if not previous.user_id:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Invalid login OTP challenge"
                ),
            )

        user = db.get(
            User,
            previous.user_id,
        )

        if not user:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="User not found",
            )

        profile = (
            get_or_create_profile(
                user,
                db,
            )
        )

        db.commit()

        if not profile.login_otp_enabled:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Login OTP is not enabled "
                    "for this account"
                ),
            )

        challenge = create_otp(
            db=db,
            email=user.email,
            purpose=(
                OTP_PURPOSE_LOGIN
            ),
            user_id=user.id,
        )

    elif (
        previous.purpose
        == OTP_PURPOSE_SIGNUP
    ):
        existing_user = db.scalar(
            select(User).where(
                User.email
                == previous.target_email
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

        challenge = create_otp(
            db=db,
            email=(
                previous.target_email
            ),
            purpose=(
                OTP_PURPOSE_SIGNUP
            ),
            user_id=None,
        )

    elif (
        previous.purpose
        == OTP_PURPOSE_RESET_PASSWORD
    ):
        user = db.scalar(
            select(User).where(
                User.email
                == previous.target_email
            )
        )

        if not user:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="User not found",
            )

        challenge = create_otp(
            db=db,
            email=user.email,
            purpose=(
                OTP_PURPOSE_RESET_PASSWORD
            ),
            user_id=user.id,
        )

    elif (
        previous.purpose
        == OTP_PURPOSE_CHANGE_PASSWORD
    ):
        if not context:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Authentication required"
                ),
            )

        if (
            previous.user_id
            != context.user.id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "OTP challenge does not "
                    "belong to this user"
                ),
            )

        challenge = create_otp(
            db=db,
            email=context.user.email,
            purpose=(
                OTP_PURPOSE_CHANGE_PASSWORD
            ),
            user_id=context.user.id,
        )

    else:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Invalid OTP purpose",
        )

    write_audit_log(
        event_type="otp_resent",
        request=request,
        user_id=(
            challenge.user_id
        ),
        session_id=(
            context.session.id
            if context
            else None
        ),
        entity_type="otp_code",
        entity_id=str(
            challenge.id
        ),
        details={
            "purpose":
                challenge.purpose
        },
    )

    return OtpChallengeResponse(
        challenge_id=challenge.id,
        purpose=challenge.purpose,
        expires_in=(
            settings.otp_expire_minutes
            * 60
        ),
    )


@router.post(
    "/otp/verify",
    response_model=OtpVerifyResponse,
)
def verify_otp(
    data: OtpVerifyRequest,
    request: Request,
    context: AuthContext | None = Depends(
        get_optional_auth_context
    ),
    db: Session = Depends(get_db),
):
    challenge = get_otp_challenge(
        db,
        data.challenge_id,
    )

    try:
        verify_otp_code(
            db=db,
            challenge=challenge,
            purpose=data.purpose,
            otp_code=data.otp,
        )

    except HTTPException:
        write_audit_log(
            event_type=(
                "otp_verification_failed"
            ),
            request=request,
            user_id=(
                challenge.user_id
            ),
            session_id=(
                context.session.id
                if context
                else None
            ),
            entity_type="otp_code",
            entity_id=str(
                challenge.id
            ),
            details={
                "purpose":
                    data.purpose
            },
        )

        raise

    if (
        data.purpose
        == OTP_PURPOSE_LOGIN
    ):
        if not challenge.user_id:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Invalid login OTP challenge"
                ),
            )

        user = db.get(
            User,
            challenge.user_id,
        )

        if not user:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="User not found",
            )

        profile = (
            get_or_create_profile(
                user,
                db,
            )
        )

        get_or_create_notification_preferences(
            user,
            db,
        )

        if not profile.login_otp_enabled:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Login OTP is no longer "
                    "enabled"
                ),
            )

        consume_otp(
            challenge
        )

        tokens = (
            create_session_and_tokens(
                user=user,
                db=db,
                request=request,
                client=data.client,
            )
        )

        db.commit()

        session = db.get(
            AuthSession,
            tokens.session_id,
        )

        write_audit_log(
            event_type="login_success",
            request=request,
            user_id=user.id,
            session_id=(
                tokens.session_id
            ),
            entity_type=(
                "auth_session"
            ),
            entity_id=str(
                tokens.session_id
            ),
            details={
                "otp_used": True
            },
        )

        if session:
            maybe_send_new_login_notification(
                user=user,
                session=session,
                db=db,
            )

        return OtpVerifyResponse(
            message=(
                "Login verified successfully"
            ),
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
            user=user,
        )

    if (
        data.purpose
        == OTP_PURPOSE_SIGNUP
    ):
        if not data.signup_data:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "signup_data is required"
                ),
            )

        signup_data = (
            data.signup_data
        )

        email = normalize_email(
            signup_data.email
        )

        if (
            email
            != challenge.target_email
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Signup email does not "
                    "match OTP email"
                ),
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

        full_name = (
            signup_data
            .full_name
            .strip()
        )

        if len(full_name) < 2:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Full name must contain "
                    "at least 2 characters"
                ),
            )

        default_role = (
            get_default_user_role(
                db
            )
        )

        user = User(
            email=email,
            full_name=full_name,
            password_hash=(
                hash_password(
                    signup_data.password
                )
            ),
            role_id=(
                default_role.id
            ),
        )

        db.add(user)

        try:
            db.flush()

            profile = UserProfile(
                user_id=user.id,
                birth_date=(
                    signup_data.birth_date
                ),
                country=(
                    signup_data.country
                ),
                occupation=(
                    signup_data.occupation
                ),
                timezone=(
                    signup_data.timezone
                ),
                preferred_language=(
                    signup_data
                    .preferred_language
                ),
                login_otp_enabled=False,
            )

            db.add(profile)

            get_or_create_notification_preferences(
                user,
                db,
            )

            challenge.user_id = (
                user.id
            )

            consume_otp(
                challenge
            )

            tokens = (
                create_session_and_tokens(
                    user=user,
                    db=db,
                    request=request,
                    client=data.client,
                )
            )

            db.commit()
            db.refresh(user)

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

        write_audit_log(
            event_type="signup_success",
            request=request,
            user_id=user.id,
            session_id=(
                tokens.session_id
            ),
            entity_type="user",
            entity_id=str(
                user.id
            ),
        )

        send_welcome_email(
            target_email=user.email,
            full_name=user.full_name,
            user_id=user.id,
        )

        return OtpVerifyResponse(
            message=(
                "Account created successfully"
            ),
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
            user=user,
        )

    if (
        data.purpose
        == OTP_PURPOSE_RESET_PASSWORD
    ):
        user = None

        if challenge.user_id:
            user = db.get(
                User,
                challenge.user_id,
            )

        if not user:
            user = db.scalar(
                select(User).where(
                    User.email
                    == challenge.target_email
                )
            )

        if not user:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail="User not found",
            )

        user.password_hash = (
            hash_password(
                data.new_password
            )
        )

        challenge.user_id = (
            user.id
        )

        consume_otp(
            challenge
        )

        revoke_all_user_sessions(
            user_id=user.id,
            db=db,
            reason="password_reset",
        )

        db.commit()

        write_audit_log(
            event_type="password_reset",
            request=request,
            user_id=user.id,
            entity_type="user",
            entity_id=str(
                user.id
            ),
        )

        return OtpVerifyResponse(
            message=(
                "Password reset successfully. "
                "Please log in with your "
                "new password."
            )
        )

    if (
        data.purpose
        == OTP_PURPOSE_CHANGE_PASSWORD
    ):
        if not context:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Authentication required"
                ),
            )

        user = context.user

        if (
            challenge.user_id
            != user.id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "OTP challenge does not "
                    "belong to this user"
                ),
            )

        if not user.password_hash:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "This account does not "
                    "have a password"
                ),
            )

        if not verify_password(
            data.current_password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Current password is "
                    "incorrect"
                ),
            )

        if verify_password(
            data.new_password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "New password must be "
                    "different from current "
                    "password"
                ),
            )

        user.password_hash = (
            hash_password(
                data.new_password
            )
        )

        consume_otp(
            challenge
        )

        revoke_all_user_sessions(
            user_id=user.id,
            db=db,
            reason="password_changed",
            exclude_session_id=(
                context.session.id
            ),
        )

        tokens = (
            renew_session_tokens(
                user=user,
                session=context.session,
                db=db,
                request=request,
            )
        )

        db.commit()
        db.refresh(user)

        write_audit_log(
            event_type=(
                "password_changed"
            ),
            request=request,
            user_id=user.id,
            session_id=(
                context.session.id
            ),
            entity_type="user",
            entity_id=str(
                user.id
            ),
        )

        return OtpVerifyResponse(
            message=(
                "Password changed successfully"
            ),
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
            user=user,
        )

    raise HTTPException(
        status_code=(
            status
            .HTTP_422_UNPROCESSABLE_ENTITY
        ),
        detail="Invalid OTP purpose",
    )
