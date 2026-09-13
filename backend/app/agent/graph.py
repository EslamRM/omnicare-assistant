"""
Graph shape (deliberately flat, per Section 6: a controlled workflow beats
an autonomous agent loop here — every path is exactly route -> one action -> END):

START -> route_node -> route_by_intent -> {
    injection_node,
    claim_status_node,
    confirm_submission_node,
    submit_claim_node,
    policy_node,
} -> END

There is no cycle in this graph, so a runaway loop is structurally
impossible. We still cap recursion_limit on invoke as defense-in-depth
(Section 19) in case the graph is extended later.
"""
from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    claim_status_node,
    confirm_submission_node,
    injection_node,
    policy_node,
    route_node,
    submit_claim_node,
)
from app.agent.router import Intent
from app.agent.state import AgentState


def _route_by_intent(state: AgentState) -> str:
    return state["intent"]


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("route", route_node)
    graph.add_node("injection", injection_node)
    graph.add_node("claim_status", claim_status_node)
    graph.add_node("confirm_submission", confirm_submission_node)
    graph.add_node("submit_claim", submit_claim_node)
    graph.add_node("policy", policy_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        _route_by_intent,
        {
            Intent.INJECTION.value: "injection",
            Intent.CONFIRM_SUBMISSION.value: "confirm_submission",
            Intent.CLAIM_STATUS.value: "claim_status",
            Intent.SUBMIT_CLAIM.value: "submit_claim",
            Intent.POLICY_OR_OTHER.value: "policy",
        },
    )
    graph.add_edge("injection", END)
    graph.add_edge("claim_status", END)
    graph.add_edge("confirm_submission", END)
    graph.add_edge("submit_claim", END)
    graph.add_edge("policy", END)

    return graph.compile()
