# PPIS Backend

Backend service for the **Personal Pattern Intelligence System (PPIS)**.

PPIS is a productivity and well-being analytics platform that combines automatic telemetry with optional subjective user input to generate daily, weekly, and monthly insights about productivity, stress, activity, meetings, screen usage, sleep-related signals, and work patterns.

The backend is built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy**, and serves the PPIS Android application and administrative interfaces.

---

## Production

Production API:

```text
https://ppis.thevirtualtrust.com/
```

Interactive API documentation:

```text
https://ppis.thevirtualtrust.com/docs
```

OpenAPI specification:

```text
https://ppis.thevirtualtrust.com/openapi.json
```

Health endpoints:

```text
GET /health
GET /health/database
```

---

# Architecture

PPIS follows a **telemetry-first architecture**.

Automatic data sources are treated as the primary source of productivity signals, while manual daily input is optional enrichment.

Core telemetry sources include:

- Android Health Connect
- Android UsageStats
- Google Calendar
- Local Android calendar
- Google Health API
- Optional subjective DailyInput data

The backend is responsible for:

- Authentication
- Session management
- OTP workflows
- User profile management
- Telemetry storage
- Google integrations
- Analytics calculation
- Productivity scoring
- Stress scoring
- Weekly/monthly aggregation
- Insight generation
- Feedback collection
- Email notifications
- Administrative APIs
- Audit logging
- API observability

The backend is the **authoritative analytics engine**.

Clients should not implement a separate productivity scoring algorithm.

---

# Technology Stack

## Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- Pydantic Settings
- SQLAlchemy 2.x
- PostgreSQL
- Psycopg 3
- Requests

## Authentication & Security

- JWT access tokens
- Stateful refresh sessions
- Refresh-token rotation
- SHA-256 refresh token storage
- PyJWT
- Argon2 password hashing
- `pwdlib`
- OTP verification
- Session revocation
- Audit logging
- Google Identity authentication

## Google Integrations

- Google Login
- Google Calendar API
- Google Health API v4

---

# Main Project Structure

```text
ppis-backend/
│
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── roles.py
│   │   └── time.py
│   │
│   ├── integrations/
│   │   └── google/
│   │       ├── auth.py
│   │       ├── calendar.py
│   │       └── health.py
│   │
│   ├── models/
│   │   ├── auth.py
│   │   ├── feedback.py
│   │   ├── google_health.py
│   │   ├── integrations.py
│   │   ├── observability.py
│   │   ├── productivity.py
│   │   └── user.py
│   │
│   ├── routers/
│   │   ├── activity.py
│   │   ├── admin.py
│   │   ├── admin_feedback.py
│   │   ├── admin_observability.py
│   │   ├── admin_sessions.py
│   │   ├── analytics.py
│   │   ├── auth.py
│   │   ├── calendar.py
│   │   ├── daily_inputs.py
│   │   ├── feedback.py
│   │   ├── google_calendar.py
│   │   ├── google_health.py
│   │   ├── health.py
│   │   ├── insights.py
│   │   ├── monthly_analytics.py
│   │   ├── otp.py
│   │   ├── profile.py
│   │   ├── screen_time.py
│   │   └── sessions.py
│   │
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── deploy/
├── migrations/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

# Authentication

PPIS supports:

- Email/password login
- Google login
- Optional login OTP
- Password reset using OTP
- Password change using OTP
- Google account linking
- Google account unlinking
- Stateful device sessions
- Refresh-token rotation

---

## Email / Password Login

```http
POST /auth/login
```

Example:

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!",
  "client": {
    "client_type": "android",
    "device_id": "device-id",
    "device_name": "Pixel",
    "app_version": "1.0.0"
  }
}
```

If OTP is disabled, the response contains access and refresh tokens.

If login OTP is enabled:

```json
{
  "requires_otp": true,
  "challenge_id": "...",
  "purpose": "login",
  "otp_expires_in": 300
}
```

The login is then completed through the OTP verification endpoint.

---

# Google Authentication

Google account login:

```http
POST /auth/google
```

Google account linking:

```http
POST /auth/google/link
```

Google account unlinking:

```http
DELETE /auth/google/unlink
```

Current authenticated user:

```http
GET /auth/me
```

A Google-only account may set a password using:

```http
POST /auth/set-password
```

---

# OTP

Supported OTP purposes:

```text
login
signup
reset_password
change_password
```

Endpoints:

```http
POST /auth/otp/send
POST /auth/otp/resend
POST /auth/otp/verify
```

Signup is completed through the OTP verification workflow rather than through a separate `/signup` route.

