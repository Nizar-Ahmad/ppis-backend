from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter()


@router.get("/")
def root():
    return {
        "message": "PPIS Backend is running"
    }


@router.get("/health")
def health():
    return {
        "status": "ok"
    }


@router.get("/health/database")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected"
    }