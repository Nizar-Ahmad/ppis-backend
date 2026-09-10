"""OTP email content."""

from app.core.config import settings

OTP_PURPOSE_LABELS = {
    "login": "Login verification", "signup": "Account verification",
    "reset_password": "Password reset", "change_password": "Password change",
}


def build_otp_email(otp_code: str, purpose: str) -> tuple[str, str, str]:
    label = OTP_PURPOSE_LABELS.get(purpose, "Verification")
    subject = f"PPIS {label} code"
    text_body = f"Your PPIS verification code is {otp_code}. It expires in {settings.otp_expire_minutes} minutes. If you did not request this code, ignore this email."
    html_body = f'''\n    <div style="\n        font-family:Arial,sans-serif;\n        max-width:560px;\n        margin:0 auto;\n        line-height:1.5\n    ">\n      <h2>PPIS</h2>\n\n      <p>{label}</p>\n\n      <p>\n        Your verification code is:\n      </p>\n\n      <div style="\n          font-size:32px;\n          font-weight:700;\n          letter-spacing:8px;\n          margin:24px 0\n      ">\n        {otp_code}\n      </div>\n\n      <p>\n        This code expires in\n        {settings.otp_expire_minutes}\n        minutes.\n      </p>\n\n      <p>\n        If you did not request this code,\n        you can ignore this email.\n      </p>\n    </div>\n    '''
    return subject, text_body, html_body
