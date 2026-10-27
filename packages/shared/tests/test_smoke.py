from bhashaflow_shared import TRACKS, __version__


def test_shared_exports_demo_tracks() -> None:
    assert __version__ == "0.1.0"
    assert TRACKS == ("vision", "audio", "action", "orchestrator")
