#!/usr/bin/env python3
"""Assemble the one-download release zip for the Blueprint Wizard.

The zip unpacks to a single folder holding the runner and the pipeline bundle
as siblings, plus top-level double-click launchers, START_HERE.txt, and a
machine-readable RELEASE_MANIFEST.json. Contents come from explicit commits;
the builder refuses dirty worktrees unless explicitly overridden and writes a
sidecar SHA-256 checksum.

Usage (from the runner repo):
    python3 scripts/make_release_bundle.py \
        --runner-ref <runner-sha> --bundle-ref <bundle-sha>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

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

Release provenance: RELEASE_MANIFEST.json
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


def read_version(repo: Path = RUNNER_ROOT, ref: str = "HEAD") -> str:
    wizard = run_git(repo, "show", f"{ref}:scripts/blueprint_wizard.py")
    match = re.search(r'^VERSION = "([^"]+)"', wizard, flags=re.MULTILINE)
    if not match:
        raise SystemExit("Could not find VERSION in scripts/blueprint_wizard.py")
    return match.group(1)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout.strip()


def require_clean(repo: Path) -> None:
    if run_git(repo, "status", "--porcelain"):
        raise RuntimeError(f"release repo is dirty: {repo}")


def resolve_commit(repo: Path, ref: str) -> str:
    return run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def export_ref(repo: Path, commit: str, dest: Path) -> None:
    dest.mkdir(parents=True)
    archive = subprocess.Popen(
        ["git", "-C", str(repo), "archive", commit], stdout=subprocess.PIPE
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {repo} at {commit}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def schema_receipt(bundle_root: Path) -> list[dict[str, str]]:
    rows = []
    for relative in (
        "schemas/blueprint_schema.json",
        "schemas/rubrics_schema.json",
        "schemas/progress_events_schema.json",
    ):
        path = bundle_root / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "schema": str(payload.get("$id") or ""),
                "path": f"brightspace-blueprint-bundle/{relative}",
                "sha256": sha256_file(path),
            }
        )
    return rows


def release_manifest(
    *,
    version: str,
    runner_ref: str,
    runner_commit: str,
    bundle_ref: str,
    bundle_commit: str,
    bundle_remote: str,
    bundle_root: Path,
) -> dict[str, Any]:
    return {
        "schema": "coursecraft.runner_release/1",
        "version": version,
        "runner": {
            "repository": run_git(RUNNER_ROOT, "remote", "get-url", "origin"),
            "ref": runner_ref,
            "commit": runner_commit,
        },
        "bundle": {
            "repository": bundle_remote,
            "ref": bundle_ref,
            "commit": bundle_commit,
        },
        "contracts": schema_receipt(bundle_root),
    }


def deterministic_zip(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            relative = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


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
    parser.add_argument("--runner-ref", required=True, help="Explicit runner git ref")
    parser.add_argument("--bundle-ref", required=True, help="Explicit bundle git ref")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Build explicit refs even when either working tree is dirty",
    )
    args = parser.parse_args()

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not (bundle_repo / "scripts" / "build_blueprint_bundle.py").exists():
        raise SystemExit(f"Not the pipeline bundle repo: {bundle_repo}")

    if not args.allow_dirty:
        require_clean(RUNNER_ROOT)
        require_clean(bundle_repo)

    runner_commit = resolve_commit(RUNNER_ROOT, args.runner_ref)
    bundle_commit = resolve_commit(bundle_repo, args.bundle_ref)

    version = read_version(RUNNER_ROOT, runner_commit)
    bundle_remote = run_git(bundle_repo, "remote", "get-url", "origin")
    release_name = f"blueprint-wizard-v{version}"

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{release_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / release_name
        runner_staging = staging / "brightspace-blueprint-runner"
        bundle_staging = staging / "brightspace-blueprint-bundle"
        export_ref(RUNNER_ROOT, runner_commit, runner_staging)
        export_ref(bundle_repo, bundle_commit, bundle_staging)

        (staging / "START_HERE.txt").write_text(
            START_HERE.format(version=version), encoding="utf-8"
        )
        manifest = release_manifest(
            version=version,
            runner_ref=args.runner_ref,
            runner_commit=runner_commit,
            bundle_ref=args.bundle_ref,
            bundle_commit=bundle_commit,
            bundle_remote=bundle_remote,
            bundle_root=bundle_staging,
        )
        (staging / "RELEASE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        command = staging / "Blueprint Wizard.command"
        command.write_text(TOP_COMMAND, encoding="utf-8")
        command.chmod(0o755)
        (staging / "Blueprint Wizard.bat").write_text(TOP_BAT, encoding="utf-8")

        deterministic_zip(staging, zip_path)

    checksum = sha256_file(zip_path)
    checksum_path = zip_path.with_name(zip_path.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"built {zip_path}  ({size_mb:.1f} MB)")
    print(f"sha256 {checksum}")
    print(f"checksum {checksum_path}")
    print("release manifest records:")
    print(f"  runner {runner_commit}")
    print(f"  bundle {bundle_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
