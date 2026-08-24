"""Register the hosted cleanup sweep from the command line."""

import argparse
import uuid

from infrai import cron


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_url", help="Public HTTPS URL for POST /cleanup-sweep")
    parser.add_argument("--cron", default="0 2 * * *", dest="cron_expr")
    args = parser.parse_args()
    result = cron.create(
        cron_expr=args.cron_expr,
        task=args.task_url,
        idempotency_key=f"edtech-cleanup-{uuid.uuid4()}",
    )
    print(f"Cleanup schedule created: {result['job_id']}")


if __name__ == "__main__":
    main()
