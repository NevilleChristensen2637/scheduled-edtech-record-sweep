from datetime import datetime

from course_cleanup import CleanupSweepRequest, decide_cleanup


def test_only_deletes_courses_after_deadlines_and_reporting_are_complete() -> None:
    request = CleanupSweepRequest.model_validate(
        {
            "stale_before": "2026-07-01T00:00:00Z",
            "records": [
                {
                    "course_id": "course-ready",
                    "delivery_ended_at": "2026-05-01T00:00:00Z",
                    "learner_deadlines": [
                        {"learner_id": "learner-1", "due_at": "2026-06-01T00:00:00Z"}
                    ],
                    "educator_reported_at": "2026-06-15T00:00:00Z",
                },
                {
                    "course_id": "course-awaiting-report",
                    "delivery_ended_at": "2026-05-01T00:00:00Z",
                    "learner_deadlines": [
                        {"learner_id": "learner-2", "due_at": "2026-06-01T00:00:00Z"}
                    ],
                    "educator_reported_at": None,
                },
                {
                    "course_id": "course-open-deadline",
                    "delivery_ended_at": "2026-05-01T00:00:00Z",
                    "learner_deadlines": [
                        {"learner_id": "learner-3", "due_at": "2026-07-15T00:00:00Z"}
                    ],
                    "educator_reported_at": "2026-06-15T00:00:00Z",
                },
            ],
        }
    )

    result = decide_cleanup(request)

    assert result.delete_course_ids == ["course-ready"]
    assert [(item.course_id, item.action) for item in result.decisions] == [
        ("course-ready", "delete"),
        ("course-awaiting-report", "keep"),
        ("course-open-deadline", "keep"),
    ]
    assert datetime.fromisoformat("2026-07-01T00:00:00+00:00") == request.stale_before
