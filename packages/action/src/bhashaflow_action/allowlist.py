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
