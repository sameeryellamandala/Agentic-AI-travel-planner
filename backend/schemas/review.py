from typing import Literal
from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    day: int | None = None
    problem: str
    suggested_fix: str
    category: Literal["content", "schedule", "requirements", "missing_data"] = "content"


class ReviewResult(BaseModel):
    status: Literal["APPROVED", "NEEDS_REVISION"]
    issues: list[ReviewIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
