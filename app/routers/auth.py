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
    GoogleLoginRequestV2,
    LoginRequestV2,
    LoginResponseV2,
    SetPasswordRequestV2,
    TokenResponseV2,
)
from app.account_service import (
    build_login_response,
    maybe_send_new_login_notification,
    verify_google_token,
)
from app.audit import write_audit_log
from app.auth import (
    AuthContext,
    create_session_and_tokens,
    get_current_auth_context,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.email_service import (
    send_welcome_email,
)
from app.extended_models import (
    AuthSession,
)
from app.models import User
from app.otp import (
    OTP_PURPOSE_LOGIN,
    create_otp,
    normalize_email,
)
from app.roles import (
    get_default_user_role,
)
from app.schemas import UserResponse
from app.user_defaults import (
    get_or_create_notification_preferences,
    get_or_create_profile,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=LoginResponseV2,
)
def login(
    data: LoginRequestV2,
    request: Request,
    db: Session = Depends(get_db),
):
    email = normalize_email(
        data.email
    )

    user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if (
        not user
        or not user.password_hash
        or not verify_password(
            data.password,
            user.password_hash,
        )
    ):
        write_audit_log(
            event_type="login_failed",
            request=request,
            details={
                "email": email
            },
        )

        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid email or password"
            ),
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

    db.commit()

    if profile.login_otp_enabled:
        challenge = create_otp(
            db=db,
            email=user.email,
            purpose=OTP_PURPOSE_LOGIN,
            user_id=user.id,
        )

        write_audit_log(
            event_type=(
                "login_otp_requested"
            ),
            request=request,
            user_id=user.id,
            entity_type="otp_code",
            entity_id=str(
                challenge.id
            ),
        )

        return LoginResponseV2(
            requires_otp=True,
            challenge_id=(
                challenge.id
            ),
            purpose=(
                OTP_PURPOSE_LOGIN
            ),
            otp_expires_in=(
                settings
                .otp_expire_minutes
                * 60
            ),
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
        entity_type="auth_session",
        entity_id=str(
            tokens.session_id
        ),
    )

    if session:
        maybe_send_new_login_notification(
            user=user,
            session=session,
            db=db,
        )

    return build_login_response(
        tokens
    )


@router.post(
    "/google",
    response_model=TokenResponseV2,
)
def google_login(
    data: GoogleLoginRequestV2,
    request: Request,
    db: Session = Depends(get_db),
):
    google_user = verify_google_token(
        data.id_token
    )

    google_sub = (
        google_user["sub"]
    )

    email = (
        google_user["email"]
    )

    full_name = (
        google_user.get("name")
        or ""
    ).strip()

    created_new_user = False

    user = db.scalar(
        select(User).where(
            User.google_sub
            == google_sub
        )
    )

    if not user:
        user = db.scalar(
            select(User).where(
                User.email == email
            )
        )

        if user:
            if (
                user.google_sub
                and user.google_sub
                != google_sub
            ):
                raise HTTPException(
                    status_code=(
                        status
                        .HTTP_409_CONFLICT
                    ),
                    detail=(
                        "This email is already "
                        "connected to another "
                        "Google account"
                    ),
                )

            user.google_sub = (
                google_sub
            )

        else:
            if len(full_name) < 2:
                full_name = (
                    email.split("@")[0]
                )

            if len(full_name) < 2:
                full_name = (
                    "Google User"
                )

            default_role = (
                get_default_user_role(
                    db
                )
            )

            user = User(
                email=email,
                full_name=full_name,
                password_hash=None,
                google_sub=google_sub,
                role_id=(
                    default_role.id
                ),
            )

            db.add(user)
            db.flush()

            created_new_user = True

    get_or_create_profile(
        user,
        db,
    )

    get_or_create_notification_preferences(
        user,
        db,
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

    session = db.get(
        AuthSession,
        tokens.session_id,
    )

    write_audit_log(
        event_type=(
            "google_signup_success"
            if created_new_user
            else "google_login_success"
        ),
        request=request,
        user_id=user.id,
        session_id=(
            tokens.session_id
        ),
        entity_type="auth_session",
        entity_id=str(
            tokens.session_id
        ),
    )

    if created_new_user:
        send_welcome_email(
            target_email=user.email,
            full_name=user.full_name,
            user_id=user.id,
        )

    elif session:
        maybe_send_new_login_notification(
            user=user,
            session=session,
            db=db,
        )

    return tokens


@router.post(
    "/google/link",
    response_model=UserResponse,
)
def link_google_account(
    data: GoogleLoginRequestV2,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    current_user = context.user

    google_user = verify_google_token(
        data.id_token
    )

    google_sub = (
        google_user["sub"]
    )

    google_email = (
        google_user["email"]
    )

    if (
        google_email
        != current_user.email
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Google account email must "
                "match the PPIS account email"
            ),
        )

    other_user = db.scalar(
        select(User).where(
            User.google_sub
            == google_sub,

            User.id
            != current_user.id,
        )
    )

    if other_user:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "This Google account is "
                "already connected to another "
                "PPIS account"
            ),
        )

    if (
        current_user.google_sub
        and current_user.google_sub
        != google_sub
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "A different Google account "
                "is already connected"
            ),
        )

    current_user.google_sub = (
        google_sub
    )

    db.commit()
    db.refresh(current_user)

    write_audit_log(
        event_type="google_linked",
        request=request,
        user_id=current_user.id,
        session_id=(
            context.session.id
        ),
        entity_type="user",
        entity_id=str(
            current_user.id
        ),
    )

    return current_user


@router.delete(
    "/google/unlink",
    response_model=UserResponse,
)
def unlink_google_account(
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    current_user = context.user

    if not current_user.google_sub:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Google account is not "
                "connected"
            ),
        )

    if not current_user.password_hash:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Set a password before "
                "disconnecting Google"
            ),
        )

    current_user.google_sub = None

    db.commit()
    db.refresh(current_user)

    write_audit_log(
        event_type="google_unlinked",
        request=request,
        user_id=current_user.id,
        session_id=(
            context.session.id
        ),
        entity_type="user",
        entity_id=str(
            current_user.id
        ),
    )

    return current_user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user


@router.post(
    "/set-password",
    response_model=UserResponse,
)
def set_password(
    data: SetPasswordRequestV2,
    request: Request,
    context: AuthContext = Depends(
        get_current_auth_context
    ),
    db: Session = Depends(get_db),
):
    current_user = (
        context.user
    )

    if current_user.password_hash:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Password is already set"
            ),
        )

    current_user.password_hash = (
        hash_password(
            data.password
        )
    )

    db.commit()
    db.refresh(current_user)

    write_audit_log(
        event_type="password_set",
        request=request,
        user_id=current_user.id,
        session_id=(
            context.session.id
        ),
        entity_type="user",
        entity_id=str(
            current_user.id
        ),
    )

    return current_user