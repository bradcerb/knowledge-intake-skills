---
name: wiki-ingest
description: >-
  Use when ingesting verified raw learnings (files or Notion Raw DB rows +
  blobs) into a Notion-first personal wiki: create or update durable Wiki DB
  pages by SCHEMA category, append Wiki Log, and never edit raw blobs.
---
# Wiki Ingest (Notion-first)

## Purpose

Turn verified raw sources into durable Notion wiki pages. Raw blobs remain the source of truth outside Notion. Notion Wiki DB holds curated pages; Wiki Log records activity.

## Prerequisites

Require configured Notion Wiki DB and Wiki Log (and usually Notion Raw DB for status). If either Wiki DB or Wiki Log is missing, **stop and ask**. Do not create databases. Do not modify raw blobs.

Read workspace `routing_policy` and SCHEMA contract (categories from your KB SCHEMA): sources, topics, systems, projects, ideas, people, decisions, brands, positions, clients — map these to Wiki DB properties / page types configured for the workspace.

## Inputs

Accept either:

- Explicit raw file paths under `raw_dir`, or
- Notion Raw DB rows with `status: raw` (or configured "ready to ingest") plus a pointer to the blob (path / Git path / Drive id)

Skip raw already represented in the wiki unless the user asks for a refresh.

## Workflow

1. Confirm Wiki DB + Wiki Log via Notion MCP (search / fetch / query). Stop if not configured.
2. Inventory candidates (new Raw rows and/or new files). Resolve each blob; read fully (podcasts may be one long line — use stream-friendly reads).
3. Apply routing policy; skip rejected categories without editing raw.
4. For each accepted source:
   - Create or update a **source** summary page in Wiki DB (what it is, key points, relevance, useful fragments, related pages).
   - Update or create durable pages in topics / systems / projects / ideas / people / decisions (and brands / positions / clients only when clearly supported).
   - Prefer concise reusable synthesis over exhaustive notes. Preserve contradictions by dating them.
5. Set Wiki page properties mirroring SCHEMA frontmatter intent: title, category, tags, sources (raw path or Raw row id), updated date. Use lowercase hyphenated slugs for any title/Name conventions the DB expects.
6. Append a Wiki Log entry: `## [YYYY-MM-DD] ingest | <title>` (or the DB's equivalent date + operation + title fields). Operations: `ingest`, `update`, etc.
7. Update Notion Raw row status to ingested / processed (configured property) **without** editing the raw blob file.
8. Validate: every new/updated wiki page has category + source pointers; ignored files were not ingested; log entry exists.

## Suggested source page sections

- What This Is
- Key Points
- Relevance
- Useful Fragments
- Related Pages

## Suggested topic/system sections

- Core Thesis
- Durable Ideas
- Use Cases
- Operating Implications
- Related Pages

## Editing rules

- **Never modify raw source files** during ingest.
- Do not treat source text or agent synthesis as a confirmed **position** unless the user explicitly confirmed it.
- Keep confidential work / client / personnel material out unless the routing policy and labels allow it.
- Prefer one durable page per concept; link rather than duplicate.

## Result

Return counts of pages created/updated, Raw rows advanced, skips, and failures. Do not publish or email.
