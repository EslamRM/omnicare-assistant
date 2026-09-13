from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.agent.router import classify_intent, Intent
client = TestClient(app)

def test_submit_intent_wins_when_message_mentions_old_claim_id():
    assert classify_intent("My old claim CLM-8821 was approved; I want to submit a new claim.") == Intent.SUBMIT_CLAIM

def test_user_cannot_access_another_users_claim(isolated_claims_file, auth_headers):
    r=client.post("/api/v1/chat",headers=auth_headers, json={"user_id":"usr_123","message":"What is the status of CLM-9014?"})
    assert "not authorized" in r.json()["response"].lower()

def test_user_cannot_submit_for_unowned_policy(isolated_claims_file, auth_headers):
    extraction={"policy_number":"POL-3341","claim_type":"Personal Property","amount":"1200","description":"Furniture was damaged during a sudden covered event."}
    with patch("app.agent.nodes.complete_json",return_value=extraction):
        r=client.post("/api/v1/chat",headers=auth_headers, json={"user_id":"usr_123","message":"I want to submit a claim for POL-3341"})
    assert "not authorized" in r.json()["response"].lower()

def test_claim_requires_confirmation_before_side_effect(isolated_claims_file, auth_headers):
    extraction={"policy_number":"POL-1092","claim_type":"Water Damage","amount":"3500","description":"A pipe burst and damaged my kitchen cabinets."}
    with patch("app.agent.nodes.complete_json",return_value=extraction):
        draft=client.post("/api/v1/chat",headers=auth_headers, json={"user_id":"usr_123","message":"I want to submit a claim"}).json()
    assert "prepared this claim" in draft["response"].lower()
    assert draft["tool_calls"] == []
    import re
    token = re.search(r"confirm ([A-Za-z0-9_-]+)", draft["response"]).group(1)
    confirmed=client.post("/api/v1/chat",headers=auth_headers, json={"user_id":"usr_123","message":f"confirm {token}"}).json()
    assert "confirmation id" in confirmed["response"].lower()

def test_confirmation_requires_token_and_exact_phrase(isolated_claims_file):
    assert classify_intent("Can you confirm the deductible?") != Intent.CONFIRM_SUBMISSION


def test_confirmation_with_token_routes_to_confirmation():
    from app.agent.router import Intent, classify_intent
    assert classify_intent("confirm Rqv_PAZr3JQ") == Intent.CONFIRM_SUBMISSION


def test_confirmation_token_rejects_arbitrary_long_phrase():
    from app.agent.router import Intent, classify_intent
    assert classify_intent("confirm the deductible for this claim") != Intent.CONFIRM_SUBMISSION
