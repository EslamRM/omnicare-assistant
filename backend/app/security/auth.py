"""Lightweight demo authentication for the assessment prototype.

This is intentionally small: demo users authenticate with a PIN and receive a
signed, short-lived session token. Authorization remains server-side in
authorization.py. A production system should replace this module with the
company's IdP/OIDC provider and durable sessions.
"""
import base64
import hashlib
import hmac
import json
import time

from app.core.config import get_settings

DEMO_USERS = {
    "usr_123": {"display_name": "Demo Customer 123", "pin": "1234"},
    "usr_456": {"display_name": "Demo Customer 456", "pin": "4567"},
}
TOKEN_TTL_SECONDS = 60 * 60


def _secret() -> bytes:
    return get_settings().auth_secret.encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def authenticate(user_id: str, pin: str) -> bool:
    user = DEMO_USERS.get(user_id)
    if not user:
        return False
    return hmac.compare_digest(str(user["pin"]), str(pin))


def create_session_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(encoded)}"


def verify_session_token(token: str) -> str | None:
    try:
        encoded, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(encoded), signature):
            return None
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        user_id = payload.get("sub")
        return user_id if user_id in DEMO_USERS else None
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def user_profile(user_id: str) -> dict:
    from app.security.authorization import policies_for_user

    user = DEMO_USERS[user_id]
    return {
        "user_id": user_id,
        "display_name": user["display_name"],
        "policies": sorted(policies_for_user(user_id)),
        "token_expires_in_seconds": TOKEN_TTL_SECONDS,
    }


def authenticated_user(authorization: str | None) -> str:
    """Return the authenticated user from an Authorization: Bearer header."""
    from fastapi import HTTPException, status

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user_id
