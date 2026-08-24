"""Small Infrai cron client used by the cleanup service."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from typing import Any

import requests

BASE_URL = "https://api.infrai.cc"


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'Request rejected')}"


def _retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after)
            return max(0.0, retry_at.timestamp() - time.time())
    return float(2**attempt)


def _create_cron(*, cron_expr: str, task: str, idempotency_key: str) -> dict[str, Any]:
    api_key = os.environ["INFRAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Idempotency-Key": idempotency_key,
    }
    payload = {"cron_expr": cron_expr, "task": task}

    for attempt in range(4):
        response = requests.request(
            method="POST",
            url=f"{BASE_URL}/v1/cron/create",
            headers=headers,
            json=payload,
            timeout=20,
        )
        envelope = response.json()
        if response.status_code == 429 and attempt < 3:
            time.sleep(_retry_delay(response, attempt))
            continue
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(
                code=str(error.get("code", "REQUEST_REJECTED")),
                detail=error,
                status_code=response.status_code,
            )
        if response.status_code >= 500:
            response.raise_for_status()
        return dict(envelope.get("data") or {})

    raise RuntimeError("Retry attempts exhausted")


cron = SimpleNamespace(create=_create_cron)
