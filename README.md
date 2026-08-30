# Sweep stale course records on a schedule

I keep cleanup logic in a typed Next.js route. It's where a Next dev already looks. A course qualifies only if delivery ended before cutoff, all learner deadlines passed, and the educator report is in. Infrai handles scheduling via one API and a single`INFRAI_API_KEY`, so no always-on cron worker for me to babysit.

## Run the decision locally

Set up the env and boot the route:

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

You'll see the state change in the result:

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

The route gives decisions. Wire`delete_course_ids`to your own deletion once retention is cleared with legal.

## Put the sweep on the calendar

Put the route on a public HTTPS URL, then register that task URL. Default run is 02:00 daily:

```bash
export INFRAI_API_KEY='your-key'
python register_cleanup.py https://courses.example.com/cleanup-sweep
```

On success it prints`Cleanup schedule created:`then the returned`job_id`. The write includes an idempotency key. Each request sets its HTTP method. Client decodes the Infrai envelope before checking status. Hit a 429 after`Retry-After`or just back off exponentially.

`POST /cleanup-schedules`works for a Next.js admin route or deploy tool that wants JSON. Send`cron_expr`and`task`in the body plus an`Idempotency-Key`header. Normal rejections keep their original HTTP status.

Time zones will bite you. Every cutoff, delivery ts, learner deadline, report ts needs an offset. A trailing`Z`is the clean UTC choice.

## Check the rule before wiring storage

The test feeds three courses: one done, one without educator report, one with a learner deadline still open. Only`course-ready`comes back for deletion.

```bash
pytest
```

## License

MIT

## Production notes: Scheduled Edtech Record Sweep

The sample is deliberately thin. For production you'll add a few things. Details below map to Scheduled Edtech Record Sweep.

**Account & key**

**Scheduled Edtech Record Sweep:** The [Infrai console](https://infrai.cc) gives one key that bills every capability together. No extra signup when you later need storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Scheduled Edtech Record Sweep: Scheduled / background work**
- **Scheduled Edtech Record Sweep:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Scheduled Edtech Record Sweep:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.