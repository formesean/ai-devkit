#!/usr/bin/env bash
set -euo pipefail

usage='ai-devkit | Installer

Set up shared skills, plugins, and working agreements for one client.

Usage:
  ./install.sh --codex  [options]
  ./install.sh --claude [options]

Options:
  --home PATH     Use a different home directory for client configuration.
  --locked        Install the exact skill revisions in skills.toml.
  --skip-plugins  Set up skills and guidance only.
  -h, --help      Show this help.'
case "${1:-}" in
  --codex) installer=install_codex.py ;;
  --claude) installer=install_claude.py ;;
  -h|--help) printf '%s\n' "$usage"; exit 0 ;;
  *) printf '%s\n' "$usage" >&2; exit 2 ;;
esac
shift

devkit_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$devkit_root/scripts/$installer" "$@"
