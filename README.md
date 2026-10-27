# BhashaFlow

BhashaFlow is a hackathon project for a voice-first desktop demo. You speak a task, and three tracks — vision, audio, and action — are coordinated by an orchestrator so the demo can listen, look at the screen, and carry the task out on the machine. ChatGPT Voice with computer use already pairs speech with computer control, and Claude is the typed-assistant comparison. This repository is the shared workspace for one continuous spoken desktop session over a short build. The tree below is scaffolding and CI only: there is no agent loop, model, or OS control yet.

## Stack

Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.13.5. The stack is still open past this baseline. Python is the default glue because the vision, audio, and orchestration tracks can share one runtime, one lockfile, and one CI job while the demo is built. A desktop shell and specific models can land later without rearranging the packages.

Runtime pins:

- Python `3.12` in [`.python-version`](.python-version) and `requires-python = ">=3.12,<3.13"`
- uv `0.13.5` in the root `pyproject.toml` (`tool.uv.required-version`) and in CI
- Third-party tools (pytest, ruff, hatchling) in the committed [`uv.lock`](uv.lock)

## Layout

| Path | Track | What lands here |
| --- | --- | --- |
| `packages/vision` | Lungile | Screen understanding |
| `packages/audio` | Alucard | Capture, speech-to-text, speech synthesis |
| `packages/action` | Satinder | OS actions |
| `packages/orchestrator` | Satinder | Coordination of the other tracks |
| `packages/shared` | All | Identifiers shared by the tracks |

The root project is a uv workspace (`tool.uv.package = false`) that depends on `bhashaflow-orchestrator`. Each directory under `packages/` is its own installable package. `uv sync` installs them editable into `.venv`.

## Run locally

Install uv 0.13.5, then sync the workspace. Tests are the runnable surface until a demo entrypoint exists.

```bash
curl -LsSf https://astral.sh/uv/0.13.5/install.sh | sh
uv python install 3.12
uv sync --all-packages
cp .env.example .env
uv run pytest
```

`.env` is gitignored. Scaffolding does not read it.

## CI locally

The GitHub Actions job [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests and on pushes to `main`. Reproduce it with:

```bash
uv python install 3.12
uv sync --frozen --all-packages
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`uv sync --frozen` fails if `uv.lock` is out of date. After changing dependencies, run `uv lock` and commit the lockfile.

## OS permissions

Nothing in this scaffolding captures the screen, reads the microphone, or injects input. When the desktop loop lands, the process that runs it will need:

- **Microphone** — voice input for the audio track.
- **Screen recording** — so vision can see the desktop. On macOS this is Screen Recording. On Windows it is graphics capture. On Linux it is a portal (or X11 capture) under Wayland or X11.
- **Accessibility** — so action can drive the UI. On macOS this is Accessibility. On Windows it is UI Automation. On Linux it is an input and assistive-technology interface such as AT-SPI.

Grant those only to the demo process, in System Settings (macOS), Privacy settings (Windows), or the desktop portal (Linux). Do not grant them to editors or shells that are only running tests.

## Environment

Placeholders live in [`.env.example`](.env.example):

- `BHASHAFLOW_LOG_LEVEL` — future process log level (`info` by default)
- `BHASHAFLOW_STT_API_KEY` and `BHASHAFLOW_TTS_API_KEY` — audio track
- `BHASHAFLOW_VISION_ENDPOINT` — vision track

Leave keys empty until the track that reads them exists. Do not commit real credentials.

## Issues

Track work in [GitHub issues](https://github.com/BhashaFlow/BhashaFlow/issues).
