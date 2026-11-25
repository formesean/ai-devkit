# ai-devkit

My portable Codex and Claude Code setup, with one skill catalog and one list of shared plugins.

## Install

Install the client CLI separately. Python 3.11 or newer and Git are required.

```sh
./install.sh --codex
./install.sh --claude
```

Choose exactly one client per run. Each installer fetches missing skills and refreshes managed copies to the latest commit on each skill repository's default branch. Both installers sync the plugins listed in `plugins.toml` using their client's native CLI. Use `--skip-plugins` to skip marketplace plugin sync.

### Codex

- `~/.codex/AGENTS.md` links to `codex/AGENTS.md`.
- `~/.codex/agents` links to the native TOML definitions in `codex/agents`.
- `~/.agents/skills` links to the single catalog in `skills`.
- Existing system-managed skills under `~/.codex/skills/.system` are preserved. When a legacy system copy exists in the checkout, setup links it there without exposing the user catalog twice. A fresh checkout does not need bundled system skills.
- Existing Codex configuration is preserved. Setup seeds a missing config and maintains only its marked skill-policy block, sourced from `codex/skill-policy.toml`.

Existing nonmatching files, directories, and symlinks block setup rather than being overwritten. Setup can migrate its own legacy `~/.codex/skills -> skills` link to the system-only layout. A separate existing `~/.agents/skills` directory must be reconciled before linking it.

### Claude Code

- `~/.claude/CLAUDE.md` links to the shared personal working agreements in `codex/AGENTS.md`.
- `~/.claude/skills/` is a native directory with links to enabled catalog entries. Codex system skills and the three disabled cleanup skills are excluded.
- `~/.claude/agents/` links to Claude Markdown generated from the same TOML definitions used by Codex. These agents cannot use Claude's native editing or delegation tools.
- Claude's settings, plugin cache, and session files live in its own config directory. Existing private skill directories and guidance files are preserved. Name collisions stop setup with the conflicting path.

Upgrades from the previous installer migrate its guidance, agents, skills, and settings links. Setup moves the old settings into a private, regular file, keeps the permission rules, and removes the obsolete hook that expected settings to be a symlink. If the old source file is gone, setup recovers the last shipped copy from this checkout's Git history. A shallow checkout missing that revision must fetch the history or restore the old file before upgrading.

Both installers accept `--home /path/to/disposable-home` to redirect client configuration. For a fully isolated setup, also run from a disposable checkout because the skill catalog and cache live in the checkout. Ordinary runs respect `CODEX_HOME` or `CLAUDE_CONFIG_DIR`. Start a new session after installation.

### Native mobile design

The shared catalog includes `mobile-design-ios`, `mobile-design-android`, and the read-only `mobile-ux-researcher` agent. To add screenshot search for iOS and Android and ordered flow search for iOS, use:

```sh
./install.sh --codex --mobile-design
./install.sh --claude --mobile-design
```

The MCP option requires Node.js and npm on PATH and preserves existing registrations with the same names. The Refero-backed server uses an upstream revision cached under `.mcp-cache/` and fetches screens and flows from Refero at runtime. Rerun setup after moving the checkout and remove the old `refero-design` registration first so it can be registered with the new path.

## Maintain

Edit personal rules in `codex/AGENTS.md`, agent roles in `codex/agents`, and skill content in `skills`. Keep repository-specific instructions in each project's own `AGENTS.md`. Add user skills to this catalog rather than another discovery root.

List upstream skills in `skills.toml` with their repository, full commit SHA, and directory containing `SKILL.md`. Ignore each generated catalog entry in `.gitignore`. Add `--locked` after the client flag to install exactly the listed revisions, including offline when those revisions are cached. Set `frozen = true` on entries that should always use their listed revision. Setup caches the skill files in `.skill-cache/`, keeps existing links if a fetch fails, and leaves the manifest unchanged. Removing a manifest entry leaves its existing link in place for manual cleanup.

Existing local skill directories take precedence. To switch an override to the pinned copy, move the local directory outside `skills/` before rerunning setup.

The retired `next-best-practices` and `next-cache-components` entries use their last available upstream revisions. For current Next.js projects, use the version-matched docs and successor skills described in [Vercel's migration guide](https://github.com/vercel-labs/next-skills#where-each-old-skill-went).

Edit `plugins.toml` to manage the shared plugin set, including the workflow skills and harness distributed by `skills@formesean`. Each listed marketplace must support both clients. Run both installers after editing it or to refresh both native plugin caches. Client-bundled and separately installed plugins are managed by their client. Removing a plugin from the manifest does not uninstall it from either client. Both clients use the shared written guardrails and retain their native permission settings.

The shared skill policy enables `clean-names`, `clean-functions`, `clean-general`, and `clean-tests`. It keeps `boy-scout`, `typescript-clean-code`, and `clean-comments` disabled to avoid mandatory extra cleanup and overlapping rules. Both installers apply this policy on every run. Upstream skill files stay unchanged; the personal working agreements govern task scope and verification.

Plugin caches, accounts, and session history stay machine-local. Existing `git-hooks/` files are retained, but setup does not change `core.hooksPath`.

## Verify

Run `python3 -m unittest discover -s tests -v` for isolated installer regression checks. They cover config preservation, repeat runs, conflicts, and migration of the old skill link. No live installer run or model request is required.
