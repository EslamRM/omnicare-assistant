import json

import pytest
from pydantic import ValidationError

from app.schemas.claims import ClaimStatusRequest, ClaimType, SubmitClaimRequest
from app.tools.claims import get_claim_status, submit_claim


# --- get_claim_status ---

def test_get_claim_status_existing_claim(isolated_claims_file):
    result = get_claim_status(ClaimStatusRequest(claim_id="CLM-8821"))
    assert result.found is True
    assert result.status == "Approved"
    assert result.amount == 3500.00
    assert result.policy_number == "POL-1092"


def test_get_claim_status_missing_claim(isolated_claims_file):
    result = get_claim_status(ClaimStatusRequest(claim_id="CLM-0000"))
    assert result.found is False
    assert result.claim_id == "CLM-0000"


def test_get_claim_status_malformed_id_rejected():
    with pytest.raises(ValidationError):
        ClaimStatusRequest(claim_id="not-a-claim-id")


# --- submit_claim ---

def test_submit_claim_valid(isolated_claims_file):
    req = SubmitClaimRequest(
        policy_number="POL-1092",
        claim_type=ClaimType.WATER_DAMAGE,
        amount=3500.0,
        description="A pipe leaked and damaged my kitchen ceiling.",
    )
    result = submit_claim(req)
    assert result.claim_id.startswith("CLM-")
    assert result.confirmation_id == result.claim_id
    assert result.status == "Submitted"
    assert result.duplicate is False

    # Verify it was actually persisted
    data = json.loads(isolated_claims_file.read_text())
    assert any(c["claim_id"] == result.claim_id for c in data)


def test_submit_claim_invalid_amount_zero_rejected():
    with pytest.raises(ValidationError):
        SubmitClaimRequest(
            policy_number="POL-1092",
            claim_type=ClaimType.WATER_DAMAGE,
            amount=0,
            description="Zero amount claim should fail validation.",
        )


def test_submit_claim_invalid_amount_too_large_rejected():
    """Guards against the 'submit a claim for $1,000,000' abuse scenario."""
    with pytest.raises(ValidationError):
        SubmitClaimRequest(
            policy_number="POL-1092",
            claim_type=ClaimType.WATER_DAMAGE,
            amount=1_000_000,
            description="This should be rejected by business validation.",
        )


def test_submit_claim_invalid_claim_type_rejected():
    with pytest.raises(ValidationError):
        SubmitClaimRequest(
            policy_number="POL-1092",
            claim_type="Alien Abduction",  # not in the ClaimType enum
            amount=500,
            description="Invalid claim type should be rejected.",
        )


def test_extraction_handles_non_string_policy_number_without_crashing(isolated_claims_file):
    """Regression test: if the LLM's JSON-mode extraction returns
    policy_number as a number instead of a string (plausible LLM output
    drift), the node must not crash with AttributeError on .strip()."""
    from unittest.mock import patch
    from app.agent.nodes import submit_claim_node

    mock_extraction = {
        "policy_number": 1092,  # int, not "POL-1092" string
        "claim_type": "Water Damage",
        "amount": 500,
        "description": "Testing non-string policy number extraction handling.",
    }
    with patch("app.agent.nodes.complete_json", return_value=mock_extraction):
        result = submit_claim_node({"user_id": "usr_123", "message": "submit a claim"})

    # Should not crash; should produce a controlled validation response
    # since "1092" doesn't match the POL-\d+ pattern once stringified.
    assert "response" in result
    assert result.get("tool_calls", []) == []


def test_extraction_normalizes_claim_type_case_and_whitespace(isolated_claims_file):
    """Regression test: 'water damage' (wrong case) or padded whitespace
    from the LLM should still validate, not fail on a cosmetic mismatch."""
    from unittest.mock import patch
    from app.agent.nodes import submit_claim_node

    mock_extraction = {
        "policy_number": "pol-1092",  # lowercase, should be uppercased
        "claim_type": "  water damage  ",  # wrong case + padding
        "amount": "1200",
        "description": "Testing case-insensitive claim type normalization.",
    }
    with patch("app.agent.nodes.complete_json", return_value=mock_extraction):
        result = submit_claim_node({"user_id": "usr_123", "message": "submit a claim"})

    assert "confirm " in result["response"].lower()
    assert result.get("tool_calls", []) == []


def test_submit_claim_malformed_policy_number_rejected():
    with pytest.raises(ValidationError):
        SubmitClaimRequest(
            policy_number="not-a-policy",
            claim_type=ClaimType.WATER_DAMAGE,
            amount=500,
            description="Malformed policy number should be rejected.",
        )


def test_submit_claim_description_too_short_rejected():
    with pytest.raises(ValidationError):
        SubmitClaimRequest(
            policy_number="POL-1092",
            claim_type=ClaimType.WATER_DAMAGE,
            amount=500,
            description="short",
        )


def test_submit_claim_duplicate_is_deduplicated(isolated_claims_file):
    req = SubmitClaimRequest(
        policy_number="POL-1092",
        claim_type=ClaimType.WATER_DAMAGE,
        amount=2000.0,
        description="Kitchen fire damaged the cabinets and countertop.",
    )
    first = submit_claim(req)
    second = submit_claim(req)  # identical resubmission

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.claim_id == first.claim_id

    # Only one new claim should have been persisted, not two
    data = json.loads(isolated_claims_file.read_text())
    matching = [c for c in data if c["claim_id"] == first.claim_id]
    assert len(matching) == 1


def test_generate_unique_claim_id_avoids_collision(monkeypatch):
    """Regression test for the claim-ID collision bug: force uuid4() to
    produce the same candidate ID twice before a free one, and verify the
    retry loop in _generate_unique_claim_id actually retries instead of
    returning a colliding ID."""
    from app.tools import claims as claims_module

    existing_ids = {"CLM-99999"}  # a previously "generated" 5-digit ID
    sequence = iter([99999, 99999, 12345])  # first two collide, third is free

    class FakeUUID:
        def __init__(self, int_val):
            self.int = int_val

    def fake_uuid4():
        target = next(sequence)
        # real code computes: uuid4().int % 90000 + 10000 == target
        # so we just need .int == (target - 10000), since that's < 90000
        return FakeUUID(target - 10000)

    monkeypatch.setattr(claims_module.uuid, "uuid4", fake_uuid4)

    result = claims_module._generate_unique_claim_id(existing_ids)

    assert result == "CLM-12345"
    assert result not in existing_ids


def test_submit_claim_generated_ids_never_collide_in_practice(isolated_claims_file):
    """Sanity check under normal (non-mocked) conditions: submitting many
    distinct claims never produces a duplicate claim_id in storage."""
    for i in range(20):
        req = SubmitClaimRequest(
            policy_number="POL-1092",
            claim_type=ClaimType.WATER_DAMAGE,
            amount=100.0 + i,
            description=f"Distinct test claim number {i} for collision check.",
        )
        submit_claim(req)

    data = json.loads(isolated_claims_file.read_text())
    ids = [c["claim_id"] for c in data]
    assert len(ids) == len(set(ids)), "duplicate claim_id detected in storage"
