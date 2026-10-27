from fastapi.testclient import TestClient

from bhashaflow_orchestrator.server import app

NOTEPAD_PLAN = [
    {
        "step": 1,
        "action": "hotkey",
        "params": {"keys": ["win", "r"]},
        "expected_outcome": "Open Run dialog",
    },
    {
        "step": 2,
        "action": "wait",
        "params": {"duration": 0.5},
        "expected_outcome": "Wait for UI",
    },
    {
        "step": 3,
        "action": "type_text",
        "params": {"text": "notepad"},
        "expected_outcome": "Type notepad",
    },
    {
        "step": 4,
        "action": "press_key",
        "params": {"key": "enter"},
        "expected_outcome": "Launch Notepad",
    },
]


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "mode": "standalone-mock",
        "agent": "BhashaFlow",
    }


def test_run_workflow_simulates_the_notepad_plan() -> None:
    with TestClient(app) as client:
        response = client.post("/api/run-workflow", json={"command": "open notepad"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "simulated"
    assert body["plan"]["thought_process"] == "Processing user voice intent: open notepad"
    assert body["plan"]["confirmation_speech"] == (
        "Workflow executed successfully on your desktop."
    )
    assert body["plan"]["execution_plan"] == NOTEPAD_PLAN


def test_run_workflow_execute_os_stays_in_process(monkeypatch) -> None:
    def fail_run(*_args, **_kwargs):
        raise AssertionError("workflow execution must not spawn a process")

    monkeypatch.setattr("subprocess.run", fail_run)
    with TestClient(app) as client:
        response = client.post(
            "/api/run-workflow",
            json={"command": "open notepad", "execute_os": True},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "executed"
    assert body["plan"]["execution_plan"] == NOTEPAD_PLAN


def test_run_workflow_requires_a_command() -> None:
    with TestClient(app) as client:
        response = client.post("/api/run-workflow", json={})
    assert response.status_code == 422


def test_root_message_when_ui_is_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        "bhashaflow_orchestrator.server.os.path.exists",
        lambda _path: False,
    )
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "BhashaFlow Server is running. Place UI files in /ui folder."
    }


def test_root_serves_ui_index(monkeypatch, tmp_path) -> None:
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<p>bhashaflow</p>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "bhashaflow" in response.text
