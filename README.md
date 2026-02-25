# Agentic Appointment Assistant (LangGraph + Middleware + HITL)

MBAN 5510 Final Project — Appointment-assistance system demonstrating **middleware-driven orchestration** using **LangGraph** with **safety controls** and a **Human-in-the-Loop (HITL)** review stage.

This repository provides a **CLI** that runs the system end-to-end and prints verifiable execution evidence:
- unique run id
- terminal status (closed set)
- route/path taken
- final client-facing response (after HITL)

---

## Features (Meets Minimum Requirements)

### Supported request types
- **Reschedule** an appointment
- **Cancel** an appointment
- **Request preparation instructions** (e.g., imaging prep)

### Safety & governance
- Risk-triggered escalation (e.g., emergency keywords) routes to **ESCALATE**
- PII masking in logs (simple patterns; extend as needed)
- Retry + call limits for model/tool calls (lightweight middleware)
- HITL: draft → human approve/edit → final output

### Required interface and outputs
- CLI entry point: `python main.py`
- Each run prints:
  - `run_id`
  - `terminal_status`: `READY | NEED_INFO | ESCALATE`
  - `route_trace`: concise node/route list
  - `final_response`

> Constraint: This system does **not** provide clinical advice. Emergency/risk cases instruct the user to seek immediate care.

---

## Project Structure

Final Project/
├─ main.py
├─ web_app.py
├─ requirements.txt
├─ .env.example
├─ src/
│  └─ agent/
│     ├─ __init__.py
│     ├─ graph.py
│     ├─ logging_utils.py
│     ├─ middleware.py
│     ├─ nodes.py
│     └─ state.py
├─ templates/
│  ├─ index.html
│  ├─ result.html
│  └─ review.html
├─ static/
│  └─ nshealth-logo.png
└─ tests/
   └─ test_smoke.py

## Setup

### 1) Python
- Python **3.10+** recommended (3.11 works well)

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Environment variables
Copy `.env.example` to `.env` and set values.

```bash
cp .env.example .env
```

**Important:** Do not commit secrets.

---

## Running the CLI (End-to-End)

```bash
python main.py
```

You’ll be prompted for a user request and then (when applicable) a HITL review decision.

### Example: normal reschedule
Input:
```
Reschedule my appointment ID 1234 to next Tuesday at 2pm
```

Output (example):
- Terminal status: `READY`
- Route trace: `START -> classify_intent -> safety_check -> info_check -> handle_intent -> draft -> hitl -> finalize -> END`
- Final response: confirmed reschedule message

### Example: escalation scenario
Input:
```
I have chest pain and need to cancel my appointment
```

Output:
- Terminal status: `ESCALATE`
- Route trace indicates escalation path
- Final response directs immediate emergency services

### Example: need-info scenario
Input:
```
Cancel my appointment
```

Output:
- Terminal status: `NEED_INFO`
- Final response requests missing appointment identifier

---

## How Human Review Works (HITL)

When the workflow produces a `draft_response`, it enters a **HITL** stage:
1. The draft is shown to the reviewer in the CLI
2. Reviewer chooses:
   - **Approve**: accept draft as final
   - **Edit**: provide replacement final text
3. The final output is stored in state as `final_response` and the run terminates with `READY`.

---

## Architecture & Design Decisions (High-Level)

### Middleware-driven orchestration
This project intentionally separates:
- **Workflow logic** (LangGraph nodes and routing)
- **Cross-cutting concerns** (middleware), applied uniformly across nodes:
  - PII masking in logs
  - call limits
  - retries
  - safety gating
  - HITL

Nodes are wrapped with a middleware pipeline in `src/agent/middleware.py` and assembled into a LangGraph state machine in `src/agent/graph.py`.

### Stateful workflow
A single `AppointmentState` object flows through the graph and accumulates:
- `intent`
- `missing_info`
- `draft_response` / `final_response`
- `terminal_status`
- `route_trace`
- `run_id`

State makes routing decisions transparent and produces verifiable evidence.

### Safety strategy
A safety node performs a lightweight risk check using keywords (configurable). If triggered:
- workflow sets `terminal_status=ESCALATE`
- generates an emergency-safe message
- short-circuits normal operations

This ensures risk cases do not proceed as normal.

---

## Tests

A minimal smoke test validates the graph compiles and can run a simple scenario.

```bash
pytest -q
```

---

## Demo (LinkedIn)
Add your LinkedIn demo URL here before submission:
- **LinkedIn demo:** <PASTE_LINK_HERE>

Your demo should show:
1) a normal scenario (reschedule/cancel/prep)
2) an escalation scenario
3) HITL approve/edit behavior

---

## Notes for Extension
- Replace the rule-based intent classifier with an LLM router.
- Add appointment “database” adapters (CSV/SQLite) using tool nodes.
- Expand PII masking patterns and safety checks.
- Add a lightweight web UI (optional).



## Web UI (Optional)

A minimal web interface is included to demo the same workflow with a browser-based Human-in-the-Loop review.

### Run the web server
```bash
pip install -r requirements.txt
uvicorn web_app:app --reload --port 8000
```

Then open:
- http://127.0.0.1:8000

### What the web UI demonstrates
- Normal request -> draft generated -> reviewer approve/edit -> READY + final response
- Risk request -> ESCALATE (ends early, no HITL)
- Missing info -> NEED_INFO (ends early, no HITL)
