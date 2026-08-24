"""HTTP service for deciding and scheduling stale course-record cleanup."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from infrai import InfraiError, cron


class LearnerDeadline(BaseModel):
    learner_id: str = Field(min_length=1)
    due_at: datetime


class CourseRecord(BaseModel):
    course_id: str = Field(min_length=1)
    delivery_ended_at: datetime
    learner_deadlines: list[LearnerDeadline] = Field(min_length=1)
    educator_reported_at: datetime | None = None

    @model_validator(mode="after")
    def require_timezone(self) -> "CourseRecord":
        timestamps = [self.delivery_ended_at, *(item.due_at for item in self.learner_deadlines)]
        if self.educator_reported_at is not None:
            timestamps.append(self.educator_reported_at)
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("All timestamps must include a timezone")
        return self


class CleanupSweepRequest(BaseModel):
    stale_before: datetime
    records: list[CourseRecord]


class CleanupDecision(BaseModel):
    course_id: str
    action: str
    reason: str


class CleanupSweepResult(BaseModel):
    decisions: list[CleanupDecision]
    delete_course_ids: list[str]


class CleanupScheduleRequest(BaseModel):
    cron_expr: str = Field(min_length=1)
    task: str = Field(pattern=r"^https://")


class CleanupScheduleResult(BaseModel):
    job_id: str


def decide_cleanup(request: CleanupSweepRequest) -> CleanupSweepResult:
    cutoff = request.stale_before
    if cutoff.tzinfo is None:
        raise ValueError("stale_before must include a timezone")

    decisions: list[CleanupDecision] = []
    delete_ids: list[str] = []
    for record in request.records:
        deadlines_passed = all(item.due_at < cutoff for item in record.learner_deadlines)
        delivery_stale = record.delivery_ended_at < cutoff
        report_complete = (
            record.educator_reported_at is not None
            and record.educator_reported_at <= datetime.now(timezone.utc)
        )
        should_delete = delivery_stale and deadlines_passed and report_complete
        if should_delete:
            action = "delete"
            reason = "delivery, learner deadlines, and educator reporting are complete"
            delete_ids.append(record.course_id)
        else:
            action = "keep"
            reason = "at least one delivery, deadline, or reporting obligation remains"
        decisions.append(CleanupDecision(course_id=record.course_id, action=action, reason=reason))

    return CleanupSweepResult(decisions=decisions, delete_course_ids=delete_ids)


app = FastAPI(title="Edtech cleanup sweep")


@app.post("/cleanup-sweep", response_model=CleanupSweepResult)
def cleanup_sweep(request: CleanupSweepRequest) -> CleanupSweepResult:
    return decide_cleanup(request)


@app.post("/cleanup-schedules", response_model=CleanupScheduleResult)
def create_cleanup_schedule(
    request: CleanupScheduleRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CleanupScheduleResult:
    try:
        created = cron.create(
            cron_expr=request.cron_expr,
            task=request.task,
            idempotency_key=idempotency_key,
        )
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail=error.detail) from error
    return CleanupScheduleResult(job_id=str(created["job_id"]))
