"""Desktop primitives. Off unless ``BHASHAFLOW_ACTIONS=desktop``.

The runner is injectable. CI uses the fixture engine and never starts this
one. A real process still cannot leave the demo allowlist: refused apps are
returned before the runner is called.
"""

import os
import platform
import subprocess
from collections.abc import Callable

from bhashaflow_action.allowlist import DEMO_ALLOWLIST, MACOS_APP_NAMES
from bhashaflow_action.engine import ActionResult, FixtureActionEngine
from bhashaflow_vision.pointer import PointerTarget

Runner = Callable[[list[str]], int]


class DesktopActionEngine:
    """Map allowlisted primitives to OS commands. No unscoped control."""

    def __init__(self, runner: Runner) -> None:
        self._runner = runner
        self.front_app = ""

    def open_app(self, app: str) -> ActionResult:
        return self._run("open_app", app, "", _open_argv(app))

    def focus(self, app: str) -> ActionResult:
        return self._run("focus", app, "", _focus_argv(app))

    def click(self, target: PointerTarget) -> ActionResult:
        return self._run(
            "click",
            target.app,
            target.element_name,
            _click_argv(target.x, target.y),
            target_name=target.element_name,
        )

    def type_text(self, target: PointerTarget, text: str) -> ActionResult:
        from bhashaflow_action.engine import _reject_text

        rejected = _reject_text(text, target.app, target.element_name)
        if rejected is not None:
            return rejected
        return self._run(
            "type",
            target.app,
            text,
            _type_argv(text),
            target_name=target.element_name,
        )

    def _run(
        self,
        action: str,
        app: str,
        detail: str,
        argv: list[str] | None,
        *,
        target_name: str = "",
    ) -> ActionResult:
        if app not in DEMO_ALLOWLIST or argv is None:
            return ActionResult(
                ok=False,
                action=action,
                app=app,
                detail=detail or app,
                recoverable=False,
                reason="app not on demo allowlist",
                target_name=target_name,
            )
        code = self._runner(argv)
        if code != 0:
            return ActionResult(
                ok=False,
                action=action,
                app=app,
                detail=detail,
                recoverable=True,
                reason=f"desktop {action} failed",
                target_name=target_name,
            )
        if action in {"open_app", "focus", "click", "type"}:
            self.front_app = app
        return ActionResult(
            ok=True,
            action=action,
            app=app,
            detail=detail or app,
            recoverable=False,
            reason="",
            target_name=target_name,
        )


def actions_from_env(runner: Runner | None = None) -> FixtureActionEngine | DesktopActionEngine:
    """Fixture engine unless ``BHASHAFLOW_ACTIONS`` is exactly ``desktop``."""
    mode = os.environ.get("BHASHAFLOW_ACTIONS", "fixture").strip().casefold()
    if mode == "desktop":
        return DesktopActionEngine(_subprocess_runner if runner is None else runner)
    return FixtureActionEngine()


def _open_argv(app: str) -> list[str] | None:
    if app not in DEMO_ALLOWLIST:
        return None
    if platform.system() == "Darwin":
        return ["open", "-a", MACOS_APP_NAMES[app]]
    if platform.system() == "Windows":
        return ["cmd", "/c", "start", "", MACOS_APP_NAMES[app]]
    return ["xdg-open", app]


def _focus_argv(app: str) -> list[str] | None:
    if app not in DEMO_ALLOWLIST:
        return None
    if platform.system() == "Darwin":
        name = MACOS_APP_NAMES[app]
        script = f'tell application "{name}" to activate'
        return ["osascript", "-e", script]
    return _open_argv(app)


def _click_argv(x: int, y: int) -> list[str]:
    if platform.system() == "Darwin":
        script = f'tell application "System Events" to click at {{{x}, {y}}}'
        return ["osascript", "-e", script]
    if platform.system() == "Windows":
        # Best-effort cursor move. A full click needs a UI Automation helper.
        command = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y})"
        )
        return ["powershell", "-NoProfile", "-Command", command]
    return ["xdotool", "mousemove", str(x), str(y), "click", "1"]


def _type_argv(text: str) -> list[str]:
    if platform.system() == "Darwin":
        script = f'tell application "System Events" to keystroke "{text}"'
        return ["osascript", "-e", script]
    if platform.system() == "Windows":
        return ["powershell", "-NoProfile", "-Command", "Write-Output skipped"]
    return ["xdotool", "type", "--", text]


def _subprocess_runner(argv: list[str]) -> int:
    completed = subprocess.run(argv, check=False, capture_output=True)
    return completed.returncode
