#!/usr/bin/env python3
"""Assemble the one-download release zip for the Blueprint Wizard.

The zip unpacks to a single folder holding the runner and the pipeline
bundle as siblings, plus top-level double-click launchers and a
START_HERE.txt — so install is download → unzip → double-click. Contents
come from each repo's git HEAD (tracked files only), so commit before
cutting a release. Pure stdlib apart from the `git`, `tar`, and `zip`
commands.

Usage (from the runner repo):
    python3 scripts/make_release_bundle.py
    python3 scripts/make_release_bundle.py --output-dir dist --bundle-dir ../brightspace-blueprint-bundle
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUNNER_ROOT = Path(__file__).resolve().parents[1]

START_HERE = """\
Blueprint Wizard v{version} — turn a Brightspace/D2L course export into a
course blueprint (Markdown + DOCX + QA report), entirely on your machine.

To start:

  macOS    double-click "Blueprint Wizard.command"
           (first time only: if macOS warns about an unidentified
            developer, right-click the file and choose Open)
  Windows  double-click "Blueprint Wizard.bat"
  Linux    bash brightspace-blueprint-runner/blueprint_wizard.sh

There is nothing else to install by hand. On first run the wizard checks
your machine and asks permission before installing anything it needs
(Python 3.11+ if missing, plus its own Python packages in a private
.venv inside this folder). Your course export never leaves your machine.

The optional "DOCX visual render QA" step needs LibreOffice and Poppler —
the wizard offers those installs too, and every other output works
without them.

Folders:
  brightspace-blueprint-runner/   the wizard (what you launch)
  brightspace-blueprint-bundle/   the conversion pipeline the wizard drives

Full documentation: brightspace-blueprint-runner/README.md
"""

TOP_COMMAND = """\
#!/usr/bin/env bash
# Double-clickable launcher for the Blueprint Wizard (macOS).
exec bash "$(dirname "$0")/brightspace-blueprint-runner/blueprint_wizard.sh" "$@"
"""

TOP_BAT = """\
@echo off
rem Double-clickable launcher for the Blueprint Wizard (Windows).
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0brightspace-blueprint-runner\\blueprint_wizard.ps1" %*
set EXITCODE=%ERRORLEVEL%
rem When launched by double-click, keep the window open so results stay visible.
echo %cmdcmdline% | find /i "%~f0" >nul && pause
exit /b %EXITCODE%
"""


def read_version() -> str:
    wizard = (RUNNER_ROOT / "scripts" / "blueprint_wizard.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', wizard, flags=re.MULTILINE)
    if not match:
        raise SystemExit("Could not find VERSION in scripts/blueprint_wizard.py")
    return match.group(1)


def warn_if_dirty(repo: Path) -> None:
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if status:
        print(f"warning: {repo.name} has uncommitted changes; the zip is built "
              f"from HEAD and will not include them", file=sys.stderr)


def export_head(repo: Path, dest: Path) -> None:
    dest.mkdir(parents=True)
    archive = subprocess.Popen(
        ["git", "-C", str(repo), "archive", "HEAD"], stdout=subprocess.PIPE
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        raise SystemExit(f"git archive failed for {repo}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bundle-dir", type=Path,
        default=RUNNER_ROOT.parent / "brightspace-blueprint-bundle",
        help="Path to the brightspace-blueprint-bundle repo",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=RUNNER_ROOT / "dist",
        help="Directory for the finished zip (default: dist/)",
    )
    args = parser.parse_args()

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not (bundle_repo / "scripts" / "build_blueprint_bundle.py").exists():
        raise SystemExit(f"Not the pipeline bundle repo: {bundle_repo}")

    version = read_version()
    release_name = f"blueprint-wizard-v{version}"
    warn_if_dirty(RUNNER_ROOT)
    warn_if_dirty(bundle_repo)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{release_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / release_name
        export_head(RUNNER_ROOT, staging / "brightspace-blueprint-runner")
        export_head(bundle_repo, staging / "brightspace-blueprint-bundle")

        (staging / "START_HERE.txt").write_text(
            START_HERE.format(version=version), encoding="utf-8"
        )
        command = staging / "Blueprint Wizard.command"
        command.write_text(TOP_COMMAND, encoding="utf-8")
        command.chmod(0o755)
        (staging / "Blueprint Wizard.bat").write_text(TOP_BAT, encoding="utf-8")

        # zip via the CLI to preserve the launchers' executable bits
        subprocess.run(
            ["zip", "-rq", str(zip_path), release_name],
            cwd=tmp, check=True,
        )

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"built {zip_path}  ({size_mb:.1f} MB)")
    print(f"attach it to a GitHub release, e.g.:")
    print(f"  gh release create v{version} '{zip_path}' --title 'Blueprint Wizard v{version}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
