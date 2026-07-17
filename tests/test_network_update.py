from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))
sys.path.insert(0, str(ROOT / "tests"))

import install_state  # noqa: E402
import network_update  # noqa: E402
from test_release_install import make_release_zip  # noqa: E402


def api_payload(version: str, checksum: str) -> dict:
    base = (
        "https://github.com/timebeing92/brightspace-blueprint-runner/"
        f"releases/download/v{version}"
    )
    zip_name = f"blueprint-wizard-v{version}.zip"
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": zip_name,
                "browser_download_url": f"{base}/{zip_name}",
                "digest": f"sha256:{checksum}",
            },
            {
                "name": f"{zip_name}.sha256",
                "browser_download_url": f"{base}/{zip_name}.sha256",
                "digest": "sha256:" + "f" * 64,
            },
        ],
    }


def copying_downloader(archive: Path, sidecar: Path):
    def download(url: str, destination: Path) -> None:
        source = sidecar if url.endswith(".sha256") else archive
        shutil.copy2(source, destination)

    return download


def test_network_delivery_cross_checks_api_sidecar_and_installs(
    tmp_path: Path,
) -> None:
    archive, sidecar, checksum = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    install_root = tmp_path / "managed"

    result = network_update.download_and_install_latest(
        install_root,
        expected_version="2.8.0",
        fetcher=lambda: api_payload("2.8.0", checksum),
        downloader=copying_downloader(archive, sidecar),
    )

    assert result["status"] == "installed"
    assert result["delivery"] == "github_release"
    assert result["api_sha256"] == checksum
    assert install_state.load_pointer(install_root)["current_version"] == "2.8.0"
    assert [
        path.name
        for path in (install_root / "staging").iterdir()
        if path.name != install_state.INSTALL_LOCK_NAME
    ] == []


def test_api_digest_sidecar_disagreement_never_installs(tmp_path: Path) -> None:
    archive, sidecar, checksum = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    install_root = tmp_path / "managed"

    with pytest.raises(network_update.NetworkUpdateError, match="do not match"):
        network_update.download_and_install_latest(
            install_root,
            fetcher=lambda: api_payload("2.8.0", "0" * 64),
            downloader=copying_downloader(archive, sidecar),
        )

    assert checksum != "0" * 64
    assert not (install_root / "versions" / "2.8.0").exists()
    assert not install_state.pointer_path(install_root).exists()
    assert [
        path.name
        for path in (install_root / "staging").iterdir()
        if path.name != install_state.INSTALL_LOCK_NAME
    ] == []


def test_unexpected_asset_url_is_rejected_before_download(tmp_path: Path) -> None:
    payload = api_payload("2.8.0", "a" * 64)
    payload["assets"][0]["browser_download_url"] = (
        "https://malicious.example/blueprint-wizard-v2.8.0.zip"
    )

    with pytest.raises(network_update.NetworkUpdateError, match="Unexpected release asset"):
        network_update.select_release_assets(payload)


def test_release_change_during_update_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(network_update.NetworkUpdateError, match="Release changed"):
        network_update.select_release_assets(
            api_payload("2.9.0", "a" * 64),
            expected_version="2.8.0",
        )
