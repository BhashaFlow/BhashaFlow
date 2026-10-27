from pathlib import Path


def test_action_doc_states_the_allowlist_and_permissions() -> None:
    root = Path(__file__).resolve().parents[3]
    doc = (root / "docs" / "action-engine.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for name in ("Files", "Preview", "Sheets", "Mail"):
        assert name in doc
    assert "allowlist" in doc
    assert "Accessibility" in doc
    assert "recoverable" in doc
    assert "muse-wonder-1.0" in doc
    assert "safety" in doc.casefold()
    assert "unscoped" in doc
    assert "BHASHAFLOW_ACTIONS" in readme
    assert "Terminal" in doc
