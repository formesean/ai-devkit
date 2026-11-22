#!/usr/bin/env python3
"""Wire the local Codex catalog and preserve config outside the managed policy."""

import argparse
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import tomllib


from install_shared import ROOT, install_manifest_skills, show_header, sync_plugins
START = "# BEGIN ai-devkit skill policy"
END = "# END ai-devkit skill policy"


def render_config(path):
    if path.is_symlink():
        raise ValueError(f"Refusing to rewrite a symlinked config: {path}")
    text = path.read_text() if path.exists() else (ROOT / "codex/config.toml").read_text()
    tomllib.loads(text)
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("Malformed ai-devkit policy markers; config preserved")
        before, rest = text.split(START, 1)
        if END not in rest:
            raise ValueError("Malformed ai-devkit policy markers; config preserved")
        _, after = rest.split(END, 1)
    else:
        before, after = text, ""
    policy = (ROOT / "codex/skill-policy.toml").read_text().rstrip()
    rendered = before.rstrip("\n") + "\n\n" + START + "\n" + policy + "\n" + END + after
    if not rendered.endswith("\n"):
        rendered += "\n"
    tomllib.loads(rendered)
    return rendered


def install(home, codex_home, locked=False):
    config = codex_home / "config.toml"
    rendered = render_config(config)
    legacy = codex_home / "skills"
    migrate_legacy = legacy.is_symlink() and legacy.resolve() == ROOT / "skills"
    if legacy.is_symlink() and not migrate_legacy:
        raise ValueError(f"Conflicting legacy skill link preserved: {legacy}")
    links = [
        (ROOT / "skills", home / ".agents/skills"),
        (ROOT / "codex/AGENTS.md", codex_home / "AGENTS.md"),
        (ROOT / "codex/agents", codex_home / "agents"),
    ]
    system_source = ROOT / "skills/.system"
    system_target = legacy / ".system"
    if system_source.exists() and (migrate_legacy or not (system_target.exists() or system_target.is_symlink())):
        links.append((system_source, system_target))
    for source, target in links:
        if source != ROOT / "skills" and not source.exists():
            raise ValueError(f"Missing source: {source}")
        if migrate_legacy and target == legacy / ".system":
            continue
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError(f"Conflicting link preserved: {target}")
        elif target.exists():
            raise ValueError(f"Existing path preserved; reconcile it first: {target}")
    install_manifest_skills(locked=locked)
    if migrate_legacy:
        legacy.unlink()
    for source, target in links:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source, target_is_directory=source.is_dir())
    current = config.read_text() if config.exists() else None
    if current != rendered:
        mode = stat.S_IMODE(config.stat().st_mode) if config.exists() else 0o600
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=codex_home, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(rendered)
            temporary.chmod(mode)
            temporary.replace(config)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(prog="./install.sh --codex", description=__doc__)
    parser.add_argument("--home", type=Path, help="Target a disposable or alternate home directory")
    parser.add_argument("--locked", action="store_true", help="Use the exact revisions in skills.toml")
    parser.add_argument("--skip-plugins", action="store_true", help="Only set up guidance and skills")
    args = parser.parse_args()
    home = (args.home or Path.home()).expanduser().resolve()
    codex_home = home / ".codex" if args.home else Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().resolve()
    try:
        show_header("Codex", codex_home)
        install(home, codex_home, locked=args.locked)
        print("\n[Config] Working agreements, agents, and skill policy are ready.", flush=True)
        if args.skip_plugins:
            print("\n[Plugins] Skipped (--skip-plugins).", flush=True)
        else:
            sync_plugins("codex", codex_home)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"\nSetup stopped: {error}\n")
    print("\nSetup complete. Start a new Codex session to load changes.")


if __name__ == "__main__":
    main()
