"""
Claim tools — the only code paths allowed to read/write mock_claims.json.

Design notes (Section 15 mental model: Tool Selection -> Schema Validation
-> Authorization -> Business Validation -> Tool Execution -> Result Validation):

- Schema validation happens in schemas/claims.py (Pydantic), before these
  functions are ever called.
- These functions assume their input is already a validated Pydantic model.
- A simple in-process lock guards the JSON file since this is a single-process
  prototype. Production evolution (Postgres unique constraint / transactional
  write) is documented in the README, not implemented here.
"""
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.schemas.claims import (
    ClaimStatusRequest,
    ClaimStatusResult,
    SubmitClaimRequest,
    SubmitClaimResult,
)

_lock = threading.Lock()


def _load_claims(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_claims(path: Path, claims: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def get_claim_status(request: ClaimStatusRequest) -> ClaimStatusResult:
    """Look up a claim by ID. Returns found=False rather than raising
    if the claim doesn't exist — this is an expected outcome, not an error."""
    settings = get_settings()
    with _lock:
        claims = _load_claims(settings.claims_db_path)

    for claim in claims:
        if claim.get("claim_id") == request.claim_id:
            return ClaimStatusResult(
                found=True,
                claim_id=claim["claim_id"],
                policy_number=claim.get("policy_number"),
                claim_type=claim.get("claim_type"),
                status=claim.get("status"),
                amount=claim.get("amount"),
            )

    return ClaimStatusResult(found=False, claim_id=request.claim_id)


def _generate_unique_claim_id(existing_ids: set[str]) -> str:
    """
    Generate a claim ID that doesn't collide with any existing claim.
    With a 90,000-value ID space this is astronomically unlikely to loop
    more than once or twice, but checking is cheap and the alternative —
    two claims silently sharing an ID, permanently orphaning one from
    get_claim_status lookups — is a real correctness bug, not a
    theoretical one.
    """
    for _ in range(1000):
        candidate = f"CLM-{uuid.uuid4().int % 90000 + 10000}"
        if candidate not in existing_ids:
            return candidate
    # If we somehow can't find a free ID after 1000 tries, the ID space
    # is effectively exhausted — fail loudly rather than risk a collision.
    raise RuntimeError("Unable to generate a unique claim ID; ID space may be exhausted")


def submit_claim(request: SubmitClaimRequest) -> SubmitClaimResult:
    """
    Append a new claim. Lightweight idempotency: if a claim with the exact
    same (policy_number, claim_type, amount, description) already exists,
    return the existing confirmation instead of creating a duplicate.

    This catches the "same request sent twice" case from Section 16. It is
    NOT a substitute for a real idempotency-key header in production — see
    README "Production Evolution" for how this would harden.
    """
    settings = get_settings()

    with _lock:
        claims = _load_claims(settings.claims_db_path)

        for claim in claims:
            if (
                claim.get("policy_number") == request.policy_number
                and claim.get("claim_type") == request.claim_type.value
                and str(claim.get("amount")) == str(request.amount)
                and claim.get("description") == request.description
            ):
                return SubmitClaimResult(
                    confirmation_id=claim["claim_id"],
                    claim_id=claim["claim_id"],
                    status=claim.get("status", "Submitted"),
                    duplicate=True,
                )

        existing_ids = {c["claim_id"] for c in claims if "claim_id" in c}
        new_claim_id = _generate_unique_claim_id(existing_ids)
        new_claim = {
            "claim_id": new_claim_id,
            "policy_number": request.policy_number,
            "claim_type": request.claim_type.value,
            "status": "Submitted",
            "amount": str(request.amount),
            "description": request.description,
        }
        claims.append(new_claim)
        _save_claims(settings.claims_db_path, claims)

        return SubmitClaimResult(
            confirmation_id=new_claim_id,
            claim_id=new_claim_id,
            status="Submitted",
            duplicate=False,
        )
