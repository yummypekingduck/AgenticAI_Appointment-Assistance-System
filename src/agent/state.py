from __future__ import annotations

from enum import Enum
from typing import TypedDict, Optional, List, Dict, Any


class TerminalStatus(str, Enum):
    READY = "READY"
    NEED_INFO = "NEED_INFO"
    ESCALATE = "ESCALATE"


class AppointmentState(TypedDict):
    # Required evidence
    run_id: str
    route_trace: List[str]

    # Input
    user_input: str

    # Derived / workflow
    intent: Optional[str]
    risk_flag: bool
    missing_info: List[str]

    draft_response: Optional[str]
    final_response: Optional[str]
    terminal_status: Optional[str]

    # Misc
    meta: Dict[str, Any]