---

# Sessions

PPIS uses stateful authentication sessions.

An authentication session tracks information including:

- Session ID
- User ID
- Client type
- Device ID
- Device name
- App version
- IP address
- User agent
- Created time
- Last activity
- Expiration
- Revocation state
- Token version

Access tokens are short-lived.

Refresh tokens are rotated and associated with a server-side session.

---

## Session Endpoints

```http
POST   /auth/refresh
POST   /auth/logout
POST   /auth/logout-all

GET    /auth/sessions
DELETE /auth/sessions/{session_id}

POST   /auth/sessions/revoke-others
```

Clients should use **single-flight refresh handling**.

If several API requests receive an expired access token simultaneously, only one refresh request should execute.

---

# User Profile

Profile endpoints:

```http
GET /profile
PUT /profile
```

Profile information includes:

- Full name
- Birth date
- Country
- Occupation
- Timezone
- Preferred language
- Login OTP preference
- Google account connection state

Timezone is important because PPIS analytics use the user's local calendar day.

---

# Notification Preferences

```http
GET /profile/notifications
PUT /profile/notifications
```

Supported preferences include:

```text
daily_report_email
weekly_report_email
monthly_report_email
new_login_email
```

---

# Telemetry-First Data Model

PPIS analytics can operate without manual DailyInput records.

A daily score can be calculated using any available combination of:

```text
DailyInput
ActivityStat
ScreenTimeStat
CalendarEvent
```

Missing data sources do not prevent analytics from being calculated.

Weights are normalized across the available signals.

---

# Daily Input

DailyInput contains optional subjective data.

Typical fields:

```text
mood
sleep_hours
energy_level
focused_work_hours
notes
```

DailyInput is **optional**.

The absence of DailyInput does not prevent productivity or stress analytics from being generated.

Endpoints:

```http
POST   /daily-inputs
GET    /daily-inputs
GET    /daily-inputs/{entry_date}
PUT    /daily-inputs/{entry_date}
DELETE /daily-inputs/{entry_date}
```

---

# Activity

Activity data contains:

```text
steps
activity_minutes
source
```

Endpoints:

```http
POST   /activity
GET    /activity
GET    /activity/{entry_date}
PUT    /activity/{entry_date}
DELETE /activity/{entry_date}
```

Client-writable activity sources currently include:

```text
manual
health_connect
```

The server may additionally create:

```text
google_health
```

records through Google Health synchronization.

---

# Activity Source Priority

PPIS uses the following activity source priority:

```text
Health Connect
     ↓
highest priority

Google Health
     ↓
secondary cloud source

Manual
     ↓
fallback
```

Android Health Connect remains the preferred source for device-derived activity data.

When Google Health synchronization encounters an existing activity record whose source is:

```text
health_connect
```

the backend preserves the Health Connect record and skips the Google Health overwrite.

---

# Screen Time

Android screen-time telemetry is normalized into daily records.

Fields:

```text
entry_date
total_minutes
night_minutes
```

Endpoints:

```http
POST   /screen-time
GET    /screen-time
GET    /screen-time/{entry_date}
PUT    /screen-time/{entry_date}
DELETE /screen-time/{entry_date}
```

Screen-time values can be used independently by the analytics engine even when no DailyInput exists.

---

# Calendar Events

Calendar events represent meetings and scheduled activities.

Sources may include:

```text
manual
local
google
```

Endpoints:

```http
POST   /calendar/events
GET    /calendar/events
GET    /calendar/events/{event_id}
PUT    /calendar/events/{event_id}
DELETE /calendar/events/{event_id}
```

The backend performs cross-source duplicate detection using event timing and title information.

---

# Google Calendar Integration

Google Calendar is integrated through server-side OAuth.

The Android/web clients do not store Google Calendar refresh tokens.

Endpoints:

```http
GET    /auth/google/calendar/connect
GET    /auth/google/calendar/callback
GET    /auth/google/calendar/status
DELETE /auth/google/calendar/disconnect
POST   /auth/google/calendar/sync
```

Example production connection request:

```http
GET /auth/google/calendar/connect?mode=server
```

The backend returns:

```json
{
  "authorization_url": "..."
}
```

The user completes OAuth in a browser.

Google redirects to the backend callback.

The backend stores the Google access/refresh credentials server-side.

---

## Google Calendar Synchronization

Example:

```http
POST /auth/google/calendar/sync?days_back=7&days_forward=30
```

The backend:

