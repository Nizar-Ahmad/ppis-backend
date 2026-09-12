"""All SQLAlchemy model declarations.

Importing this package registers every table on the single shared Base before
``Base.metadata.create_all`` runs.
"""

from app.models.auth import AuthSession, OtpCode
from app.models.feedback import Feedback
from app.models.google_health import GoogleHealthConnection
from app.models.integrations import GoogleCalendarConnection
from app.models.observability import ApiUsageStat, AuditLog, EmailLog
from app.models.productivity import (
    ActivityStat,
    CalendarEvent,
    DailyInput,
    DailyScore,
    Insight,
    ScreenTimeStat,
)
from app.models.user import NotificationPreference, Role, User, UserProfile

__all__ = [
    "ActivityStat", "ApiUsageStat", "AuditLog", "AuthSession",
    "CalendarEvent", "DailyInput", "DailyScore", "EmailLog", "Feedback",
    "GoogleCalendarConnection", "GoogleHealthConnection", "Insight",
    "NotificationPreference", "OtpCode", "Role", "ScreenTimeStat",
    "User", "UserProfile",
]
