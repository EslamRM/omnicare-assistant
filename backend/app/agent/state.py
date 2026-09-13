"""Shared state passed between LangGraph nodes."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_id: str
    message: str

    intent: str

    response: str
    sources: list[str]
    tool_calls: list[dict]
