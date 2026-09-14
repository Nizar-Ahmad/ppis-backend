from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.roles import ROLE_ADMIN, ROLE_USER, get_role
from app.models import DailyScore, Role, User
from app.models.auth import AuthSession
from app.models.feedback import Feedback
from app.models.observability import ApiUsageStat, AuditLog
from app.routers.admin import get_statistics
from app.routers.admin_feedback import get_feedback_statistics
from app.routers.admin_observability import get_observability_summary
from app.services.auth import verify_password
from app.services.auth.sessions import revoke_session
from app.services.observability.audit import write_audit_log


router = APIRouter(prefix="/admin", tags=["Admin Web"])
templates = Jinja2Templates(directory="app/templates")

SESSION_COOKIE = "ppis_admin_session"
CSRF_COOKIE = "ppis_admin_csrf"
SESSION_HOURS = 8


def _create_web_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "type": "admin_web",
        "iat": now,
        "exp": now + timedelta(hours=SESSION_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _decode_web_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "admin_web":
            raise ValueError("wrong token type")
        return UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin session expired") from exc


def _get_admin_or_none(request: Request, db: Session) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        user_id = _decode_web_token(token)
    except HTTPException:
        return None
    user = db.get(User, user_id)
    if not user or user.role != ROLE_ADMIN:
        return None
    return user


def require_web_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = _get_admin_or_none(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")
    return user


def _redirect_login() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)


def _csrf(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)


def _require_csrf(request: Request, token: str) -> None:
    cookie = request.cookies.get(CSRF_COOKIE)
    if not cookie or not secrets.compare_digest(cookie, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def _context(request: Request, admin: User, **kwargs) -> dict:
    return {"request": request, "admin": admin, "csrf_token": _csrf(request), **kwargs}


@router.get("", include_in_schema=False)
def admin_root(request: Request, db: Session = Depends(get_db)):
    if _get_admin_or_none(request, db):
        return RedirectResponse("/admin/dashboard", status_code=status.HTTP_302_FOUND)
    return _redirect_login()


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, db: Session = Depends(get_db)):
    if _get_admin_or_none(request, db):
        return RedirectResponse("/admin/dashboard", status_code=status.HTTP_302_FOUND)
    csrf = _csrf(request)
    response = templates.TemplateResponse(request=request, name="admin/login.html", context={"csrf_token": csrf, "error": None})
    if not request.cookies.get(CSRF_COOKIE):
        response.set_cookie(CSRF_COOKIE, csrf, secure=True, httponly=False, samesite="lax", max_age=SESSION_HOURS * 3600)
    return response


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    _require_csrf(request, csrf_token)
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    valid = bool(user and user.password_hash and verify_password(password, user.password_hash) and user.role == ROLE_ADMIN)
    if not valid:
        response = templates.TemplateResponse(
            request=request,
            name="admin/login.html",
            context={"csrf_token": csrf_token, "error": "Invalid administrator credentials."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        return response

    response = RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        _create_web_token(user),
        secure=True,
        httponly=True,
        samesite="lax",
        max_age=SESSION_HOURS * 3600,
    )
    write_audit_log(event_type="admin_web_login", request=request, user_id=user.id, actor_user_id=user.id, entity_type="user", entity_id=str(user.id))
    return response


@router.post("/logout", include_in_schema=False)
def logout(
    request: Request,
    csrf_token: str = Form(...),
    admin: User = Depends(require_web_admin),
):
    _require_csrf(request, csrf_token)
    response = _redirect_login()
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    statistics = get_statistics(current_admin=admin, db=db)
    observability = get_observability_summary(current_admin=admin, db=db)
    feedback_stats = get_feedback_statistics(current_admin=admin, db=db)
    recent_users = db.scalars(select(User).order_by(User.created_at.desc()).limit(6)).all()
    recent_feedback = db.scalars(select(Feedback).order_by(Feedback.created_at.desc()).limit(6)).all()
    recent_audit = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=_context(
            request,
            admin,
            statistics=statistics,
            observability=observability,
            feedback_stats=feedback_stats,
            recent_users=recent_users,
            recent_feedback=recent_feedback,
            recent_audit=recent_audit,
            active_page="dashboard",
        ),
    )


def _user_query(q: str | None, role: str | None):
    statement = select(User).join(Role)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
    if role in {ROLE_ADMIN, ROLE_USER}:
        statement = statement.where(Role.name == role)
    return statement.order_by(User.created_at.desc())


@router.get("/users", response_class=HTMLResponse, include_in_schema=False)
def users_page(
    request: Request,
    q: str | None = None,
    role: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    page = max(page, 1)
    per_page = 25
    base = _user_query(q, role)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    users = db.scalars(base.offset((page - 1) * per_page).limit(per_page)).all()
    context = _context(request, admin, users=users, q=q or "", role=role or "", page=page, pages=max(1, (total + per_page - 1) // per_page), total=total, active_page="users")
    template = "admin/partials/users_table.html" if request.headers.get("HX-Request") else "admin/users.html"
    return templates.TemplateResponse(request=request, name=template, context=context)


@router.get("/users/{user_id}", response_class=HTMLResponse, include_in_schema=False)
def user_detail(user_id: UUID, request: Request, db: Session = Depends(get_db)):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id).order_by(AuthSession.last_seen_at.desc()).limit(15)).all()
    scores = db.scalars(select(DailyScore).where(DailyScore.user_id == user.id).order_by(DailyScore.entry_date.desc()).limit(14)).all()
    return templates.TemplateResponse(request=request, name="admin/user_detail.html", context=_context(request, admin, user=user, sessions=sessions, scores=scores, active_page="users"))


@router.post("/users/{user_id}/role", include_in_schema=False)
def change_user_role(
    user_id: UUID,
    request: Request,
    role: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    _require_csrf(request, csrf_token)
    if role not in {ROLE_ADMIN, ROLE_USER}:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and role != ROLE_ADMIN:
        raise HTTPException(status_code=409, detail="You cannot remove your own admin role")
    previous_role = user.role
    user.role_id = get_role(db, role).id
    db.commit()
    write_audit_log(event_type="admin_role_changed", request=request, user_id=user.id, actor_user_id=admin.id, entity_type="user", entity_id=str(user.id), details={"previous_role": previous_role, "new_role": role})
    return RedirectResponse(f"/admin/users/{user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/sessions", response_class=HTMLResponse, include_in_schema=False)
def sessions_page(request: Request, active_only: bool = True, db: Session = Depends(get_db)):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    query = select(AuthSession).order_by(AuthSession.last_seen_at.desc()).limit(200)
    if active_only:
        now = datetime.now(timezone.utc)
        query = query.where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
    sessions = db.scalars(query).all()
    user_ids = {item.user_id for item in sessions}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return templates.TemplateResponse(request=request, name="admin/sessions.html", context=_context(request, admin, sessions=sessions, users=users, active_only=active_only, active_page="sessions"))


@router.post("/sessions/{session_id}/revoke", include_in_schema=False)
def revoke_web_session(
    session_id: UUID,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    _require_csrf(request, csrf_token)
    session = db.get(AuthSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    revoke_session(session, "admin_web_revoked")
    db.commit()
    write_audit_log(event_type="admin_session_revoked", request=request, user_id=session.user_id, actor_user_id=admin.id, entity_type="auth_session", entity_id=str(session.id))
    return RedirectResponse("/admin/sessions", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/feedback", response_class=HTMLResponse, include_in_schema=False)
def feedback_page(request: Request, feedback_type: str | None = None, db: Session = Depends(get_db)):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    query = select(Feedback).order_by(Feedback.created_at.desc()).limit(250)
    if feedback_type:
        query = query.where(Feedback.feedback_type == feedback_type)
    feedback = db.scalars(query).all()
    stats = get_feedback_statistics(current_admin=admin, db=db)
    return templates.TemplateResponse(request=request, name="admin/feedback.html", context=_context(request, admin, feedback=feedback, stats=stats, feedback_type=feedback_type or "", active_page="feedback"))


@router.get("/observability", response_class=HTMLResponse, include_in_schema=False)
def observability_page(request: Request, db: Session = Depends(get_db)):
    admin = _get_admin_or_none(request, db)
    if not admin:
        return _redirect_login()
    summary = get_observability_summary(current_admin=admin, db=db)
    audits = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)).all()
    api_usage = db.scalars(select(ApiUsageStat).order_by(ApiUsageStat.usage_date.desc(), ApiUsageStat.request_count.desc()).limit(100)).all()
    return templates.TemplateResponse(request=request, name="admin/observability.html", context=_context(request, admin, summary=summary, audits=audits, api_usage=api_usage, active_page="observability"))
