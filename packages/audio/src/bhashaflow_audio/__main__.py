"""Print the fixture demo lines. No API key and no microphone."""

from bhashaflow_audio.pipeline import transcribe_fixture


def main() -> None:
    for line in transcribe_fixture():
        print(line)


if __name__ == "__main__":
    main()
