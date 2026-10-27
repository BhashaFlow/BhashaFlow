"""Apps the demo is allowed to touch. Everything else is refused."""

# Logical names from the stage script, not a license to drive the whole desktop.
DEMO_ALLOWLIST = frozenset({"Files", "Preview", "Sheets", "Mail"})

# macOS application names for `open -a`. Files is Finder. Sheets is Numbers.
MACOS_APP_NAMES = {
    "Files": "Finder",
    "Preview": "Preview",
    "Sheets": "Numbers",
    "Mail": "Mail",
}

# Names a model may say for the same allowlisted app. Anything else is kept
# so the action engine can refuse it.
_APP_ALIASES = {
    "files": "Files",
    "finder": "Files",
    "preview": "Preview",
    "sheets": "Sheets",
    "numbers": "Sheets",
    "mail": "Mail",
}


def canonical_app(name: str) -> str:
    """Map Finder or Numbers onto the allowlist. Unknown names are unchanged."""
    stripped = name.strip()
    if not stripped:
        return ""
    return _APP_ALIASES.get(stripped.casefold(), stripped)
