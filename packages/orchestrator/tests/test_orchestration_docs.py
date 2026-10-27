from pathlib import Path


def test_orchestration_doc_names_the_state_machine_and_entrypoint() -> None:
    root = Path(__file__).resolve().parents[3]
    doc = (root / "docs" / "orchestration.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for phase in ("listen", "ground", "act", "confirm", "next"):
        assert phase in doc
    assert "uv run bhashaflow-demo" in doc
    assert "uv run bhashaflow-demo" in readme
    assert "muse-spark-1.3" in doc
    assert "muse-wonder-1.0" in doc
    assert "sam-3.1" in doc
    assert "fixture" in doc
    assert "keyboard" in doc.casefold()
