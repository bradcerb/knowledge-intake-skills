---
name: capture-youtube
description: >-
  Use when transcribing a YouTube video, processing a YouTube URL, monitoring a
  YouTube channel RSS feed, or preparing YouTube transcripts as raw Markdown for
  a Notion-first KB using local Whisper (not captions).
---
# Capture YouTube (Notion-first)

## Prerequisites

Require workspace config: `raw_dir`, optional channel registry, loop state, and configured Notion Raw DB. If Raw DB is missing, stop and ask. Do not create databases.

This skill **skips YouTube captions as source of truth** and always uses local Whisper. If `yt-dlp`, `ffmpeg`, or Whisper are missing, ask for approval to bootstrap.

## Submitted link

1. Resolve metadata with `yt-dlp`.
2. Download temporary best-audio.
3. Convert to 16 kHz mono WAV with local `ffmpeg`.
4. Transcribe with local Whisper.
5. Write one immutable Markdown under `raw_dir`.
6. Delete temp audio after a non-empty raw transcript exists.

## Channel review

For configured public YouTube channel RSS feeds: on first initialization record current video IDs as seen and process none. Later runs process unseen videos oldest-first. Advance cursor only after verified raw writes + Notion Raw upserts. Honor max-items guardrails.

## Raw write + Notion index

Frontmatter: `source_type: youtube`, `platform: youtube`, `external_id` (video id), `title`, `channel`, `published_at`, `captured_at`, `duration_minutes`, `source_url`, `transcript_source`, `visibility: private`, `status: raw`, `raw_path`.

Upsert Notion Raw DB row pointing at blob path / Git path / Drive id. Do not paste full transcripts into Notion when large.

## Result

Return counts and exact filenames / Raw row refs. Do not invoke wiki-ingest; return control to the orchestrator.
