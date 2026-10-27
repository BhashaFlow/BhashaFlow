"""Desktop primitives. Off unless ``BHASHAFLOW_ACTIONS=desktop``.

The runner is injectable. CI uses the fixture engine and never starts this
one. A real process still cannot leave the demo allowlist: refused apps are
returned before the runner is called.
"""

import os
import platform
import shutil
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
        command = (
            "if (-not ('BhashaFlow.BhashaInput' -as [type])) { "
            "Add-Type -MemberDefinition '"
            '[DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); '
            '[DllImport("user32.dll")] public static extern void mouse_event('
            "uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);' "
            "-Name BhashaInput -Namespace BhashaFlow | Out-Null }; "
            f"[BhashaFlow.BhashaInput]::SetCursorPos({int(x)}, {int(y)}); "
            "[BhashaFlow.BhashaInput]::mouse_event(2,0,0,0,0); "
            "[BhashaFlow.BhashaInput]::mouse_event(4,0,0,0,0)"
        )
        return ["powershell", "-NoProfile", "-Command", command]
    return ["xdotool", "mousemove", str(x), str(y), "click", "1"]


def _type_argv(text: str) -> list[str]:
    if platform.system() == "Darwin":
        safe = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{safe}"'
        return ["osascript", "-e", script]
    if platform.system() == "Windows":
        command = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.SendKeys]::SendWait(" + _powershell_single(_sendkeys(text)) + ")"
        )
        return ["powershell", "-NoProfile", "-Command", command]
    return ["xdotool", "type", "--", text]


def _sendkeys(text: str) -> str:
    specials = set("+^%~{}()")
    return "".join("{" + char + "}" if char in specials else char for char in text)


def _powershell_single(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def action_runtime_status() -> tuple[bool, str]:
    """Check that the OS helper exists. This does not click or grant permission."""
    system = platform.system()
    if system == "Linux":
        missing = [name for name in ("xdotool", "xdg-open") if shutil.which(name) is None]
        if missing:
            needed = " and ".join(missing)
            return False, (
                f"Linux desktop actions need {needed} on PATH. Install them and grant "
                "input access (AT-SPI or X11). This check does not click; a missing "
                "permission shows up as a failed action, which is retried once."
            )
        return True, (
            "xdotool and xdg-open are on PATH. Input permission is not proven until "
            "the first click."
        )
    if system == "Darwin":
        if shutil.which("osascript") is None:
            return False, (
                "macOS desktop actions need osascript. Grant Accessibility to the "
                "process that runs bhashaflow."
            )
        return True, (
            "osascript is on PATH. Grant Accessibility in System Settings. This probe "
            "does not click."
        )
    if system == "Windows":
        if shutil.which("powershell") is None:
            return False, (
                "Windows desktop actions need powershell. Allow this process to inject input."
            )
        return True, ("powershell is on PATH. Allow UI input. This probe does not click.")
    return False, (
        f"Desktop actions are not implemented for {system}. "
        "Use uv run bhashaflow-demo for the fixture rehearsal."
    )


def _subprocess_runner(argv: list[str]) -> int:
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return 124
    except FileNotFoundError:
        return 127
    return completed.returncode
