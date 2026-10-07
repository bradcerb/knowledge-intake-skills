# knowledge-intake-skills

> **Canonical home moved.** These skills now live in the private repo [`bradcerb/bstack`](https://github.com/bradcerb/bstack) under `plugins/knowledge-intake/`. Prefer installing from bstack for new setups. This standalone repo stays usable so existing installs keep working; treat it as a thin mirror until you switch.

Portable **Notion-first** knowledge capture and wiki ingest skills.

Raw Markdown blobs live outside Notion. Notion holds a Raw DB index, curated Wiki DB pages, and a Wiki Log. Skills follow the [Agent Skills](https://agentskills.io) folder + `SKILL.md` shape; thin plugin manifests are the install layer only. **No MCP server** ships in this pack — use your host’s Notion connector when writing rows/pages.

## Skills

| Skill | Role |
| --- | --- |
| `knowledge-intake` | Orchestrator: capture → verify raw + Raw DB → `wiki-ingest` |
| `capture-newsletters` | Approved newsletter email / RSS → raw + Raw DB |
| `capture-articles` | Submitted / queued URLs → raw + Raw DB |
| `capture-podcasts` | Public RSS + local Whisper → raw + Raw DB |
| `capture-youtube` | YouTube + local Whisper (not captions) → raw + Raw DB |
| `capture-meetings` | Authorized Meet/Teams artifacts → raw + Raw DB |
| `wiki-ingest` | Verified raw → Notion Wiki DB + Wiki Log (never edit raw) |

## Install matrix

For new installs, use [`bradcerb/bstack`](https://github.com/bradcerb/bstack) `plugins/knowledge-intake/` (private). Steps below still work for this standalone checkout.

### 1. Bare skills (Claude / Codex / agentskills.io)

Clone this repo, then copy or symlink each folder under `skills/` into your tool’s skills directory:

- Claude Code: `~/.claude/skills/<name>/`
- Codex / agents: `~/.codex/skills/` or `.agents/skills/`
- Other hosts that accept Agent Skills folders: copy `skills/<name>` as-is

### 2. Cursor (plugin marketplace)

Add this GitHub repo as a marketplace (uses `.cursor-plugin/marketplace.json`), then install the `knowledge-intake-skills` plugin. Skills are discovered from `skills/`.

### 3. Grok Bot / Agent Plugins

```text
InstallPlugin from https://github.com/bradcerb/knowledge-intake-skills
```

Or clone locally and install from the directory path. Root `plugin.json` is Agent Plugins 1.0 (skills-only; no `mcp.json`).

**Note:** InstallPlugin loads skills for the plugin connector. Registering the same bodies as editable Grok Bot user skills via `UpdateSkill` is a separate optional step.

### 4. Claude Code marketplace

`.claude-plugin/marketplace.json` points at `./` so skill bodies stay under `skills/` (no duplication).

## Configure (required)

1. Copy `examples/workspace.json.example` into your workspace as `workspace.json`.
2. Set `raw_dir`, Notion Raw / Wiki / Wiki Log targets (**your** DB names or IDs — never commit real IDs).
3. Optionally copy `examples/feeds.json.example` → `skills/capture-podcasts/references/feeds.json` (or another path listed in workspace config).
4. Optionally copy `examples/channels.json.example` → `skills/capture-youtube/references/channels.json`.

Skill-local `references/feeds.json` and `references/channels.json` ship empty so the repo stays portable.

## Safety

- Do not create Notion databases; stop and ask if Raw/Wiki targets are missing.
- No historical podcast/YouTube backfill unless explicitly requested.
- Never cross personal vs work / confidential boundaries per `routing_policy`.
- Do not publish, email, reply, unsubscribe, or modify calendar events from these skills.
- Prefer publisher transcripts for podcasts; YouTube always uses local Whisper.

## License

MIT
