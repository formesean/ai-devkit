"""Shared catalog and marketplace setup for both clients."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parent.parent
REFERO_REPO = "https://github.com/NerdBaba/Design-MCP.git"
REFERO_REF = "b13d82a8d849e9a6a589a5f7cf90f3844514c20a"


def show_header(client, config_home):
    title = f"ai-devkit | {client} setup"
    print(f"{title}\n{'=' * len(title)}\nConfig: {config_home}", flush=True)


def sync_plugins(client, config_home):
    with (ROOT / "plugins.toml").open("rb") as stream:
        plugins = tomllib.load(stream)["plugin"]
    config_variable = "CODEX_HOME" if client == "codex" else "CLAUDE_CONFIG_DIR"
    env = {**os.environ, config_variable: str(config_home)}
    cli = [client, "plugin"]

    def query(*args):
        return json.loads(subprocess.check_output(cli + list(args) + ["--json"], env=env, text=True))

    def run(*args):
        try:
            subprocess.run(cli + list(args), env=env, check=True, stdout=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as error:
            if error.stdout:
                print(error.stdout.rstrip(), file=sys.stderr)
            raise

    print("\n[Plugins] Syncing the shared plugin catalog...", flush=True)
    markets = query("marketplace", "list")
    if client == "codex":
        markets = markets["marketplaces"]
    known = {entry["name"] for entry in markets}
    installed = set()
    if client == "claude":
        installed = {entry["id"] for entry in query("list") if entry.get("scope") == "user"}
    refreshed = set()
    for plugin in plugins:
        selector = plugin["id"]
        _, market = selector.split("@", 1)
        if market not in refreshed:
            if market not in known:
                source = plugin["source"]
                if client == "claude":
                    # Claude distinguishes GitHub shorthand from an equivalent Git URL.
                    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)\.git", source)
                    if match:
                        source = match[1]
                run("marketplace", "add", source)
            else:
                action = "upgrade" if client == "codex" else "update"
                run("marketplace", action, market)
            refreshed.add(market)
        if client == "codex":
            run("add", selector)
        else:
            action = "update" if selector in installed else "install"
            run(action, selector, "--scope", "user")
        print(f"  Ready: {selector}", flush=True)


def install_refero_server():
    cache = ROOT / ".mcp-cache"
    cache.mkdir(exist_ok=True)
    server = cache / f"refero-{REFERO_REF}"
    with (cache / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not server.exists():
            print("  Preparing the pinned Refero design server...", flush=True)
            with tempfile.TemporaryDirectory(dir=cache) as temporary:
                checkout = Path(temporary) / "server"
                subprocess.run(["git", "init", "-q", checkout], check=True)
                git = ["git", "-C", checkout]
                subprocess.run(git + ["fetch", "-q", "--depth", "1", "--", REFERO_REPO, REFERO_REF], check=True)
                subprocess.run(git + ["checkout", "-q", "--detach", REFERO_REF], check=True)
                subprocess.run(
                    ["npm", "ci", "--include=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
                    cwd=checkout, check=True,
                )
                checkout.rename(server)
    return [str(server / "node_modules/.bin/tsx"), str(server / "src/index.ts")]


def sync_mobile_design_mcp(client, config_home):
    config_variable = "CODEX_HOME" if client == "codex" else "CLAUDE_CONFIG_DIR"
    env = {**os.environ, config_variable: str(config_home)}
    scope = [] if client == "codex" else ["--scope", "user"]
    print("\n[MCP] Registering mobile design reference servers...", flush=True)
    servers = {
        "design-screenshots": lambda: ["npx", "--yes", "screenshots-design-inspiration-mcp@1.1.1"],
        "refero-design": install_refero_server,
    }
    for name, command in servers.items():
        cli = [client, "mcp"]
        existing = subprocess.run(cli + ["get", name], env=env, cwd=ROOT, capture_output=True)
        if existing.returncode == 0:
            print(f"  Preserved existing registration: {name}", flush=True)
            continue
        if existing.returncode != 1:
            existing.check_returncode()
        subprocess.run(cli + ["add", *scope, name, "--", *command()], env=env, cwd=ROOT, check=True)


def install_manifest_skills(locked=False):
    manifest = ROOT / "skills.toml"
    with manifest.open("rb") as stream:
        entries = tomllib.load(stream)["skill"]
    catalog = ROOT / "skills"
    catalog.mkdir(exist_ok=True)
    cache = ROOT / ".skill-cache"
    cache.mkdir(exist_ok=True)
    mode = "using manifest revisions" if locked else "checking upstream for updates"
    print(f"\n[Skills] Processing {len(entries)} catalog entries ({mode})...", flush=True)
    installed = updated = unchanged = overrides = 0
    with (cache / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        names = set()
        latest = {}
        for entry in entries:
            name, repo, ref, path = (entry[key] for key in ("name", "repo", "ref", "path"))
            source_path = Path(path)
            if (
                not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name)
                or name in names
                or not re.fullmatch(r"[0-9a-f]{40}", ref)
                or source_path.is_absolute()
                or ".." in source_path.parts
            ):
                raise ValueError(f"Invalid or duplicate skill entry: {name}")
            names.add(name)
            target = catalog / name
            managed = target.is_symlink() and target.resolve().parent == cache.resolve()
            if not managed and (target.exists() or target.is_symlink()):
                if not (target / "SKILL.md").is_file():
                    raise ValueError(f"Conflicting skill path preserved: {target}")
                overrides += 1
                continue
            if not locked and not entry.get("frozen", False):
                if repo not in latest:
                    output = subprocess.check_output(
                        ["git", "ls-remote", "--exit-code", "--", repo, "HEAD"], text=True
                    )
                    revision, separator, branch = output.strip().partition("\t")
                    if not separator or branch != "HEAD" or not re.fullmatch(r"[0-9a-f]{40}", revision):
                        raise ValueError(f"Invalid upstream HEAD for {name}: {repo}")
                    latest[repo] = revision
                ref = latest[repo]
            digest = hashlib.sha256(f"{repo}\n{ref}\n{path}".encode()).hexdigest()
            pinned = cache / digest
            if not (pinned / "SKILL.md").is_file():
                with tempfile.TemporaryDirectory(dir=cache) as temporary:
                    staging = Path(temporary)
                    checkout = staging / "checkout"
                    subprocess.run(["git", "init", "-q", checkout], check=True)
                    git = ["git", "-C", checkout]
                    subprocess.run(git + ["fetch", "-q", "--depth", "1", "--", repo, ref], check=True)
                    subprocess.run(git + ["checkout", "-q", "--detach", ref], check=True)
                    source = (checkout / source_path).resolve()
                    if (
                        not source.is_relative_to(checkout.resolve())
                        or not (source / "SKILL.md").is_file()
                    ):
                        raise ValueError(f"Invalid skill directory at {name}@{ref}: {path}")
                    for item in source.rglob("*"):
                        if not item.is_symlink():
                            continue
                        relative_target = Path(os.path.normpath(item.parent.relative_to(source) / item.readlink()))
                        resolved = item.resolve(strict=True)
                        if (
                            relative_target.is_absolute()
                            or ".." in relative_target.parts
                            or not resolved.is_relative_to(source)
                            or ".git" in resolved.relative_to(source).parts
                        ):
                            raise ValueError(f"Skill link leaves its payload at {name}@{ref}: {item.relative_to(source)}")
                    payload = staging / "skill"
                    shutil.copytree(source, payload, symlinks=True, ignore=shutil.ignore_patterns(".git"))
                    license_file = checkout / "LICENSE"
                    if license_file.is_file() and not license_file.is_symlink() and not (payload / "LICENSE").exists():
                        shutil.copyfile(license_file, payload / "LICENSE")
                    payload.rename(pinned)
            if managed and target.resolve() == pinned.resolve():
                unchanged += 1
                continue
            if managed:
                with tempfile.TemporaryDirectory(dir=catalog) as temporary:
                    link = Path(temporary) / name
                    link.symlink_to(pinned, target_is_directory=True)
                    link.replace(target)
                updated += 1
            else:
                target.symlink_to(pinned, target_is_directory=True)
                installed += 1
    print(f"  {installed} installed, {updated} updated, {unchanged} current, {overrides} local overrides kept", flush=True)
