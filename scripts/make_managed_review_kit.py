#!/usr/bin/env python3
"""Build a one-unzip, explicitly unreleased stable-launcher review kit."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import make_release_bundle as release

RUNNER_ROOT = Path(__file__).resolve().parents[1]
MANAGED_BUILDER = RUNNER_ROOT / "scripts" / "make_managed_install_bundle.py"
CHECKLIST = RUNNER_ROOT / "docs" / "review" / "STABLE_LAUNCHER_REVIEW_CHECKLIST.md"
REPORT_TEMPLATE = (
    RUNNER_ROOT / "docs" / "review" / "STABLE_LAUNCHER_REPORT_TEMPLATE.md"
)
APP_FOLDER = "Blueprint Wizard - UNRELEASED REVIEW"
KIT_SCHEMA = "coursecraft.wizard_review_kit/1"


def kit_name(runner_commit: str) -> str:
    return f"UNRELEASED-blueprint-wizard-stable-launcher-review-{runner_commit[:7]}"


def review_readme(
    *,
    version: str,
    runner_commit: str,
    bundle_commit: str,
    candidate_sha256: str,
) -> str:
    return f"""\
BLUEPRINT WIZARD STABLE-LAUNCHER REVIEW KIT
===========================================

UNRELEASED TEST BUILD -- DO NOT REDISTRIBUTE OR USE AS A PRODUCTION INSTALL.

This kit is for hands-on review of the durable Blueprint Wizard launcher. It
is unsigned on both macOS and Windows and has not been notarized by Apple.
Security warnings on first launch are therefore expected and must be recorded
in the report rather than hidden or bypassed silently.

Candidate identity
------------------
Wizard version: v{version} (review build; not the published v{version} ZIP)
Runner commit: {runner_commit}
Bundle commit: {bundle_commit}
Candidate build SHA-256: {candidate_sha256}

Start here
----------
1. Read TEST_CHECKLIST.md before launching anything.
2. Open the folder "{APP_FOLDER}".
3. macOS: double-click "Blueprint Wizard.command".
   Windows: double-click "Blueprint Wizard.bat".
4. Record every Gatekeeper, SmartScreen, antivirus, or institutional-policy
   message exactly as shown.
5. Complete REPORT_TEMPLATE.md. Do not attach course exports or generated
   course content unless your institution has approved sharing them.

The entire review kit should be extracted into a new folder. Do not copy it
over an existing Blueprint Wizard installation. Generated work should remain
under the app folder's user-data/ directory and survive relaunches.

What this kit does not test
---------------------------
The public latest release is still v{version}, so this review cannot visibly
exercise a future A-to-B network update. Update, restart, rollback, corruption,
and cleanup behavior are covered by the recorded automated and fixture-backed
acceptance suite. A separate controlled two-version rehearsal can be prepared
without publishing a release.
"""


def extract_candidate(archive_path: Path, destination: Path) -> None:
    """Extract the locally built candidate beneath a reviewer-friendly name."""
    with zipfile.ZipFile(archive_path) as archive:
        files = archive.infolist()
        top_levels: set[str] = set()
        for info in files:
            name = info.filename.rstrip("/")
            if not name or "\\" in name:
                raise RuntimeError(f"Unexpected candidate ZIP member: {info.filename!r}")
            path = PurePosixPath(name)
            if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
                raise RuntimeError(f"Unsafe candidate ZIP member: {info.filename!r}")
            top_levels.add(path.parts[0])
        if len(top_levels) != 1:
            raise RuntimeError("Managed candidate must contain one top-level folder")

        for info in files:
            path = PurePosixPath(info.filename.rstrip("/"))
            relative = path.parts[1:]
            if not relative:
                continue
            target = destination.joinpath(*relative)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                target.chmod(mode)


def install_tree_manifest(app_root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(app_root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        files.append(
            {
                "path": path.relative_to(app_root).as_posix(),
                "bytes": path.stat().st_size,
                "mode": oct(path.stat().st_mode & 0o777),
                "sha256": release.sha256_file(path),
            }
        )
    return {
        "schema": "coursecraft.wizard_review_install_tree/1",
        "root": APP_FOLDER,
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-ref", required=True)
    parser.add_argument("--bundle-ref", required=True)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=RUNNER_ROOT.parent / "brightspace-blueprint-bundle",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RUNNER_ROOT / "dist" / "review",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv or sys.argv[1:])

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not args.allow_dirty:
        release.require_clean(RUNNER_ROOT)
        release.require_clean(bundle_repo)
    runner_commit = release.resolve_commit(RUNNER_ROOT, args.runner_ref)
    bundle_commit = release.resolve_commit(bundle_repo, args.bundle_ref)
    version = release.read_version(RUNNER_ROOT, runner_commit)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    name = kit_name(runner_commit)
    kit_zip = output_dir / f"{name}.zip"

    with tempfile.TemporaryDirectory() as tmp_text:
        tmp = Path(tmp_text)
        candidate_dir = tmp / "candidate"
        command = [
            sys.executable,
            str(MANAGED_BUILDER),
            "--runner-ref",
            runner_commit,
            "--bundle-ref",
            bundle_commit,
            "--bundle-dir",
            str(bundle_repo),
            "--output-dir",
            str(candidate_dir),
        ]
        if args.allow_dirty:
            command.append("--allow-dirty")
        subprocess.run(command, check=True)
        candidate_zip = candidate_dir / f"blueprint-wizard-managed-v{version}.zip"
        candidate_sha256 = release.sha256_file(candidate_zip)

        staging = tmp / name
        staging.mkdir()
        app_root = staging / APP_FOLDER
        app_root.mkdir()
        extract_candidate(candidate_zip, app_root)
        shutil.copy2(CHECKLIST, staging / "TEST_CHECKLIST.md")
        shutil.copy2(REPORT_TEMPLATE, staging / "REPORT_TEMPLATE.md")
        (staging / "READ_ME_FIRST.txt").write_text(
            review_readme(
                version=version,
                runner_commit=runner_commit,
                bundle_commit=bundle_commit,
                candidate_sha256=candidate_sha256,
            ),
            encoding="utf-8",
        )
        provenance = {
            "schema": KIT_SCHEMA,
            "status": "unreleased_review_only",
            "wizard_version": version,
            "runner": {
                "repository": release.normalized_remote(
                    release.run_git(RUNNER_ROOT, "remote", "get-url", "origin")
                ),
                "commit": runner_commit,
            },
            "bundle": {
                "repository": release.normalized_remote(
                    release.run_git(bundle_repo, "remote", "get-url", "origin")
                ),
                "commit": bundle_commit,
            },
            "candidate_zip_sha256": candidate_sha256,
            "distribution_security": {
                "macos_code_signed": False,
                "macos_notarized": False,
                "windows_code_signed": False,
            },
        }
        (staging / "PROVENANCE.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "INSTALL_TREE_MANIFEST.json").write_text(
            json.dumps(install_tree_manifest(app_root), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        release.deterministic_zip(staging, kit_zip)

    checksum = release.sha256_file(kit_zip)
    checksum_path = kit_zip.with_name(kit_zip.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {kit_zip.name}\n", encoding="utf-8")
    print(f"built {kit_zip}")
    print(f"sha256 {checksum}")
    print(f"runner {runner_commit}")
    print(f"bundle {bundle_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
