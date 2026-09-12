import os
import unittest
from datetime import date
from unittest.mock import patch


os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+pysqlite:///:memory:",
)

os.environ.setdefault(
    "SECRET_KEY",
    "test-secret",
)

os.environ.setdefault(
    "OTP_SECRET_KEY",
    "test-otp-secret",
)

os.environ.setdefault(
    "SMTP_USERNAME",
    "test@example.com",
)

os.environ.setdefault(
    "SMTP_APP_PASSWORD",
    "test-password",
)

os.environ.setdefault(
    "EMAIL_FROM",
    "PPIS <test@example.com>",
)

os.environ.setdefault(
    "GOOGLE_WEB_CLIENT_ID",
    "test-client",
)

os.environ.setdefault(
    "GOOGLE_WEB_CLIENT_SECRET",
    "test-secret",
)

os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_LOCAL",
    (
        "http://127.0.0.1:8000/"
        "auth/google/calendar/callback"
    ),
)

os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_SERVER",
    (
        "https://ppis.example.com/"
        "auth/google/calendar/callback"
    ),
)


from app.integrations.google.health import (
    active_minutes_by_date,
    civil_datetime,
    daily_rollup,
    steps_by_date,
)


class GoogleHealthHelpersTests(
    unittest.TestCase
):
    def test_civil_datetime(self):
        self.assertEqual(
            civil_datetime(
                date(2026, 9, 12)
            ),
            {
                "date": {
                    "year": 2026,
                    "month": 9,
                    "day": 12,
                },
                "time": {
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 0,
                    "nanos": 0,
                },
            },
        )

    def test_steps_by_date(self):
        raw = {
            "rollupDataPoints": [
                {
                    "civilStartTime": {
                        "date": {
                            "year": 2026,
                            "month": 9,
                            "day": 12,
                        }
                    },
                    "steps": {
                        "countSum": "8123"
                    },
                }
            ]
        }

        self.assertEqual(
            steps_by_date(raw),
            {
                date(
                    2026,
                    9,
                    12,
                ): 8123
            },
        )

    def test_active_minutes_by_date(self):
        raw = {
            "rollupDataPoints": [
                {
                    "civilStartTime": {
                        "date": {
                            "year": 2026,
                            "month": 9,
                            "day": 12,
                        }
                    },
                    "activeMinutes": {
                        (
                            "activeMinutes"
                            "RollupByActivityLevel"
                        ): [
                            {
                                "activityLevel":
                                    "LIGHT",

                                "activeMinutesSum":
                                    "20",
                            },
                            {
                                "activityLevel":
                                    "MODERATELY_ACTIVE",

                                "activeMinutesSum":
                                    "15",
                            },
                            {
                                "activityLevel":
                                    "VERY_ACTIVE",

                                "activeMinutesSum":
                                    "10",
                            },
                        ]
                    },
                }
            ]
        }

        self.assertEqual(
            active_minutes_by_date(raw),
            {
                date(
                    2026,
                    9,
                    12,
                ): 25
            },
        )

    @patch(
        (
            "app.integrations.google.health."
            "google_health_post"
        )
    )
    def test_daily_rollup_request(
        self,
        mock_post,
    ):
        mock_post.return_value = {
            "rollupDataPoints": []
        }

        daily_rollup(
            data_type="steps",
            start_date=
                date(2026, 9, 5),
            end_date_exclusive=
                date(2026, 9, 13),
            access_token=
                "test-token",
        )

        args = mock_post.call_args.args

        self.assertEqual(
            args[0],
            (
                "/dataTypes/steps/"
                "dataPoints:dailyRollUp"
            ),
        )

        self.assertEqual(
            args[1],
            "test-token",
        )

        body = args[2]

        self.assertEqual(
            body["windowSizeDays"],
            1,
        )

        self.assertEqual(
            body["range"]["start"],
            {
                "date": {
                    "year": 2026,
                    "month": 9,
                    "day": 5,
                },
                "time": {
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 0,
                    "nanos": 0,
                },
            },
        )

        self.assertEqual(
            body["range"]["end"],
            {
                "date": {
                    "year": 2026,
                    "month": 9,
                    "day": 13,
                },
                "time": {
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 0,
                    "nanos": 0,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
