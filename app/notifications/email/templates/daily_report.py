"""Daily productivity report email content."""

from datetime import date


def build_daily_report_email(
    *,
    full_name: str,
    report_date: date,
    productivity_score: int,
    stress_index: int,
    data_coverage: float,
    stress_data_coverage: float,
) -> tuple[str, str, str]:
    subject = f"Your PPIS daily report for {report_date}"

    stress_label = (
        f"{stress_index}/100"
        if stress_data_coverage > 0
        else "Not enough stress-related data"
    )

    text_body = (
        f"Hello {full_name}. "
        f"Your PPIS daily report for {report_date} is ready. "
        f"Productivity: {productivity_score}/100. "
        f"Stress: {stress_label}. "
        f"Productivity data coverage: {data_coverage}%. "
        f"Stress data coverage: {stress_data_coverage}%."
    )

    html_body = f'''
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;line-height:1.6">
      <h2>PPIS daily report</h2>
      <p>Hello {full_name},</p>
      <p>Your report for <strong>{report_date}</strong> is ready.</p>
      <p><strong>Productivity:</strong> {productivity_score}/100</p>
      <p><strong>Stress:</strong> {stress_label}</p>
      <p><strong>Productivity data coverage:</strong> {data_coverage}%</p>
      <p><strong>Stress data coverage:</strong> {stress_data_coverage}%</p>
      <p>Open PPIS to review the detailed signals and patterns behind this score.</p>
    </div>
    '''

    return subject, text_body, html_body
