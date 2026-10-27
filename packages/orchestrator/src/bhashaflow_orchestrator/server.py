"""Local orchestrator UI server.

Health and workflow routes run without a model API key. The workflow plan is
the canned notepad script from the standalone server. ``execute_os`` accepts
that plan in-process and does not inject keys or move the pointer.
Allowlisted desktop actions stay in ``bhashaflow_action``.
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="BhashaFlow Core Server")


class CommandRequest(BaseModel):
    command: str
    execute_os: bool = False


def _notepad_plan(command: str) -> dict[str, object]:
    """Deterministic plan. The command is recorded and not parsed."""
    return {
        "thought_process": f"Processing user voice intent: {command}",
        "execution_plan": [
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
        ],
        "confirmation_speech": "Workflow executed successfully on your desktop.",
    }


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "online", "mode": "standalone-mock", "agent": "BhashaFlow"}


@app.post("/api/run-workflow")
def run_workflow(req: CommandRequest) -> dict[str, object]:
    """Return the canned plan. ``execute_os`` does not touch the desktop."""
    plan = _notepad_plan(req.command)
    if req.execute_os:
        return {"status": "executed", "plan": plan}
    return {"status": "simulated", "plan": plan}


if os.path.exists("ui"):
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")


@app.get("/", response_model=None)
def root() -> FileResponse | dict[str, str]:
    if os.path.exists("ui/index.html"):
        return FileResponse("ui/index.html")
    return {"message": "BhashaFlow Server is running. Place UI files in /ui folder."}


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)
