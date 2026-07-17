from __future__ import annotations

import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE_MODULE = ROOT / "scripts" / "update_installer_compatibility.py"
SPEC = importlib.util.spec_from_file_location(
    "update_installer_compatibility", UPDATE_MODULE
)
assert SPEC and SPEC.loader
compatibility = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compatibility)
VERSION_TEXT = (ROOT / "scripts" / "blueprint_wizard.py").read_text(encoding="utf-8")
VERSION_MATCH = re.search(r'^VERSION = "([^"]+)"', VERSION_TEXT, flags=re.MULTILINE)
assert VERSION_MATCH
CURRENT_VERSION = VERSION_MATCH.group(1)


def run_launcher(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    run_git(repo, "add", ".")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Launcher Test",
            "-c",
            "user.email=launcher-test@example.invalid",
            "commit",
            "-m",
            message,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return run_git(repo, "rev-parse", "HEAD")


class LauncherTests(unittest.TestCase):
    def test_macos_and_posix_launchers_report_current_version(self) -> None:
        for command in (
            ("bash", "Blueprint Wizard.command", "--version"),
            ("bash", "blueprint_wizard.sh", "--version"),
            (sys.executable, "scripts/blueprint_wizard.py", "--version"),
        ):
            with self.subTest(command=command):
                result = run_launcher(*command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout.strip(), f"blueprint-wizard v{CURRENT_VERSION}"
                )

    def test_macos_and_posix_launchers_are_executable(self) -> None:
        for name in (
            "Blueprint Wizard.command",
            "blueprint_wizard.sh",
            "launcher/blueprint_wizard_launcher.sh",
        ):
            with self.subTest(name=name):
                mode = (ROOT / name).stat().st_mode
                self.assertTrue(mode & stat.S_IXUSR)

    def test_stable_posix_launcher_has_valid_shell_syntax(self) -> None:
        result = run_launcher(
            "bash",
            "-n",
            "launcher/blueprint_wizard_launcher.sh",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is not installed")
    def test_stable_powershell_launcher_parses(self) -> None:
        result = run_launcher(
            "pwsh",
            "-NoProfile",
            "-Command",
            (
                "$errors = $null; "
                "[System.Management.Automation.Language.Parser]::ParseFile("
                "'launcher/blueprint_wizard_launcher.ps1', [ref]$null, "
                "[ref]$errors) | Out-Null; "
                "if ($errors.Count) { $errors | Out-String; exit 1 }"
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is not installed")
    def test_powershell_launcher_reports_current_version(self) -> None:
        result = run_launcher(
            "pwsh",
            "-NoProfile",
            "-File",
            "./blueprint_wizard.ps1",
            "--version",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(), f"blueprint-wizard v{CURRENT_VERSION}"
        )

    def test_windows_batch_delegates_and_preserves_exit_status(self) -> None:
        text = (ROOT / "Blueprint Wizard.bat").read_text(encoding="utf-8")
        self.assertIn(r'%~dp0blueprint_wizard.ps1', text)
        self.assertIn("set EXITCODE=%ERRORLEVEL%", text)
        self.assertIn("exit /b %EXITCODE%", text)

    def test_installer_lock_is_generated_and_uses_release_identities(self) -> None:
        text = (ROOT / "installer-compatibility.lock").read_text(encoding="utf-8")
        values = {}
        for line in text.splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
        self.assertEqual(values["schema"], "coursecraft.runner_compatibility/1")
        self.assertRegex(values["runner_ref"], r"^v[0-9][0-9A-Za-z._-]*$")
        self.assertRegex(values["bundle_ref"], r"^v[0-9][0-9A-Za-z._-]*$")
        self.assertRegex(values["runner_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(values["bundle_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(
            text,
            compatibility.render_lock(
                runner_ref=values["runner_ref"],
                runner_commit=values["runner_commit"],
                bundle_ref=values["bundle_ref"],
                bundle_commit=values["bundle_commit"],
            ),
        )

    def test_installer_checks_out_verified_commits(self) -> None:
        text = (ROOT / "install_blueprint_wizard.sh").read_text(encoding="utf-8")
        self.assertIn("installer-compatibility.lock", text)
        self.assertIn('if [ "$resolved" != "$expected_commit" ]', text)
        self.assertIn('checkout --quiet --detach "$expected_commit"', text)
        self.assertIn("INSTALL_RECEIPT.txt", text)

    def test_installer_fetches_and_records_one_verified_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remotes = root / "remotes"
            remotes.mkdir()
            runner_remote = remotes / "brightspace-blueprint-runner.git"
            bundle_remote = remotes / "brightspace-blueprint-bundle.git"
            run_git(root, "init", "--bare", str(runner_remote))
            run_git(root, "init", "--bare", str(bundle_remote))

            bundle_work = root / "bundle-work"
            run_git(root, "init", "-b", "main", str(bundle_work))
            (bundle_work / "README.md").write_text("fixture bundle\n", encoding="utf-8")
            bundle_commit = commit_all(bundle_work, "Fixture bundle release")
            run_git(bundle_work, "tag", "v8.2.0")
            run_git(bundle_work, "remote", "add", "origin", str(bundle_remote))
            run_git(bundle_work, "push", "origin", "main", "v8.2.0")

            runner_work = root / "runner-work"
            run_git(root, "init", "-b", "main", str(runner_work))
            fixture_launcher = runner_work / "blueprint_wizard.sh"
            fixture_launcher.write_text(
                "#!/usr/bin/env bash\nprintf 'fixture wizard ran\\n'\n",
                encoding="utf-8",
            )
            fixture_launcher.chmod(0o755)
            runner_commit = commit_all(runner_work, "Fixture runner release")
            run_git(runner_work, "tag", "v9.1.0")
            (runner_work / "installer-compatibility.lock").write_text(
                compatibility.render_lock(
                    runner_ref="v9.1.0",
                    runner_commit=runner_commit,
                    bundle_ref="v8.2.0",
                    bundle_commit=bundle_commit,
                ),
                encoding="utf-8",
            )
            commit_all(runner_work, "Record compatible fixture pair")
            run_git(runner_work, "remote", "add", "origin", str(runner_remote))
            run_git(runner_work, "push", "origin", "main", "v9.1.0")

            target = root / "installed"
            result = subprocess.run(
                ["bash", str(ROOT / "install_blueprint_wizard.sh"), str(target)],
                cwd=root,
                env={
                    **os.environ,
                    "BLUEPRINT_WIZARD_REPO_BASE": str(remotes),
                },
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Verified pair: runner v9.1.0 + bundle v8.2.0", result.stdout)
            self.assertIn("No terminal available", result.stdout)
            self.assertEqual(
                run_git(
                    target / "brightspace-blueprint-runner", "rev-parse", "HEAD"
                ),
                runner_commit,
            )
            self.assertEqual(
                run_git(
                    target / "brightspace-blueprint-bundle", "rev-parse", "HEAD"
                ),
                bundle_commit,
            )
            receipt = (target / "INSTALL_RECEIPT.txt").read_text(encoding="utf-8")
            self.assertIn(f"runner_commit={runner_commit}", receipt)
            self.assertIn(f"bundle_commit={bundle_commit}", receipt)

            rerun = subprocess.run(
                ["bash", str(ROOT / "install_blueprint_wizard.sh"), str(target)],
                cwd=root,
                env={
                    **os.environ,
                    "BLUEPRINT_WIZARD_REPO_BASE": str(remotes),
                },
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertIn("already present", rerun.stdout)

    def test_release_tag_validation_rejects_moving_branches(self) -> None:
        for invalid in ("main", "HEAD", "feature/test", "v"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    compatibility.resolve_release(ROOT, invalid)
        self.assertTrue(re.fullmatch(r"v[0-9][0-9A-Za-z._-]*", "v2.5.1"))


if __name__ == "__main__":
    unittest.main()
