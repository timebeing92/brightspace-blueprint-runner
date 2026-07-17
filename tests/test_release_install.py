from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launcher"
sys.path.insert(0, str(LAUNCHER))

import install_release  # noqa: E402
import install_state  # noqa: E402


def release_manifest(
    version: str,
    *,
    runner_commit: str,
    bundle_commit: str,
    runner_repository: str = (
        "https://github.com/timebeing92/brightspace-blueprint-runner.git"
    ),
) -> dict:
    return {
        "schema": install_state.RELEASE_SCHEMA,
        "version": version,
        "runner": {
            "repository": runner_repository,
            "ref": runner_commit,
            "commit": runner_commit,
        },
        "bundle": {
            "repository": "https://github.com/timebeing92/brightspace-blueprint-bundle.git",
            "ref": bundle_commit,
            "commit": bundle_commit,
        },
        "contracts": [
            {"schema": "coursecraft.blueprint/4", "path": "blueprint", "sha256": "a" * 64},
            {"schema": "coursecraft.rubrics/1", "path": "rubrics", "sha256": "b" * 64},
            {"schema": "coursecraft.progress/1", "path": "progress", "sha256": "c" * 64},
        ],
    }


def make_release_zip(
    root: Path,
    version: str,
    *,
    runner_commit: str,
    bundle_commit: str,
    runner_repository: str = (
        "https://github.com/timebeing92/brightspace-blueprint-runner.git"
    ),
    include_requirements: bool = True,
    extra_member: str | None = None,
) -> tuple[Path, Path, str]:
    source = root / f"source-{version}"
    release_root = source / f"blueprint-wizard-v{version}"
    runner = release_root / "brightspace-blueprint-runner"
    bundle = release_root / "brightspace-blueprint-bundle"
    (runner / "scripts").mkdir(parents=True)
    (bundle / "scripts").mkdir(parents=True)
    (runner / "scripts" / "blueprint_wizard.py").write_text(
        "print('fixture wizard')\n", encoding="utf-8"
    )
    (runner / "blueprint_wizard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (runner / "blueprint_wizard.ps1").write_text("# fixture\n", encoding="utf-8")
    (bundle / "scripts" / "build_blueprint_bundle.py").write_text(
        "# fixture\n", encoding="utf-8"
    )
    if include_requirements:
        (bundle / "requirements.txt").write_text("# fixture\n", encoding="utf-8")
    manifest = release_manifest(
        version,
        runner_commit=runner_commit,
        bundle_commit=bundle_commit,
        runner_repository=runner_repository,
    )
    (release_root / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    archive = root / f"blueprint-wizard-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(release_root.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(source).as_posix())
        if extra_member:
            output.writestr(extra_member, "unsafe")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = archive.with_name(archive.name + ".sha256")
    sidecar.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    return archive, sidecar, checksum


def test_side_by_side_install_activation_and_rollback_preserve_user_data(
    tmp_path: Path,
) -> None:
    first_zip, first_sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    second_zip, second_sidecar, _ = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    install_root = tmp_path / "managed"

    first = install_release.install_release_zip(
        install_root,
        first_zip,
        checksum_path=first_sidecar,
    )
    sentinel = install_root / "user-data" / "outputs" / "keep-me.txt"
    sentinel.write_text("user work\n", encoding="utf-8")
    second = install_release.install_release_zip(
        install_root,
        second_zip,
        checksum_path=second_sidecar,
    )
    rolled_back = install_state.rollback(install_root)

    assert first["status"] == "installed"
    assert second["status"] == "installed"
    assert second["pointer"]["current_version"] == "2.8.0"
    assert second["pointer"]["previous_version"] == "2.7.0"
    assert rolled_back["current_version"] == "2.7.0"
    assert rolled_back["previous_version"] == "2.8.0"
    assert sentinel.read_text(encoding="utf-8") == "user work\n"
    assert (install_root / "versions" / "2.7.0").is_dir()
    assert (install_root / "versions" / "2.8.0").is_dir()


def test_same_verified_release_is_idempotent(tmp_path: Path) -> None:
    archive, sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        archive,
        checksum_path=sidecar,
    )

    repeated = install_release.install_release_zip(
        install_root,
        archive,
        checksum_path=sidecar,
    )

    assert repeated["status"] == "already_installed"
    assert repeated["pointer"]["current_version"] == "2.7.0"


def test_bad_checksum_leaves_no_version_or_pointer(tmp_path: Path) -> None:
    archive, _, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    install_root = tmp_path / "managed"

    with pytest.raises(install_release.ReleaseInstallError, match="checksum mismatch"):
        install_release.install_release_zip(
            install_root,
            archive,
            expected_sha256="0" * 64,
        )

    assert not (install_root / "versions" / "2.7.0").exists()
    assert not install_state.pointer_path(install_root).exists()


def test_traversal_member_cannot_change_the_current_version(tmp_path: Path) -> None:
    good_zip, good_sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    bad_zip, bad_sidecar, _ = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
        extra_member="blueprint-wizard-v2.8.0/../../outside.txt",
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        good_zip,
        checksum_path=good_sidecar,
    )

    with pytest.raises(install_release.ReleaseInstallError, match="Unsafe ZIP"):
        install_release.install_release_zip(
            install_root,
            bad_zip,
            checksum_path=bad_sidecar,
        )

    assert install_state.load_pointer(install_root)["current_version"] == "2.7.0"
    assert not (tmp_path / "outside.txt").exists()
    assert not (install_root / "versions" / "2.8.0").exists()


def test_untrusted_manifest_cannot_change_current_version(tmp_path: Path) -> None:
    good_zip, good_sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    bad_zip, bad_sidecar, _ = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
        runner_repository="https://malicious.example/wizard.git",
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        good_zip,
        checksum_path=good_sidecar,
    )

    with pytest.raises(install_state.InstallStateError, match="Unexpected runner"):
        install_release.install_release_zip(
            install_root,
            bad_zip,
            checksum_path=bad_sidecar,
        )

    assert install_state.load_pointer(install_root)["current_version"] == "2.7.0"
    assert not (install_root / "versions" / "2.8.0").exists()


def test_post_extract_failure_cleans_staging_and_keeps_current(tmp_path: Path) -> None:
    good_zip, good_sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    incomplete_zip, incomplete_sidecar, _ = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
        include_requirements=False,
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        good_zip,
        checksum_path=good_sidecar,
    )

    with pytest.raises(install_state.InstallStateError, match="missing required files"):
        install_release.install_release_zip(
            install_root,
            incomplete_zip,
            checksum_path=incomplete_sidecar,
        )

    assert install_state.load_pointer(install_root)["current_version"] == "2.7.0"
    assert [
        path.name
        for path in (install_root / "staging").iterdir()
        if path.name != install_state.INSTALL_LOCK_NAME
    ] == []
    assert not (install_root / "versions" / "2.8.0").exists()


def test_concurrent_install_is_refused_without_changing_current(
    tmp_path: Path,
) -> None:
    first_zip, first_sidecar, _ = make_release_zip(
        tmp_path,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    second_zip, second_sidecar, _ = make_release_zip(
        tmp_path,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        first_zip,
        checksum_path=first_sidecar,
    )

    with install_state.install_lock(install_root):
        with pytest.raises(install_state.InstallStateError, match="already in progress"):
            install_release.install_release_zip(
                install_root,
                second_zip,
                checksum_path=second_sidecar,
            )

    assert install_state.load_pointer(install_root)["current_version"] == "2.7.0"
    assert not (install_root / "versions" / "2.8.0").exists()
