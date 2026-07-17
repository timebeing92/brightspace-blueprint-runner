#!/usr/bin/env python3
"""Validated pointer and receipt operations for managed Wizard installs."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

POINTER_SCHEMA = "coursecraft.wizard_install_pointer/1"
RELEASE_SCHEMA = "coursecraft.runner_release/1"
LAUNCH_RECEIPT_SCHEMA = "coursecraft.wizard_launch/1"
LAUNCHER_PROTOCOL = 1

RUNNER_REPOSITORY = "github.com/timebeing92/brightspace-blueprint-runner"
BUNDLE_REPOSITORY = "github.com/timebeing92/brightspace-blueprint-bundle"

INSTALL_ROOT_ENV = "BLUEPRINT_WIZARD_INSTALL_ROOT"
DATA_ROOT_ENV = "BLUEPRINT_WIZARD_DATA_ROOT"
OUTPUT_ROOT_ENV = "BLUEPRINT_WIZARD_OUTPUT_ROOT"
MANAGED_VERSION_ENV = "BLUEPRINT_WIZARD_MANAGED_VERSION"
LAUNCHER_PATH_ENV = "BLUEPRINT_WIZARD_LAUNCHER_PATH"


class InstallStateError(RuntimeError):
    """A managed install is incomplete, unsafe, or inconsistent."""


def utc_text() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def require_version(value: str) -> str:
    parsed = version_tuple(value)
    if parsed is None:
        raise InstallStateError(f"Invalid release version: {value!r}")
    return ".".join(str(part) for part in parsed)


def canonical_repository(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("git@") and ":" in text:
        text = text.split("@", 1)[1].replace(":", "/", 1)
    elif "://" in text:
        parts = urlsplit(text)
        text = f"{parts.hostname or ''}{parts.path}"
    return text.lower().removesuffix(".git").rstrip("/")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InstallStateError(f"Required file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallStateError(f"Could not read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallStateError(f"Expected a JSON object in {path}")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def pointer_path(install_root: Path) -> Path:
    return install_root / "current.json"


def version_root(install_root: Path, version: str) -> Path:
    normalized = require_version(version)
    return install_root / "versions" / normalized


def ensure_install_directories(install_root: Path) -> None:
    for relative in (
        "versions",
        "staging",
        "receipts",
        "user-data/settings",
        "user-data/logs",
        "user-data/outputs",
        "user-data/update-cache",
    ):
        (install_root / relative).mkdir(parents=True, exist_ok=True)


def validate_release_manifest(
    root: Path,
    *,
    expected_version: str | None = None,
) -> dict[str, Any]:
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = load_json(manifest_path)
    validate_manifest_payload(
        manifest,
        expected_version=expected_version,
        source=str(manifest_path),
    )

    required = (
        root / "brightspace-blueprint-runner" / "scripts" / "blueprint_wizard.py",
        root / "brightspace-blueprint-runner" / "blueprint_wizard.sh",
        root / "brightspace-blueprint-runner" / "blueprint_wizard.ps1",
        root / "brightspace-blueprint-bundle" / "scripts" / "build_blueprint_bundle.py",
        root / "brightspace-blueprint-bundle" / "requirements.txt",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        detail = "\n".join(f"  - {path}" for path in missing)
        raise InstallStateError(f"Release is missing required files:\n{detail}")
    return manifest


def validate_manifest_payload(
    manifest: dict[str, Any],
    *,
    expected_version: str | None = None,
    source: str = "release manifest",
) -> str:
    if manifest.get("schema") != RELEASE_SCHEMA:
        raise InstallStateError(
            f"Unsupported release manifest schema in {source}: "
            f"{manifest.get('schema')!r}"
        )
    version = require_version(str(manifest.get("version") or ""))
    if expected_version is not None and version != require_version(expected_version):
        raise InstallStateError(
            f"Release version mismatch: expected {expected_version}, found {version}"
        )

    for key, expected_repository in (
        ("runner", RUNNER_REPOSITORY),
        ("bundle", BUNDLE_REPOSITORY),
    ):
        record = manifest.get(key)
        if not isinstance(record, dict):
            raise InstallStateError(f"Release manifest is missing its {key} record")
        repository = canonical_repository(record.get("repository"))
        if repository != expected_repository:
            raise InstallStateError(
                f"Unexpected {key} repository in release: {repository or '(blank)'}"
            )
        commit = str(record.get("commit") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise InstallStateError(f"Invalid {key} commit in release manifest")

    contracts = manifest.get("contracts")
    if not isinstance(contracts, list) or len(contracts) < 3:
        raise InstallStateError("Release manifest is missing contract receipts")
    for contract in contracts:
        if not isinstance(contract, dict):
            raise InstallStateError("Release manifest contains an invalid contract receipt")
        if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("sha256") or "")):
            raise InstallStateError("Release manifest contains an invalid contract hash")
    return version


def validate_installed_version(
    install_root: Path,
    version: str,
) -> tuple[Path, dict[str, Any]]:
    normalized = require_version(version)
    root = version_root(install_root, normalized)
    if not root.is_dir():
        raise InstallStateError(f"Wizard version {normalized} is not installed")
    manifest = validate_release_manifest(root, expected_version=normalized)
    return root, manifest


def load_pointer(install_root: Path) -> dict[str, Any]:
    path = pointer_path(install_root)
    pointer = load_json(path)
    if pointer.get("schema") != POINTER_SCHEMA:
        raise InstallStateError(
            f"Unsupported install pointer schema: {pointer.get('schema')!r}"
        )
    if pointer.get("launcher_protocol") != LAUNCHER_PROTOCOL:
        raise InstallStateError(
            "This installation requires a different stable-launcher protocol"
        )
    current = require_version(str(pointer.get("current_version") or ""))
    previous_text = str(pointer.get("previous_version") or "").strip()
    previous = require_version(previous_text) if previous_text else ""
    if previous and previous == current:
        raise InstallStateError("Current and previous versions cannot be identical")
    pointer["current_version"] = current
    pointer["previous_version"] = previous
    validate_installed_version(install_root, current)
    if previous:
        validate_installed_version(install_root, previous)
    return pointer


def activate_version(install_root: Path, version: str) -> dict[str, Any]:
    ensure_install_directories(install_root)
    normalized = require_version(version)
    _, manifest = validate_installed_version(install_root, normalized)
    prior: dict[str, Any] = {}
    if pointer_path(install_root).exists():
        prior = load_pointer(install_root)
    prior_current = str(prior.get("current_version") or "")
    previous = (
        prior_current
        if prior_current and prior_current != normalized
        else str(prior.get("previous_version") or "")
    )
    pointer = {
        "schema": POINTER_SCHEMA,
        "launcher_protocol": LAUNCHER_PROTOCOL,
        "current_version": normalized,
        "previous_version": previous,
        "activated_at_utc": utc_text(),
        "runner_commit": manifest["runner"]["commit"],
        "bundle_commit": manifest["bundle"]["commit"],
    }
    atomic_write_json(pointer_path(install_root), pointer)
    return pointer


def rollback(install_root: Path) -> dict[str, Any]:
    pointer = load_pointer(install_root)
    previous = str(pointer.get("previous_version") or "")
    if not previous:
        raise InstallStateError("No previous Wizard version is available for rollback")
    current = pointer["current_version"]
    result = activate_version(install_root, previous)
    if result.get("previous_version") != current:
        raise InstallStateError("Rollback pointer did not preserve the prior current version")
    return result


def installed_versions(install_root: Path) -> list[str]:
    versions_dir = install_root / "versions"
    if not versions_dir.is_dir():
        return []
    versions: list[str] = []
    for path in versions_dir.iterdir():
        if not path.is_dir() or version_tuple(path.name) is None:
            continue
        try:
            validate_installed_version(install_root, path.name)
        except InstallStateError:
            continue
        versions.append(path.name)
    return sorted(versions, key=lambda value: version_tuple(value) or (0, 0, 0))


def managed_environment(
    install_root: Path,
    *,
    version: str,
    launcher_path: Path,
) -> dict[str, str]:
    normalized = require_version(version)
    data_root = install_root / "user-data"
    return {
        INSTALL_ROOT_ENV: str(install_root),
        DATA_ROOT_ENV: str(data_root),
        OUTPUT_ROOT_ENV: str(data_root / "outputs"),
        MANAGED_VERSION_ENV: normalized,
        LAUNCHER_PATH_ENV: str(launcher_path),
    }


def append_launch_receipt(install_root: Path, payload: dict[str, Any]) -> None:
    ensure_install_directories(install_root)
    path = install_root / "receipts" / "launches.jsonl"
    record = {
        "schema": LAUNCH_RECEIPT_SCHEMA,
        "recorded_at_utc": utc_text(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
