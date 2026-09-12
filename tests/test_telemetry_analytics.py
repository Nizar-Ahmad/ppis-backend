import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+pysqlite:///:memory:",
)
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OTP_SECRET_KEY", "test-otp-secret")
os.environ.setdefault("SMTP_USERNAME", "test@example.com")
os.environ.setdefault("SMTP_APP_PASSWORD", "test-password")
os.environ.setdefault("EMAIL_FROM", "PPIS <test@example.com>")
os.environ.setdefault("GOOGLE_WEB_CLIENT_ID", "test-client")
os.environ.setdefault("GOOGLE_WEB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_LOCAL",
    "http://127.0.0.1:8000/auth/google/calendar/callback",
)
os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_SERVER",
    "https://ppis.example.com/auth/google/calendar/callback",
)

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.jobs import report_reminders
from app.models import (
    ActivityStat,
    CalendarEvent,
    DailyInput,
    DailyScore,
    NotificationPreference,
    Role,
    ScreenTimeStat,
    User,
    UserProfile,
)
from app.services.analytics.daily import (
    calculate_and_save_daily_score,
    get_available_dates_between,
    get_meeting_minutes_for_day,
)
from app.services.analytics.insights import (
    get_weekly_insights,
)
from app.services.analytics.monthly import (
    get_monthly_analytics,
)
from app.services.analytics.weekly import (
    get_weekly_analytics,
)


UTC = timezone.utc


class TelemetryFirstAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:"
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.db = self.Session()

        role = Role(
            name="USER",
            description="Test user",
        )
        self.db.add(role)
        self.db.flush()

        self.user = User(
            email="telemetry@example.com",
            full_name="Telemetry User",
            role_id=role.id,
        )
        self.db.add(self.user)
        self.db.flush()

        self.profile = UserProfile(
            user_id=self.user.id,
            timezone="Asia/Dubai",
            preferred_language="en",
            login_otp_enabled=False,
        )
        self.db.add(self.profile)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_activity(
        self,
        entry_date: date,
        *,
        steps: int = 8000,
        activity_minutes: int = 30,
    ):
        self.db.add(
            ActivityStat(
                user_id=self.user.id,
                entry_date=entry_date,
                steps=steps,
                activity_minutes=activity_minutes,
                source="health_connect",
            )
        )
        self.db.commit()

    def add_screen(
        self,
        entry_date: date,
        *,
        total_minutes: int = 240,
        night_minutes: int = 60,
    ):
        self.db.add(
            ScreenTimeStat(
                user_id=self.user.id,
                entry_date=entry_date,
                total_minutes=total_minutes,
                night_minutes=night_minutes,
            )
        )
        self.db.commit()

    def add_event(
        self,
        start_time: datetime,
        end_time: datetime,
    ):
        self.db.add(
            CalendarEvent(
                user_id=self.user.id,
                external_id=None,
                source="local",
                title="Test meeting",
                start_time=start_time,
                end_time=end_time,
                duration_minutes=int(
                    (end_time - start_time)
                    .total_seconds()
                    / 60
                ),
            )
        )
        self.db.commit()

    def add_daily_input(
        self,
        entry_date: date,
        *,
        mood: int = 4,
        sleep_hours: float = 8,
        energy_level: int = 3,
        focused_work_hours: float = 3,
    ):
        self.db.add(
            DailyInput(
                user_id=self.user.id,
                entry_date=entry_date,
                mood=mood,
                sleep_hours=sleep_hours,
                energy_level=energy_level,
                focused_work_hours=focused_work_hours,
                notes="Optional input",
            )
        )
        self.db.commit()

    def test_activity_only_without_daily_input(self):
        target = date(2026, 9, 12)
        self.add_activity(target)

        score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )

        self.assertEqual(score.productivity_score, 100)
        self.assertEqual(score.data_coverage, 10.0)
        self.assertEqual(score.stress_data_coverage, 0.0)

    def test_screen_time_only_without_daily_input(self):
        target = date(2026, 9, 12)
        self.add_screen(target)

        score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )

        self.assertEqual(score.distraction_score, 50)
        self.assertEqual(score.productivity_score, 50)
        self.assertEqual(score.stress_index, 50)
        self.assertEqual(score.data_coverage, 5.0)
        self.assertEqual(score.stress_data_coverage, 20.0)

    def test_calendar_activity_screen_without_daily_input(self):
        target = date(2026, 9, 12)
        self.add_activity(target)
        self.add_screen(target)
        self.add_event(
            datetime(2026, 9, 12, 6, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 7, 0, tzinfo=UTC),
        )

        score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )

        self.assertEqual(score.productivity_score, 82)
        self.assertEqual(score.stress_index, 35)
        self.assertEqual(score.data_coverage, 20.0)
        self.assertEqual(score.stress_data_coverage, 40.0)

    def test_daily_input_enriches_existing_automatic_score(self):
        target = date(2026, 9, 12)
        self.add_activity(target)

        automatic_score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )
        self.assertEqual(automatic_score.data_coverage, 10.0)

        self.add_daily_input(target)
        enriched_score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )

        self.assertEqual(enriched_score.productivity_score, 71)
        self.assertEqual(enriched_score.data_coverage, 90.0)
        self.assertEqual(enriched_score.stress_data_coverage, 60.0)

    def test_weekly_analytics_includes_days_without_daily_input(self):
        start = date(2026, 9, 7)
        self.add_activity(start)
        self.add_screen(start + timedelta(days=1))
        self.add_event(
            datetime(2026, 9, 9, 6, 0, tzinfo=UTC),
            datetime(2026, 9, 9, 7, 0, tzinfo=UTC),
        )

        result = get_weekly_analytics(
            start,
            self.user,
            self.db,
        )

        self.assertEqual(result.days_analyzed, 3)
        self.assertEqual(result.subjective_days, 0)
        self.assertGreater(result.average_data_coverage, 0)

    def test_monthly_analytics_works_with_telemetry_only(self):
        self.add_activity(date(2026, 9, 2))
        self.add_screen(date(2026, 9, 3))

        result = get_monthly_analytics(
            2026,
            9,
            self.user,
            self.db,
        )

        self.assertEqual(result.days_analyzed, 2)
        self.assertEqual(result.subjective_days, 0)

    def test_weekly_insights_work_without_daily_input(self):
        start = date(2026, 9, 7)
        self.add_activity(start, steps=9000, activity_minutes=40)
        self.add_activity(
            start + timedelta(days=1),
            steps=0,
            activity_minutes=0,
        )

        insights = get_weekly_insights(
            start,
            self.user,
            self.db,
        )

        types = {
            item.insight_type
            for item in insights
        }
        self.assertIn("weekly_summary", types)
        self.assertIn("activity_productivity", types)

    def test_calendar_day_attribution_uses_user_timezone(self):
        self.add_event(
            datetime(2026, 9, 11, 21, 30, tzinfo=UTC),
            datetime(2026, 9, 11, 22, 30, tzinfo=UTC),
        )

        self.assertEqual(
            get_meeting_minutes_for_day(
                self.user.id,
                date(2026, 9, 11),
                self.db,
            ),
            0,
        )
        self.assertEqual(
            get_meeting_minutes_for_day(
                self.user.id,
                date(2026, 9, 12),
                self.db,
            ),
            60,
        )

        dates = get_available_dates_between(
            user_id=self.user.id,
            start_date=date(2026, 9, 11),
            end_date=date(2026, 9, 12),
            db=self.db,
        )
        self.assertEqual(dates, [date(2026, 9, 12)])

    def test_daily_report_is_deduplicated(self):
        report_date = date(2026, 9, 16)
        self.add_activity(report_date)
        now_utc = datetime(
            2026, 9, 16, 22, 0,
            tzinfo=UTC,
        )
        self.db.close()

        with (
            patch.object(
                report_reminders,
                "SessionLocal",
                self.Session,
            ),
            patch.object(
                report_reminders,
                "send_daily_report_email",
                return_value=True,
            ) as send_daily,
        ):
            report_reminders.run_report_reminders(
                now_utc=now_utc
            )
            report_reminders.run_report_reminders(
                now_utc=now_utc
            )
            self.assertEqual(send_daily.call_count, 1)

        self.db = self.Session()
        preferences = self.db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id
                == self.user.id
            )
        )
        self.assertEqual(
            preferences.last_daily_report_date,
            report_date,
        )

        score = self.db.scalar(
            select(DailyScore).where(
                DailyScore.user_id == self.user.id,
                DailyScore.entry_date == report_date,
            )
        )
        self.assertIsNotNone(score)

    def test_existing_full_weight_behavior_is_preserved(self):
        target = date(2026, 9, 12)
        self.add_daily_input(
            target,
            mood=5,
            sleep_hours=8,
            energy_level=5,
            focused_work_hours=6,
        )
        self.add_activity(target)
        self.add_screen(
            target,
            total_minutes=0,
            night_minutes=0,
        )
        self.add_event(
            datetime(2026, 9, 12, 6, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 7, 0, tzinfo=UTC),
        )

        score = calculate_and_save_daily_score(
            target,
            self.user,
            self.db,
        )

        self.assertEqual(score.productivity_score, 99)
        self.assertEqual(score.stress_index, 4)
        self.assertEqual(score.data_coverage, 100.0)
        self.assertEqual(score.stress_data_coverage, 100.0)


if __name__ == "__main__":
    unittest.main()
