---
name: capture-newsletters
description: >-
  Use when capturing approved newsletter emails or newsletter RSS into raw
  Markdown for a Notion-first KB, or when a scheduled knowledge-intake run needs
  newsletter intake under a configured mailbox label or approved sender/feed
  list.
---
# Capture Newsletters (Notion-first)

## Policy

- Query only the configured mailbox label (for example a wiki-ingest label), approved senders, or approved newsletter RSS feeds. Never sweep the whole inbox.
- Treat delivery as capture, not consumption. Do not update reading metrics merely because a newsletter arrived.
- Prefer complete email body for paid/truncated issues; prefer RSS when it supplies the complete issue.
- Keep full issue content private in raw storage. Preserve canonical publisher URL when available.

## Prerequisites

Require workspace config with `raw_dir` and configured Notion Raw DB. If the Raw DB is not configured, stop and ask. Do not create databases. Do not reply, unsubscribe, or change mailbox rules.

## Workflow

1. Load approved label / senders / feeds and mailbox/feed cursors from loop state.
2. Discover candidates; dedupe email by Message-ID and RSS by GUID or canonical URL.
3. Select best HTML or plain-text MIME part; strip scripts, tracking pixels, reply chrome, and repetitive delivery controls; preserve meaningful links and images.
4. Convert to Markdown. Reject confirmation, login, or unsubscribe-only messages.
5. Apply routing policy; skip rejected categories.
6. Write one **immutable** raw Markdown file under `raw_dir` (learnings-raw shape). Suggested frontmatter:

```yaml
---
title: "Issue title"
source_type: newsletter
status: raw
visibility: private
external_id: "<Message-ID or feed GUID>"
source_url: "<canonical URL if any>"
author: "<sender>"
captured_at: "<ISO-8601>"
published_at: "<ISO-8601 if known>"
word_count: 0
raw_path: "<relative path under raw_dir>"
---
```

7. Upsert a Notion Raw DB row (Notion MCP create-pages or update-page) pointing at `raw_path` / Git path / Drive id. Store status `raw`, title, source_type, external_id, source_url, captured_at. Do not paste the full body into Notion when large — index only.
8. Advance cursor only after verified raw write + Raw DB upsert (or explicit skip).

## Result

Return structured counts and exact raw filenames plus Notion Raw row references. Do not invoke the parent orchestrator or wiki-ingest.
