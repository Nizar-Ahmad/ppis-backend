import smtplib
import ssl
from datetime import (
    date,
    datetime,
    timezone,
)
from email.message import EmailMessage
from email.utils import (
    format_datetime,
    make_msgid,
)
from uuid import UUID

from fastapi import (
    HTTPException,
    status,
)

from app.config import settings
from app.database import SessionLocal
from app.extended_models import EmailLog


EMAIL_PROVIDER = "gmail_smtp"


OTP_PURPOSE_LABELS = {
    "login": "Login verification",
    "signup": "Account verification",
    "reset_password": "Password reset",
    "change_password": "Password change",
}


def _record_email_log(
    *,
    target_email: str,
    email_type: str,
    status_value: str,
    user_id: UUID | None = None,
    provider_message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        with SessionLocal() as db:
            log = EmailLog(
                user_id=user_id,
                target_email=target_email,
                email_type=email_type,
                provider=EMAIL_PROVIDER,
                provider_message_id=(
                    provider_message_id
                ),
                status=status_value,
                error_message=error_message,
                sent_at=(
                    datetime.now(
                        timezone.utc
                    )
                    if status_value == "sent"
                    else None
                ),
            )

            db.add(log)
            db.commit()

    except Exception:
        # Email logging must never break
        # the application request.
        return


def _email_service_is_configured() -> bool:
    return all(
        [
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_app_password,
            settings.email_from,
        ]
    )


def send_email(
    *,
    target_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    email_type: str,
    user_id: UUID | None = None,
    raise_on_failure: bool = False,
) -> bool:
    if not _email_service_is_configured():
        error_message = (
            "Email service is not configured"
        )

        _record_email_log(
            target_email=target_email,
            email_type=email_type,
            status_value="failed",
            user_id=user_id,
            error_message=error_message,
        )

        if raise_on_failure:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=error_message,
            )

        return False

    message_id = make_msgid(
        domain=(
            settings.smtp_username
            .split("@")[-1]
        )
    )

    message = EmailMessage()

    message["From"] = settings.email_from
    message["To"] = target_email
    message["Subject"] = subject
    message["Date"] = format_datetime(
        datetime.now(timezone.utc)
    )
    message["Message-ID"] = message_id

    message.set_content(
        text_body
    )

    message.add_alternative(
        html_body,
        subtype="html",
    )

    try:
        tls_context = (
            ssl.create_default_context()
        )

        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=20,
        ) as smtp:
            smtp.ehlo()

            smtp.starttls(
                context=tls_context
            )

            smtp.ehlo()

            smtp.login(
                settings.smtp_username,
                settings.smtp_app_password,
            )

            refused = smtp.send_message(
                message
            )

            if refused:
                raise smtplib.SMTPRecipientsRefused(
                    refused
                )

    except (
        smtplib.SMTPException,
        OSError,
    ) as exc:
        error_message = (
            f"{type(exc).__name__}: "
            f"{str(exc)}"
        )[:2000]

        _record_email_log(
            target_email=target_email,
            email_type=email_type,
            status_value="failed",
            user_id=user_id,
            provider_message_id=(
                message_id
            ),
            error_message=error_message,
        )

        if raise_on_failure:
            raise HTTPException(
                status_code=(
                    status.HTTP_502_BAD_GATEWAY
                ),
                detail=(
                    "Email service is currently "
                    "unavailable"
                ),
            )

        return False

    _record_email_log(
        target_email=target_email,
        email_type=email_type,
        status_value="sent",
        user_id=user_id,
        provider_message_id=(
            message_id
        ),
    )

    return True


