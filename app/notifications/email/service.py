"""Business-level email sending, EmailLog integration, and failure semantics."""

import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.observability import EmailLog
from app.notifications.email.sender import send_smtp_message
from app.notifications.email.templates.new_login import build_new_login_email
from app.notifications.email.templates.otp import build_otp_email
from app.notifications.email.templates.report_reminder import build_report_reminder_email
from app.notifications.email.templates.welcome import build_welcome_email


EMAIL_PROVIDER = "gmail_smtp"


def _record_email_log(
    *, target_email: str, email_type: str, status_value: str,
    user_id: UUID | None = None, provider_message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            log = EmailLog(
                user_id=user_id, target_email=target_email, email_type=email_type,
                provider=EMAIL_PROVIDER, provider_message_id=provider_message_id,
                status=status_value, error_message=error_message,
                sent_at=datetime.now(timezone.utc) if status_value == "sent" else None,
            )
            db.add(log)
            db.commit()
    except Exception:
        # Email logging must never break the application request.
        return


def _email_service_is_configured() -> bool:
    return all([
        settings.smtp_host, settings.smtp_port, settings.smtp_username,
        settings.smtp_app_password, settings.email_from,
    ])


def send_email(
    *, target_email: str, subject: str, text_body: str, html_body: str,
    email_type: str, user_id: UUID | None = None, raise_on_failure: bool = False,
) -> bool:
    if not _email_service_is_configured():
        error_message = "Email service is not configured"
        _record_email_log(target_email=target_email, email_type=email_type,
                          status_value="failed", user_id=user_id,
                          error_message=error_message)
        if raise_on_failure:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=error_message)
        return False

    message_id = make_msgid(domain=settings.smtp_username.split("@")[-1])
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = target_email
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = message_id
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        send_smtp_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        error_message = f"{type(exc).__name__}: {str(exc)}"[:2000]
        _record_email_log(target_email=target_email, email_type=email_type,
                          status_value="failed", user_id=user_id,
                          provider_message_id=message_id,
                          error_message=error_message)
        if raise_on_failure:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail="Email service is currently unavailable")
        return False

    _record_email_log(target_email=target_email, email_type=email_type,
                      status_value="sent", user_id=user_id,
                      provider_message_id=message_id)
    return True


def send_otp_email(
    *, target_email: str, otp_code: str, purpose: str, user_id: UUID | None = None,
) -> None:
    subject, text_body, html_body = build_otp_email(otp_code, purpose)
    send_email(target_email=target_email, subject=subject, text_body=text_body,
               html_body=html_body, email_type=f"otp_{purpose}", user_id=user_id,
               raise_on_failure=True)


def send_welcome_email(*, target_email: str, full_name: str, user_id: UUID) -> bool:
    subject, text_body, html_body = build_welcome_email(full_name)
    return send_email(target_email=target_email, subject=subject, text_body=text_body,
                      html_body=html_body, email_type="welcome", user_id=user_id,
                      raise_on_failure=False)


def send_new_login_email(
    *, target_email: str, full_name: str, user_id: UUID, device_name: str | None,
    client_type: str, ip_address: str | None, occurred_at: datetime,
) -> bool:
    subject, text_body, html_body = build_new_login_email(
        full_name, device_name, client_type, ip_address, occurred_at,
    )
    return send_email(target_email=target_email, subject=subject, text_body=text_body,
                      html_body=html_body, email_type="new_login", user_id=user_id,
                      raise_on_failure=False)


def send_report_reminder_email(
    *, target_email: str, full_name: str, user_id: UUID, report_type: str,
    start_date: date, end_date: date,
) -> bool:
    pretty_type, subject, text_body, html_body = build_report_reminder_email(
        full_name, report_type, start_date, end_date,
    )
    return send_email(target_email=target_email, subject=subject, text_body=text_body,
                      html_body=html_body,
                      email_type=f"{pretty_type}_report_reminder", user_id=user_id,
                      raise_on_failure=False)
