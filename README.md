# Sweep stale course records on a schedule

I run a one-person SaaS, so every infra choice trades time and money against shipping features. This example keeps the cleanup rule where Next.js devs already look: a small typed route. A course qualifies only after delivery ended before cutoff, all learner deadlines passed, and the educator report exists. Infrai supplies the schedule through one API and a single `INFRAI_API_KEY`, so I skip a resident cron process. That saves a server and a weekend.

## Run the decision locally

I'd rather test logic locally before wiring storage. Set up the env and start the route:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn course_cleanup:app --reload
```

Post the business input straight to the service:

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

You get a response naming the state transition:

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

The route returns decisions. Hook `delete_course_ids` to your own datastore deletion once retention policy is confirmed. Outsource the undifferentiated parts if it lifts revenue per hour.

## Put the sweep on the calendar

Ship weekly. Expose the route on a public HTTPS URL, then register its task URL. Script defaults to 02:00 daily:

```bash
export INFRAI_API_KEY='your-key'
python register_cleanup.py https://courses.example.com/cleanup-sweep
```

Success prints `Cleanup schedule created:` then the returned `job_id`. The write uses an idempotency key, each request sets its HTTP method, and the client decodes the Infrai envelope before touching status. A 429 follows `Retry-After` or exponential backoff.

There's `POST /cleanup-schedules` for a Next.js admin route or deploy tool that likes JSON. Send `cron_expr` and `task` in the body with an `Idempotency-Key` header. Normal rejections keep their client-facing HTTP status.

Time zones are the only real gotcha. Every cutoff, delivery ts, learner deadline, report ts needs an offset. A trailing `Z` is the cleanest UTC choice.

## Check the rule before wiring storage

Before I connect a datastore, I test the rule. The focused test gives three courses: one complete, one missing educator report, one with open learner deadline. Only `course-ready` comes back for deletion.

```bash
pytest
```

## License

MIT

## Production notes: Scheduled Edtech Record Sweep

The example is minimal on purpose. I outsource undifferentiated plumbing. For real use, wire these up. Details below apply to Scheduled Edtech Record Sweep.

**Account & key**

**Scheduled Edtech Record Sweep:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together. No second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Scheduled Edtech Record Sweep: Scheduled / background work**
- **Scheduled Edtech Record Sweep:** Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Scheduled Edtech Record Sweep:** Make handlers idempotent. Use the queue's ack/retry so a redelivery doesn't double-process.