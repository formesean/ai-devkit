#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"

link() {
  local src="$KIT/$1" dst="$2"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$dst.pre-devkit"
    echo "  (existing $dst moved to $dst.pre-devkit)"
  fi
  ln -sfn "$src" "$dst"
  echo "linked $dst -> $src"
}

mkdir -p "$HOME/.claude"
link CLAUDE.md     "$HOME/.claude/CLAUDE.md"
link settings.json "$HOME/.claude/settings.json"
link agents        "$HOME/.claude/agents"
link skills        "$HOME/.claude/skills"

mkdir -p "$HOME/.config/git"
link git-hooks "$HOME/.config/git/hooks"
git config --global core.hooksPath "$HOME/.config/git/hooks"
command -v gitleaks >/dev/null 2>&1 ||
  echo "WARN: gitleaks not installed (pacman -S gitleaks / brew install gitleaks) — the pre-push hook refuses to push without it"

mkdir -p "$HOME/.codex"
link codex/AGENTS.md "$HOME/.codex/AGENTS.md"
link codex/agents    "$HOME/.codex/agents"
link codex/prompts   "$HOME/.codex/prompts"
link skills          "$HOME/.codex/skills"
cp "$KIT/codex/config.toml" "$HOME/.codex/config.toml"
echo "copied ~/.codex/config.toml from devkit"

if command -v codex >/dev/null 2>&1; then
  echo "-- codex plugins"
  codex plugin marketplace add DietrichGebert/ponytail ||
    echo "  (marketplace ponytail: already added or failed)"
  for p in context7@claude-plugins-official ponytail@ponytail; do
    codex plugin add "$p" || echo "  (codex plugin $p: already installed or failed)"
  done
  perl -0pi -e 's/(\[plugins\."context7\@claude-plugins-official"\]\nenabled = )true/${1}false/' \
    "$HOME/.codex/config.toml"
else
  echo "WARN: codex CLI not installed (npm i -g @openai/codex), then: codex login"
fi

echo "-- marketplaces (from settings.json extraKnownMarketplaces)"
jq -r '.extraKnownMarketplaces // {} | .[].source | .url // .repo' "$KIT/settings.json" |
  while read -r src; do
    claude plugin marketplace add "$src" || echo "  (marketplace $src: already added or failed — check /plugin)"
  done

echo "-- plugins (from settings.json enabledPlugins)"
jq -r '.enabledPlugins // {} | to_entries[] | select(.value) | .key' "$KIT/settings.json" |
  while read -r p; do
    claude plugin install "$p" || echo "  (plugin $p: already installed or failed — check /plugin)"
  done

echo "-- MCP servers (user scope)"
claude mcp get atlassian >/dev/null 2>&1 ||
  claude mcp add -s user -t sse atlassian https://mcp.atlassian.com/v1/sse
claude mcp get claude-design >/dev/null 2>&1 ||
  claude mcp add -s user -t http claude-design https://api.anthropic.com/v1/design/mcp

echo "done. run 'claude' then '/plugin list' to verify."
