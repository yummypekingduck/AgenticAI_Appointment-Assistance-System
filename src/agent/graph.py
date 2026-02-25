from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import AppointmentState, TerminalStatus
from .middleware import (
    apply_middleware,
    CallLimitMiddleware,
    RetryMiddleware,
    PIIMaskingLogMiddleware,
)
from . import nodes


def build_graph(hitl_mode: str = "cli"):
    """
    Build and compile the LangGraph workflow with middleware-wrapped nodes.
    """
    # Middleware stack applied to (most) nodes
    middleware_stack = [
        CallLimitMiddleware(max_node_calls=50),
        RetryMiddleware(retries=1, backoff_s=0.2),
        PIIMaskingLogMiddleware(),
    ]

    graph = StateGraph(AppointmentState)

    # Wrap nodes with middleware
    graph.add_node("classify_intent", apply_middleware(nodes.node_classify_intent, middleware_stack))
    graph.add_node("safety_check", apply_middleware(nodes.node_safety_check, middleware_stack))
    graph.add_node("info_check", apply_middleware(nodes.node_check_missing_info, middleware_stack))
    graph.add_node("handle_intent", apply_middleware(nodes.node_handle_intent, middleware_stack))
    graph.add_node("draft", apply_middleware(nodes.node_generate_draft, middleware_stack))

    # HITL should still be protected by call limits & retry, but prints drafts. Keep it wrapped.
    graph.add_node("hitl", apply_middleware(nodes.node_human_review if hitl_mode=="cli" else nodes.node_hitl_pause, middleware_stack))
    graph.add_node("finalize", apply_middleware(nodes.node_finalize, middleware_stack))

    # Entry
    graph.set_entry_point("classify_intent")

    # Sequence
    graph.add_edge("classify_intent", "safety_check")

    # Conditional routing after safety:
    def route_after_safety(state: AppointmentState) -> str:
        if state.get("terminal_status") == TerminalStatus.ESCALATE.value:
            return END
        return "info_check"

    graph.add_conditional_edges("safety_check", route_after_safety, {"info_check": "info_check", END: END})

    # Conditional routing after info check:
    def route_after_info(state: AppointmentState) -> str:
        if state.get("terminal_status") == TerminalStatus.NEED_INFO.value:
            return END
        return "handle_intent"

    graph.add_conditional_edges("info_check", route_after_info, {"handle_intent": "handle_intent", END: END})

    graph.add_edge("handle_intent", "draft")
    graph.add_edge("draft", "hitl")

    def route_after_hitl(state: AppointmentState) -> str:
        # In web mode, pause after producing a draft and return control to the UI.
        if hitl_mode != "cli":
            return END
        return "finalize"

    graph.add_conditional_edges("hitl", route_after_hitl, {"finalize": "finalize", END: END})
    graph.add_edge("finalize", END)

    return graph.compile()
