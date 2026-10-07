# Portable Workspaces

These skills are **Notion-first**: curated wiki pages live in Notion; raw Markdown blobs live outside Notion (`raw_dir`). Local `learnings/wiki` layouts in older scripts are optional mirrors only — follow the SKILL.md Notion workflow when Notion DBs are configured.


Use this reference when running the intake skills from a new machine, a Claude export, or a workspace that is not already obvious from the conversation.

## Workspace Root

Ask the user which workspace to use when the task does not clearly name or open one. Do not assume a personal Documents path; ask which workspace root to use.

The selected workspace should contain:

```text
skills/
  knowledge-intake/
  capture-podcasts/
  capture-youtube/
  capture-articles/
learnings/
  raw/
  wiki/
```

Resolve relative paths from that workspace root. Prefer one of these patterns:

```bash
python3 skills/capture-youtube/scripts/capture_youtube.py \
  --workspace-root "/path/to/workspace" \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --raw-dir learnings/raw
```

or:

```bash
export KNOWLEDGE_WORKSPACE_ROOT="/path/to/workspace"
python3 skills/capture-youtube/scripts/capture_youtube.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --raw-dir learnings/raw
```

On Windows PowerShell:

```powershell
$env:KNOWLEDGE_WORKSPACE_ROOT = "C:\Users\You\Documents\Workspace"
py skills\capture-youtube\scripts\capture_youtube.py `
  --url "https://www.youtube.com/watch?v=VIDEO_ID" `
  --raw-dir learnings\raw
```

## Local Tool Bootstrap

Use `skills/knowledge-intake/scripts/prepare_local_transcription.py` when local audio/video capture needs `yt-dlp`, `ffmpeg`, or `whisper.cpp`.

Check the current machine:

```bash
python3 skills/knowledge-intake/scripts/prepare_local_transcription.py \
  --workspace-root "/path/to/workspace" \
  --check
```

Install missing workspace-local tools after user approval:

```bash
python3 skills/knowledge-intake/scripts/prepare_local_transcription.py \
  --workspace-root "/path/to/workspace" \
  --yes
```

On Windows PowerShell:

```powershell
py skills\knowledge-intake\scripts\prepare_local_transcription.py `
  --workspace-root "C:\Users\You\Documents\Workspace" `
  --yes
```

The bootstrap keeps artifacts under the selected workspace:

- `tools/bin`
- `tools/youtube/venv`
- `tools/ffmpeg/venv`
- `tools/whisper.cpp`

It avoids global package managers. It may require network access, Python venv support, `git`, and `cmake` to build `whisper.cpp` when a preexisting `whisper-cli` is unavailable.
