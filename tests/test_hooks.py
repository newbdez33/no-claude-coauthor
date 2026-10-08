import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
CLAUDE = "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="no-coauthor-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "guard with spaces"
        shutil.copytree(SOURCE, self.project, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update({
            "GIT_CONFIG_GLOBAL": str(self.root / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test User",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_EDITOR": ":",
        })
        self.run_cmd("git", "init", "-q", "-b", "main")

    def run_cmd(self, *args, ok=True):
        result = subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                                capture_output=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def install(self):
        return self.run_cmd("sh", str(self.project / "install.sh"))

    def hook(self, name, body):
        path = self.repo / ".git" / "hooks" / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def test_global_install_and_idempotence(self):
        self.install()
        self.install()
        result = self.run_cmd("git", "config", "--global", "--get-all", "core.hooksPath")
        self.assertEqual(result.stdout.strip(), str(self.project / "hooks"))
        self.run_cmd("git", "commit", "--allow-empty", "-m", "Clean commit")

    def test_rejects_attribution_without_creating_a_commit(self):
        self.install()
        for trailer in (CLAUDE, "co-authored-by: Claude <bot@example.com>",
                        "Co-authored-by: Model <NOREPLY@ANTHROPIC.COM>",
                        "  CO-AUTHORED-BY : Claude Code <bot@example.com>\r",
                        "🤖 Generated with [Claude Code](https://claude.com/claude-code)",
                        "Generated with Claude Code", "Claude-Session: https://claude.ai/code/session_test"):
            with self.subTest(trailer=trailer):
                result = self.run_cmd("git", "commit", "--allow-empty", "-m", "Change\n\n" + trailer, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no-claude-coauthor", result.stderr)
        self.assertNotEqual(self.run_cmd("git", "rev-parse", "--verify", "HEAD", ok=False).returncode, 0)

    def test_preserves_human_credit_and_normal_text(self):
        self.install()
        message = "Fix Claude Code integration\n\nCo-authored-by: Alice <alice@example.com>"
        self.run_cmd("git", "commit", "--allow-empty", "-m", message)
        self.assertEqual(self.run_cmd("git", "log", "-1", "--format=%B").stdout.strip(), message)

    def test_no_verify_still_checks_prepared_message(self):
        self.install()
        result = self.run_cmd("git", "commit", "--no-verify", "--allow-empty", "-m", "Change\n\n" + CLAUDE, ok=False)
        self.assertNotEqual(result.returncode, 0)

    def test_checks_file_messages(self):
        self.install()
        path = self.root / "message file"
        path.write_text("Change\n\n" + CLAUDE + "\n")
        result = self.run_cmd("git", "commit", "--allow-empty", "-F", str(path), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_text(), "Change\n\n" + CLAUDE + "\n")

    def test_checks_after_editor(self):
        self.install()
        editor = self.root / "editor.sh"
        editor.write_text('#!/bin/sh\nprintf "Change\\n\\n' + CLAUDE + '\\n" > "$1"\n')
        editor.chmod(0o755)
        self.env["GIT_EDITOR"] = str(editor)
        result = self.run_cmd("git", "commit", "--allow-empty", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no-claude-coauthor", result.stderr)

    def test_checks_after_repository_message_hooks(self):
        self.install()
        for name in ("prepare-commit-msg", "commit-msg"):
            with self.subTest(name=name):
                path = self.hook(name, 'printf "\\n' + CLAUDE + '\\n" >> "$1"')
                result = self.run_cmd("git", "commit", "--allow-empty", "-m", "Change", ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no-claude-coauthor", result.stderr)
                path.unlink()

    def test_preserves_repository_hook_failure(self):
        self.install()
        for name in ("pre-commit", "prepare-commit-msg", "commit-msg"):
            with self.subTest(name=name):
                path = self.hook(name, 'echo "local hook failed" >&2\nexit 42')
                result = self.run_cmd("git", "commit", "--allow-empty", "-m", "Change", ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("local hook failed", result.stderr)
                path.unlink()

    def test_forwards_arguments_and_stdin(self):
        self.install()
        self.hook("pre-push", 'printf "%s\\n" "$@" > args.txt\ncat > input.txt\nexit 23')
        result = subprocess.run([str(self.project / "hooks/pre-push"), "origin", "remote-url"],
                                input="ref data\n", text=True, env=self.env, cwd=self.repo)
        self.assertEqual(result.returncode, 23)
        self.assertEqual((self.repo / "args.txt").read_text(), "origin\nremote-url\n")
        self.assertEqual((self.repo / "input.txt").read_text(), "ref data\n")

    def test_refuses_existing_global_hook_configuration(self):
        for value in ("/some/existing/hooks", ""):
            with self.subTest(value=value):
                self.run_cmd("git", "config", "--global", "core.hooksPath", value)
                result = self.run_cmd("sh", str(self.project / "install.sh"), ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("existing global core.hooksPath", result.stderr)
                self.assertEqual(self.run_cmd("git", "config", "--global", "--get", "core.hooksPath").stdout.rstrip("\n"), value)

    def test_missing_message_fails_closed(self):
        result = self.run_cmd("sh", str(self.project / "bin/check-message"), str(self.root / "missing"), ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("expected a readable commit message file", result.stderr)

    def test_repository_symlink_does_not_recurse(self):
        self.install()
        path = self.repo / ".git/hooks/commit-msg"
        path.symlink_to(self.project / "hooks/commit-msg")
        self.run_cmd("git", "commit", "--allow-empty", "-m", "Change")

    def test_new_repositories_inherit_global_policy(self):
        self.install()
        self.repo = self.root / "new repo"
        self.repo.mkdir()
        self.run_cmd("git", "init", "-q", "-b", "main")
        result = self.run_cmd("git", "commit", "--allow-empty", "-m", "Change\n\n" + CLAUDE, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no-claude-coauthor", result.stderr)

    def test_forwards_reference_hook_during_git_init(self):
        self.install()
        template = self.root / "template"
        (template / "hooks").mkdir(parents=True)
        hook = template / "hooks/reference-transaction"
        hook.write_text('#!/bin/sh\necho "$1" >> "${GIT_DIR:-.git}/reference-hook.log"\n')
        hook.chmod(0o755)
        self.repo = self.root / "template repo"
        self.repo.mkdir()
        self.run_cmd("git", "init", "-q", "-b", "main", "--template", str(template))
        self.run_cmd("git", "commit", "--allow-empty", "-m", "Change")
        self.assertIn("committed", (self.repo / ".git/reference-hook.log").read_text())

    def test_amend_rejects_attribution_and_keeps_head(self):
        self.install()
        self.run_cmd("git", "commit", "--allow-empty", "-m", "Change")
        before = self.run_cmd("git", "rev-parse", "HEAD").stdout
        result = self.run_cmd("git", "commit", "--amend", "-m", "Change\n\n" + CLAUDE, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.run_cmd("git", "rev-parse", "HEAD").stdout, before)

    def test_git_trailer_argument_is_checked(self):
        self.install()
        result = self.run_cmd("git", "commit", "--allow-empty", "-m", "Change", "--trailer", CLAUDE, ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no-claude-coauthor", result.stderr)

    def test_patch_message_is_checked(self):
        self.install()
        path = self.root / "patch-message"
        path.write_text("Change\n\n" + CLAUDE + "\n")
        result = self.run_cmd(str(self.project / "hooks/applypatch-msg"), str(path), ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no-claude-coauthor", result.stderr)

    def test_local_override_is_a_documented_limit(self):
        self.install()
        self.run_cmd("git", "config", "--local", "core.hooksPath", "/dev/null")
        self.run_cmd("git", "commit", "--allow-empty", "-m", "Change\n\n" + CLAUDE)
        self.assertIn(CLAUDE, self.run_cmd("git", "log", "-1", "--format=%B").stdout)


if __name__ == "__main__":
    unittest.main()
