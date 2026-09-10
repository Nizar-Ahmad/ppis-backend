"""Gmail SMTP transport only."""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_smtp_message(message: EmailMessage) -> None:
    tls_context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=tls_context)
        smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_app_password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
