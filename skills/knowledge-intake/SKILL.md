---
name: knowledge-intake
description: >-
  Use when running a scheduled or on-demand knowledge-intake cycle for a
  Notion-first personal KB: orchestrate capture skills into raw storage, upsert
  Notion Raw DB index rows, verify writes, then invoke wiki-ingest for new raw
  only.
---
# Knowledge Intake (Notion-first)

## Purpose

Run a conservative intake cycle for the active personal workspace. Delegate source acquisition to capture skills, write immutable raw Markdown outside Notion, upsert a Notion Raw DB index row per raw item, then invoke wiki-ingest only for newly verified raw.

## Architecture

- **Raw blobs** live outside Notion (Git `learnings-raw` shape, Drive file, or box/workspace path). Notion Raw DB is an **index + status**, not the full body when large.
- **Curated wiki** lives in Notion (Wiki DB + Wiki Log). Mirror your KB SCHEMA categories as Notion properties/pages.
- Capture skills never invent database IDs. They require configured Notion targets from workspace config.

## Workspace configuration

Ask which workspace to use when ambiguous. Read workspace config (for example `workspace.json` or the equivalent Notion-first config the user points to). Resolve:

- `raw_dir` — local/Git path for raw Markdown blobs
- `notion_raw_db` — configured Notion Raw DB (name or id from config; never hard-code)
- `notion_wiki_db` — configured Notion Wiki DB
- `notion_wiki_log` — configured Wiki Log DB or page
- `loop_state` — cursor / in-flight state file
- `routing_policy` — accept / reject / on_ambiguous
- `wiki_ingest_skill` — usually `wiki-ingest`
- optional feed registries for podcasts / YouTube

If `notion_raw_db` or `notion_wiki_db` is missing, **stop and ask**. Do not create Notion databases.

## Delegation

Invoke only the skills needed:

1. `capture-newsletters` — approved newsletter email or RSS
2. `capture-articles` — submitted or queued article URLs
3. `capture-podcasts` — monitored public feeds and submitted episode links
4. `capture-youtube` — submitted YouTube links and monitored channel RSS
5. `capture-meetings` — authorized calendar-linked transcripts/notes/recordings
6. Configured `wiki_ingest_skill` for verified new raw only

Do not reproduce source-specific procedures here. Capture skills must not call this orchestrator.

## Scheduled workflow

1. Read routing policy, loop state, and confirm Notion Raw DB + Wiki DB are configured (Notion MCP search/fetch/query). If either DB is missing, stop and ask.
2. Refuse to start if `state.in_flight` is active and newer than six hours. Otherwise record in-flight run id and start time.
3. Run needed capture skills within guardrail limits.
4. Require each skill to return counts: discovered, written, deferred, skipped, failed — plus exact raw paths and Notion Raw row ids when upserted.
5. Verify each reported raw blob exists and is non-empty. Verify each has a Notion Raw row with `status: raw` (or configured equivalent) pointing at the blob path / Git path / Drive id.
6. Invoke wiki-ingest only for those verified new raw items. Never edit raw blobs during ingest.
7. Update loop state (`last_run_at`, cursors, handled ids, failures); clear `in_flight`.
8. Return one concise report. Surface failures and missing permissions; do not guess, bypass access controls, or silently discard items.

## Safety and cost controls

- Initialize monitored feeds at the cursor; never historical backfill unless the user explicitly asks.
- Podcasts: prefer publisher transcripts. YouTube: local Whisper only (no captions as source of truth).
- Cap audio items / minutes per run from config.
- Treat delivery as captured, not consumed.
- Apply `routing_policy`. Never cross personal vs work / confidential company boundaries.
- Do not publish, email, reply, unsubscribe, or modify calendar events.
- Prefer deterministic fetch/parse/hash/transcribe scripts; use judgment for routing, ambiguity, and wiki synthesis.
- Leave recoverable failures pending for the next run.

## Completion contract

Complete only when state is saved, raw blob + Notion Raw index rows are verified, requested wiki-ingest is verified, and deferred/failed items are listed.
