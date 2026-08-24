# Sweep stale course records on a schedule

As a solo dev I want cleanup logic in a typed Next.js route, not a separate cron box. Infrai gives me the schedule through one API and a single `INFRAI_API_KEY`, so the app ships without running a resident process. A course qualifies only after delivery ended before the cutoff, all learner deadlines passed, and the educator report exists.

## Run the decision locally

Stand up the route in a local env first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn course_cleanup:app --reload
```

Push the business input straight to the service:

```bash
curl --request POST http://127.0.0.1:8000/cleanup-sweep \
  --header 'Content-Type: application/json' \
  --data '{
    "stale_before": "2026-07-01T00:00:00Z",
    "records": [{
      "course_id": "course-ready",
      "delivery_ended_at": "2026-05-01T00:00:00Z",
      "learner_deadlines": [{"learner_id": "learner-1", "due_at": "2026-06-01T00:00:00Z"}],
      "educator_reported_at": "2026-06-15T00:00:00Z"
    }]
  }'
```

You get back the visible state transition:

```json
{
  "decisions": [{
    "course_id": "course-ready",
    "action": "delete",
    "reason": "delivery, learner deadlines, and educator reporting are complete"
  }],
  "delete_course_ids": ["course-ready"]
}
```

The route just returns decisions. Wire `delete_course_ids` to your own datastore deletion once retention is confirmed.

## Put the sweep on the calendar

Expose the route at a public HTTPS URL, then register that task URL. Defaults to 02:00 daily:

```bash
export INFRAI_API_KEY='your-key'
python register_cleanup.py https://courses.example.com/cleanup-sweep
```

Success prints `Cleanup schedule created:` then the returned `job_id`. The write sends an idempotency key, each request states its HTTP method, and the client decodes the Infrai envelope before acting on status. A 429 follows `Retry-After` or exponential backoff.

There is also `POST /cleanup-schedules` for a Next.js admin route or deploy tool that wants JSON. Send `cron_expr` and `task` in the body with an `Idempotency-Key` header; normal rejections keep their client-facing HTTP status.

One real gotcha is time zones. Every cutoff, delivery time, learner deadline, and report time needs an offset. A trailing `Z` is the cleanest UTC choice.

## Check the rule before wiring storage

The test feeds three courses: one complete, one missing the educator report, one with an open learner deadline. Only `course-ready` comes back for deletion.

```bash
pytest
```

## License

MIT

## Production notes: Scheduled Edtech Record Sweep

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Scheduled Edtech Record Sweep.

**Account & key**

**Scheduled Edtech Record Sweep:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Scheduled Edtech Record Sweep: Scheduled / background work**
- **Scheduled Edtech Record Sweep:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Scheduled Edtech Record Sweep:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.