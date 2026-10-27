from bhashaflow_vision import TRACK, __version__, registered


def test_vision_track_is_registered() -> None:
    assert __version__ == "0.4.0"
    assert TRACK == "vision"
    assert registered()