1. Reads the user's Google calendars.
2. Fetches events within the requested interval.
3. Ignores all-day events for meeting analytics.
4. Creates new events.
5. Updates existing events.
6. Handles cancelled events.
7. Prevents duplicate calendar records.

Production also supports scheduled server-side Google Calendar synchronization.

---

# Google Health API

PPIS uses **Google Health API v4** as an optional cloud health integration.

The backend communicates with:

```text
https://health.googleapis.com/v4
```

Google Health is a **server-side integration**.

The mobile application must never store the Google Health client secret or Google Health refresh token.

---

## Google Health Endpoints

```http
GET    /auth/google/health/connect
GET    /auth/google/health/callback
GET    /auth/google/health/status
DELETE /auth/google/health/disconnect

GET    /auth/google/health/daily/{metric}
GET    /auth/google/health/sleep
GET    /auth/google/health/exercise

POST   /auth/google/health/sync
```

---

## Supported Daily Google Health Metrics

Current daily rollup support includes:

```text
steps
active-minutes
distance
calories
heart-rate
```

Example:

```http
GET /auth/google/health/daily/steps?days=7
```

---

## Google Health Synchronization

```http
POST /auth/google/health/sync?days_back=7
```

`days_back=7` means:

```text
today + previous 7 days
```

for a total of eight local calendar dates.

The synchronization currently imports:

```text
steps
active minutes
```

into `ActivityStat`.

Imported records use:

```text
source = google_health
```

If an existing day already contains:

```text
source = health_connect
```

that day is skipped so that Android Health Connect remains authoritative.

---

## Google Health OAuth

The Google Health backend uses server-side OAuth.

Production callback:

```text
https://ppis.thevirtualtrust.com/auth/google/health/callback
```

Required Google Health scopes currently include:

```text
googlehealth.activity_and_fitness.readonly

googlehealth.health_metrics_and_measurements.readonly

googlehealth.sleep.readonly
```

Google access and refresh tokens remain stored only by the backend.

---

# Legacy Google Fit

The previous temporary Google Fit REST integration has been removed from the running application.

The following route family is no longer supported:

```text
/auth/google/fit/*
```

Do not build new clients against the legacy Google Fitness REST API.

The legacy database table may remain temporarily in production for rollback safety, but it is not used by the application.

---

# Analytics

The analytics engine is telemetry-first.

---

## Daily Analytics

```http
GET /analytics/daily/{entry_date}
```

The response contains metrics such as:

```text
productivity_score
stress_index
sleep_score
meeting_load_score
distraction_score
activity_score
data_coverage
stress_data_coverage
```

`data_coverage` indicates how much of the available productivity model was represented by actual data.

---

# Productivity Model

Conceptual productivity weights:

| Signal | Weight |
|---|---:|
| Focus | 30% |
| Energy | 20% |
| Mood | 15% |
| Sleep | 15% |
| Activity | 10% |
| Distraction | 5% |
| Meeting Load | 5% |

When some sources are unavailable, weights are normalized across the available signals.

---

# Stress Model

Conceptual stress weights:

| Signal | Weight |
|---|---:|
| Sleep | 25% |
| Energy | 20% |
| Mood | 15% |
| Meeting Load | 20% |
| Distraction | 20% |

The stress score also works with partial telemetry.

---

# Weekly Analytics

```http
GET /analytics/weekly?start_date=YYYY-MM-DD
```

Weekly analytics include:

```text
days_analyzed
subjective_days
average_sleep_hours
average_mood
average_energy_level
total_focused_work_hours
total_meeting_minutes
total_screen_minutes
average_productivity_score
average_stress_index
average_data_coverage
average_stress_data_coverage
best_day
worst_day
```

Telemetry-only days are included.

---

# Monthly Analytics

```http
GET /analytics/monthly?year=2026&month=9
```

Monthly analytics support the same telemetry-first behavior as daily and weekly analytics.

---

# Insights

Weekly insights:

```http
GET /insights/weekly?start_date=YYYY-MM-DD
```

Insights can be generated even when some days contain only automatic telemetry.

---

# Feedback

Users can submit feedback about:

```text
app
weekly_report
monthly_report
insight
```

Endpoints:

```http
POST   /feedback
GET    /feedback/mine
PUT    /feedback/{feedback_id}
DELETE /feedback/{feedback_id}
```

Ratings range from:

```text
1 to 5
```

---

# Administration API

Administrative endpoints use the:

```text
/api/admin
```

prefix.

Admin authorization is role-based.

Supported roles include:

```text
USER
ADMIN
```

---

## Admin Statistics

```http
GET /api/admin/statistics
```

