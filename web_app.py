from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from src.agent.graph import build_graph
from src.agent.state import AppointmentState, TerminalStatus
from src.agent.nodes import node_finalize
from urllib.parse import urlencode

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory run store (OK for class demo)
PENDING: Dict[str, AppointmentState] = {}

def new_run_id() -> str:
    return f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}_{uuid.uuid4().hex[:8]}"


def mask_id(value: Optional[str], keep: int = 3) -> str:
    """Mask IDs for UI display. Keep last N chars."""
    if not value:
        return ""
    v = value.strip()
    if len(v) <= keep:
        return "*" * len(v)
    return ("*" * (len(v) - keep)) + v[-keep:]


def extract_requested_timeslot(text: str) -> Optional[str]:
    """
    Very lightweight time extraction (demo-quality).
    Examples: '2pm', '2 pm', '14:00'
    """
    t = text.lower()
    m = re.search(r"\b(\d{1,2})\s*(:\s*\d{2})?\s*(am|pm)\b", t)
    if m:
        hour = m.group(1)
        mins = m.group(2) or ""
        ap = m.group(3)
        return f"{hour}{mins}{ap}"
    m2 = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", t)
    if m2:
        return m2.group(0)
    return None


def check_slot_availability(request_text: str) -> Tuple[bool, str]:
    """
    Demo availability check.
    Rule (simple and deterministic for grading):
    - If user requests 2pm (or 14:00), mark as unavailable.
    - Otherwise available.
    Returns (available, suggested_alternative)
    """
    slot = extract_requested_timeslot(request_text) or ""
    s = slot.replace(" ", "")
    unavailable = {"2pm", "2:00pm", "14:00"}
    if s in unavailable:
        return False, "3:00pm"
    return True, ""


def build_base_state(user_input: str, appointment_id: str, insurance_id: str) -> AppointmentState:
    return {
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
            "model_provider": "rules",
            "appointment_id": appointment_id or None,
            "insurance_id": insurance_id or None,
        },
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Optionally allow prefilling via query params
    appt = request.query_params.get("appointment_id", "")
    ins = request.query_params.get("insurance_id", "")
    req = request.query_params.get("user_input", "")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "appointment_id": appt, "insurance_id": ins, "user_input": req},
    )


@app.post("/intake", response_class=HTMLResponse)
def intake(
    request: Request,
    appointment_id: str = Form(""),
    insurance_id: str = Form(""),
    user_input: str = Form(""),
):
    appointment_id = (appointment_id or "").strip()
    insurance_id = (insurance_id or "").strip()
    user_input = (user_input or "").strip()

    if not appointment_id or not insurance_id:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "Please enter BOTH appointment ID and insurance card number.",
                "appointment_id": appointment_id,
                "insurance_id": insurance_id,
                "user_input": user_input,
            },
        )

    if not user_input:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "Please enter your request.",
                "appointment_id": appointment_id,
                "insurance_id": insurance_id,
                "user_input": user_input,
            },
        )

    state = build_base_state(user_input=user_input, appointment_id=appointment_id, insurance_id=insurance_id)
    PENDING[state["run_id"]] = state

    # Show confirm screen before running the agent
    return templates.TemplateResponse(
        "confirm.html",
        {
            "request": request,
            "run_id": state["run_id"],
            "appointment_id": appointment_id,
            "insurance_id": insurance_id,
            "masked_appt": mask_id(appointment_id),
            "masked_ins": mask_id(insurance_id),
            "user_input": user_input,
        },
    )


