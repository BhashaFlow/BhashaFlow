from bhashaflow_audio import TRACK, __version__, registered


def test_audio_track_is_registered() -> None:
    assert __version__ == "0.3.0"
    assert TRACK == "audio"
    assert registered()
