from app.schemas.claims import SubmitClaimRequest

# Assessment-only ownership map. Production should load policy ownership from
# the authenticated user's authorization claims / policy database.
USER_POLICIES = {"usr_123": {"POL-1092"}, "usr_456": {"POL-3341"}}


def policies_for_user(user_id: str) -> set[str]:
    return set(USER_POLICIES.get(user_id, set()))


def owns_policy(user_id: str, policy_number: str) -> bool:
    return policy_number in USER_POLICIES.get(user_id, set())


def can_submit_claim(user_id: str, request: SubmitClaimRequest) -> bool:
    return owns_policy(user_id, request.policy_number)
