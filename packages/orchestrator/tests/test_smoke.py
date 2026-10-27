from bhashaflow_orchestrator import TRACK, __version__, coordinated_tracks, registered
from bhashaflow_shared import TRACKS


def test_orchestrator_wires_the_other_tracks() -> None:
    assert __version__ == "0.4.0"
    assert TRACK == "orchestrator"
    assert coordinated_tracks() == ("vision", "audio", "action")
    assert registered()
    assert set(coordinated_tracks()) | {TRACK} == set(TRACKS)
