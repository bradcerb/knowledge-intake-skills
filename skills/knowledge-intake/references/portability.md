# Knowledge Intake Portability

Each skill owns its deterministic scripts and supporting references. Machine-level programs such as FFmpeg and Python environments are dependencies, not workspace tools.

## Portability

Keep skill names and scripts workspace-neutral. Each workspace supplies its own config (see `examples/workspace.json.example` at the plugin root, or a local `workspace.json` the user points to), feed registry, loop state, routing policy, and `wiki-ingest` behavior. Relative paths resolve from that workspace's root.

For a second workspace (for example work vs personal), use a distinct `workspace_id`, its own `raw_dir` / Notion DB targets, and a routing policy that rejects the other boundary. Never share state files or raw output directories between workspaces.

## Runtime Data

- Store durable cursors in `.agents/loops/knowledge-intake.json` (or the path in workspace config).
- Store temporary audio outside the wiki and delete it only after a transcript is verified.
- Keep secrets out of this directory. Use the operating-system credential store or ignored environment files.
- A workspace Python environment may live at `.venv/` and should remain ignored by version control.
- Install FFmpeg with the machine package manager. Install Whisper and extraction libraries into the workspace environment. Keep model caches in their normal user cache location.
