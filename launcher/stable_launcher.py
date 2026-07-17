#!/usr/bin/env python3
"""Launch, inspect, activate, or roll back a managed Blueprint Wizard."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import install_state
import install_release
import network_update

LAUNCHER_VERSION = "0.1.0-dev"
RESTART_EXIT_CODE = 75
MAX_RESTARTS = 1


def default_install_root() -> Path:
    return Path(__file__).resolve().parents[1]


def current_command(
    install_root: Path,
    wizard_args: list[str],
) -> tuple[str, list[str], dict[str, str]]:
    if "--bundle-dir" in wizard_args:
        raise install_state.InstallStateError(
            "Managed installs always use the bundle paired with the active release"
        )
    pointer = install_state.load_pointer(install_root)
    version = pointer["current_version"]
    root, _ = install_state.validate_installed_version(install_root, version)
    runner = root / "brightspace-blueprint-runner"
    bundle = root / "brightspace-blueprint-bundle"
    command = [
        sys.executable,
        str(runner / "scripts" / "blueprint_wizard.py"),
        *wizard_args,
        "--bundle-dir",
        str(bundle),
    ]
    environment = {
        **os.environ,
        **install_state.managed_environment(
            install_root,
            version=version,
            launcher_path=Path(__file__).resolve(),
        ),
        "PYTHONUNBUFFERED": "1",
    }
    return version, command, environment


def launch(install_root: Path, wizard_args: list[str]) -> int:
    install_state.ensure_install_directories(install_root)
    restarts = 0
    while True:
        version, command, environment = current_command(install_root, wizard_args)
        install_state.append_launch_receipt(
            install_root,
            {
                "event": "launch_start",
                "version": version,
                "command": command,
            },
        )
        result = subprocess.run(command, env=environment, check=False)
        status = (
            "restart_requested"
            if result.returncode == RESTART_EXIT_CODE
            else ("ok" if result.returncode == 0 else "error")
        )
        install_state.append_launch_receipt(
            install_root,
            {
                "event": "launch_end",
                "version": version,
                "exit_code": result.returncode,
                "status": status,
            },
        )
        if result.returncode != RESTART_EXIT_CODE:
            return result.returncode
        next_version = install_state.load_pointer(install_root)["current_version"]
        if next_version == version:
            print(
                "Stable launcher error: restart was requested without activating "
                "a different version",
                file=sys.stderr,
            )
            return 1
        if restarts >= MAX_RESTARTS:
            print(
                "Stable launcher error: the one permitted update restart was already used",
                file=sys.stderr,
            )
            return 1
        restarts += 1
        print(f"Restarting Blueprint Wizard in v{next_version}…")


def print_versions(install_root: Path) -> int:
    versions = install_state.installed_versions(install_root)
    pointer = (
        install_state.load_pointer(install_root)
        if install_state.pointer_path(install_root).exists()
        else {}
    )
    current = pointer.get("current_version")
    previous = pointer.get("previous_version")
    if not versions:
        print("No valid Wizard versions are installed.")
        return 1
    for version in versions:
        labels = []
        if version == current:
            labels.append("current")
        if version == previous:
            labels.append("rollback")
        suffix = f" ({', '.join(labels)})" if labels else ""
        print(f"v{version}{suffix}")
    return 0


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, default=default_install_root())
    parser.add_argument("--launcher-version", action="store_true")
    parser.add_argument("--list-versions", action="store_true")
    parser.add_argument("--activate", metavar="VERSION")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--remove-version", metavar="VERSION")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--install-release", type=Path, metavar="ZIP")
    verification = parser.add_mutually_exclusive_group()
    verification.add_argument("--sha256")
    verification.add_argument("--checksum", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--no-activate", action="store_true")
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, wizard_args = parse_args(argv or sys.argv[1:])
    install_root = args.install_root.expanduser().resolve()
    try:
        if args.launcher_version:
            print(f"blueprint-wizard-stable-launcher {LAUNCHER_VERSION}")
            return 0
        if args.list_versions:
            return print_versions(install_root)
        if args.activate:
            pointer = install_state.activate_version(install_root, args.activate)
            print(json.dumps(pointer, indent=2, sort_keys=True))
            return 0
        if args.rollback:
            pointer = install_state.rollback(install_root)
            print(json.dumps(pointer, indent=2, sort_keys=True))
            return 0
        if args.remove_version:
            receipt = install_state.remove_version(install_root, args.remove_version)
            print(json.dumps(receipt, indent=2, sort_keys=True))
            return 0
        if args.health:
            pointer = install_state.load_pointer(install_root)
            root, manifest = install_state.validate_installed_version(
                install_root,
                pointer["current_version"],
            )
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "current_version": pointer["current_version"],
                        "version_root": str(root),
                        "runner_commit": manifest["runner"]["commit"],
                        "bundle_commit": manifest["bundle"]["commit"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.install_release:
            if bool(args.sha256) == bool(args.checksum):
                raise install_state.InstallStateError(
                    "--install-release needs exactly one of --sha256 or --checksum"
                )
            result = install_release.install_release_zip(
                install_root,
                args.install_release,
                expected_sha256=args.sha256,
                checksum_path=args.checksum,
                expected_version=args.expected_version,
                activate=not args.no_activate,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.update:
            result = network_update.download_and_install_latest(
                install_root,
                expected_version=args.expected_version,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        return launch(install_root, wizard_args)
    except install_state.InstallStateError as exc:
        print(f"Stable launcher error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
