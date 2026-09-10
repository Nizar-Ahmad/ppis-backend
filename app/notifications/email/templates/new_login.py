"""New-login alert email content."""

from datetime import datetime, timezone


def build_new_login_email(full_name: str, device_name: str | None, client_type: str, ip_address: str | None, occurred_at: datetime) -> tuple[str, str, str]:
    subject = "New sign-in to your PPIS account"
    device_label = device_name or client_type or "Unknown device"
    ip_label = ip_address or "Unknown"
    time_label = occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text_body = f"Hello {full_name}. A new sign-in to your PPIS account was detected. Device: {device_label}. IP: {ip_label}. Time: {time_label}. If this was not you, change your password and revoke active sessions."
    html_body = f'''\n    <div style="\n        font-family:Arial,sans-serif;\n        max-width:600px;\n        margin:0 auto;\n        line-height:1.6\n    ">\n      <h2>New PPIS sign-in</h2>\n\n      <p>Hello {full_name},</p>\n\n      <p>\n        A new sign-in to your PPIS\n        account was detected.\n      </p>\n\n      <p>\n        <strong>Device:</strong>\n        {device_label}\n      </p>\n\n      <p>\n        <strong>IP:</strong>\n        {ip_label}\n      </p>\n\n      <p>\n        <strong>Time:</strong>\n        {time_label}\n      </p>\n\n      <p>\n        If this was not you, change\n        your password and revoke your\n        active sessions.\n      </p>\n    </div>\n    '''
    return subject, text_body, html_body
