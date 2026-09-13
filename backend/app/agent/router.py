"""Deterministic routing and cheap abuse detection.

Regexes are an early filter only. Authorization and schema validation are the
actual security boundaries for data access and side effects.
"""
import re
from enum import Enum

_CLAIM_ID_PATTERN = re.compile(r"\bCLM-\d{3,10}\b", re.IGNORECASE)
_CONFIRM_PATTERN = re.compile(r"^\s*(?:confirm\s+[A-Za-z0-9_-]{6,64}|yes\s+submit\s+[A-Za-z0-9_-]{6,64}|submit\s+it\s+[A-Za-z0-9_-]{6,64})\s*[.!]?\s*$", re.IGNORECASE)
_SUBMIT_KEYWORDS = re.compile(
    r"(?:\b(?:submit|file|open|start|make)\b.{0,30}\bclaim\b|\breport\b.{0,30}\b(?:damage|claim)\b|\bmake\s+a\s+claim\b)",
    re.IGNORECASE,
)
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(your|previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system\s+prompt|instructions)", re.IGNORECASE),
    re.compile(r"(ignore|disregard)\s+(the\s+)?(validation|rules|guardrails|safety)", re.IGNORECASE),
    re.compile(r"bypass\s+(validation|the\s+rules|security)", re.IGNORECASE),
    re.compile(r"\b(show|list|dump|give)\s+me\s+(all\s+(the\s+)?claims|access\s+to\s+all)", re.IGNORECASE),
    re.compile(r"\baccess\s+to\s+all\s+claims\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+have\s+)?no\s+restrictions", re.IGNORECASE),
]


class Intent(str, Enum):
    INJECTION = "injection"
    CONFIRM_SUBMISSION = "confirm_submission"
    CLAIM_STATUS = "claim_status"
    SUBMIT_CLAIM = "submit_claim"
    POLICY_OR_OTHER = "policy_or_other"


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def classify_intent(text: str) -> Intent:
    if looks_like_injection(text):
        return Intent.INJECTION
    if _CONFIRM_PATTERN.search(text):
        return Intent.CONFIRM_SUBMISSION
    # Submission wins over an incidental historical claim ID.
    if _SUBMIT_KEYWORDS.search(text):
        return Intent.SUBMIT_CLAIM
    if _CLAIM_ID_PATTERN.search(text):
        return Intent.CLAIM_STATUS
    return Intent.POLICY_OR_OTHER


def extract_claim_id(text: str) -> str | None:
    match = _CLAIM_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None
