---
name: capture-meetings
description: >-
  Use for scheduled post-meeting intake or when asked to retrieve an authorized
  Google Meet or Microsoft Teams transcript/notes/recording into raw Markdown
  for a Notion-first KB, with a Notion Raw DB index row. Also use for an optional
  date range, one-person filter, or raw transcript return.
---
# Capture Meetings (Notion-first)

## Prerequisites

Require workspace config: `raw_dir`, routing policy, loop state, and configured Notion Raw DB. If Raw DB is missing, stop and ask. Do not create databases.

Exception: `output=raw` does not write to Notion, so a missing Raw DB does not block that mode. `capture` and `both` still require it.

Process only meetings the user is authorized to access.

This skill has no skill-local config file. Do not create one and do not start an onboarding flow. Caller parameters apply only to this invocation.

## Parameters

Three optional caller parameters. `skills/capture-meetings/scripts/meeting_params.py` resolves them and formats the raw payload. It does not fetch calendars or transcripts. Omitting all three is the current capture path.

### date_range

Optional discovery window for this call.

- Relative: `last <n> days` or `last <n> weeks`. `<n>` is a positive integer or a number word from one to twelve (`a` and `an` count as one). Examples: `last 7 days`, `last two weeks`. A week is seven days. The window ends today and is inclusive.
- Explicit: `YYYY-MM-DD..YYYY-MM-DD`, or `start` and `end` as `YYYY-MM-DD`. Both ends are inclusive.

Resolve relative phrases from today's date in the calendar timezone. Pass that date as `--today`. If resolve exits non-zero, stop. Do not invent a window.

Default: omitted. Search the configured lookback window. Do not substitute a new default length.

```bash
python3 skills/capture-meetings/scripts/meeting_params.py resolve \
  --date-range "last two weeks" \
  --today 2026-10-08
```

```bash
python3 skills/capture-meetings/scripts/meeting_params.py resolve \
  --start 2026-09-01 \
  --end 2026-09-14 \
  --today 2026-10-08
```

### person

Optional display name or email. Omitted means every meeting in the window.

Match attendees and participants the provider already returned, including the organizer when listed. Do not search transcript text. Do not fetch a broader guest list. Map provider fields to `name` and `email` before filtering. The filter reads only those two keys.

```bash
python3 skills/capture-meetings/scripts/meeting_params.py filter \
  --person "name@example.com"
```

Stdin is a JSON array. Each item has `attendees` as objects (`name`, `email`) or strings (`Name <email>`, a bare email, or a display name).

Matching is exact, not fuzzy:

- A filter that contains `@`, or `Name <email>`, matches email, case-insensitive. The display name in that filter is not required.
- Any other filter matches display name, case-insensitive, after collapsing whitespace. It does not match an email-only attendee.
- An email filter does not match a name-only attendee.
- One matching attendee is enough. No match: skip the event.

### output

- `capture` (default): private raw Markdown plus a Notion Raw DB index row. Return counts and exact filenames / Raw row refs. Do not put the transcript in the return.
- `raw`: return the JSON Lines payload in `references/raw-output.md`. Do not write the raw file, do not upsert Notion, and do not mark the event handled. Already-handled events stay eligible.
- `both`: perform `capture` and also return JSON Lines for meetings written on this call. Already-handled events stay skipped.

```bash
python3 skills/capture-meetings/scripts/meeting_params.py resolve --output raw
```

## Workflow

Follow the booleans from resolve: `date_range_applied`, `write_raw`, `write_notion`, `mark_handled`, `include_already_handled`, and `return_raw`.

1. Run `meeting_params.py resolve` for the caller parameters. If `date_range` was omitted, search completed calendar events inside the configured lookback window and read full details only for candidates. If `date_range` was set, search that inclusive window instead and read full details only for candidates. Include an event in that window when its start date, in the calendar timezone, falls on `date_start` through `date_end` inclusive.
2. Skip buffers, holds without artifacts, declined events, already-handled events, and meetings rejected by `routing_policy`. If `person` is set, also skip events that `meeting_params.py filter` does not match. Exception for already-handled events: `output=raw` keeps them eligible. `capture` and `both` still skip them.
3. Detect provider; inspect authorized attachments, descriptions, and recording/transcript links.
4. Prefer provider transcripts or generated notes. Download and transcribe a recording locally only when no usable transcript exists.
5. Wait and retry later if an artifact is still processing. Never bypass permissions.
6. Apply routing policy. Never write across personal vs work / confidential boundaries. Apply the same policy before a raw return.
7. When `write_raw` is true (`capture` and `both`), write one private immutable raw Markdown with calendar provenance, attendees when appropriate, timestamps, transcript source, and links to authorized artifacts. Frontmatter: `source_type: meeting`, `status: raw`, `visibility: private`, `external_id` (event id + artifact id), `title`, `captured_at`, `source_url` when applicable, `raw_path`.
8. When `write_notion` is true (`capture` and `both`), upsert Notion Raw DB row pointing at the blob. Index only. Do not dump full transcripts into Notion when large.
9. Preserve action items and provider notes as source content; leave durable synthesis to wiki-ingest.
10. When `return_raw` is true (`raw` and `both`), pass one record per meeting to `meeting_params.py format` and return that payload. For `both`, include only meetings whose raw write and Raw DB upsert succeeded. For `raw`, include meetings whose transcript was retrieved. Use the same `external_id` as capture frontmatter.

## Privacy

- Keep `visibility: private`.
- Do not publish, share, email, or alter the calendar event.
- Do not turn casual or sensitive remarks into durable claims during capture.

## Result

Deduplicate by calendar event ID plus artifact ID. Mark handled only after verified raw write + Raw DB upsert. `output=raw` does not mark handled.

`capture` (default): return counts and exact filenames / Raw row refs.

`raw`: return only the JSON Lines payload in a `jsonl` fence. See `references/raw-output.md`.

`both`: return the capture counts, then a `Raw transcripts` heading and one `jsonl` fence.