Provides system-level statistics including users, telemetry records, scores, Google Calendar connections, productivity averages, and other operational information.

---

## Admin User Management

```http
GET    /api/admin/users
GET    /api/admin/users/{user_id}
GET    /api/admin/users/{user_id}/data

POST   /api/admin/users

PUT    /api/admin/users/{user_id}/role
PUT    /api/admin/users/{user_id}/password

DELETE /api/admin/users/{user_id}
```

Administrators can:

- Create users
- Inspect user data
- Change roles
- Reset passwords
- Delete accounts

Administrative password resets revoke existing user sessions.

---

# Admin Session Management

```http
GET    /api/admin/sessions
DELETE /api/admin/sessions/{session_id}
```

Available filters include:

```text
active_only
user_id
client_type
limit
offset
```

---

# Admin Feedback

```http
GET /api/admin/feedback
GET /api/admin/feedback/statistics
```

---

# Observability

The backend tracks:

- API usage
- Client/server errors
- Request duration
- Authentication events
- OTP events
- Email activity
- Administrative actions
- Session events
- Feedback activity

Administrative observability endpoints include:

```http
GET /api/admin/observability/summary
GET /api/admin/observability/api-usage
GET /api/admin/observability/audit-logs
```

---

# Email Notifications

PPIS supports SMTP-based email notifications.

Current email use cases include:

- OTP delivery
- Welcome emails
- New-login notifications
- Daily reports
- Weekly reports
- Monthly reports

SMTP configuration is loaded through environment variables.

---

# Scheduled Jobs

Production uses systemd timers for background jobs.

Current production jobs include:

```text
ppis-maintenance.timer
ppis-report-reminders.timer
ppis-google-calendar-sync.timer
```

Typical responsibilities include:

- Data maintenance
- Report processing/reminders
- Google Calendar synchronization

Google Health currently does not depend on a separate server-side systemd synchronization timer.

---

# Database

Production uses PostgreSQL.

Main data areas include:

```text
users
roles
user profiles

authentication sessions
OTP challenges

daily inputs
activity statistics
screen-time statistics
calendar events

daily scores
insights

Google Calendar connections
Google Health connections

feedback

audit logs
email logs
API usage statistics
```

SQLAlchemy models share a common declarative `Base`.

The application currently calls:

```python
Base.metadata.create_all(bind=engine)
```

during application initialization.

Explicit SQL migration scripts are also stored in:

```text
migrations/
```

The project currently does not depend on Alembic.

---

# Environment Configuration

Copy the example configuration:

```bash
cp .env.example .env
```

Then configure the required values.

Example categories:

```env
APP_NAME=PPIS API
APP_VERSION=1.0.0

DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@127.0.0.1:5432/DATABASE_NAME

SECRET_KEY=CHANGE_ME
OTP_SECRET_KEY=CHANGE_ME_TOO

ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=YOUR_EMAIL
SMTP_APP_PASSWORD=YOUR_APP_PASSWORD
EMAIL_FROM="PPIS <YOUR_EMAIL>"

GOOGLE_WEB_CLIENT_ID=YOUR_WEB_CLIENT_ID
GOOGLE_WEB_CLIENT_SECRET=YOUR_WEB_CLIENT_SECRET

GOOGLE_CALENDAR_REDIRECT_URI_LOCAL=http://127.0.0.1:8000/auth/google/calendar/callback
GOOGLE_CALENDAR_REDIRECT_URI_SERVER=https://ppis.thevirtualtrust.com/auth/google/calendar/callback

GOOGLE_HEALTH_REDIRECT_URI_LOCAL=http://127.0.0.1:8000/auth/google/health/callback
GOOGLE_HEALTH_REDIRECT_URI_SERVER=https://ppis.thevirtualtrust.com/auth/google/health/callback
```

Never commit the real `.env` file.

Never commit:

- Database passwords
- JWT secrets
- OTP secrets
- SMTP passwords
- Google client secrets
- Access tokens
- Refresh tokens

---

# Local Development

## 1. Clone

```bash
git clone https://github.com/Nizar-Ahmad/ppis-backend.git
cd ppis-backend
```

---

## 2. Create a Virtual Environment

```bash
python -m venv venv
```

Linux/macOS:

```bash
source venv/bin/activate
```

Windows:

```text
venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Core dependencies include:

- FastAPI
- SQLAlchemy
- Psycopg
- Pydantic
- PyJWT
- pwdlib
- Argon2
- google-auth
- requests
- Uvicorn

---

## 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with local database, authentication, SMTP, and Google OAuth configuration.

---

## 5. Run the API

```bash
uvicorn app.main:app --reload
```

Default development URL:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

OpenAPI:

```text
http://127.0.0.1:8000/openapi.json
```

---

# Testing

Compile the application:

```bash
python -m compileall -q app
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

