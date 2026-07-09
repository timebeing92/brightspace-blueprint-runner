#!/usr/bin/env python3
"""Guided one-terminal runner for the Brightspace blueprint bundle."""
from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 11)
REQUIRED_MODULES = [
    ("openpyxl", "openpyxl"),
    ("docx", "python-docx"),
    ("pdf2image", "pdf2image"),
]


def runner_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_bundle_dir() -> Path:
    return runner_root().parent / "brightspace-blueprint-bundle"


def safe_label(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "export"


def command_text(cmd: list[str | os.PathLike[str]]) -> str:
    return " ".join(shlex.quote(str(part)) for part in cmd)


def run(cmd: list[str | os.PathLike[str]], *, cwd: Path | None = None) -> None:
    print(f"\n$ {command_text(cmd)}")
    sys.stdout.flush()
    subprocess.run([str(part) for part in cmd], cwd=str(cwd) if cwd else None, check=True)


def confirm(prompt: str, *, default: bool = False, assume_yes: bool = False) -> bool:
    if assume_yes:
        print(f"{prompt} yes")
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        reply = input(f"{prompt} {suffix} ").strip().lower()
    except EOFError:
        print("")
        return default
    if not reply:
        return default
    return reply in {"y", "yes"}


def prompt_text(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    reply = input(f"{prompt}{suffix}: ").strip()
    return reply or default


def parse_path(value: str) -> Path:
    raw = value.strip()
    if not raw:
        raise ValueError("empty path")
    try:
        parts = shlex.split(raw)
        if len(parts) == 1:
            raw = parts[0]
    except ValueError:
        raw = raw.strip("\"'")
    return Path(raw).expanduser().resolve()


def find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    mac_path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(mac_path) if mac_path.exists() else None


def poppler_status() -> tuple[bool, list[str]]:
    missing = [name for name in ("pdftoppm", "pdfinfo") if shutil.which(name) is None]
    return not missing, missing


def validate_bundle(bundle: Path) -> None:
    required = [
        bundle / "requirements.txt",
        bundle / "bootstrap.sh",
        bundle / "scripts" / "build_blueprint_bundle.py",
        bundle / "scripts" / "render_blueprint_docx.py",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        lines = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Bundle directory is missing required files:\n{lines}")


def venv_python(bundle: Path) -> Path:
    return bundle / ".venv" / "bin" / "python"


def module_installed(python: Path, module: str) -> bool:
    result = subprocess.run(
        [str(python), "-c", f"import {module}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def package_status(bundle: Path) -> tuple[bool, list[str]]:
    python = venv_python(bundle)
    if not python.exists():
        return False, [package for _, package in REQUIRED_MODULES]
    missing = [package for module, package in REQUIRED_MODULES if not module_installed(python, module)]
    return not missing, missing


def ensure_venv(bundle: Path, *, fix: bool, assume_yes: bool) -> bool:
    python = venv_python(bundle)
    if python.exists():
        return True
    if not fix:
        print("Bundle .venv: missing")
        return False
    if confirm("Create the bundle .venv now?", default=True, assume_yes=assume_yes):
        run([sys.executable, "-m", "venv", bundle / ".venv"])
        return python.exists()
    return False


def install_requirements(bundle: Path) -> None:
    python = venv_python(bundle)
    run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=bundle)
    run([python, "-m", "pip", "install", "-r", bundle / "requirements.txt"], cwd=bundle)


def ensure_requirements(bundle: Path, *, fix: bool, assume_yes: bool) -> bool:
    ok, missing = package_status(bundle)
    if ok:
        return True
    print(f"Missing Python package(s) in bundle .venv: {', '.join(missing)}")
    if not fix:
        return False
    if confirm("Install Python dependencies into the bundle .venv now?", default=True, assume_yes=assume_yes):
        install_requirements(bundle)
    return package_status(bundle)[0]


def package_manager_install_commands(missing_tools: list[str]) -> list[list[str]]:
    system = platform.system()
    commands: list[list[str]] = []
    needs_libreoffice = "LibreOffice/soffice" in missing_tools
    needs_poppler = "Poppler" in missing_tools

    if system == "Darwin" and shutil.which("brew"):
        if needs_poppler:
            commands.append(["brew", "install", "poppler"])
        if needs_libreoffice:
            commands.append(["brew", "install", "--cask", "libreoffice"])
    elif system == "Linux":
        if shutil.which("apt-get"):
            packages = []
            if needs_libreoffice:
                packages.append("libreoffice")
            if needs_poppler:
                packages.append("poppler-utils")
            if packages:
                commands.append(["sudo", "apt-get", "update"])
                commands.append(["sudo", "apt-get", "install", "-y", *packages])
        elif shutil.which("dnf"):
            packages = []
            if needs_libreoffice:
                packages.append("libreoffice")
            if needs_poppler:
                packages.append("poppler-utils")
            if packages:
                commands.append(["sudo", "dnf", "install", "-y", *packages])
        elif shutil.which("yum"):
            packages = []
            if needs_libreoffice:
                packages.append("libreoffice")
            if needs_poppler:
                packages.append("poppler-utils")
            if packages:
                commands.append(["sudo", "yum", "install", "-y", *packages])
        elif shutil.which("pacman"):
            packages = []
            if needs_libreoffice:
                packages.append("libreoffice-fresh")
            if needs_poppler:
                packages.append("poppler")
            if packages:
                commands.append(["sudo", "pacman", "-S", "--needed", *packages])
    return commands


def missing_render_tools() -> list[str]:
    missing: list[str] = []
    if not find_soffice():
        missing.append("LibreOffice/soffice")
    poppler_ok, _ = poppler_status()
    if not poppler_ok:
        missing.append("Poppler")
    return missing


def ensure_render_tools(*, fix: bool, assume_yes: bool, no_system_install: bool) -> bool:
    missing = missing_render_tools()
    if not missing:
        return True
    print(f"Missing optional render QA tool(s): {', '.join(missing)}")
    if no_system_install or not fix:
        print("DOCX visual render QA will not work until these tools are installed.")
        return False
    commands = package_manager_install_commands(missing)
    if not commands:
        print("No supported package-manager install command was found for these tools.")
        print("Install LibreOffice and Poppler manually, then rerun the wizard.")
        return False
    if confirm("Install missing render QA system tools now?", default=True, assume_yes=assume_yes):
        for cmd in commands:
            run(cmd)
    return not missing_render_tools()


def print_doctor(bundle: Path) -> int:
    print("Brightspace Blueprint Runner doctor\n")
    print(f"Runner: {runner_root()}")
    print(f"Bundle: {bundle}")
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    validate_bundle(bundle)

    python = venv_python(bundle)
    print(f"Bundle .venv: {'present' if python.exists() else 'missing'}")
    if python.exists():
        print(f"Bundle Python: {python}")
    req_ok, missing_packages = package_status(bundle)
    print(f"Python packages: {'ok' if req_ok else 'missing ' + ', '.join(missing_packages)}")
    soffice = find_soffice()
    print(f"LibreOffice/soffice: {soffice or 'missing'}")
    poppler_ok, missing_poppler = poppler_status()
    print(f"Poppler: {'ok' if poppler_ok else 'missing ' + ', '.join(missing_poppler)}")
    print("\nCore pipeline:", "ready" if req_ok else "not ready")
    print("DOCX render QA:", "ready" if soffice and poppler_ok and req_ok else "not ready")
    return 0 if req_ok else 1


def prompt_export(args: argparse.Namespace) -> Path:
    if args.export:
        export = parse_path(args.export)
        if not export.exists():
            raise SystemExit(f"Export path not found: {export}")
        return export
    print("\nDrag the Brightspace export ZIP or unpacked export folder into Terminal, then press Return.")
    while True:
        try:
            export = parse_path(input("Export path: "))
        except ValueError:
            print("Please enter a path.")
            continue
        if export.exists():
            return export
        print(f"Path not found: {export}")


def choose_layout(args: argparse.Namespace, *, render_docx: bool) -> str:
    if args.docx_section_layout:
        return args.docx_section_layout
    if not render_docx:
        return "top"
    reply = prompt_text("DOCX layout: top or left", default="top").lower()
    while reply not in {"top", "left"}:
        reply = prompt_text("Please enter top or left", default="top").lower()
    return reply


def build_command(bundle: Path, args: argparse.Namespace) -> tuple[list[str | os.PathLike[str]], Path]:
    python = venv_python(bundle)
    export = prompt_export(args)
    label = args.label
    if label is None:
        label = prompt_text("Optional output label; press Return to derive from export")
    stem = safe_label(label) if label else safe_label(export.stem if export.is_file() else export.name)

    render_docx = not args.no_docx
    if args.no_docx is None:
        render_docx = confirm("Render DOCX output?", default=True)
    render_qa = bool(args.render_docx_check)
    if render_docx and args.render_docx_check is None:
        render_qa = confirm("Run DOCX visual render QA? Requires LibreOffice and Poppler.", default=False)
    if render_qa:
        ensure_render_tools(fix=True, assume_yes=args.yes, no_system_install=args.no_system_install)

    run_qa = not args.skip_qa
    if args.skip_qa is None:
        run_qa = confirm("Run standard QA report?", default=True)

    check_external = bool(args.check_external_links)
    if args.check_external_links is None:
        check_external = confirm("Check external URLs live? This uses the network and can take longer.", default=False)

    layout = choose_layout(args, render_docx=render_docx)

    cmd: list[str | os.PathLike[str]] = [python, bundle / "scripts" / "build_blueprint_bundle.py", export]
    if label:
        cmd.extend(["--label", safe_label(label)])
    if not run_qa:
        cmd.append("--skip-qa")
    if check_external:
        cmd.append("--check-external-links")
    if not render_docx:
        cmd.append("--no-docx")
    if render_qa:
        cmd.append("--render-docx-check")
    if render_docx:
        cmd.extend(["--docx-section-layout", layout])
    output_dir = bundle / "workspace" / "review"
    output_bundle = output_dir / f"{stem}__blueprint_bundle"
    return cmd, output_bundle


def run_wizard(args: argparse.Namespace) -> int:
    bundle = args.bundle_dir.expanduser().resolve()
    print("Brightspace Blueprint Runner\n")
    validate_bundle(bundle)
    if sys.version_info < MIN_PYTHON:
        raise SystemExit("Python 3.11+ is required.")

    if not ensure_venv(bundle, fix=True, assume_yes=args.yes):
        raise SystemExit("Cannot continue without the bundle .venv.")
    if not ensure_requirements(bundle, fix=True, assume_yes=args.yes):
        raise SystemExit("Cannot continue without the required Python packages.")

    if not args.no_docx:
        missing = missing_render_tools()
        if missing:
            print(f"\nOptional render QA tools missing: {', '.join(missing)}")
            print("You can still create Markdown, JSON, XLSX, and DOCX outputs.")

    cmd, output_bundle = build_command(bundle, args)
    print("\nReady to run the blueprint pipeline.")
    print(command_text(cmd))
    if not confirm("Run now?", default=True, assume_yes=args.yes):
        print("Canceled.")
        return 2
    run(cmd, cwd=bundle)
    print("\nPipeline finished.")
    print(f"Expected output folder: {output_bundle}")
    if output_bundle.exists():
        print("Key outputs:")
        for path in sorted(output_bundle.glob("*__blueprint.*")):
            print(f"- {path}")
        qa = next(iter(sorted(output_bundle.glob("*__course_qa.md"))), None)
        if qa:
            print(f"- {qa}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle_dir(), help="Path to brightspace-blueprint-bundle")
    parser.add_argument("--doctor", action="store_true", help="Check setup without running an export")
    parser.add_argument("--fix", action="store_true", help="With --doctor, offer to install missing bundle dependencies")
    parser.add_argument("--yes", "-y", action="store_true", help="Answer yes to install/run confirmations")
    parser.add_argument("--no-system-install", action="store_true", help="Do not offer package-manager installs for system tools")
    parser.add_argument("--export", help="Brightspace export ZIP or unpacked folder")
    parser.add_argument("--label", help="Optional output label")
    parser.add_argument("--render-docx-check", dest="render_docx_check", action="store_true", default=None)
    parser.add_argument("--no-render-docx-check", dest="render_docx_check", action="store_false")
    parser.add_argument("--check-external-links", dest="check_external_links", action="store_true", default=None)
    parser.add_argument("--no-check-external-links", dest="check_external_links", action="store_false")
    parser.add_argument("--skip-qa", dest="skip_qa", action="store_true", default=None)
    parser.add_argument("--no-skip-qa", dest="skip_qa", action="store_false")
    parser.add_argument("--no-docx", dest="no_docx", action="store_true", default=None)
    parser.add_argument("--docx", dest="no_docx", action="store_false")
    parser.add_argument("--docx-section-layout", choices=("top", "left"), default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv or sys.argv[1:])
    bundle = args.bundle_dir.expanduser().resolve()
    if args.doctor:
        validate_bundle(bundle)
        if args.fix:
            ensure_venv(bundle, fix=True, assume_yes=args.yes)
            ensure_requirements(bundle, fix=True, assume_yes=args.yes)
            ensure_render_tools(fix=True, assume_yes=args.yes, no_system_install=args.no_system_install)
        return print_doctor(bundle)
    return run_wizard(args)


if __name__ == "__main__":
    raise SystemExit(main())
