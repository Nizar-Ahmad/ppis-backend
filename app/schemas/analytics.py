from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class DailyScoreResponse(BaseModel):
    id: UUID
    entry_date: date
    productivity_score: int
    stress_index: int
    sleep_score: int
    meeting_load_score: int
    distraction_score: int
    activity_score: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class WeeklyAnalyticsResponse(BaseModel):
    start_date: date
    end_date: date
    days_analyzed: int
    average_sleep_hours: float
    average_mood: float
    average_energy_level: float
    total_focused_work_hours: float
    total_meeting_minutes: int
    total_screen_minutes: int
    average_productivity_score: float
    average_stress_index: float
    best_day: date | None
    worst_day: date | None
class InsightResponse(BaseModel):
    id: UUID
    start_date: date
    end_date: date
    insight_type: str
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class MonthlyAnalyticsResponse(BaseModel):
    year: int
    month: int
    start_date: date
    end_date: date
    days_analyzed: int
    average_sleep_hours: float
    average_mood: float
    average_energy_level: float
    total_focused_work_hours: float
    total_meeting_minutes: int
    total_screen_minutes: int
    average_productivity_score: float
    average_stress_index: float
    best_day: date | None
    worst_day: date | None
