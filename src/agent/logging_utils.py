from __future__ import annotations

import re
from typing import Any, Dict

from .state import AppointmentState


_APPT_ID_RE = re.compile(r"\b(?:appt|appointment)\s*(?:id)?\s*[:#]?\s*([A-Za-z0-9\-]{3,})\b", re.IGNORECASE)
_DIGIT_ID_RE = re.compile(r"\b\d{3,}\b")


def mask_pii(text: str) -> str:
    """
    Simple masking:
    - appointment id-like patterns
    - long digit sequences (>=3)
    Extend this for your context.
    """
    if not text:
        return text

    # mask appointment id tokens
    def repl_appt(m: re.Match) -> str:
        token = m.group(0)
        return token.replace(m.group(1), "***")

    text = _APPT_ID_RE.sub(repl_appt, text)

    # mask long digit sequences
    text = _DIGIT_ID_RE.sub("***", text)
    return text


def safe_print_summary(state: AppointmentState) -> None:
    """
    Prints the required run evidence, while masking sensitive tokens in displayed content.
    """
    run_id = state.get("run_id")
    terminal_status = state.get("terminal_status")
    route_trace = state.get("route_trace", [])
    final_response = state.get("final_response") or ""

    print("\n--- EXECUTION SUMMARY ---")
    print("run_id:", run_id)
    print("terminal_status:", terminal_status)
    print("route_trace:", " -> ".join(route_trace))
    print("\nfinal_response:")
    print(mask_pii(final_response))
