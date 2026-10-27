"""
BhashaFlow Main Orchestrator & Local UI Server.
Runs completely standalone (Mock Mode) without requiring Meta/Llama API keys.
"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from action_engine import OSActionEngine

app = FastAPI(title="BhashaFlow Core Server")
engine = OSActionEngine()

class CommandRequest(BaseModel):
    command: str
    execute_os: bool = False

@app.get("/api/health")
def health_check():
    return {"status": "online", "mode": "standalone-mock", "agent": "BhashaFlow"}

@app.post("/api/run-workflow")
def run_workflow(req: CommandRequest):
    # Pre-built deterministic workflow (works without external LLM)
    mock_plan = {
        "thought_process": f"Processing user voice intent: {req.command}",
        "execution_plan": [
            {"step": 1, "action": "hotkey", "params": {"keys": ["win", "r"]}, "expected_outcome": "Open Run dialog"},
            {"step": 2, "action": "wait", "params": {"duration": 0.5}, "expected_outcome": "Wait for UI"},
            {"step": 3, "action": "type_text", "params": {"text": "notepad"}, "expected_outcome": "Type notepad"},
            {"step": 4, "action": "press_key", "params": {"key": "enter"}, "expected_outcome": "Launch Notepad"}
        ],
        "confirmation_speech": "Workflow executed successfully on your desktop."
    }
    
    if req.execute_os:
        success = engine.execute_plan(mock_plan)
        return {"status": "executed" if success else "failed", "plan": mock_plan}
    
    return {"status": "simulated", "plan": mock_plan}

# Serve UI files
if os.path.exists("ui"):
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

@app.get("/")
def root():
    if os.path.exists("ui/index.html"):
        return FileResponse("ui/index.html")
    return {"message": "BhashaFlow Server is running. Place UI files in /ui folder."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
