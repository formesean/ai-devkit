# ai-devkit

My portable Claude Code setup: house rules, settings, skills, agents, git hooks.
`~/.claude` symlinks into this clone, so the repo is always the source of truth —
edit here, commit, pull on other machines.

## Fresh machine

```sh
# prerequisites: git, jq, claude (claude.ai/code), gitleaks
git clone https://github.com/formesean/ai-devkit.git ~/ai-devkit
cd ~/ai-devkit && ./install.sh
```

`install.sh` is idempotent and does five things:

1. Symlinks `CLAUDE.md`, `settings.json`, `agents/`, `skills/` into `~/.claude/`.
2. Symlinks `git-hooks/` to `~/.config/git/hooks` and sets `core.hooksPath`
   (gitleaks secret scan on every push, all repos).
3. Adds every marketplace and installs every plugin declared in
   `settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) — no manual
   searching in `/plugin`.
4. Adds user-scope MCP servers (`atlassian`, `claude-design`).
   Remote servers need a one-time `/mcp` authentication per machine.
5. Codex CLI: symlinks `codex/{AGENTS.md,agents,prompts}` into `~/.codex/` and
   seeds `~/.codex/config.toml` from `codex/config.toml` if none exists (seed
   only — Codex rewrites that file with machine state, so it's never synced
   back). Set `CONTEXT7_API_KEY` in your shell profile; the seed reads the
   context7 MCP key from the environment so no secret lives in this repo.
   Then `npm i -g @openai/codex && codex login`.

Plugin caches (`~/.claude/plugins/`) are machine-local and never tracked.

## Guardrails baked in

- A `SessionStart` hook warns if `~/.claude/settings.json` stops being a
  symlink (an app rewrite would silently break the sync).
- The pre-push hook blocks pushes when gitleaks is missing or finds secrets.
  Bypass once with `SKIP_GITLEAKS=1 git push`. If a secret ever hit history:
  rotate the key first.
