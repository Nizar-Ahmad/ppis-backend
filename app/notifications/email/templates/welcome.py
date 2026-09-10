"""Welcome email content."""


def build_welcome_email(full_name: str) -> tuple[str, str, str]:
    subject = "Welcome to PPIS"
    text_body = f"Welcome to PPIS, {full_name}. Start tracking your daily sleep, mood, energy, focused work, activity, screen time and calendar patterns to understand your productivity and well-being."
    html_body = f'''\n    <div style="\n        font-family:Arial,sans-serif;\n        max-width:600px;\n        margin:0 auto;\n        line-height:1.6\n    ">\n      <h2>Welcome to PPIS</h2>\n\n      <p>Hello {full_name},</p>\n\n      <p>\n        Your PPIS account is ready.\n        Start tracking your daily patterns\n        and PPIS will help you understand\n        how sleep, mood, activity, screen\n        time, meetings and focused work\n        relate to your productivity and\n        well-being.\n      </p>\n\n      <p>\n        We are glad to have you with us.\n      </p>\n    </div>\n    '''
    return subject, text_body, html_body
