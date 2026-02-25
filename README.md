# Maritime Health Medical Care  
## Agentic Appointment Assistant  
**MBAN 5510 – Agentic AI Final Project**

An Agentic AI healthcare appointment assistant built with **LangGraph** demonstrating:

- Middleware-driven orchestration
- Risk-aware escalation logic
- Human-in-the-Loop (HITL) approval
- CLI + Web UI execution
- Transparent execution trace
- Safety and PII masking controls

---

## Project Objective

Design and implement an **agentic workflow system** capable of handling healthcare appointment requests while enforcing:

- Structured state transitions (LangGraph state machine)
- Safety escalation rules
- Human review checkpoints
- Verifiable execution evidence

---

## Supported Patient Intents

1. **Reschedule an appointment**
2. **Cancel an appointment**
3. **Request preparation instructions** (e.g., imaging / MRI prep)

---

## Agent Architecture

The workflow is built using a LangGraph state machine with conditional routing:

> `classify_intent → safety_check → info_check → handle_intent → draft → HITL → finalize`

 **Flow Diagram**

<img width="368" height="537" alt="image" src="https://github.com/user-attachments/assets/cd2f7f40-7c71-4485-9032-4163240ee662" />


=======
<img width="368" height="537" alt="image" src="https://github.com/user-attachments/assets/849d593f-cb17-4b3c-b331-dadcb744ca59" />

## Setup

### 1) Python
- Python **3.10+** recommended (3.11 works well)

### 2) Install dependencies
```bash
pip install -r requirements.txt
```



## Middleware Stack

Each node is wrapped with:

- **Call limit enforcement** (prevents runaway loops)
- **Retry logic** (handles transient failures)
- **PII masking logger** (prevents leaking identifiers in logs)

---

## Safety & Governance

- Emergency keyword detection (e.g., “chest pain”) routes to **ESCALATE**
- Closed terminal states:
  - `READY`
  - `NEED_INFO`
  - `ESCALATE`
- Human approval/edit before final client-facing response
- Full execution trace stored in `route_trace`

---

## CLI Usage

Run end-to-end in terminal:

```bash
python main.py

## CLI Outputs (required evidence):

run_id
terminal_status
route_trace
final_response

Web UI Usage
Start the server:
uvicorn web_app:app --reload --port 8010

Open in browser:

http://127.0.0.1:8010

Web flow includes:

Appointment ID intake

Insurance card intake

Request confirmation (Yes/No)

Slot availability simulation (reschedule)

Human-in-the-Loop review (prep instructions)

Interactive follow-up dialog (Yes → back to intake)

Example Scenarios
1 Reschedule

If time available → Success

If unavailable → suggest an alternative time slot

User accepts/declines → run completes

2 Cancel

Confirmation → immediate success message:

“Your appointment has been cancelled successfully… please book if needed.”

3 Preparation Instructions

Draft generated → HITL approve/edit

Follow-up message:

“Do you have any other request? Please take a good rest…”

Technologies Used

Python 3.11+

FastAPI

LangGraph

Pydantic

Jinja2

Middleware pattern

State machine orchestration

Execution Evidence Example
run_id: 2024-04-15T19:20:10Z_a1b2c3d4
terminal_status: READY
route_trace: classify_intent → safety_ok → info_complete → handle_intent → draft_generated → hitl_approve → finalize

Future Improvements

Replace rule-based intent classifier with an LLM router

Connect to a real scheduling API / database

Add authentication layer

Persistent state storage (Redis/SQLite)

Docker containerization


---



---
