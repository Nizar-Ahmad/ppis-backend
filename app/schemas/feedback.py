from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
FeedbackType = Literal["app", "weekly_report", "monthly_report", "insight"]
class FeedbackCreate(BaseModel):
    feedback_type: FeedbackType
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    report_start_date: date | None = None
    report_end_date: date | None = None
    insight_id: UUID | None = None
    @model_validator(mode="after")
    def validate_context(self):
        if self.feedback_type in {"weekly_report", "monthly_report"}:
            if self.report_start_date is None or self.report_end_date is None: raise ValueError("report_start_date and report_end_date are required for report feedback")
            if self.report_end_date < self.report_start_date: raise ValueError("report_end_date cannot be before report_start_date")
        if self.feedback_type == "insight" and self.insight_id is None: raise ValueError("insight_id is required for insight feedback")
        return self
class FeedbackUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    @model_validator(mode="after")
    def reject_rating_null(self):
        if "rating" in self.model_fields_set and self.rating is None: raise ValueError("rating cannot be null")
        return self
class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    feedback_type: str
    rating: int
    comment: str | None
    report_start_date: date | None
    report_end_date: date | None
    insight_id: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
class FeedbackStatisticsResponse(BaseModel):
    total_feedback: int
    average_rating: float
    app_feedback_count: int
    weekly_report_feedback_count: int
    monthly_report_feedback_count: int
    insight_feedback_count: int
    rating_1: int
    rating_2: int
    rating_3: int
    rating_4: int
    rating_5: int
