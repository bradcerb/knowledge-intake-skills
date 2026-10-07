# Local Podcast Transcription

This workflow keeps podcast transcription off paid APIs by running a local Whisper-compatible engine.

## Current runner

Use `scripts/transcribe_episode.py` for one episode at a time. It:

- downloads the episode enclosure to a temporary directory;
- converts the audio with `ffmpeg`;
- transcribes with a local Whisper engine;
- writes one immutable Markdown file directly under `learnings/raw`;
- reports missing dependencies without marking the episode handled.

Check readiness from the selected workspace:

```bash
python3 skills/capture-podcasts/scripts/transcribe_episode.py \
  --workspace-root "/path/to/workspace" \
  --check-dependencies
```

## Workspace-local install

The portable layout is:

- `tools/bin/ffmpeg` or `tools/bin/ffmpeg.cmd`
- `tools/bin/whisper-cli` or `tools/bin/whisper-cli.cmd`
- `tools/whisper.cpp/models/ggml-base.en.bin`

The runner discovers these paths from the selected workspace root. No shell PATH setup or OpenAI API key is required.

Check or prepare the selected workspace:

```bash
python3 skills/knowledge-intake/scripts/prepare_local_transcription.py \
  --workspace-root "/path/to/workspace" \
  --check
```

After user approval:

```bash
python3 skills/knowledge-intake/scripts/prepare_local_transcription.py \
  --workspace-root "/path/to/workspace" \
  --yes
```

`whisper.cpp` runs in CPU mode by default because it is the most portable scheduled-background option across macOS and Windows. Enable machine-specific acceleration only after a successful local smoke test.

## Supported engines

Preferred:

- `whisper.cpp` via `whisper-cli`
- Set `WHISPER_CPP_MODEL` to a local `.bin` model path.

Fallback:

- OpenAI's open-source Python Whisper package via the `whisper` CLI.
- This is still local and has no per-minute API cost.

## Required tools

- `ffmpeg`
- either `whisper-cli` with `WHISPER_CPP_MODEL`, or the Python `whisper` CLI

No OpenAI API key is required for local transcription.
