from src.agent.graph import build_graph


def test_graph_runs_noninteractive():
    app = build_graph()
    state = {
        "run_id": "test_run",
        "user_input": "Cancel appointment ID 1234",
        "intent": None,
        "risk_flag": False,
        "missing_info": [],
        "draft_response": None,
        "final_response": None,
        "terminal_status": None,
        "route_trace": [],
        "meta": {"model_provider": "rules", "non_interactive": True},
    }

    out = app.invoke(state)
    assert out["terminal_status"] in {"READY", "NEED_INFO", "ESCALATE"}
    assert "final_response" in out and out["final_response"]
    assert out["route_trace"]