Important regression coverage includes:

- Telemetry-first analytics
- Activity-only analytics
- Screen-time-only analytics
- Calendar/activity/screen combinations
- Timezone-aware calendar attribution
- DailyInput enrichment
- Weekly analytics without DailyInput
- Monthly telemetry analytics
- Insight generation
- Daily report deduplication
- Google Health helper logic

---

# Production Deployment

Production uses:

```text
Uvicorn
systemd
PostgreSQL
```

Example service execution:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 80
```

Production service:

```text
ppis.service
```

Check service:

```bash
sudo systemctl status ppis --no-pager -l
```

Restart:

```bash
sudo systemctl restart ppis
```

Logs:

```bash
sudo journalctl -u ppis -n 100 --no-pager
```

Live logs:

```bash
sudo journalctl -u ppis -f
```

---

# Deployment Workflow

Recommended deployment flow:

```text
feature branch
      ↓
tests
      ↓
merge into main
      ↓
push main
      ↓
production backup
      ↓
git pull --ff-only origin main
      ↓
database migration if required
      ↓
compile/import verification
      ↓
tests
      ↓
restart service
      ↓
local health check
      ↓
public health check
```

Do not run database-changing migrations without a backup.

---

# Production Verification

After deployment:

```bash
curl -fsS http://127.0.0.1/health
```

Expected:

```json
{
  "status": "ok"
}
```

Database:

```bash
curl -fsS http://127.0.0.1/health/database
```

Expected:

```json
{
  "status": "ok",
  "database": "connected"
}
```

Public:

```bash
curl -fsS https://ppis.thevirtualtrust.com/health
```

---

# Android Integration

The Android application should treat automatic telemetry as primary.

Recommended foreground synchronization:

```text
App opens
    ↓
Health Connect
    ↓
UsageStats
    ↓
Local calendar if enabled
    ↓
Backend integrations
    ↓
Upload telemetry
    ↓
Fetch backend analytics
    ↓
Render dashboard
```

The Android application normally synchronizes:

```text
today + previous 7 days
```

so missed days can be backfilled.

---

# Health Connect

Health Connect is the primary Android activity source.

Android uploads:

```text
steps
activity_minutes
source = health_connect
```

The backend protects Health Connect records from lower-priority Google Health synchronization.

---

# Google Health vs Health Connect

These integrations serve different purposes.

### Health Connect

```text
Android device → PPIS API
```

Primary source for local device telemetry.

### Google Health API

```text
Google cloud → PPIS backend
```

Optional cloud source.

Google Health does **not** replace Health Connect.

---

# Analytics Design Principle

The central PPIS rule is:

> Missing subjective data must not prevent analytics from working.

For example:

```text
Health Connect available
Screen Time available
Calendar available
DailyInput missing
```

must still produce useful productivity and stress analytics.

Likewise:

```text
Only Screen Time available
```

or:

```text
Only Activity available
```

can still produce partial analytics with appropriate coverage values.

---

# Security Principles

PPIS follows these rules:

- Never expose server OAuth client secrets to mobile clients.
- Never return Google refresh tokens to mobile clients.
- Never store plaintext passwords.
- Never store plaintext refresh tokens.
- Rotate PPIS refresh tokens.
- Revoke sessions after security-sensitive events.
- Keep authentication sessions server-side.
- Require role authorization for admin APIs.
- Record security-relevant actions in audit logs.
- Keep `.env` outside version control.

---

# API Summary

Major API groups:

```text
/
├── health
├── auth
│   ├── login
│   ├── google
│   ├── otp
│   ├── refresh
│   ├── sessions
│   ├── google/calendar
│   └── google/health
│
├── profile
├── daily-inputs
├── activity
├── screen-time
├── calendar
├── analytics
├── insights
├── feedback
│
└── api/admin
    ├── users
    ├── sessions
    ├── feedback
    └── observability
```

For the complete current contract, always use:

```text
https://ppis.thevirtualtrust.com/docs
```

or:

```text
https://ppis.thevirtualtrust.com/openapi.json
```

---

# PPIS

**Personal Pattern Intelligence System for Productivity and Well-being**

PPIS combines automatic digital and health telemetry with optional subjective information to create a unified, privacy-conscious view of personal productivity patterns and well-being.

The system is designed so that useful analytics remain available even when only part of the telemetry ecosystem is connected.