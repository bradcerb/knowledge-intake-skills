---
name: capture-meetings
description: >-
  Use for scheduled post-meeting intake or when asked to retrieve an authorized
  Google Meet or Microsoft Teams transcript/notes/recording into raw Markdown
  for a Notion-first KB, with a Notion Raw DB index row.
---
# Capture Meetings (Notion-first)

## Prerequisites

Require workspace config: `raw_dir`, routing policy, loop state, and configured Notion Raw DB. If Raw DB is missing, stop and ask. Do not create databases.

Process only meetings the user is authorized to access.

## Workflow

1. Search completed calendar events inside the configured lookback window. Read full details only for candidates.
2. Skip buffers, holds without artifacts, declined events, already-handled events, and meetings rejected by `routing_policy`.
3. Detect provider; inspect authorized attachments, descriptions, and recording/transcript links.
4. Prefer provider transcripts or generated notes. Download and transcribe a recording locally only when no usable transcript exists.
5. Wait and retry later if an artifact is still processing. Never bypass permissions.
6. Apply routing policy. Never write across personal vs work / confidential boundaries.
7. Write one private immutable raw Markdown with calendar provenance, attendees when appropriate, timestamps, transcript source, and links to authorized artifacts. Frontmatter: `source_type: meeting`, `status: raw`, `visibility: private`, `external_id` (event id + artifact id), `title`, `captured_at`, `source_url` when applicable, `raw_path`.
8. Upsert Notion Raw DB row pointing at the blob. Index only — do not dump full transcripts into Notion when large.
9. Preserve action items and provider notes as source content; leave durable synthesis to wiki-ingest.

## Privacy

- Keep `visibility: private`.
- Do not publish, share, email, or alter the calendar event.
- Do not turn casual or sensitive remarks into durable claims during capture.

## Result

Deduplicate by calendar event ID plus artifact ID. Mark handled only after verified raw write + Raw DB upsert. Return counts and exact filenames / Raw row refs.
