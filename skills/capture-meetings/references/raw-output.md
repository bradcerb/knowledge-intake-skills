# Raw transcript payload

`output=raw` and `output=both` return UTF-8 JSON Lines. One JSON object per line. No other lines inside the payload. `skills/capture-meetings/scripts/meeting_params.py format` emits this payload. It does not fetch providers.

Capture files keep the existing Markdown frontmatter. This document is only the return payload other skills parse.

## Fields

| Field | Type | Content |
| --- | --- | --- |
| `title` | string | Meeting title. May be empty. |
| `occurred_at` | string | ISO-8601 date and time with `Z` or a numeric offset. |
| `timezone` | string | IANA timezone name when the source provides one. Empty string when only the offset is known. |
| `attendees` | array of strings | `Name <email>`, a bare email, or a display name. Source order. Exact duplicates removed. |
| `external_id` | string | Same non-empty id capture frontmatter uses (calendar event id and artifact id). |
| `source_url` | string | Authorized link when one exists. Empty string otherwise. |
| `transcript` | string | Transcript or generated notes. Non-empty. Newlines stay inside the JSON string. |

Objects are ordered by `occurred_at`, then `external_id`.

`output=raw`: the skill return is one `jsonl` fence and nothing else. Zero meetings is an empty fence.

`output=both`: the skill return is the usual capture counts, then a heading `Raw transcripts`, then one `jsonl` fence. Include only meetings whose raw write and Raw DB upsert succeeded.

## Example

```jsonl
{"title":"Weekly sync","occurred_at":"2026-10-01T19:00:00Z","timezone":"Etc/UTC","attendees":["Teammate <name@example.com>"],"external_id":"evt_example:art_example","source_url":"https://example.com/meet/evt_example","transcript":"Teammate: Hello.\n"}
```
