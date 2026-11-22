import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
CLEANUP_POLICY = {
    "boy-scout": False,
    "typescript-clean-code": False,
    "clean-comments": False,
    "clean-functions": True,
    "clean-general": True,
    "clean-names": True,
    "clean-tests": True,
}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-devkit-install-")
        self.addCleanup(self.directory.cleanup)
        workspace = Path(self.directory.name)
        self.home = workspace / "home"
        self.home.mkdir()
        self.config = self.home / ".codex/config.toml"
        self.checkout = workspace / "checkout"
        for name in [
            "install.sh",
            "scripts/install_codex.py", "scripts/install_claude.py", "scripts/install_shared.py",
            "codex/config.toml", "codex/skill-policy.toml", "codex/AGENTS.md",
        ]:
            target = self.checkout / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        shutil.copytree(ROOT / "codex/agents", self.checkout / "codex/agents")
        (self.checkout / "skills.toml").write_text("skill = []\n")

    def run_install(self):
        return subprocess.run(
            ["bash", str(self.checkout / "install.sh"), "--codex", "--home", str(self.home), "--skip-plugins"],
            capture_output=True, text=True,
        )

    def write_config(self, text):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(text)

    def test_fresh_install_has_one_user_catalog_and_no_claude_setup(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / ".agents/skills").resolve(), self.checkout / "skills")
        self.assertEqual((self.home / ".codex/AGENTS.md").resolve(), self.checkout / "codex/AGENTS.md")
        self.assertEqual((self.home / ".codex/agents").resolve(), self.checkout / "codex/agents")
        self.assertFalse((self.home / ".codex/skills").is_symlink())
        system = self.home / ".codex/skills/.system"
        self.assertFalse(system.exists())
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".gitconfig").exists())
        entries = tomllib.loads(self.config.read_text())["skills"]["config"]
        self.assertEqual(len(entries), 7)
        self.assertEqual({entry["name"]: entry["enabled"] for entry in entries}, CLEANUP_POLICY)

    def test_existing_config_and_mode_survive_repeat_installs(self):
        original = 'model = "chosen-model"\n\n[plugins.custom]\nenabled = true\n'
        old_policy = (self.checkout / "codex/skill-policy.toml").read_text().replace("enabled = true", "enabled = false")
        self.write_config(original + "\n# BEGIN ai-devkit skill policy\n" + old_policy + "# END ai-devkit skill policy\n")
        self.config.chmod(0o640)
        self.assertEqual(self.run_install().returncode, 0)
        first = self.config.read_bytes()
        self.assertTrue(first.startswith(original.rstrip("\n").encode()))
        self.assertEqual(tomllib.loads(first.decode())["plugins"]["custom"], {"enabled": True})
        entries = tomllib.loads(first.decode())["skills"]["config"]
        self.assertEqual({entry["name"]: entry["enabled"] for entry in entries}, CLEANUP_POLICY)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(self.config.read_bytes(), first)

    def test_claude_reenables_selected_cleanup_skills_on_repeat_installs(self):
        for name in (*CLEANUP_POLICY, "no-comments"):
            skill = self.checkout / "skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("fixture")
        policy = self.checkout / "codex/skill-policy.toml"
        current = policy.read_text()
        command = ["bash", str(self.checkout / "install.sh"), "--claude", "--home", str(self.home), "--skip-plugins"]
        policy.write_text(current.replace("enabled = true", "enabled = false"))
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.home / ".claude/skills"
        self.assertEqual({path.name for path in destination.iterdir()}, {"no-comments"})
        policy.write_text(current)
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {name for name, enabled in CLEANUP_POLICY.items() if enabled} | {"no-comments"}
            self.assertEqual({path.name for path in destination.iterdir()}, expected)
            for name in expected:
                self.assertTrue((destination / name).is_symlink())
                self.assertEqual((destination / name).resolve(), self.checkout / "skills" / name)

    def test_existing_custom_skill_directory_is_not_replaced(self):
        skill = self.home / ".agents/skills/custom/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("user-owned")
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(skill.read_text(), "user-owned")
        self.assertFalse(self.config.exists())
        self.assertFalse((self.home / ".codex/AGENTS.md").exists())

    def test_legacy_owned_skill_link_becomes_system_only(self):
        legacy = self.home / ".codex/skills"
        legacy.parent.mkdir(parents=True)
        bundled = self.checkout / "skills/.system"
        bundled.mkdir(parents=True)
        legacy.symlink_to(bundled.parent, target_is_directory=True)
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(legacy.is_symlink())
        system = legacy / ".system"
        self.assertEqual(system.resolve(), bundled)

    def test_foreign_legacy_link_is_preserved(self):
        other = self.home / "other-skills"
        other.mkdir()
        legacy = self.home / ".codex/skills"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(other)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(legacy.resolve(), other)
        self.assertFalse(self.config.exists())

    def test_invalid_config_is_unchanged_and_no_links_are_created(self):
        original = 'model = "unterminated\n'
        self.write_config(original)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(self.config.read_text(), original)
        self.assertFalse((self.home / ".agents/skills").exists())

    def test_broken_policy_markers_do_not_modify_config(self):
        original = 'model = "chosen-model"\n# BEGIN ai-devkit skill policy\n'
        self.write_config(original)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(self.config.read_text(), original)

    def test_existing_system_skills_are_preserved(self):
        sentinel = self.home / ".codex/skills/.system/managed/SKILL.md"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("managed by Codex")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(), "managed by Codex")
        self.assertFalse((self.home / ".codex/skills/.system").is_symlink())

    def test_claude_migrates_legacy_links_and_recovers_settings(self):
        config = self.home / ".claude"
        config.mkdir()
        catalog = self.checkout / "skills"
        catalog.mkdir()
        for name in ("CLAUDE.md", "agents", "skills", "settings.json"):
            (config / name).symlink_to(self.checkout / name)
        revision = "97acab9503e04a508694aeccecc1e3d8951668f5"
        git = ["git", "-C", str(self.checkout)]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["fetch", "-q", "--depth=1", str(ROOT), revision], check=True)
        original = json.loads(subprocess.check_output(git + ["show", f"{revision}:settings.json"]))
        command = ["bash", str(self.checkout / "install.sh"), "--claude", "--home", str(self.home), "--skip-plugins"]
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((config / "CLAUDE.md").resolve(), self.checkout / "codex/AGENTS.md")
            self.assertFalse((config / "agents").is_symlink())
            self.assertTrue((config / "agents/preflight.md").is_file())
            self.assertTrue((config / "agents/ticket-auditor.md").is_file())
            self.assertFalse((config / "skills").is_symlink())
            self.assertTrue((config / "skills").is_dir())
            settings = config / "settings.json"
            self.assertFalse(settings.is_symlink())
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(settings.read_text()), {k: v for k, v in original.items() if k != "hooks"})

    def test_claude_prefers_existing_legacy_settings_and_preserves_other_hooks(self):
        config = self.home / ".claude"
        config.mkdir()
        source = self.checkout / "settings.json"
        data = {"permissions": {"deny": ["Read(./private/**)"]}, "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo user-hook"}]},
        ]}}
        source.write_text(json.dumps(data))
        settings = config / "settings.json"
        settings.symlink_to(source)
        result = subprocess.run(
            ["bash", str(self.checkout / "install.sh"), "--claude", "--home", str(self.home), "--skip-plugins"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(settings.is_symlink())
        self.assertEqual(json.loads(settings.read_text()), data)
        self.assertEqual(json.loads(source.read_text()), data)

    def test_claude_stops_on_foreign_or_unrecoverable_settings_links(self):
        config = self.home / ".claude"
        config.mkdir()
        guidance = config / "CLAUDE.md"
        guidance.symlink_to(self.checkout / "CLAUDE.md")
        settings = config / "settings.json"
        for target, message in [
            (self.home / "foreign.json", "Conflicting settings link preserved"),
            (self.checkout / "settings.json", "Cannot recover"),
        ]:
            with self.subTest(target=target):
                settings.symlink_to(target)
                result = subprocess.run(
                    ["bash", str(self.checkout / "install.sh"), "--claude", "--home", str(self.home), "--skip-plugins"],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertEqual(settings.readlink(), target)
                self.assertEqual(guidance.readlink(), self.checkout / "CLAUDE.md")
                self.assertFalse((config / "agents").exists())
                settings.unlink()

    def test_checkout_without_bundled_system_skills_installs(self):
        checkout = self.checkout
        upstream = self.home / "upstream"
        subprocess.run(["git", "init", "-q", "--template=", upstream], check=True)
        skill = upstream / "catalog/demo/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("pinned fixture")
        skill.with_name("alias.md").symlink_to("SKILL.md")
        git = ["git", "-C", upstream]
        subprocess.run(git + ["add", "--", "catalog/demo"], check=True)
        subprocess.run(
            git + ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                   "-c", "commit.gpgsign=false",
                   "commit", "-qm", "test: add skill fixture"],
            check=True,
        )
        ref = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
        (checkout / "skills.toml").write_text(
            f'[[skill]]\nname = "demo"\nrepo = "{upstream.as_uri()}"\n'
            f'ref = "{ref}"\npath = "catalog/demo"\n'
        )
        target_home = self.home / "fresh-home"
        command = ["bash", str(checkout / "install.sh"), "--codex", "--home", str(target_home), "--skip-plugins"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        catalog = target_home / ".agents/skills"
        self.assertEqual(catalog.resolve(), checkout / "skills")
        self.assertEqual((catalog / "demo/SKILL.md").read_text(), "pinned fixture")
        self.assertEqual((catalog / "demo/alias.md").read_text(), "pinned fixture")
        self.assertTrue((target_home / ".codex/config.toml").is_file())
        for relative in ("skills/.system/example", "skills/boy-scout"):
            excluded = checkout / relative
            excluded.mkdir(parents=True)
            (excluded / "SKILL.md").write_text("not shared")
        claude_home = self.home / "claude-home"
        claude_skills = claude_home / ".claude/skills"
        claude_skills.mkdir(parents=True)
        local = claude_skills / "local"
        local.mkdir()
        (local / "SKILL.md").write_text("Claude only")
        claude = ["bash", str(checkout / "install.sh"), "--claude", "--home", str(claude_home), "--skip-plugins"]
        result = subprocess.run(claude, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((claude_home / ".claude/CLAUDE.md").resolve(), checkout / "codex/AGENTS.md")
        for name in ("preflight", "ticket-auditor"):
            definition = tomllib.loads((checkout / f"codex/agents/{name}.toml").read_text())
            agent = claude_home / f".claude/agents/{name}.md"
            self.assertTrue(agent.is_symlink())
            self.assertIn(f"name: {name}\n", agent.read_text())
            self.assertIn(definition["developer_instructions"].rstrip(), agent.read_text())
        self.assertEqual({p.name for p in claude_skills.iterdir()}, {"demo", "local"})
        self.assertEqual((local / "SKILL.md").read_text(), "Claude only")
        self.assertEqual((claude_skills / "demo").resolve(), (catalog / "demo").resolve())
        skill.write_text("latest fixture")
        subprocess.run(
            git + ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                   "-c", "commit.gpgsign=false",
                   "commit", "-qam", "test: update skill fixture"],
            check=True,
        )
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((catalog / "demo/SKILL.md").read_text(), "latest fixture")
        self.assertEqual((claude_skills / "demo/SKILL.md").read_text(), "latest fixture")
        updated = (catalog / "demo").resolve()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((catalog / "demo").resolve(), updated)
        upstream.rename(self.home / "offline")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((catalog / "demo").resolve(), updated)
        result = subprocess.run(command + ["--locked"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((catalog / "demo/SKILL.md").read_text(), "pinned fixture")

    def test_symlinked_config_is_not_followed_or_overwritten(self):
        original = self.home / "custom.toml"
        original.write_text('model = "custom"\n')
        self.config.parent.mkdir()
        self.config.symlink_to(original)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(original.read_text(), 'model = "custom"\n')

    def test_plugin_catalog_uses_each_clients_native_commands(self):
        (self.checkout / "plugins.toml").write_text(
            '[[plugin]]\nid = "demo@sample"\nsource = "https://github.com/example/sample.git"\n'
        )
        spec = importlib.util.spec_from_file_location(
            "shared_installer", self.checkout / "scripts/install_shared.py"
        )
        shared = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shared)
        with patch.object(shared.subprocess, "check_output", side_effect=[
            json.dumps({"marketplaces": []}),
            json.dumps([]),
            json.dumps([]),
            json.dumps([{"name": "sample"}]),
            json.dumps([{"id": "demo@sample", "scope": "user"}]),
        ]), patch.object(shared.subprocess, "run") as execute:
            shared.sync_plugins("codex", self.home / ".codex")
            shared.sync_plugins("claude", self.home / ".claude")
            shared.sync_plugins("claude", self.home / ".claude")
        self.assertEqual([call.args[0] for call in execute.call_args_list], [
            ["codex", "plugin", "marketplace", "add", "https://github.com/example/sample.git"],
            ["codex", "plugin", "add", "demo@sample"],
            ["claude", "plugin", "marketplace", "add", "example/sample"],
            ["claude", "plugin", "install", "demo@sample", "--scope", "user"],
            ["claude", "plugin", "marketplace", "update", "sample"],
            ["claude", "plugin", "update", "demo@sample", "--scope", "user"],
        ])
        self.assertEqual(execute.call_args_list[0].kwargs["env"]["CODEX_HOME"], str(self.home / ".codex"))
        self.assertEqual(execute.call_args_list[-1].kwargs["env"]["CLAUDE_CONFIG_DIR"], str(self.home / ".claude"))

    def test_installer_requires_one_client(self):
        for flags in ([], ["--codex", "--claude"], ["--claude", "--codex"]):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    ["bash", str(self.checkout / "install.sh"), *flags, "--home", str(self.home)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(list(self.home.iterdir()), [])
                self.assertFalse((self.checkout / ".skill-cache").exists())


if __name__ == "__main__":
    unittest.main()
