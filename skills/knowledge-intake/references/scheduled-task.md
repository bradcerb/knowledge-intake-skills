# Scheduled Task

## Recommended Cadence

- Daily at 2:00 AM America/New_York.
- Run from the selected workspace root, or pass `--workspace-root` explicitly.
- Keep the first runs conservative: at most two podcast episodes, two meeting artifacts, and 180 audio minutes per run.

## Task Prompt

Use `$knowledge-intake` in the current workspace. Read `AGENTS.md`, `examples/workspace.json.example (copy to your workspace as workspace.json)`, the configured wiki schema, and `.agents/loops/knowledge-intake.json`. Review approved newsletter sources, queued article URLs, configured public podcast feeds, and authorized completed-meeting artifacts. Initialize new podcast feeds without historical backfill. Write only verified, immutable sources into the configured `learnings/raw` directory, then invoke `$wiki-ingest` only for the raw files created in this run. Respect workspace routing boundaries, leave recoverable failures pending, update loop state atomically, and report discovered, written, ingested, deferred, skipped, and failed counts with filenames.

## Dependency Behavior

If a provider transcript is unavailable and local Whisper or FFmpeg is not installed, ask for approval to run `skills/knowledge-intake/scripts/prepare_local_transcription.py --yes` for the selected workspace. If setup is not approved or fails, defer that item and report the exact missing dependency. Do not advance its handled cursor.

## Podcast Capture Command

Until a Codex app scheduled task is created, the podcast portion can be run locally from the selected workspace:

```bash
python3 skills/capture-podcasts/scripts/run_podcast_capture.py \
  --workspace-root "/path/to/workspace" \
  --registry skills/capture-podcasts/references/feeds.json \
  --state .agents/loops/knowledge-intake.json \
  --raw-dir learnings/raw \
  --runner skills/capture-podcasts/scripts/transcribe_episode.py \
  --max-items 2 \
  --max-audio-minutes 180 \
  --write-state
```

New podcast and YouTube channel feeds initialize without historical backfill; historical backfills should be explicit one-off runs.

## YouTube Capture Command

Submitted YouTube links should use local Whisper from the start rather than YouTube captions:

```bash
python3 skills/capture-youtube/scripts/capture_youtube.py \
  --workspace-root "/path/to/workspace" \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --raw-dir learnings/raw
```

Configured YouTube channels can be checked with:

```bash
python3 skills/capture-youtube/scripts/run_youtube_capture.py \
  --workspace-root "/path/to/workspace" \
  --registry skills/capture-youtube/references/channels.json \
  --state .agents/loops/knowledge-intake.json \
  --raw-dir learnings/raw \
  --runner skills/capture-youtube/scripts/capture_youtube.py \
  --max-items 2 \
  --write-state
```

On Windows, use `py` and backslashes if preferred:

```powershell
py skills\knowledge-intake\scripts\prepare_local_transcription.py `
  --workspace-root "C:\Users\You\Documents\Workspace" `
  --check
```
