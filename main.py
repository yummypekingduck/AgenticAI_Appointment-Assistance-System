import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

from src.agent.graph import build_graph
from src.agent.state import AppointmentState, TerminalStatus
from src.agent.logging_utils import safe_print_summary


def new_run_id() -> str:
    # ISO timestamp + short uuid for uniqueness
    return f"{datetime.utcnow().isoformat(timespec='seconds')}Z_{uuid.uuid4().hex[:8]}"


def main() -> None:
    load_dotenv()

    user_input = input("Enter request: ").strip()
    if not user_input:
        print("No input provided. Exiting.")
        return

    state: AppointmentState = {
        "run_id": new_run_id(),
        "user_input": user_input,
        "intent": None,
        "risk_flag": False,
        "missing_info": [],
        "draft_response": None,
        "final_response": None,
        "terminal_status": None,
        "route_trace": [],
        "meta": {
            "model_provider": os.getenv("MODEL_PROVIDER", "rules"),
        },
    }

    app = build_graph()
    # Invoke with the initial state
    final_state = app.invoke(state)

    # Required outputs (verifiable evidence)
    safe_print_summary(final_state)


if __name__ == "__main__":
    main()
