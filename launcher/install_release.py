#!/usr/bin/env python3
"""Safely import a verified Blueprint Wizard release ZIP side by side."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import install_state

INSTALL_RECEIPT_SCHEMA = "coursecraft.wizard_version_install/1"
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ReleaseInstallError(install_state.InstallStateError):
    """A release archive failed verification or safe installation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ReleaseInstallError("Expected SHA-256 must contain exactly 64 hex characters")
    return normalized


def checksum_from_sidecar(path: Path, *, archive_name: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReleaseInstallError(f"Could not read checksum sidecar {path}: {exc}") from exc
    parts = text.split()
    if not parts:
        raise ReleaseInstallError(f"Checksum sidecar is empty: {path}")
    checksum = require_sha256(parts[0])
    if len(parts) > 1:
        recorded_name = parts[-1].lstrip("*")
        if recorded_name != archive_name:
            raise ReleaseInstallError(
                f"Checksum sidecar names {recorded_name!r}, not {archive_name!r}"
            )
    return checksum


def verified_checksum(
    archive: Path,
    *,
    expected_sha256: str | None = None,
    checksum_path: Path | None = None,
) -> str:
    if bool(expected_sha256) == bool(checksum_path):
        raise ReleaseInstallError(
            "Provide exactly one of an expected SHA-256 or a checksum sidecar"
        )
    expected = (
        require_sha256(expected_sha256 or "")
        if expected_sha256
        else checksum_from_sidecar(checksum_path or Path(), archive_name=archive.name)
    )
    actual = sha256_file(archive)
    if actual != expected:
        raise ReleaseInstallError(
            f"Release checksum mismatch: expected {expected}, found {actual}"
        )
    return actual


def validate_member_name(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise ReleaseInstallError(f"Unsafe ZIP member name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseInstallError(f"Unsafe ZIP member path: {name!r}")
    for part in path.parts:
        if part.endswith((" ", ".")) or ":" in part:
            raise ReleaseInstallError(f"Non-portable ZIP member path: {name!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED:
            raise ReleaseInstallError(f"Windows-reserved ZIP member path: {name!r}")
    return path


def validated_members(archive: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    members = archive.infolist()
    if not members or len(members) > MAX_ARCHIVE_FILES:
        raise ReleaseInstallError("Release ZIP has an invalid number of entries")
    total_size = 0
    top_levels: set[str] = set()
    seen: set[str] = set()
    for info in members:
        path = validate_member_name(info.filename.rstrip("/"))
        top_levels.add(path.parts[0])
        collision_key = "/".join(path.parts).casefold()
        if collision_key in seen:
            raise ReleaseInstallError(
                f"Release ZIP contains a duplicate or case-colliding path: {info.filename}"
            )
        seen.add(collision_key)
        if info.flag_bits & 0x1:
            raise ReleaseInstallError("Encrypted ZIP members are not supported")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise ReleaseInstallError(f"Release ZIP contains a symbolic link: {info.filename}")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ReleaseInstallError(f"Release member is too large: {info.filename}")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_BYTES:
            raise ReleaseInstallError("Release ZIP expands beyond the safety limit")
    if len(top_levels) != 1:
        raise ReleaseInstallError("Release ZIP must contain exactly one top-level folder")
    return next(iter(top_levels)), members


def read_archive_manifest(
    archive: zipfile.ZipFile,
    *,
    top_level: str,
    expected_version: str | None,
) -> tuple[str, dict[str, Any]]:
    member = f"{top_level}/RELEASE_MANIFEST.json"
    try:
        payload = json.loads(archive.read(member).decode("utf-8"))
    except KeyError as exc:
        raise ReleaseInstallError("Release ZIP is missing RELEASE_MANIFEST.json") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseInstallError(f"Release manifest is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseInstallError("Release manifest must be a JSON object")
    version = install_state.validate_manifest_payload(
        payload,
        expected_version=expected_version,
        source=f"{top_level}/RELEASE_MANIFEST.json",
    )
    return version, payload


def extract_members(
    archive: zipfile.ZipFile,
    *,
    members: list[zipfile.ZipInfo],
    destination: Path,
) -> None:
    for info in members:
        relative = validate_member_name(info.filename.rstrip("/"))
        target = destination.joinpath(*relative.parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        mode = (info.external_attr >> 16) & 0o777
        if mode:
            target.chmod(mode)


def install_receipt_path(version_root: Path) -> Path:
    return version_root / "INSTALL_RECEIPT.json"


def existing_version_matches(version_root: Path, checksum: str) -> bool:
    try:
        receipt = install_state.load_json(install_receipt_path(version_root))
    except install_state.InstallStateError:
        return False
    return (
        receipt.get("schema") == INSTALL_RECEIPT_SCHEMA
        and receipt.get("archive_sha256") == checksum
    )


def install_release_zip(
    install_root: Path,
    archive_path: Path,
    *,
    expected_sha256: str | None = None,
    checksum_path: Path | None = None,
    expected_version: str | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    install_root = install_root.expanduser().resolve()
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise ReleaseInstallError(f"Release ZIP not found: {archive_path}")
    checksum = verified_checksum(
        archive_path,
        expected_sha256=expected_sha256,
        checksum_path=checksum_path.expanduser().resolve() if checksum_path else None,
    )
    install_state.ensure_install_directories(install_root)
    with install_state.install_lock(install_root):
        return _install_verified_release(
            install_root,
            archive_path,
            checksum=checksum,
            expected_version=expected_version,
            activate=activate,
        )


def _install_verified_release(
    install_root: Path,
    archive_path: Path,
    *,
    checksum: str,
    expected_version: str | None,
    activate: bool,
) -> dict[str, Any]:

    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseInstallError(f"Release is not a valid ZIP archive: {exc}") from exc

    staging_job: Path | None = None
    try:
        with archive:
            top_level, members = validated_members(archive)
            version, manifest = read_archive_manifest(
                archive,
                top_level=top_level,
                expected_version=expected_version,
            )
            destination = install_state.version_root(install_root, version)
            if destination.exists():
                if not existing_version_matches(destination, checksum):
                    raise ReleaseInstallError(
                        f"Version {version} already exists with a different or missing receipt"
                    )
                install_state.validate_installed_version(install_root, version)
                pointer = (
                    install_state._activate_version(install_root, version)
                    if activate
                    else None
                )
                return {
                    "status": "already_installed",
                    "version": version,
                    "archive_sha256": checksum,
                    "activated": bool(activate),
                    "pointer": pointer,
                }

            staging_job = install_root / "staging" / (
                f"install-{version}-{uuid.uuid4().hex}"
            )
            staging_job.mkdir(parents=True)
            extract_members(archive, members=members, destination=staging_job)
            extracted_root = staging_job / top_level
            installed_manifest = install_state.validate_release_manifest(
                extracted_root,
                expected_version=version,
            )
            if installed_manifest != manifest:
                raise ReleaseInstallError("Extracted release manifest changed during install")
            receipt = {
                "schema": INSTALL_RECEIPT_SCHEMA,
                "version": version,
                "archive_name": archive_path.name,
                "archive_sha256": checksum,
                "installed_at_utc": install_state.utc_text(),
                "runner_commit": manifest["runner"]["commit"],
                "bundle_commit": manifest["bundle"]["commit"],
            }
            install_state.atomic_write_json(
                install_receipt_path(extracted_root),
                receipt,
            )
            os.replace(extracted_root, destination)
            pointer = (
                install_state._activate_version(install_root, version)
                if activate
                else None
            )
            return {
                "status": "installed",
                "version": version,
                "archive_sha256": checksum,
                "activated": bool(activate),
                "pointer": pointer,
            }
    finally:
        if staging_job and staging_job.exists():
            shutil.rmtree(staging_job, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Verified Wizard release ZIP")
    parser.add_argument("--install-root", type=Path, required=True)
    verification = parser.add_mutually_exclusive_group(required=True)
    verification.add_argument("--sha256", help="Expected release ZIP SHA-256")
    verification.add_argument("--checksum", type=Path, help="Published .sha256 sidecar")
    parser.add_argument("--expected-version")
    parser.add_argument("--no-activate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = install_release_zip(
            args.install_root,
            args.archive,
            expected_sha256=args.sha256,
            checksum_path=args.checksum,
            expected_version=args.expected_version,
            activate=not args.no_activate,
        )
    except install_state.InstallStateError as exc:
        print(f"Release install failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
