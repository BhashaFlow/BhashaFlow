from bhashaflow_action import TRACK, __version__, registered


def test_action_track_is_registered() -> None:
    assert __version__ == "0.2.0"
    assert TRACK == "action"
    assert registered()
