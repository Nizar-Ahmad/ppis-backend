"""Report-reminder email content."""

from datetime import date


def build_report_reminder_email(full_name: str, report_type: str, start_date: date, end_date: date) -> tuple[str, str, str, str]:
    pretty_type = "weekly" if report_type == "weekly" else "monthly"
    subject = f"Your PPIS {pretty_type} report is ready"
    text_body = f"Hello {full_name}. Your PPIS {pretty_type} reporting period from {start_date} to {end_date} has ended. Open the PPIS app to review your productivity and well-being report."
    html_body = f'''\n    <div style="\n        font-family:Arial,sans-serif;\n        max-width:600px;\n        margin:0 auto;\n        line-height:1.6\n    ">\n      <h2>\n        Your PPIS {pretty_type}\n        report is ready\n      </h2>\n\n      <p>Hello {full_name},</p>\n\n      <p>\n        Your reporting period from\n        <strong>{start_date}</strong>\n        to\n        <strong>{end_date}</strong>\n        has ended.\n      </p>\n\n      <p>\n        Open the PPIS app to review\n        your productivity and\n        well-being report.\n      </p>\n    </div>\n    '''
    return pretty_type, subject, text_body, html_body
