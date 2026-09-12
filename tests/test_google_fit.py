import os
import unittest
from datetime import datetime, timezone

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
os.environ.setdefault("GOOGLE_WEB_CLIENT_SECRET", "test-secret")
os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_LOCAL",
    "http://127.0.0.1:8000/auth/google/calendar/callback",
)
os.environ.setdefault(
    "GOOGLE_CALENDAR_REDIRECT_URI_SERVER",
    "https://ppis.example.com/auth/google/calendar/callback",
)
os.environ.setdefault(
    "GOOGLE_FIT_REDIRECT_URI_LOCAL",
    "http://127.0.0.1:8000/auth/google/fit/callback",
)
os.environ.setdefault(
    "GOOGLE_FIT_REDIRECT_URI_SERVER",
    "https://ppis.example.com/auth/google/fit/callback",
)

from app.integrations.google.fit import (
    aggregate_numeric_total,
    milliseconds,
    move_minutes_from_aggregate,
    simplify_aggregate_response,
)


class GoogleFitHelpersTests(unittest.TestCase):
    def test_milliseconds(self):
        value = datetime(
            2026,
            9,
            12,
            tzinfo=timezone.utc,
        )
        self.assertEqual(
            milliseconds(value),
            1789171200000,
        )

    def test_aggregate_numeric_total(self):
        data = {
            "bucket": [
                {
                    "dataset": [
                        {
                            "point": [
                                {
                                    "value": [
                                        {"intVal": 1200},
                                        {"fpVal": 2.5},
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(
            aggregate_numeric_total(data),
            1202.5,
        )

    def test_move_minutes_converts_milliseconds(self):
        data = {
            "bucket": [
                {
                    "dataset": [
                        {
                            "point": [
                                {
                                    "value": [
                                        {"intVal": 1_800_000}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(
            move_minutes_from_aggregate(data),
            30,
        )

    def test_simplify_aggregate_response(self):
        raw = {
            "bucket": [
                {
                    "startTimeMillis": "1",
                    "endTimeMillis": "2",
                    "dataset": [
                        {
                            "dataSourceId": "source",
                            "point": [
                                {
                                    "startTimeNanos": "10",
                                    "endTimeNanos": "20",
                                    "dataTypeName": "com.google.step_count.delta",
                                    "originDataSourceId": "origin",
                                    "value": [{"intVal": 4000}],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        result = simplify_aggregate_response(raw)

        self.assertEqual(result[0]["startTimeMillis"], "1")
        self.assertEqual(
            result[0]["datasets"][0]["points"][0]["values"][0]["intVal"],
            4000,
        )


if __name__ == "__main__":
    unittest.main()
