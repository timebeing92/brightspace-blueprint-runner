from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launcher"
sys.path.insert(0, str(LAUNCHER))

import install_state  # noqa: E402
import stable_launcher  # noqa: E402


def write_version(
    install_root: Path,
    version: str,
    *,
    runner_commit: str,
    bundle_commit: str,
    repository: str = "https://github.com/timebeing92/brightspace-blueprint-runner.git",
) -> Path:
    root = install_root / "versions" / version
    runner = root / "brightspace-blueprint-runner"
    bundle = root / "brightspace-blueprint-bundle"
    (runner / "scripts").mkdir(parents=True)
    (bundle / "scripts").mkdir(parents=True)
    (runner / "scripts" / "blueprint_wizard.py").write_text(
        """
import json
import os
import sys
from pathlib import Path

data = Path(os.environ["BLUEPRINT_WIZARD_DATA_ROOT"])
data.mkdir(parents=True, exist_ok=True)
(data / "fixture_launch.json").write_text(json.dumps({
    "argv": sys.argv[1:],
    "install_root": os.environ["BLUEPRINT_WIZARD_INSTALL_ROOT"],
    "data_root": os.environ["BLUEPRINT_WIZARD_DATA_ROOT"],
    "output_root": os.environ["BLUEPRINT_WIZARD_OUTPUT_ROOT"],
    "version": os.environ["BLUEPRINT_WIZARD_MANAGED_VERSION"],
}), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (runner / "blueprint_wizard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (runner / "blueprint_wizard.ps1").write_text("# fixture\n", encoding="utf-8")
    (bundle / "scripts" / "build_blueprint_bundle.py").write_text(
        "# fixture\n", encoding="utf-8"
    )
    (bundle / "requirements.txt").write_text("# fixture\n", encoding="utf-8")
    manifest = {
        "schema": install_state.RELEASE_SCHEMA,
        "version": version,
        "runner": {
            "repository": repository,
            "ref": runner_commit,
            "commit": runner_commit,
        },
        "bundle": {
            "repository": "https://github.com/timebeing92/brightspace-blueprint-bundle.git",
            "ref": bundle_commit,
            "commit": bundle_commit,
        },
        "contracts": [
            {
                "schema": schema,
                "path": path,
                "sha256": character * 64,
            }
            for schema, path, character in (
                ("coursecraft.blueprint/4", "schemas/blueprint_schema.json", "a"),
                ("coursecraft.rubrics/1", "schemas/rubrics_schema.json", "b"),
                (
                    "coursecraft.progress/1",
                    "schemas/progress_events_schema.json",
                    "c",
                ),
            )
        ],
    }
    (root / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def fixture_install(tmp_path: Path) -> Path:
    install_root = tmp_path / "Blueprint Wizard"
    write_version(
        install_root,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
    )
    write_version(
        install_root,
        "2.8.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    return install_root


def test_activation_and_rollback_swap_only_the_atomic_pointer(
    tmp_path: Path,
) -> None:
    install_root = fixture_install(tmp_path)

    first = install_state.activate_version(install_root, "2.7.0")
    second = install_state.activate_version(install_root, "v2.8.0")
    rolled_back = install_state.rollback(install_root)

    assert first["current_version"] == "2.7.0"
    assert first["previous_version"] == ""
    assert second["current_version"] == "2.8.0"
    assert second["previous_version"] == "2.7.0"
    assert rolled_back["current_version"] == "2.7.0"
    assert rolled_back["previous_version"] == "2.8.0"
    assert not install_state.pointer_path(install_root).with_suffix(".json.tmp").exists()
    assert (install_root / "versions" / "2.7.0").is_dir()
    assert (install_root / "versions" / "2.8.0").is_dir()


def test_launcher_uses_paired_bundle_and_external_user_data(
    tmp_path: Path,
) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.8.0")

    result = stable_launcher.launch(install_root, ["--plain", "--version"])

    assert result == 0
    capture_path = install_root / "user-data" / "fixture_launch.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    expected_bundle = install_root / "versions" / "2.8.0" / "brightspace-blueprint-bundle"
    assert capture["version"] == "2.8.0"
    assert capture["install_root"] == str(install_root)
    assert capture["data_root"] == str(install_root / "user-data")
    assert capture["output_root"] == str(install_root / "user-data" / "outputs")
    assert capture["argv"][-2:] == ["--bundle-dir", str(expected_bundle)]
    receipts = (install_root / "receipts" / "launches.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"event": "launch_start"' in receipts
    assert '"event": "launch_end"' in receipts
    assert '"status": "ok"' in receipts


def test_launcher_refuses_bundle_override(tmp_path: Path) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.7.0")

    with pytest.raises(install_state.InstallStateError, match="bundle paired"):
        stable_launcher.current_command(
            install_root,
            ["--bundle-dir", str(tmp_path / "unpaired")],
        )


def test_pointer_cannot_escape_versions_directory(tmp_path: Path) -> None:
    install_root = fixture_install(tmp_path)
    install_state.atomic_write_json(
        install_state.pointer_path(install_root),
        {
            "schema": install_state.POINTER_SCHEMA,
            "launcher_protocol": install_state.LAUNCHER_PROTOCOL,
            "current_version": "../../outside",
            "previous_version": "",
        },
    )

    with pytest.raises(install_state.InstallStateError, match="Invalid release version"):
        install_state.load_pointer(install_root)


def test_untrusted_release_repository_is_rejected(tmp_path: Path) -> None:
    install_root = tmp_path / "Blueprint Wizard"
    root = write_version(
        install_root,
        "2.7.0",
        runner_commit="1" * 40,
        bundle_commit="2" * 40,
        repository="https://malicious.example/blueprint-wizard.git",
    )

    with pytest.raises(install_state.InstallStateError, match="Unexpected runner"):
        install_state.validate_release_manifest(root, expected_version="2.7.0")


def test_version_listing_ignores_invalid_directories(tmp_path: Path) -> None:
    install_root = fixture_install(tmp_path)
    (install_root / "versions" / "scratch").mkdir(parents=True)
    broken = install_root / "versions" / "9.9.9"
    broken.mkdir(parents=True)

    assert install_state.installed_versions(install_root) == ["2.7.0", "2.8.0"]


def test_launcher_restarts_once_after_atomic_version_change(
    tmp_path: Path,
    monkeypatch,
) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.7.0")
    launched: list[str] = []

    def fake_run(command, *, env, check):
        version = env[install_state.MANAGED_VERSION_ENV]
        launched.append(version)
        if version == "2.7.0":
            install_state.activate_version(install_root, "2.8.0")
            return subprocess.CompletedProcess(command, stable_launcher.RESTART_EXIT_CODE)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(stable_launcher.subprocess, "run", fake_run)

    assert stable_launcher.launch(install_root, ["--plain"]) == 0
    assert launched == ["2.7.0", "2.8.0"]
    receipts = (install_root / "receipts" / "launches.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"status": "restart_requested"' in receipts
    assert '"status": "ok"' in receipts


def test_restart_without_version_change_is_refused(
    tmp_path: Path,
    monkeypatch,
) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.7.0")
    monkeypatch.setattr(
        stable_launcher.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], stable_launcher.RESTART_EXIT_CODE
        ),
    )

    assert stable_launcher.launch(install_root, []) == 1


def test_cleanup_protects_current_and_unproven_rollback_version(
    tmp_path: Path,
) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.7.0")
    install_state.activate_version(install_root, "2.8.0")

    with pytest.raises(install_state.InstallStateError, match="current.*cannot"):
        install_state.remove_version(install_root, "2.8.0")
    with pytest.raises(install_state.InstallStateError, match="rollback.*protected"):
        install_state.remove_version(install_root, "2.7.0")

    assert (install_root / "versions" / "2.7.0").is_dir()
    assert (install_root / "versions" / "2.8.0").is_dir()


def test_explicit_cleanup_can_retire_rollback_after_current_launch_succeeds(
    tmp_path: Path,
) -> None:
    install_root = fixture_install(tmp_path)
    install_state.activate_version(install_root, "2.7.0")
    install_state.activate_version(install_root, "2.8.0")
    sentinel = install_root / "user-data" / "outputs" / "keep-me.txt"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("user work\n", encoding="utf-8")
    install_state.append_launch_receipt(
        install_root,
        {
            "event": "launch_end",
            "version": "2.8.0",
            "exit_code": 0,
            "status": "ok",
        },
    )

    receipt = install_state.remove_version(install_root, "2.7.0")

    assert receipt["version"] == "2.7.0"
    assert not (install_root / "versions" / "2.7.0").exists()
    assert install_state.load_pointer(install_root)["previous_version"] == ""
    assert sentinel.read_text(encoding="utf-8") == "user work\n"
    assert (install_root / "receipts" / "retired-v2.7.0.json").is_file()
