from __future__ import annotations
import re
from typing import List

from .state import AppointmentState, TerminalStatus


# ==============================
# Intent Classification
# ==============================

def node_classify_intent(state: AppointmentState) -> AppointmentState:
    text = state["user_input"].lower()

    if any(k in text for k in ["reschedule", "move my appointment", "change my appointment"]):
        state["intent"] = "RESCHEDULE"
    elif any(k in text for k in ["cancel", "call off"]):
        state["intent"] = "CANCEL"
    elif any(k in text for k in ["prep", "prepare", "preparation", "instructions"]):
        state["intent"] = "PREP_INFO"
    else:
        state["intent"] = "UNKNOWN"

    state["route_trace"].append("classify_intent")
    return state


# ==============================
# Safety / Escalation Check
# ==============================

def node_safety_check(state: AppointmentState) -> AppointmentState:
    text = state["user_input"].lower()

    emergency_keywords = [
        "chest pain",
        "shortness of breath",
        "difficulty breathing",
        "unconscious",
        "severe bleeding",
        "stroke",
        "suicidal",
        "kill myself",
        "overdose",
        "emergency",
    ]

    if any(k in text for k in emergency_keywords):
        state["risk_flag"] = True
        state["terminal_status"] = TerminalStatus.ESCALATE.value
        state["final_response"] = (
            "Your message suggests a potential emergency. "
            "Please call local emergency services immediately or go to the nearest emergency department. "
            "If possible, contact the clinic afterward to update your appointment."
        )
        state["route_trace"].append("safety_escalate")
    else:
        state["risk_flag"] = False
        state["route_trace"].append("safety_ok")

    return state


# ==============================
# Helper: Extract Appointment ID
# ==============================

def _extract_appointment_id(text: str) -> str | None:
    m = re.search(
        r"\b(?:appointment|appt)\s*(?:id)?\s*[:#]?\s*([A-Za-z0-9\-]{3,})\b",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    if re.search(r"\b(?:appointment|appt)\b", text, re.IGNORECASE):
        m2 = re.search(r"\b(\d{3,})\b", text)
        if m2:
            return m2.group(1)

    return None


# ==============================
# Missing Information Check
# ==============================

def node_check_missing_info(state: AppointmentState) -> AppointmentState:
    text = state["user_input"]
    missing: List[str] = []

    if state["intent"] in ("RESCHEDULE", "CANCEL"):
        appt_id = _extract_appointment_id(text) or state.get("meta", {}).get("appointment_id")
        if not appt_id:
            missing.append("appointment_id")

    state["missing_info"] = missing

    if missing:
        state["terminal_status"] = TerminalStatus.NEED_INFO.value

        if state["intent"] == "RESCHEDULE":
            state["final_response"] = (
                "I can help reschedule. Please provide your appointment ID "
                "(or confirmation number) and your preferred new date/time window."
            )
        elif state["intent"] == "CANCEL":
            state["final_response"] = (
                "I can help cancel. Please provide your appointment ID "
                "(or confirmation number)."
            )
        else:
            state["final_response"] = "Please provide more details so I can assist."

        state["route_trace"].append("need_info")
    else:
        state["route_trace"].append("info_complete")

    return state


# ==============================
# Intent Handler (Business Logic Stub)
# ==============================

def node_handle_intent(state: AppointmentState) -> AppointmentState:
    intent = state["intent"]

    state.setdefault("meta", {})
    state["meta"]["intent_payload"] = {}

    if intent == "RESCHEDULE":
        state["meta"]["intent_payload"] = {"action": "reschedule"}
    elif intent == "CANCEL":
        state["meta"]["intent_payload"] = {"action": "cancel"}
    elif intent == "PREP_INFO":
        state["meta"]["intent_payload"] = {"action": "prep_info"}
    else:
        state["meta"]["intent_payload"] = {"action": "unknown"}

    state["route_trace"].append("handle_intent")
    return state


# ==============================
# Draft Generation
# ==============================

def node_generate_draft(state: AppointmentState) -> AppointmentState:
    intent = state["intent"]

    if intent == "RESCHEDULE":
        state["draft_response"] = (
            "I can help with rescheduling. I’ve noted your request and will move "
            "the appointment to your requested window once confirmed."
        )
    elif intent == "CANCEL":
        state["draft_response"] = (
            "I can help cancel your appointment. I’ve recorded the cancellation request."
        )

    elif intent == "PREP_INFO":
        t = (state.get("user_input") or "").lower()
        if "mri" in t:
            state["draft_response"] = (
                "MRI preparation (general):\n"
                "- Tell the clinic if you have any implanted devices or metal in your body.\n"
                "- Remove metal objects (jewelry, watches, hairpins) before the scan.\n"
                "- You may be asked not to eat or drink for a few hours if contrast is used.\n"
                "- Let staff know if you are pregnant, have kidney disease, or feel claustrophobic.\n"
                "If you share whether contrast is planned and your appointment time, I can tailor the instructions."
            )
        elif "ct" in t or "cat scan" in t:
            state["draft_response"] = (
                "CT scan preparation (general):\n"
                "- You may be asked not to eat or drink for a few hours before the scan.\n"
                "- If contrast is used, tell the clinic about allergies (especially iodine/contrast) and kidney disease.\n"
                "- Wear comfortable clothing and remove metal items as instructed.\n"
                "If you share whether contrast is planned and your appointment time, I can tailor the instructions."
            )
        elif "ultrasound" in t or "sonogram" in t:
            state["draft_response"] = (
                "Ultrasound preparation (general):\n"
                "- Preparation depends on the body area being scanned.\n"
                "- For some pelvic ultrasounds, you may be asked to drink water and arrive with a full bladder.\n"
                "- For some abdominal ultrasounds, you may be asked to avoid eating for several hours.\n"
                "Tell me which body area is being scanned and your appointment time, and I’ll tailor the instructions."
            )
        else:
            state["draft_response"] = (
            "Preparation instructions depend on the procedure.\n"
            "Please tell me the procedure type (e.g., MRI, CT, ultrasound) and your appointment time, "
            "and I’ll draft the relevant preparation steps for review."
            )

    else:
        state["draft_response"] = (
            "I can assist with rescheduling, cancellation, or preparation instructions. "
            "Which would you like?"
        )

    state["route_trace"].append("draft_generated")
    return state


# ==============================
# CLI Human-in-the-Loop
# ==============================

def node_human_review(state: AppointmentState) -> AppointmentState:
    print("\n--- HUMAN REVIEW REQUIRED ---")
    print("Draft response:")
    print(state["draft_response"])
    print("")
    print("Options: [a]pprove  [e]dit")

    decision = input("Enter choice (a/e): ").strip().lower()

    if decision == "e":
        edited = input("Enter edited response: ").strip()
        state["final_response"] = edited if edited else state["draft_response"]
        state["route_trace"].append("hitl_edit")
    else:
        state["final_response"] = state["draft_response"]
        state["route_trace"].append("hitl_approve")

    state["terminal_status"] = TerminalStatus.READY.value
    state["route_trace"].append("hitl_completed")
    return state


# ==============================
# Web UI Pause Node
# ==============================

def node_hitl_pause(state: AppointmentState) -> AppointmentState:
    state["route_trace"].append("hitl_pause")
    return state


# ==============================
# Finalization
# ==============================

def node_finalize(state: AppointmentState) -> AppointmentState:
    if not state.get("terminal_status"):
        state["terminal_status"] = TerminalStatus.READY.value

    state["route_trace"].append("finalize")
    return state