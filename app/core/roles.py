from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role


ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"


def get_role(
    db: Session,
    role_name: str
) -> Role:

    role = db.scalar(
        select(Role).where(
            Role.name == role_name
        )
    )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Required role '{role_name}' is not configured"
        )

    return role


def get_default_user_role(
    db: Session
) -> Role:

    return get_role(
        db,
        ROLE_USER
    )
