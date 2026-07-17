#!/usr/bin/env python3
"""Download, cross-check, and install the latest stable Wizard release."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

import install_release
import install_state

API_URL = (
    "https://api.github.com/repos/timebeing92/"
    "brightspace-blueprint-runner/releases/latest"
)
DOWNLOAD_PREFIX = (
    "/timebeing92/brightspace-blueprint-runner/releases/download/"
)
REQUEST_TIMEOUT_SECONDS = 10.0
DOWNLOAD_TIMEOUT_SECONDS = 60.0


class NetworkUpdateError(install_state.InstallStateError):
    """The public release could not be identified or downloaded safely."""


def fetch_latest_release() -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Blueprint-Wizard-Stable-Updater",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise NetworkUpdateError(f"Could not read the latest GitHub release: {exc}") from exc
    if not isinstance(payload, dict):
        raise NetworkUpdateError("GitHub returned an unexpected latest-release response")
    return payload


def safe_asset_url(value: object, *, version: str, name: str) -> str:
    text = str(value or "")
    parts = urllib.parse.urlsplit(text)
    expected_path = f"{DOWNLOAD_PREFIX}v{version}/{name}"
    if (
        parts.scheme != "https"
        or parts.netloc.lower() != "github.com"
        or parts.path != expected_path
        or parts.query
        or parts.fragment
    ):
        raise NetworkUpdateError(f"Unexpected release asset URL for {name}")
    return text


def select_release_assets(
    payload: dict[str, Any],
    *,
    expected_version: str | None = None,
) -> dict[str, str]:
    if payload.get("draft") or payload.get("prerelease"):
        raise NetworkUpdateError("Latest-release response is not a stable published release")
    version = install_state.require_version(str(payload.get("tag_name") or ""))
    if expected_version and version != install_state.require_version(expected_version):
        raise NetworkUpdateError(
            f"Release changed during update: expected {expected_version}, found {version}"
        )
    zip_name = f"blueprint-wizard-v{version}.zip"
    checksum_name = f"{zip_name}.sha256"
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise NetworkUpdateError("Latest release does not list downloadable assets")
    by_name = {
        str(asset.get("name") or ""): asset
        for asset in assets
        if isinstance(asset, dict)
    }
    zip_asset = by_name.get(zip_name)
    checksum_asset = by_name.get(checksum_name)
    if not isinstance(zip_asset, dict) or not isinstance(checksum_asset, dict):
        raise NetworkUpdateError(
            "Latest release is missing its Wizard ZIP or checksum sidecar"
        )
    digest_text = str(zip_asset.get("digest") or "")
    if not digest_text.startswith("sha256:"):
        raise NetworkUpdateError("Latest release ZIP does not expose a SHA-256 digest")
    digest = install_release.require_sha256(digest_text.split(":", 1)[1])
    return {
        "version": version,
        "zip_name": zip_name,
        "zip_url": safe_asset_url(
            zip_asset.get("browser_download_url"),
            version=version,
            name=zip_name,
        ),
        "checksum_name": checksum_name,
        "checksum_url": safe_asset_url(
            checksum_asset.get("browser_download_url"),
            version=version,
            name=checksum_name,
        ),
        "api_sha256": digest,
    }


def download_file(url: str, destination: Path, *, max_bytes: int) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Blueprint-Wizard-Stable-Updater"},
    )
    temporary = destination.with_name(destination.name + ".tmp")
    received = 0
    try:
        with urllib.request.urlopen(
            request,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response, temporary.open("wb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise NetworkUpdateError(f"Download exceeds the safety limit: {url}")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                received += len(block)
                if received > max_bytes:
                    raise NetworkUpdateError(f"Download exceeds the safety limit: {url}")
                output.write(block)
        os.replace(temporary, destination)
    except NetworkUpdateError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except (
        OSError,
        TimeoutError,
        ValueError,
        urllib.error.URLError,
    ) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise NetworkUpdateError(f"Could not download {url}: {exc}") from exc


Fetcher = Callable[[], dict[str, Any]]
Downloader = Callable[[str, Path], None]


def download_and_install_latest(
    install_root: Path,
    *,
    expected_version: str | None = None,
    fetcher: Fetcher = fetch_latest_release,
    downloader: Downloader | None = None,
) -> dict[str, Any]:
    install_root = install_root.expanduser().resolve()
    release = select_release_assets(
        fetcher(),
        expected_version=expected_version,
    )
    install_state.ensure_install_directories(install_root)
    download_dir = install_root / "staging" / f"download-{uuid.uuid4().hex}"
    download_dir.mkdir(parents=True)
    archive = download_dir / release["zip_name"]
    sidecar = download_dir / release["checksum_name"]

    def default_downloader(url: str, path: Path) -> None:
        limit = (
            install_release.MAX_ARCHIVE_BYTES
            if path.suffix == ".zip"
            else 16 * 1024
        )
        download_file(url, path, max_bytes=limit)

    transfer = downloader or default_downloader
    try:
        transfer(release["zip_url"], archive)
        transfer(release["checksum_url"], sidecar)
        sidecar_sha = install_release.checksum_from_sidecar(
            sidecar,
            archive_name=archive.name,
        )
        if sidecar_sha != release["api_sha256"]:
            raise NetworkUpdateError(
                "GitHub asset digest and published checksum sidecar do not match"
            )
        result = install_release.install_release_zip(
            install_root,
            archive,
            expected_sha256=release["api_sha256"],
            expected_version=release["version"],
            activate=True,
        )
        return {
            **result,
            "delivery": "github_release",
            "api_sha256": release["api_sha256"],
        }
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--expected-version")
    args = parser.parse_args(argv or sys.argv[1:])
    try:
        result = download_and_install_latest(
            args.install_root,
            expected_version=args.expected_version,
        )
    except install_state.InstallStateError as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
