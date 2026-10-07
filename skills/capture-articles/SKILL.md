---
name: capture-articles
description: >-
  Use when the user submits an article URL, asks to save online reading into a
  Notion-first KB, or a scheduled knowledge-intake run has queued article links
  to capture as private raw Markdown with a Notion Raw DB index row.
---
# Capture Articles (Notion-first)

## Prerequisites

Require workspace config with `raw_dir` and configured Notion Raw DB. If missing, stop and ask. Do not create databases. Do not ingest browsing history — only explicit submissions or approved queue URLs.

## Workflow

1. Normalize URL; strip tracking parameters; discover canonical URL.
2. Attempt direct HTTP retrieval and deterministic article extraction first.
3. Fall back to one reused signed-in browser session for JS-rendered pages. Never store credentials or defeat access controls.
4. Reject login pages, bot challenges, navigation-only pages, and implausibly short extractions.
5. Convert body to Markdown; preserve headings, lists, links, quotations, code, and meaningful images.
6. Apply routing policy before write.
7. Write one immutable raw file under `raw_dir` using lowercase slug + stable URL hash. Frontmatter:

```yaml
---
title: "Article title"
source_type: article
status: raw
visibility: private
external_id: "<stable hash or canonical URL>"
source_url: "<canonical URL>"
submitted_url: "<original URL>"
author: "<when available>"
published_at: "<ISO-8601 if known>"
captured_at: "<ISO-8601>"
word_count: 0
raw_path: "<relative path>"
---
```

8. Upsert Notion Raw DB row pointing at the blob (path / Git path / Drive id). Status `raw`. No full-body paste when large.
9. Deduplicate by canonical URL and content hash. Mark queue item handled only after verified raw write + Raw DB upsert.

## Result

Return counts and exact filenames / Raw row refs. Do not invoke wiki-ingest unless the user asked for standalone end-to-end ingest.
