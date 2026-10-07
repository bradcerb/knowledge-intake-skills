---
name: capture-podcasts
description: >-
  Use when monitoring a public podcast RSS feed, initializing a podcast without
  backfill, transcribing new episodes, or resolving a Spotify/episode link
  through its public RSS source into raw Markdown for a Notion-first KB.
---
# Capture Podcasts (Notion-first)

## Prerequisites

Require workspace config: `raw_dir`, podcast feed registry path, loop state, and configured Notion Raw DB. If Raw DB is missing, stop and ask. Do not create databases.

If local transcription tools (`ffmpeg`, Whisper) are missing when needed, ask for approval to bootstrap — do not assume a machine-specific install path.

## Feed review

1. Read feed registry and loop state.
2. Fetch each active public RSS feed (conditional headers when ETag / Last-Modified exist).
3. Identify episodes by RSS GUID (fallback: canonical episode URL).
4. **First initialization:** record every current GUID as seen and process **none** (no accidental backfill).
5. Later runs: queue only unseen episodes newer than the cursor; apply exclusions and duration limits.
6. Honor orchestration max-items / max-audio-minutes guardrails.

## Submitted links

Accept Spotify episode URLs, publisher pages, Apple Podcasts, RSS item URLs, and direct audio URLs. Resolve to public RSS + GUID. Use unauthenticated oEmbed title only for matching when needed. Require high-confidence match or defer.

## Transcript priority

1. Prefer Podcasting 2.0 `<podcast:transcript>` when valid.
2. Otherwise download enclosure temporarily and transcribe with local Whisper.
3. Preserve timestamps/speaker labels when present; never invent speakers.
4. Delete temp audio only after a non-empty transcript is atomically written.
5. If dependencies are missing, report them and leave the episode pending — do not mark handled.

## Raw write + Notion index

Write one immutable Markdown per episode under `raw_dir` (slug + short hash). Frontmatter should include `source_type: podcast` (or `type: podcast`), `external_id`, `title`, `show`, `published_at`, `captured_at`, `duration_minutes`, `rss_feed`, `source_url` / episode URL, `audio_url`, `transcript_source`, `visibility: private`, `status: raw`, `raw_path`.

Include show notes before the transcript body.

Upsert Notion Raw DB row pointing at the blob path / Git path / Drive id. Index metadata only when the transcript is large.

Advance feed cursor / handled GUID only after verified raw write + Raw DB upsert.

## Result

Return structured counts and exact raw filenames / Raw row refs. Never invoke the parent orchestrator or wiki-ingest from this skill. Explicit historical backfill only when the user requests it.
