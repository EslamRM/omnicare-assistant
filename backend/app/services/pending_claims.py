"""Short-lived, per-user pending claim store for explicit confirmation.

This is intentionally in-memory for the assessment prototype. Production should
replace it with a durable store (e.g. Redis) keyed by user/session + token.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import threading

from app.schemas.claims import SubmitClaimRequest

_TTL = timedelta(minutes=10)
_lock = threading.Lock()
_pending: dict[tuple[str, str], "PendingClaim"] = {}


@dataclass(frozen=True)
class PendingClaim:
    request: SubmitClaimRequest
    created_at: datetime
    expires_at: datetime


def put(user_id: str, request: SubmitClaimRequest) -> str:
    token = secrets.token_urlsafe(8)
    now = datetime.now(timezone.utc)
    with _lock:
        _pending[(user_id, token)] = PendingClaim(request, now, now + _TTL)
    return token


def pop(user_id: str, token: str) -> SubmitClaimRequest | None:
    now = datetime.now(timezone.utc)
    with _lock:
        item = _pending.pop((user_id, token), None)
    if item is None or item.expires_at <= now:
        return None
    return item.request
