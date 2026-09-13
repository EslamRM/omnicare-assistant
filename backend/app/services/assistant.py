import logging

from app.agent.graph import build_graph
from app.core.config import get_settings

logger = logging.getLogger("omnicare.assistant")
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class AssistantService:
    def handle_message(self, user_id: str, message: str) -> dict:
        settings = get_settings()
        graph = _get_graph()
        final_state = graph.invoke(
            {"user_id": user_id, "message": message},
            config={"recursion_limit": settings.max_agent_steps},
        )
        # Tool traces are internal audit data; customer API exposes only the
        # response and citations. Logs/telemetry can capture tool events safely.
        internal_tools = final_state.get("tool_calls", [])
        if internal_tools:
            logger.info('{"event":"tool_trace","tools":%s}', [t.get("name") for t in internal_tools])
        return {
            "response": final_state.get("response", ""),
            "sources": final_state.get("sources", []),
            "tool_calls": [{"name": t.get("name", ""), "arguments": {}} for t in internal_tools],
        }
