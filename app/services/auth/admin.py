from fastapi import (
    Depends,
    HTTPException,
    status,
)

from app.services.auth.dependencies import get_current_user
from app.models import User
from app.core.roles import ROLE_ADMIN


def get_current_admin(
    current_user: User = Depends(
        get_current_user
    )
) -> User:

    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
