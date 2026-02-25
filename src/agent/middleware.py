from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Protocol, TypeVar, Any
import time

from .state import AppointmentState
from .logging_utils import mask_pii

NodeFn = Callable[[AppointmentState], AppointmentState]
T = TypeVar("T")


class Middleware(Protocol):
    def __call__(self, fn: NodeFn) -> NodeFn: ...


@dataclass
class CallLimitMiddleware:
    """
    Prevent runaway executions by limiting node invocations per run.
    Tracks counts in state['meta'].
    """
    max_node_calls: int = 50

    def __call__(self, fn: NodeFn) -> NodeFn:
        def wrapped(state: AppointmentState) -> AppointmentState:
            meta = state.setdefault("meta", {})
            calls = int(meta.get("node_calls", 0)) + 1
            meta["node_calls"] = calls
            if calls > self.max_node_calls:
                # Hard stop: convert to escalation-safe behavior
                state["terminal_status"] = "ESCALATE"
                state["final_response"] = (
                    "I’m not able to safely complete that request right now. "
                    "Please contact the clinic directly for assistance."
                )
                state["route_trace"].append("call_limit_exceeded")
                return state
            return fn(state)
        return wrapped


@dataclass
class RetryMiddleware:
    """
    Simple retry for transient errors in a node function.
    """
    retries: int = 2
    backoff_s: float = 0.25

    def __call__(self, fn: NodeFn) -> NodeFn:
        def wrapped(state: AppointmentState) -> AppointmentState:
            last_err: Exception | None = None
            for i in range(self.retries + 1):
                try:
                    return fn(state)
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    time.sleep(self.backoff_s * (2**i))
            # If still failing, escalate safely
            state["terminal_status"] = "ESCALATE"
            state["final_response"] = (
                "Something went wrong while processing your request. "
                "Please contact the clinic directly."
            )
            state["route_trace"].append(f"node_error:{type(last_err).__name__}")
            return state
        return wrapped


@dataclass
class PIIMaskingLogMiddleware:
    """
    Ensures any debug strings stored in meta are masked.
    Note: we already mask printed outputs; this keeps stored debug safe too.
    """
    def __call__(self, fn: NodeFn) -> NodeFn:
        def wrapped(state: AppointmentState) -> AppointmentState:
            out = fn(state)
            meta = out.setdefault("meta", {})
            if "debug" in meta and isinstance(meta["debug"], str):
                meta["debug"] = mask_pii(meta["debug"])
            return out
        return wrapped


def apply_middleware(fn: NodeFn, middleware: List[Middleware]) -> NodeFn:
    """
    Compose middleware around a node function (like a web server middleware stack).
    The last middleware in the list is the innermost wrapper.
    """
    wrapped = fn
    for m in reversed(middleware):
        wrapped = m(wrapped)
    return wrapped