def send_otp_email(
    *,
    target_email: str,
    otp_code: str,
    purpose: str,
    user_id: UUID | None = None,
) -> None:
    label = OTP_PURPOSE_LABELS.get(
        purpose,
        "Verification",
    )

    subject = (
        f"PPIS {label} code"
    )

    text_body = (
        f"Your PPIS verification code "
        f"is {otp_code}. "
        f"It expires in "
        f"{settings.otp_expire_minutes} "
        f"minutes. "
        f"If you did not request this code, "
        f"ignore this email."
    )

    html_body = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:0 auto;
        line-height:1.5
    ">
      <h2>PPIS</h2>

      <p>{label}</p>

      <p>
        Your verification code is:
      </p>

      <div style="
          font-size:32px;
          font-weight:700;
          letter-spacing:8px;
          margin:24px 0
      ">
        {otp_code}
      </div>

      <p>
        This code expires in
        {settings.otp_expire_minutes}
        minutes.
      </p>

      <p>
        If you did not request this code,
        you can ignore this email.
      </p>
    </div>
    """

    send_email(
        target_email=target_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        email_type=f"otp_{purpose}",
        user_id=user_id,
        raise_on_failure=True,
    )


def send_welcome_email(
    *,
    target_email: str,
    full_name: str,
    user_id: UUID,
) -> bool:
    subject = "Welcome to PPIS"

    text_body = (
        f"Welcome to PPIS, {full_name}. "
        "Start tracking your daily sleep, "
        "mood, energy, focused work, "
        "activity, screen time and calendar "
        "patterns to understand your "
        "productivity and well-being."
    )

    html_body = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:600px;
        margin:0 auto;
        line-height:1.6
    ">
      <h2>Welcome to PPIS</h2>

      <p>Hello {full_name},</p>

      <p>
        Your PPIS account is ready.
        Start tracking your daily patterns
        and PPIS will help you understand
        how sleep, mood, activity, screen
        time, meetings and focused work
        relate to your productivity and
        well-being.
      </p>

      <p>
        We are glad to have you with us.
      </p>
    </div>
    """

    return send_email(
        target_email=target_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        email_type="welcome",
        user_id=user_id,
        raise_on_failure=False,
    )


def send_new_login_email(
    *,
    target_email: str,
    full_name: str,
    user_id: UUID,
    device_name: str | None,
    client_type: str,
    ip_address: str | None,
    occurred_at: datetime,
) -> bool:
    subject = (
        "New sign-in to your PPIS account"
    )

    device_label = (
        device_name
        or client_type
        or "Unknown device"
    )

    ip_label = (
        ip_address
        or "Unknown"
    )

    time_label = (
        occurred_at
        .astimezone(timezone.utc)
        .strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    )

    text_body = (
        f"Hello {full_name}. "
        f"A new sign-in to your PPIS "
        f"account was detected. "
        f"Device: {device_label}. "
        f"IP: {ip_label}. "
        f"Time: {time_label}. "
        f"If this was not you, change "
        f"your password and revoke active "
        f"sessions."
    )

    html_body = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:600px;
        margin:0 auto;
        line-height:1.6
    ">
      <h2>New PPIS sign-in</h2>

      <p>Hello {full_name},</p>

      <p>
        A new sign-in to your PPIS
        account was detected.
      </p>

      <p>
        <strong>Device:</strong>
        {device_label}
      </p>

      <p>
        <strong>IP:</strong>
        {ip_label}
      </p>

      <p>
        <strong>Time:</strong>
        {time_label}
      </p>

      <p>
        If this was not you, change
        your password and revoke your
        active sessions.
      </p>
    </div>
    """

    return send_email(
        target_email=target_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        email_type="new_login",
        user_id=user_id,
        raise_on_failure=False,
    )


def send_report_reminder_email(
    *,
    target_email: str,
    full_name: str,
    user_id: UUID,
    report_type: str,
    start_date: date,
    end_date: date,
) -> bool:
    pretty_type = (
        "weekly"
        if report_type == "weekly"
        else "monthly"
    )

    subject = (
        f"Your PPIS {pretty_type} "
        f"report is ready"
    )

    text_body = (
        f"Hello {full_name}. "
        f"Your PPIS {pretty_type} "
        f"reporting period from "
        f"{start_date} to {end_date} "
        f"has ended. "
        f"Open the PPIS app to review "
        f"your productivity and "
        f"well-being report."
    )

    html_body = f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:600px;
        margin:0 auto;
        line-height:1.6
    ">
      <h2>
        Your PPIS {pretty_type}
        report is ready
      </h2>

      <p>Hello {full_name},</p>

      <p>
        Your reporting period from
        <strong>{start_date}</strong>
        to
        <strong>{end_date}</strong>
        has ended.
      </p>

      <p>
        Open the PPIS app to review
        your productivity and
        well-being report.
      </p>
    </div>
    """

    return send_email(
        target_email=target_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        email_type=(
            f"{pretty_type}_report_reminder"
        ),
        user_id=user_id,
        raise_on_failure=False,
    )