@app.post("/confirm", response_class=HTMLResponse)
def confirm(
    request: Request,
    run_id: str = Form(...),
    proceed: str = Form(...),  # "yes" or "no"
):
    state = PENDING.get(run_id)
    if not state:
        return RedirectResponse("/", status_code=303)

    appt = (state.get("meta", {}) or {}).get("appointment_id") or ""
    ins = (state.get("meta", {}) or {}).get("insurance_id") or ""
    user_input = state.get("user_input") or ""

    if proceed.lower() != "yes":
        # User said NO -> go back to intake with prefill
        PENDING.pop(run_id, None)
        url = f"/?appointment_id={appt}&insurance_id={ins}&user_input={user_input}"
        return RedirectResponse(url, status_code=303)

    # User said YES -> run the graph
    graph = build_graph(hitl_mode="pause")
    out = graph.invoke(state)

    # Early end: ESCALATE / NEED_INFO
    if out.get("terminal_status") in (TerminalStatus.NEED_INFO.value, TerminalStatus.ESCALATE.value):
        PENDING.pop(run_id, None)
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "state": out,
                "ended_early": True,
                "masked_appt": mask_id(appt),
                "masked_ins": mask_id(ins),
            },
        )

    intent = out.get("intent")

    # CANCEL: once confirmed YES -> immediate success message, no review needed
    if intent == "CANCEL":
        out["final_response"] = (
            "Your appointment has been cancelled successfully. "
            "If you have any other medical needs, please book an appointment."
        )
        out["terminal_status"] = TerminalStatus.READY.value
        out["route_trace"].append("cancel_confirmed")
        out = node_finalize(out)

        PENDING.pop(run_id, None)
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "state": out,
                "ended_early": False,
                "masked_appt": mask_id(appt),
                "masked_ins": mask_id(ins),
            },
        )

    # RESCHEDULE: check availability and branch
    if intent == "RESCHEDULE":
        # Show "checking..." message immediately via the slot page
        available, alternative = check_slot_availability(user_input)
        out["route_trace"].append("slot_checked")

        if available:
            out["final_response"] = "Your reschedule request has been completed successfully."
            out["terminal_status"] = TerminalStatus.READY.value
            out["route_trace"].append("reschedule_success")
            out = node_finalize(out)

            PENDING.pop(run_id, None)
            return templates.TemplateResponse(
                "result.html",
                {
                    "request": request,
                    "state": out,
                    "ended_early": False,
                    "masked_appt": mask_id(appt),
                    "masked_ins": mask_id(ins),
                },
            )

        # Not available: store and ask user to accept alternative
        out["meta"]["suggested_slot"] = alternative
        PENDING[run_id] = out
        return templates.TemplateResponse(
            "slot.html",
            {
                "request": request,
                "state": out,
                "masked_appt": mask_id(appt),
                "masked_ins": mask_id(ins),
                "requested": extract_requested_timeslot(user_input) or "your requested time",
                "alternative": alternative,
            },
        )

    # PREP_INFO: show draft for approve/edit (HITL)
    # Keep your existing review flow here.
    PENDING[run_id] = out
    return templates.TemplateResponse(
        "review.html",
        {"request": request, "state": out, "masked_appt": mask_id(appt), "masked_ins": mask_id(ins)},
    )


@app.post("/slot", response_class=HTMLResponse)
def slot_decision(
    request: Request,
    run_id: str = Form(...),
    accept: str = Form(...),  # "yes" / "no"
):
    state = PENDING.get(run_id)
    if not state:
        return RedirectResponse("/", status_code=303)

    appt = (state.get("meta", {}) or {}).get("appointment_id") or ""
    ins = (state.get("meta", {}) or {}).get("insurance_id") or ""
    alt = (state.get("meta", {}) or {}).get("suggested_slot") or ""

    if accept.lower() == "yes":
        state["final_response"] = f"Your reschedule request has been completed successfully for {alt}."
        state["terminal_status"] = TerminalStatus.READY.value
        state["route_trace"].append("reschedule_alt_accepted")
        state = node_finalize(state)
    else:
        state["final_response"] = (
            "No problem. If that time does not work, I suggest booking a new appointment "
            "for a time that better fits your schedule."
        )
        state["terminal_status"] = TerminalStatus.READY.value
        state["route_trace"].append("reschedule_alt_declined")
        state = node_finalize(state)

    PENDING.pop(run_id, None)
    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "state": state,
            "ended_early": False,
            "masked_appt": mask_id(appt),
            "masked_ins": mask_id(ins),
        },
    )


@app.post("/review", response_class=HTMLResponse)
def review(
    request: Request,
    run_id: str = Form(...),
    action: str = Form(...),
    edited_text: str = Form(""),
):
    state = PENDING.get(run_id)
    if not state:
        return RedirectResponse("/", status_code=303)

    draft = state.get("draft_response") or ""

    if action == "edit":
        final = (edited_text or "").strip() or draft
        state["final_response"] = final
        state["route_trace"].append("hitl_edit")
    else:
        state["final_response"] = draft
        state["route_trace"].append("hitl_approve")

    # Mark complete
    state["terminal_status"] = TerminalStatus.READY.value
    state["route_trace"].append("hitl_done")

    # Add PREP_INFO closing follow-up text
    if state.get("intent") == "PREP_INFO":
        state["final_response"] += (
            "\n\nDo you have any other request? "
            "Please take a good rest and wish you a smooth and pleasant medical check experience."
        )
        state["route_trace"].append("prep_followup_added")

    # Finalize (mirrors graph finalize)
    state = node_finalize(state)

    # Pop pending
    PENDING.pop(run_id, None)

    # For UI display
    appt = (state.get("meta") or {}).get("appointment_id", "")
    ins = (state.get("meta") or {}).get("insurance_id", "")

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "state": state,
            "ended_early": False,
            "masked_appt": mask_id(appt),
            "masked_ins": mask_id(ins),
        },
    )

@app.post("/followup", response_class=HTMLResponse)
def followup(
    request: Request,
    appointment_id: str = Form(""),
    insurance_id: str = Form(""),
    answer: str = Form(...),  # yes/no
):
    appointment_id = (appointment_id or "").strip()
    insurance_id = (insurance_id or "").strip()

    if answer.lower() == "yes":
        params = urlencode({"appointment_id": appointment_id, "insurance_id": insurance_id})
        return RedirectResponse(f"/?{params}", status_code=303)

    return templates.TemplateResponse(
        "thanks.html",
        {
            "request": request,
            "masked_appt": mask_id(appointment_id),
            "masked_ins": mask_id(insurance_id),
        },
    )