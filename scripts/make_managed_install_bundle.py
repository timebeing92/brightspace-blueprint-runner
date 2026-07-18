#!/usr/bin/env python3
"""Build the managed stable-launcher package from explicit git refs."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import make_release_bundle as release

RUNNER_ROOT = Path(__file__).resolve().parents[1]

START_HERE = """\
Blueprint Wizard managed installation v{version}

This package keeps complete Wizard releases under versions/, persistent work
under user-data/, and selects the active release through current.json.

To start:

  macOS    double-click "Blueprint Wizard.command"
  Windows  double-click "Blueprint Wizard.bat"
  Linux    bash blueprint_wizard_launcher.sh

The initial active version is v{version}. The launcher never mixes runner and
bundle versions. Settings, logs, update cache, and generated outputs remain
outside version folders so rollback and later cleanup cannot remove user work.

When a future release is available, the Wizard can install the verified
runner/bundle pair beside the current version after asking permission. It
checks the GitHub asset digest, published SHA-256 sidecar, release manifest,
repository identities, exact commits, runtime files, and contract hashes
before activation. A one-time restart completes the switch. The prior complete
version remains available for rollback, and old-version removal is explicit.

This v{version} package is unsigned and is not notarized by Apple. macOS may
require right-clicking "Blueprint Wizard.command" and choosing Open on first
launch; Windows or institution-managed devices may show an equivalent trust
prompt. Do not weaken system-wide security settings.

Install checks and maintenance commands:

  bash blueprint_wizard_launcher.sh --health
  bash blueprint_wizard_launcher.sh --list-versions
  bash blueprint_wizard_launcher.sh --rollback

Old-version removal is always explicit. The active version can never be
selected, and the rollback version stays protected until the replacement has
completed a successful launch.
"""

TOP_COMMAND = """\
#!/usr/bin/env bash
# Stable double-clickable launcher for macOS.
exec bash "$(dirname "$0")/blueprint_wizard_launcher.sh" "$@"
"""

TOP_BAT = """\
@echo off
rem Stable double-clickable launcher for Windows.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0blueprint_wizard_launcher.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo %cmdcmdline% | find /i "%~f0" >nul && pause
exit /b %EXITCODE%
"""


def initial_pointer(version: str, manifest: dict) -> dict:
    return {
        "schema": "coursecraft.wizard_install_pointer/1",
        "launcher_protocol": 1,
        "current_version": version,
        "previous_version": "",
        "activated_at_utc": "1980-01-01T00:00:00Z",
        "runner_commit": manifest["runner"]["commit"],
        "bundle_commit": manifest["bundle"]["commit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-ref", required=True)
    parser.add_argument("--bundle-ref", required=True)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=RUNNER_ROOT.parent / "brightspace-blueprint-bundle",
    )
    parser.add_argument("--output-dir", type=Path, default=RUNNER_ROOT / "dist")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not args.allow_dirty:
        release.require_clean(RUNNER_ROOT)
        release.require_clean(bundle_repo)
    runner_commit = release.resolve_commit(RUNNER_ROOT, args.runner_ref)
    bundle_commit = release.resolve_commit(bundle_repo, args.bundle_ref)
    version = release.read_version(RUNNER_ROOT, runner_commit)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"blueprint-wizard-managed-v{version}"
    zip_path = output_dir / f"{package_name}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / package_name
        version_root = staging / "versions" / version
        runner_staging = version_root / "brightspace-blueprint-runner"
        bundle_staging = version_root / "brightspace-blueprint-bundle"
        release.export_ref(RUNNER_ROOT, runner_commit, runner_staging)
        release.export_ref(bundle_repo, bundle_commit, bundle_staging)
        manifest = release.release_manifest(
            version=version,
            runner_ref=args.runner_ref,
            runner_commit=runner_commit,
            bundle_ref=args.bundle_ref,
            bundle_commit=bundle_commit,
            bundle_remote=release.normalized_remote(
                release.run_git(bundle_repo, "remote", "get-url", "origin")
            ),
            bundle_root=bundle_staging,
        )
        (version_root / "RELEASE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        shutil.copytree(runner_staging / "launcher", staging / "launcher")
        shell = staging / "blueprint_wizard_launcher.sh"
        shutil.copy2(
            runner_staging / "launcher" / "blueprint_wizard_launcher.sh",
            shell,
        )
        shell.chmod(0o755)
        shutil.copy2(
            runner_staging / "launcher" / "blueprint_wizard_launcher.ps1",
            staging / "blueprint_wizard_launcher.ps1",
        )
        command = staging / "Blueprint Wizard.command"
        command.write_text(TOP_COMMAND, encoding="utf-8")
        command.chmod(0o755)
        (staging / "Blueprint Wizard.bat").write_text(TOP_BAT, encoding="utf-8")
        (staging / "START_HERE.txt").write_text(
            START_HERE.format(version=version),
            encoding="utf-8",
        )
        (staging / "current.json").write_text(
            json.dumps(initial_pointer(version, manifest), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        (staging / "MANAGED_INSTALL_MANIFEST.json").write_text(
            json.dumps(
                {
                    "schema": "coursecraft.wizard_managed_package/1",
                    "launcher_protocol": 1,
                    "initial_version": version,
                    "runner_commit": runner_commit,
                    "bundle_commit": bundle_commit,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        release.deterministic_zip(staging, zip_path)

    checksum = release.sha256_file(zip_path)
    checksum_path = zip_path.with_name(zip_path.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    print(f"built {zip_path}")
    print(f"sha256 {checksum}")
    print(f"runner {runner_commit}")
    print(f"bundle {bundle_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
