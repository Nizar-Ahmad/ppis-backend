from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.roles import get_default_user_role
from app.schemas import (
    GoogleLoginRequest,
    LoginRequest,
    SetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()
    full_name = data.full_name.strip()

    if len(full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name must contain at least 2 characters",
        )

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    default_role = get_default_user_role(
        db
    )

    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(
            data.password
        ),
        role_id=default_role.id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()

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
            user.password_hash
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        user.id
    )

    return TokenResponse(
        access_token=token
    )


@router.post(
    "/google",
    response_model=TokenResponse,
)
def google_login(
    data: GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    try:
        google_request = (
            google_requests.Request()
        )

        google_user = (
            google_id_token.verify_oauth2_token(
                data.id_token,
                google_request,
                settings.google_web_client_id,
            )
        )

    except (ValueError, GoogleAuthError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
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

    full_name = (
        google_user.get("name")
        or ""
    ).strip()

    if (
        not google_sub
        or not email
        or email_verified is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account could not be verified",
        )

    email = email.lower().strip()

    # Existing Google-linked user.
    user = db.scalar(
        select(User).where(
            User.google_sub == google_sub
        )
    )

    if user:
        token = create_access_token(
            user.id
        )

        return TokenResponse(
            access_token=token
        )

    # Existing password user with same verified email.
    user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if user:
        if (
            user.google_sub
            and user.google_sub != google_sub
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This email is already connected "
                    "to another Google account"
                ),
            )

        user.google_sub = google_sub

        db.commit()
        db.refresh(user)

        token = create_access_token(
            user.id
        )

        return TokenResponse(
            access_token=token
        )

    # Completely new Google user.
    if len(full_name) < 2:
        full_name = email.split("@")[0]

    if len(full_name) < 2:
        full_name = "Google User"

    default_role = get_default_user_role(
        db
    )

    user = User(
        email=email,
        full_name=full_name,
        password_hash=None,
        google_sub=google_sub,
        role_id=default_role.id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        user.id
    )

    return TokenResponse(
        access_token=token
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    )
):
    return current_user


@router.post(
    "/set-password",
    response_model=UserResponse,
)
def set_password(
    data: SetPasswordRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    if current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password is already set",
        )

    current_user.password_hash = hash_password(
        data.password
    )

    db.commit()
    db.refresh(current_user)

    return current_user