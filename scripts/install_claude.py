#!/usr/bin/env python3
"""Set up Claude Code with the shared skill and plugin catalogs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib

from install_shared import ROOT, install_manifest_skills, show_header, sync_plugins


def install_agents(config_home):
    source = ROOT / "codex/agents"
    generated = config_home / "ai-devkit/agents"
    destination = config_home / "agents"
    agents = {}
    for path in sorted(source.glob("*.toml")):
        with path.open("rb") as stream:
            agent = tomllib.load(stream)
        if agent["name"] != path.stem:
            raise ValueError(f"Agent name must match its filename: {path}")
        agents[path.with_suffix(".md").name] = (
            f"---\nname: {agent['name']}\n"
            f"description: {json.dumps(agent['description'], ensure_ascii=False)}\n"
            "disallowedTools: Edit, Write, NotebookEdit, Agent\n"
            f"---\n\n{agent['developer_instructions'].rstrip()}\n"
        )

    if destination.is_symlink() or destination.exists() and not destination.is_dir():
        raise ValueError(f"Conflicting agent directory preserved: {destination}")
    for name in agents:
        link = destination / name
        if link.is_symlink() and link.readlink() == generated / name:
            continue
        if link.exists() or link.is_symlink():
            raise ValueError(f"Existing agent preserved: {link}")

    generated.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in agents.items():
        with tempfile.TemporaryDirectory(dir=generated) as temporary:
            path = Path(temporary) / name
            path.write_text(content)
            path.replace(generated / name)
        link = destination / name
        if not link.is_symlink():
            link.symlink_to(generated / name)
    for link in destination.iterdir():
        if link.name not in agents and link.is_symlink() and link.readlink() == generated / link.name:
            link.unlink()


def install(config_home, locked):
    catalog = ROOT / "skills"
    destination = config_home / "skills"
    guidance = config_home / "CLAUDE.md"
    guidance_source = ROOT / "codex/AGENTS.md"
    if guidance.is_symlink():
        if guidance.resolve() != guidance_source:
            raise ValueError(f"Conflicting guidance link preserved: {guidance}")
    elif guidance.exists():
        raise ValueError(f"Existing guidance preserved: {guidance}")
    legacy = destination.is_symlink() and destination.resolve() == catalog
    if not legacy and (destination.is_symlink() or destination.exists() and not destination.is_dir()):
        raise ValueError(f"Conflicting skill directory preserved: {destination}")

    install_manifest_skills(locked=locked)
    with (ROOT / "codex/skill-policy.toml").open("rb") as stream:
        disabled = {
            entry["name"] for entry in tomllib.load(stream)["skills"]["config"] if not entry["enabled"]
        }
    shared = {
        source.name: source for source in catalog.iterdir()
        if not source.name.startswith(".") and source.name not in disabled and (source / "SKILL.md").is_file()
    }
    if not legacy:
        for name, source in shared.items():
            link = destination / name
            if link.is_symlink() and link.readlink() == source:
                continue
            if link.exists() or link.is_symlink():
                raise ValueError(f"Existing skill preserved: {link}")
    install_agents(config_home)
    if legacy:
        destination.unlink()
    destination.mkdir(parents=True, exist_ok=True)
    for link in destination.iterdir():
        if link.name not in shared and link.is_symlink() and link.readlink() == catalog / link.name:
            link.unlink()
    for name, source in shared.items():
        link = destination / name
        if not link.is_symlink():
            link.symlink_to(source, target_is_directory=True)
    if not guidance.is_symlink():
        guidance.symlink_to(guidance_source)


def main():
    parser = argparse.ArgumentParser(prog="./install.sh --claude", description=__doc__)
    parser.add_argument("--home", type=Path, help="Target a disposable or alternate home directory")
    parser.add_argument("--locked", action="store_true", help="Use the exact revisions in skills.toml")
    parser.add_argument("--skip-plugins", action="store_true", help="Only set up guidance and skills")
    args = parser.parse_args()
    home = (args.home or Path.home()).expanduser().resolve()
    config_home = home / ".claude" if args.home else Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    ).expanduser().resolve()
    try:
        show_header("Claude Code", config_home)
        install(config_home, args.locked)
        print("\n[Config] Working agreements and agents are ready.", flush=True)
        if args.skip_plugins:
            print("\n[Plugins] Skipped (--skip-plugins).", flush=True)
        else:
            sync_plugins("claude", config_home)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"\nSetup stopped: {error}\n")
    print("\nSetup complete. Start a new Claude Code session to load changes.")


if __name__ == "__main__":
    main()
