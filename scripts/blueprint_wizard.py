#!/usr/bin/env python3
"""Guided one-terminal runner for the Brightspace blueprint bundle.

v2: splash art, doctor checklist, export peek, options card, live step board
driven by the bundle's NDJSON progress events (coursecraft.progress/1), and a
results card. Pure stdlib; --plain (or no TTY / NO_COLOR) degrades to text.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import art
import update_check
import ui

MIN_PYTHON = (3, 11)
REQUIRED_MODULES = [
    ("openpyxl", "openpyxl"),
    ("docx", "python-docx"),
    ("jsonschema", "jsonschema"),
]
VERSION = "2.7.0"

INSTALL_ROOT_ENV = "BLUEPRINT_WIZARD_INSTALL_ROOT"
DATA_ROOT_ENV = "BLUEPRINT_WIZARD_DATA_ROOT"
OUTPUT_ROOT_ENV = "BLUEPRINT_WIZARD_OUTPUT_ROOT"
MANAGED_VERSION_ENV = "BLUEPRINT_WIZARD_MANAGED_VERSION"

# Minimum on-screen time per step in interactive runs, so the flavor line and
# its animation register before the step flips to done. The pipeline itself is
# not slowed — only the display. Eight steps add at most ~9 seconds.
MIN_STEP_SECONDS = 1.1

FLAVOR = {
    "Inventory export files": "The wizard surveys the archive…",
    "Probe manifest": "The wizard holds the scroll to the light…",
    "Reconstruct course structure": "Rebuilding the halls of the course…",
    "Extract course activities": "Gathering assignments and discussions…",
    "Extract rubrics": "Reading rubric grids and scoring bands…",
    "Run QA report": "Casting detection spells…",
    "Assemble blueprint model and Markdown": "Inscribing the blueprint…",
    "Render DOCX": "Binding the review tome…",
    "Check DOCX structure": "Testing the tome's binding…",
    "Render DOCX preview pages": "Preparing pages for maintainer inspection…",
}

TERM = ui.Term(plain=True)  # replaced in main() once flags are parsed

# Journey position shown beside phase headings ("2 of 4"); configured by
# run_wizard, disabled for --yes runs where the phases fly by anyway.
PHASE = {"current": 0, "total": 0, "enabled": False}


def phase_heading(text: str) -> str:
    if not PHASE["enabled"]:
        return ui.heading(TERM, text)
    PHASE["current"] += 1
    return ui.heading(TERM, text, note=f"{PHASE['current']} of {PHASE['total']}")


def runner_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_bundle_dir() -> Path:
    return runner_root().parent / "brightspace-blueprint-bundle"


def configured_root(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def managed_install_root() -> Path | None:
    return configured_root(INSTALL_ROOT_ENV)


def data_root() -> Path:
    return configured_root(DATA_ROOT_ENV) or runner_root()


def managed_mode() -> bool:
    return managed_install_root() is not None


def settings_dir() -> Path:
    return data_root() / "settings" if managed_mode() else runner_root()


def state_path() -> Path:
    if managed_mode():
        return settings_dir() / "last_run.json"
    return runner_root() / ".last_run.json"


def update_cache_path() -> Path:
    if managed_mode():
        return data_root() / "update-cache" / "release_check.json"
    return runner_root() / ".update_check.json"


def logs_dir() -> Path:
    return data_root() / "logs" if managed_mode() else runner_root() / "logs"


def configured_output_root() -> Path | None:
    explicit = configured_root(OUTPUT_ROOT_ENV)
    if explicit is not None:
        return explicit
    return data_root() / "outputs" if managed_mode() else None


def ensure_managed_data_dirs() -> None:
    if not managed_mode():
        return
    for path in (
        settings_dir(),
        data_root() / "logs",
        data_root() / "outputs",
        data_root() / "update-cache",
    ):
        path.mkdir(parents=True, exist_ok=True)


def safe_label(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "export"


def command_text(cmd: list[str | os.PathLike[str]]) -> str:
    return " ".join(shlex.quote(str(part)) for part in cmd)


def run(cmd: list[str | os.PathLike[str]], *, cwd: Path | None = None) -> None:
    print(f"\n$ {command_text(cmd)}")
    sys.stdout.flush()
    subprocess.run([str(part) for part in cmd], cwd=str(cwd) if cwd else None, check=True)


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


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m {secs:02d}s"


# --------------------------------------------------------------------------- #
# Environment checks (doctor)
# --------------------------------------------------------------------------- #
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
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        lines = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Bundle directory is missing required files:\n{lines}")


def venv_python(bundle: Path) -> Path:
    if os.name == "nt":
        return bundle / ".venv" / "Scripts" / "python.exe"
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
        print(ui.status_line(TERM, "bad", "Bundle .venv", "missing"))
        return False
    if ui.confirm(TERM, "Create the bundle .venv now?", default=True, assume_yes=assume_yes):
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
    print(ui.status_line(TERM, "bad", "Python packages", "missing " + ", ".join(missing)))
    if not fix:
        return False
    if ui.confirm(TERM, "Install Python dependencies into the bundle .venv now?", default=True, assume_yes=assume_yes):
        install_requirements(bundle)
    return package_status(bundle)[0]


def missing_advanced_render_tools(bundle: Path) -> list[str]:
    missing: list[str] = []
    python = venv_python(bundle)
    if not python.exists() or not module_installed(python, "pdf2image"):
        missing.append("pdf2image (requirements-render.txt)")
    if not find_soffice():
        missing.append("LibreOffice/soffice")
    poppler_ok, _ = poppler_status()
    if not poppler_ok:
        missing.append("Poppler")
    return missing


def require_advanced_render_tools(bundle: Path) -> None:
    missing = missing_advanced_render_tools(bundle)
    if not missing:
        return
    details = "\n".join(f"  - {item}" for item in missing)
    raise SystemExit(
        "Advanced --render-docx-check was explicitly requested, but its optional "
        f"preview tools are missing:\n{details}\n"
        "Install the bundle's requirements-render.txt plus the named system "
        "tools, or rerun without --render-docx-check. Normal DOCX generation "
        "and structural QA do not need them."
    )


def preparation_checks(bundle: Path, args: argparse.Namespace) -> None:
    """Doctor checks rendered as a checklist; fixes offered inline."""
    print(phase_heading("The workshop"))
    print(TERM.dim("  The wizard checks the tools before drafting."))
    validate_bundle(bundle)
    print(ui.status_line(TERM, "ok", "Bundle", str(bundle)))
    if sys.version_info < MIN_PYTHON:
        print(ui.status_line(TERM, "bad", "Python 3.11+", sys.version.split()[0]))
        raise SystemExit("Python 3.11+ is required.")
    print(ui.status_line(TERM, "ok", "Python", f"{sys.version.split()[0]} ({sys.executable})"))

    if not ensure_venv(bundle, fix=True, assume_yes=args.yes):
        raise SystemExit("Cannot continue without the bundle .venv.")
    print(ui.status_line(TERM, "ok", "Bundle .venv", str(venv_python(bundle))))
    if not ensure_requirements(bundle, fix=True, assume_yes=args.yes):
        raise SystemExit("Cannot continue without the required Python packages.")
    print(ui.status_line(TERM, "ok", "Python packages", "openpyxl, python-docx, jsonschema"))
    if managed_mode():
        print(ui.status_line(TERM, "ok", "Managed user data", str(data_root())))


def report_update_check(*, force: bool, offer_open: bool) -> None:
    """Report a newer published Wizard release without blocking normal use."""
    cache_path = update_cache_path()
    status = update_check.check_latest_release(
        current_version=VERSION,
        cache_path=cache_path,
        force=force,
    )
    if status.state == "unavailable":
        if force:
            print()
            print(
                ui.card(
                    TERM,
                    "Update check unavailable",
                    [
                        ("Installed", f"v{VERSION}"),
                        (
                            "",
                            "The latest release could not be confirmed. "
                            "The installed Wizard is still usable.",
                        ),
                    ],
                )
            )
        return

    if not status.update_available:
        if force:
            title = (
                "Blueprint Wizard is newer than the latest published release"
                if status.state == "ahead"
                else "Blueprint Wizard is up to date"
            )
            print()
            print(
                ui.card(
                    TERM,
                    title,
                    [
                        ("Installed", f"v{VERSION}"),
                        ("Latest", f"v{status.latest_version}"),
                    ],
                )
            )
        return

    if not force and not update_check.notice_is_due(
        cache_path,
        latest_version=status.latest_version,
    ):
        return

    rows = [
        ("Installed", f"v{VERSION}"),
        ("Available", TERM.bold(f"v{status.latest_version}")),
    ]
    if status.release_name and status.release_name != status.latest_tag:
        rows.append(("Release", status.release_name))
    rows.extend(
        [
            ("Download", TERM.supporting(status.release_url)),
            (
                "",
                "The current Wizard will keep working; no files were replaced.",
            ),
        ]
    )
    print()
    print(ui.card(TERM, "Blueprint Wizard update available", rows))
    update_check.mark_notified(
        cache_path,
        latest_version=status.latest_version,
    )
    if offer_open and ui.confirm(
        TERM,
        "Open the verified release page now?",
        default=False,
    ):
        try:
            opened = webbrowser.open(status.release_url)
        except OSError:
            opened = False
        if not opened:
            print(TERM.secondary(f"  Open this page: {status.release_url}"))


def print_doctor(bundle: Path) -> int:
    print(ui.heading(TERM, "Blueprint Runner doctor"))
    print(TERM.dim("  The wizard inspects the workshop."))
    print(ui.status_line(TERM, "ok", "Runner", str(runner_root())))
    validate_bundle(bundle)
    print(ui.status_line(TERM, "ok", "Bundle", str(bundle)))
    print(ui.status_line(TERM, "ok", "Python", f"{sys.executable} ({sys.version.split()[0]})"))

    python = venv_python(bundle)
    print(ui.status_line(TERM, "ok" if python.exists() else "bad", "Bundle .venv",
                         str(python) if python.exists() else "missing"))
    req_ok, missing_packages = package_status(bundle)
    print(ui.status_line(TERM, "ok" if req_ok else "bad", "Python packages",
                         "ok" if req_ok else "missing " + ", ".join(missing_packages)))
    print()
    print(ui.status_line(TERM, "ok" if req_ok else "bad", "Core pipeline",
                         "ready" if req_ok else "not ready"))
    print(ui.status_line(TERM, "ok" if req_ok else "bad", "DOCX structural QA",
                         "ready" if req_ok else "not ready"))
    return 0 if req_ok else 1


# --------------------------------------------------------------------------- #
# Export selection + peek
# --------------------------------------------------------------------------- #
def _manifest_bytes(export: Path) -> tuple[bytes | None, int, int]:
    """Return (manifest bytes, file count, total size) without full extraction."""
    if export.is_file() and zipfile.is_zipfile(export):
        with zipfile.ZipFile(export) as archive:
            names = [
                info.filename
                for info in archive.infolist()
                if not info.is_dir() and "__MACOSX" not in info.filename
            ]
            manifests = sorted(
                (name for name in names if Path(name).name == "imsmanifest.xml"),
                key=lambda name: (len(Path(name).parts), name),
            )
            data = archive.read(manifests[0]) if manifests else None
            return data, len(names), export.stat().st_size
    if export.is_dir():
        files = [path for path in export.rglob("*") if path.is_file()]
        manifests = sorted(
            (path for path in files if path.name == "imsmanifest.xml"),
            key=lambda path: (len(path.parts), str(path)),
        )
        data = manifests[0].read_bytes() if manifests else None
        return data, len(files), sum(path.stat().st_size for path in files)
    return None, 0, 0


def peek_export(export: Path) -> dict:
    """Cheap look inside the export: course title, module names, file counts."""
    info = {
        "title": "", "modules": None, "module_titles": [],
        "files": 0, "size": 0, "has_manifest": False,
    }
    try:
        data, file_count, size = _manifest_bytes(export)
        info["files"] = file_count
        info["size"] = size
        if data is None:
            return info
        info["has_manifest"] = True
        root = ET.fromstring(data)
        org = next(
            (el for el in root.iter() if el.tag.split("}", 1)[-1] == "organization"), None
        )
        if org is not None:
            title_el = next(
                (child for child in org if child.tag.split("}", 1)[-1] == "title"), None
            )
            if title_el is not None and title_el.text:
                info["title"] = title_el.text.strip()
            module_titles = []
            for child in org:
                if child.tag.split("}", 1)[-1] != "item":
                    continue
                item_title = next(
                    (c for c in child if c.tag.split("}", 1)[-1] == "title"), None
                )
                module_titles.append(
                    (item_title.text or "").strip() if item_title is not None else ""
                )
            info["modules"] = len(module_titles)
            info["module_titles"] = [t for t in module_titles if t]
    except (OSError, ET.ParseError, zipfile.BadZipFile, KeyError):
        pass
    return info


def prompt_export(args: argparse.Namespace) -> Path:
    if args.export:
        export = parse_path(args.export)
        if not export.exists():
            raise SystemExit(f"Export path not found: {export}")
        return export
    if args.yes:
        raise SystemExit("--yes needs --export <path> to run non-interactively.")
    return pick_export_interactive()


def pick_export_interactive(*, revisit: bool = False) -> Path:
    # A revisit (changing the export from the review card) repeats the phase,
    # so it keeps the plain heading rather than advancing the journey count.
    print(ui.heading(TERM, "The export") if revisit else phase_heading("The export"))
    print(TERM.dim("  Drag the Brightspace export ZIP (or unpacked folder) into this window,"))
    print(TERM.dim("  then press Return."))
    while True:
        try:
            export = parse_path(input(f"  {TERM.accent('?')} Export path: "))
        except ValueError:
            print(TERM.dim("    Please enter a path."))
            continue
        except EOFError:
            print("")
            raise SystemExit("No export provided.")
        if not export.exists():
            print(TERM.warn(f"    Path not found: {export}"))
            continue
        peek = peek_export(export)
        rows: list[tuple[str, str]] = []
        if peek["title"]:
            rows.append(("Course", TERM.bold(peek["title"])))
        if peek["modules"] is not None:
            rows.append(("Modules", str(peek["modules"])))
            titles = peek.get("module_titles") or []
            # One module per line, deep enough to get past the boilerplate
            # openers (Welcome / Getting Started / Syllabus) into the weeks.
            limit = len(titles) if len(titles) <= 9 else 8
            for title in titles[:limit]:
                if len(title) > 52:
                    title = title[:51] + "…"
                rows.append(("", TERM.supporting(f"  · {title}")))
            if len(titles) > limit:
                rows.append(
                    ("", TERM.supporting(f"    … +{len(titles) - limit} more"))
                )
        rows.append(("Files", f"{peek['files']}  ·  {human_size(peek['size'])}"))
        if not peek["has_manifest"]:
            rows.append(("", TERM.warn("No imsmanifest.xml found — this may not be a Brightspace export.")))
        print()
        print(ui.card(TERM, "The wizard peers into the scroll", rows))
        if ui.confirm(TERM, "Is this the right course?", default=True):
            return export
        print(TERM.dim("    Okay — pick a different file."))


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #
def load_last_answers() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_answers(options: dict) -> None:
    try:
        state_path().parent.mkdir(parents=True, exist_ok=True)
        state_path().write_text(json.dumps(options, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def suggested_output_name(options: dict, fallback: str) -> str:
    """Build the suggested output name from what the user entered (course
    number, or title, plus term) rather than the raw export filename; fall
    back to the export-derived name only when those are blank."""
    core = options.get("course_number") or options.get("course_title") or ""
    text = f"{core} {options.get('term') or ''}".strip()
    return safe_label(text) if text else fallback


def gather_options(args: argparse.Namespace, export: Path, peek: dict) -> dict:
    if not args.yes:
        print(phase_heading("The commission"))
    last = {} if args.yes else load_last_answers()
    use_last = False
    if last and not args.yes:
        summary = last.get("course_title") or last.get("label") or "previous run"
        use_last = ui.confirm(
            TERM, f"Reuse the answers from last time ({summary})?", default=False
        )
    base = last if use_last else {}

    derived_label = safe_label(export.stem if export.is_file() else export.name)
    options = {
        "label": args.label or base.get("label", ""),
        "course_title": args.course_title or base.get("course_title", "") or peek.get("title", ""),
        "course_number": args.course_number or base.get("course_number", ""),
        "term": args.term or base.get("term", ""),
        "render_docx": (not args.no_docx) if args.no_docx is not None else base.get("render_docx", True),
        "layout": args.docx_section_layout or base.get("layout", "top"),
        "run_qa": (not args.skip_qa) if args.skip_qa is not None else base.get("run_qa", True),
        "check_external": args.check_external_links
        if args.check_external_links is not None
        else base.get("check_external", False),
        # Never revive a remembered visual-preview choice. This is an explicit
        # maintainer-only flag, not part of the ordinary commission.
        "render_qa": bool(args.render_docx_check),
    }

    if not args.yes and not use_last:
        print(TERM.dim("  Blueprint front matter — Return keeps the suggestion; leave blank for 'Needs review'."))
        options["course_title"] = ui.prompt_text(TERM, "Course title", default=options["course_title"])
        options["course_number"] = ui.prompt_text(TERM, "Course number (e.g. ABC 123)", default=options["course_number"])
        options["term"] = ui.prompt_text(TERM, "Term (e.g. Fall 2026)", default=options["term"])
        suggested = options["label"] or suggested_output_name(options, derived_label)
        print(TERM.dim(f"  The output name labels the results folder and files — e.g. {suggested}__blueprint.docx"))
        options["label"] = ui.prompt_text(TERM, "Output name", default=suggested)
        options["render_docx"] = ui.confirm(TERM, "Render the DOCX review document?", default=options["render_docx"])
        if options["render_docx"]:
            options["layout"] = ui.choose(
                TERM,
                "DOCX weekly section-label layout:",
                [("top", "Top — label row above each section"), ("left", "Left — label column beside it")],
                default=options["layout"],
            )
        options["run_qa"] = ui.confirm(TERM, "Run the QA report?", default=options["run_qa"])
        if options["run_qa"]:
            options["check_external"] = ui.confirm(
                TERM, "Fetch external URLs live? (network; slower)", default=options["check_external"]
            )
    if not options["label"]:
        options["label"] = suggested_output_name(options, derived_label)
    options["label"] = safe_label(options["label"])
    return options


def options_rows(export: Path, options: dict) -> list[tuple[str, str]]:
    yes_no = lambda flag: "yes" if flag else "no"  # noqa: E731
    rows = [
        ("1. Export", str(export)),
        ("2. Course title", options["course_title"] or TERM.dim("(blank — Needs review)")),
        ("3. Course number", options["course_number"] or TERM.dim("(blank)")),
        ("4. Term", options["term"] or TERM.dim("(blank)")),
        ("5. Output name", options["label"]
         + TERM.dim(f"  → {options['label']}__blueprint_bundle/")),
        ("6. DOCX output", yes_no(options["render_docx"])
         + (f"  ·  layout: {options['layout']}" if options["render_docx"] else "")),
        ("7. QA report", yes_no(options["run_qa"])
         + ("  ·  live external links" if options["run_qa"] and options["check_external"] else "")),
    ]
    if options["render_qa"]:
        rows.append(
            (
                "Advanced render preview",
                "yes  ·  explicit --render-docx-check",
            )
        )
    return rows


def review_options(args: argparse.Namespace, export: Path, options: dict) -> tuple[Path, dict]:
    if args.yes:
        return export, options
    while True:
        print()
        print(ui.card(TERM, "Ready to draft", options_rows(export, options)))
        try:
            reply = input(
                f"  {TERM.accent('?')} Press Return to run, or a number to change: "
            ).strip()
        except EOFError:
            print("")
            return export, options
        if not reply:
            return export, options
        if reply == "1":
            old_derived = safe_label(export.stem if export.is_file() else export.name)
            export = pick_export_interactive(revisit=True)
            if options["label"] == old_derived:
                options["label"] = safe_label(export.stem if export.is_file() else export.name)
        elif reply == "2":
            options["course_title"] = ui.prompt_text(TERM, "Course title", default=options["course_title"])
        elif reply == "3":
            options["course_number"] = ui.prompt_text(TERM, "Course number", default=options["course_number"])
        elif reply == "4":
            options["term"] = ui.prompt_text(TERM, "Term", default=options["term"])
        elif reply == "5":
            print(TERM.dim("    The output name labels the results folder and files."))
            options["label"] = safe_label(ui.prompt_text(TERM, "Output name", default=options["label"]))
        elif reply == "6":
            options["render_docx"] = ui.confirm(TERM, "Render the DOCX review document?", default=options["render_docx"])
            if options["render_docx"]:
                options["layout"] = ui.choose(
                    TERM, "DOCX layout:",
                    [("top", "Top"), ("left", "Left")], default=options["layout"],
                )
        elif reply == "7":
            options["run_qa"] = ui.confirm(TERM, "Run the QA report?", default=options["run_qa"])
            if options["run_qa"]:
                options["check_external"] = ui.confirm(TERM, "Fetch external URLs live?", default=options["check_external"])
        else:
            print(TERM.dim("    Enter 1-7, or Return to run."))


# --------------------------------------------------------------------------- #
# Pipeline run
# --------------------------------------------------------------------------- #
def build_command(bundle: Path, export: Path, options: dict) -> list[str]:
    python = venv_python(bundle)
    cmd: list[str] = [
        str(python),
        str(bundle / "scripts" / "build_blueprint_bundle.py"),
        str(export),
        "--label", options["label"],
        "--progress-events",
    ]
    if options["course_title"]:
        cmd.extend(["--course-title", options["course_title"]])
    if options["course_number"]:
        cmd.extend(["--course-number", options["course_number"]])
    if options["term"]:
        cmd.extend(["--term", options["term"]])
    if not options["run_qa"]:
        cmd.append("--skip-qa")
    if options["check_external"]:
        cmd.append("--check-external-links")
    if not options["render_docx"]:
        cmd.append("--no-docx")
    else:
        cmd.extend(["--docx-section-layout", options["layout"]])
    if options["render_qa"]:
        cmd.append("--render-docx-check")
    output_root = configured_output_root()
    if output_root is not None:
        cmd.extend(["--output-dir", str(output_root)])
    return cmd


def open_log(label: str) -> tuple[Path, "object"]:
    log_dir = logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"blueprint_run_{stamp}_{label}.log"
    return path, path.open("w", encoding="utf-8")


def run_pipeline(
    bundle: Path, cmd: list[str], options: dict, *, pace: bool = False
) -> tuple[int, dict | None, list[str], Path, str | None]:
    """Run the pipeline, rendering progress events live. Returns
    (exit code, run_end event or None, recent output lines, log path,
    name of the step that failed or None). With pace=True each step stays
    on screen at least MIN_STEP_SECONDS so the flavor line registers."""
    log_path, log_file = open_log(options["label"])
    log_file.write("$ " + command_text(cmd) + "\n")

    print(phase_heading("The drafting"))
    board: ui.StepBoard | None = None
    run_end: dict | None = None
    recent: list[str] = []
    steps: list[str] = []
    failed_step: str | None = None

    proc = subprocess.Popen(
        cmd, cwd=str(bundle), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    lines: "queue.Queue[str | None]" = queue.Queue()

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()

    try:
        done = False
        while not done:
            try:
                line = lines.get(timeout=0.12)
            except queue.Empty:
                if board:
                    board.tick()
                continue
            if line is None:
                done = True
                continue
            log_file.write(line)
            stripped = line.strip()
            payload = None
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict) and "event" in parsed:
                        payload = parsed
                except json.JSONDecodeError:
                    payload = None
            if payload is None:
                recent.append(stripped)
                recent = recent[-15:]
                if board:
                    board.output_line(stripped)
                elif stripped:
                    print(TERM.dim("  " + stripped))
                continue
            event = payload["event"]
            if event == "run_start":
                steps = payload["steps"]
                board = ui.StepBoard(TERM, steps, flavor=FLAVOR)
            elif event == "step_start" and board:
                board.step_start(payload["index"])
            elif event == "step_end" and board:
                index = payload["index"]
                if payload["status"] != "ok" and 0 < index <= len(steps):
                    failed_step = steps[index - 1]
                if pace and board.current >= 0:
                    # Let the step linger long enough to be seen; the
                    # pipeline itself has already moved on.
                    while time.monotonic() - board.started < MIN_STEP_SECONDS:
                        board.tick()
                        time.sleep(0.07)
                board.step_end(index, payload["status"], payload.get("seconds", 0.0))
                if payload.get("message"):
                    recent.extend(payload["message"].splitlines())
            elif event == "run_end":
                run_end = payload
        returncode = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.write("\n[canceled by user]\n")
        raise
    finally:
        log_file.close()
        TERM.show_cursor()
    if board:
        board.finish()
    return returncode, run_end, recent, log_path, failed_step


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def _output_row(label: str, path_text: str | None, emphasis: str = "normal") -> tuple[str, str] | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.exists():
        return None
    size = human_size(path.stat().st_size)
    if emphasis == "primary":
        return (TERM.bold(label), TERM.bold(path.name) + f"  {TERM.dim(size)}  " + TERM.good("← start here"))
    if emphasis == "dim":
        return (TERM.dim(label), TERM.dim(f"{path.name}  {size}"))
    return (label, f"{path.name}  {TERM.dim(size)}")


def show_results(run_end: dict, log_path: Path, args: argparse.Namespace, elapsed: float) -> None:
    outputs = run_end.get("outputs", {})
    summary = run_end.get("summary", {})
    bundle_dir = Path(run_end.get("bundle_dir", ""))
    status = run_end.get("status", "ok")
    issues = run_end.get("issues", []) or []

    rows: list[tuple[str, str]] = []
    rows.append(("Drafted in", format_duration(elapsed)))
    if status == "partial":
        rows.append(("Run status", TERM.warn("Partial — review component findings")))
    elif status == "error":
        rows.append(("Run status", TERM.bad("Error — recovered outputs are incomplete")))
    else:
        rows.append(("Run status", TERM.good("Complete")))
    weeks = summary.get("weeks")
    if weeks is not None:
        rows.append(("Weeks", str(weeks)))
    rubrics = summary.get("rubrics")
    if rubrics:
        rows.append(("Rubrics", str(rubrics)))
    qa = summary.get("qa")
    if qa:
        qa_text = f"{qa.get('breaks', 0)} breaks · {qa.get('warnings', 0)} warnings · {qa.get('notes', 0)} notes"
        if qa.get("breaks"):
            qa_text = TERM.bad(qa_text)
        elif qa.get("warnings"):
            qa_text = TERM.warn(qa_text)
        else:
            qa_text = TERM.good(qa_text)
        rows.append(("QA findings", qa_text))
    needs_review = summary.get("needs_review")
    if needs_review is not None:
        rows.append(("Needs review", f"{needs_review} field(s) to fill in during review"))
    if issues:
        rows.append(("Component findings", TERM.warn(str(len(issues)))))
        for issue in issues[:3]:
            rows.append(
                (
                    TERM.dim(issue.get("step", "Component")),
                    TERM.dim(issue.get("message", "Unknown issue").splitlines()[0]),
                )
            )
    rows.append(("", ""))
    primary_key = "docx" if outputs.get("docx") and Path(outputs["docx"]).exists() else "markdown"
    for label, key, quiet_row in (
        ("Blueprint DOCX", "docx", False),
        ("Blueprint MD", "markdown", False),
        ("Model JSON", "json", True),
        ("Activities XLSX", "workbook", False),
        ("Rubrics DOCX", "rubrics_docx", False),
        ("Rubrics XLSX", "rubrics_workbook", False),
        ("Rubrics JSON", "rubrics_json", True),
        ("Rubrics raw/unparsed", "rubrics_unparsed", True),
        ("QA report", "qa_report", False),
        ("DOCX structure QA", "docx_structure_report", False),
        ("Pipeline status", "status_report", False),
    ):
        emphasis = "primary" if key == primary_key else ("dim" if quiet_row else "normal")
        row = _output_row(label, outputs.get(key), emphasis)
        if row:
            rows.append(row)
    rows.append(("", ""))
    rows.append(("Folder", str(bundle_dir)))
    rows.append((TERM.dim("Run log"), TERM.dim(str(log_path))))

    print()
    if status == "ok":
        title = "The blueprint is drafted ✦"
    elif status == "partial":
        title = TERM.warn("The blueprint is drafted — review needed")
    else:
        title = TERM.bad("Recovered blueprint outputs")
    print(ui.card(TERM, title, rows))

    if args.yes or TERM.plain:
        return
    if sys.platform == "darwin" and bundle_dir.exists():
        if ui.confirm(TERM, "Open the output folder in Finder?", default=True):
            subprocess.run(["open", str(bundle_dir)], check=False)
        docx = outputs.get("docx")
        if docx and Path(docx).exists() and ui.confirm(TERM, "Open the DOCX blueprint?", default=False):
            subprocess.run(["open", docx], check=False)
    elif shutil.which("xdg-open") and bundle_dir.exists():
        if ui.confirm(TERM, "Open the output folder?", default=True):
            subprocess.run(["xdg-open", str(bundle_dir)], check=False)


def show_failure(
    returncode: int,
    recent: list[str],
    log_path: Path,
    failed_step: str | None,
    args: argparse.Namespace,
) -> None:
    rows: list[tuple[str, str]] = []
    rows.append(("", TERM.dim(TERM.italic("The spell fizzled — the scroll below tells why."))))
    rows.append(("", ""))
    if failed_step:
        rows.append(("Failed step", TERM.bold(failed_step)))
    rows.append(("Exit code", str(returncode)))
    rows.append(("", ""))
    # The failing step's message reaches us twice (step_end event + the
    # pipeline's own exit output), so dedupe for display.
    detail: list[str] = []
    seen: set[str] = set()
    for entry in recent:
        for part in entry.splitlines():
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                detail.append(part)
    for line in detail[-10:]:
        rows.append(("", TERM.dim(line)))
    rows.append(("", ""))
    rows.append(("Full log", str(log_path)))
    print()
    print(ui.card(TERM, TERM.bad("The drafting failed"), rows))
    print(TERM.dim("  Fix the issue above and rerun; the wizard remembers your answers."))
    print(TERM.dim("  If the setup itself looks broken, try: bash blueprint_wizard.sh --doctor --fix"))
    if args.yes or TERM.plain:
        return
    opener = "open" if sys.platform == "darwin" else shutil.which("xdg-open")
    if opener and log_path.exists() and ui.confirm(TERM, "Open the full run log?", default=False):
        subprocess.run([opener, str(log_path)], check=False)


# --------------------------------------------------------------------------- #
# Main flow
# --------------------------------------------------------------------------- #
def run_wizard(args: argparse.Namespace) -> int:
    bundle = args.bundle_dir.expanduser().resolve()
    ensure_managed_data_dirs()
    PHASE["enabled"] = not args.yes
    PHASE["total"] = 4 - (1 if args.export else 0)
    PHASE["current"] = 0
    if not args.no_splash and not args.yes:
        art.splash(TERM, animate=True, version=f"v{VERSION}")
    else:
        print(TERM.accent(TERM.bold("  Blueprint Wizard")) + TERM.dim(f"  v{VERSION}"))

    preparation_checks(bundle, args)
    if (
        not args.no_update_check
        and not args.yes
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    ):
        report_update_check(force=False, offer_open=True)

    export = prompt_export(args)
    peek = peek_export(export)
    options = gather_options(args, export, peek)
    export, options = review_options(args, export, options)
    if options["render_qa"]:
        require_advanced_render_tools(bundle)

    cmd = build_command(bundle, export, options)
    print()
    print(TERM.dim("  $ " + command_text(cmd)))
    if not ui.confirm(TERM, "Begin drafting?", default=True, assume_yes=args.yes):
        print("  Canceled.")
        return 2

    started = time.monotonic()
    pace = not TERM.plain and not args.brisk
    returncode, run_end, recent, log_path, failed_step = run_pipeline(
        bundle, cmd, options, pace=pace
    )
    elapsed = time.monotonic() - started
    if not TERM.plain:
        # A tap on the shoulder for anyone who tabbed away during a long run.
        sys.stdout.write("\a")
        sys.stdout.flush()
    outputs = (run_end or {}).get("outputs", {})
    usable_output = any(
        path_text and Path(path_text).exists()
        for path_text in (outputs.get("docx"), outputs.get("markdown"))
    )
    if run_end and usable_output:
        status = run_end.get("status")
        if not TERM.plain:
            print()
            if status == "ok":
                print("  " + TERM.good("✦") + " The drafting is complete.")
            elif status == "partial":
                print(
                    "  "
                    + TERM.warn("!")
                    + " The blueprint was produced with component findings to review."
                )
            else:
                print(
                    "  "
                    + TERM.warn("!")
                    + " The pipeline reported an error, but recovered outputs are available."
                )
            if pace:
                time.sleep(0.9)
        save_answers(options)
        show_results(run_end, log_path, args, elapsed)
        return 0 if status in {"ok", "partial"} else (returncode or 1)
    show_failure(returncode, recent, log_path, failed_step, args)
    return returncode or 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"blueprint-wizard v{VERSION}")
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle_dir(), help="Path to brightspace-blueprint-bundle")
    parser.add_argument("--doctor", action="store_true", help="Check setup without running an export")
    parser.add_argument("--fix", action="store_true", help="With --doctor, offer to install missing bundle dependencies")
    parser.add_argument(
        "--check-for-updates",
        action="store_true",
        help="Check GitHub for the latest published Wizard release, then exit",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip the once-daily automatic update check",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Non-interactive: accept defaults; requires --export")
    parser.add_argument(
        "--no-system-install",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--plain", action="store_true", help="No color, art, or animation")
    parser.add_argument("--no-splash", action="store_true", help="Skip the splash screen")
    parser.add_argument(
        "--brisk", action="store_true",
        help="Skip the theatrical step pacing (each step normally lingers ~1s so its message is readable)",
    )
    parser.add_argument("--export", help="Brightspace export ZIP or unpacked folder")
    parser.add_argument("--label", help="Optional output label")
    parser.add_argument("--course-title", help="Course title for the blueprint front matter")
    parser.add_argument("--course-number", help="Course number metadata (e.g. ABC 123)")
    parser.add_argument("--term", help="Term metadata (e.g. Fall 2026)")
    parser.add_argument(
        "--render-docx-check",
        dest="render_docx_check",
        action="store_true",
        default=False,
        help=(
            "Advanced maintainer preview: render DOCX pages for human inspection "
            "(requires the bundle's optional requirements-render.txt, LibreOffice, and Poppler)"
        ),
    )
    parser.add_argument(
        "--no-render-docx-check",
        dest="render_docx_check",
        action="store_false",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--check-external-links", dest="check_external_links", action="store_true", default=None)
    parser.add_argument("--no-check-external-links", dest="check_external_links", action="store_false")
    parser.add_argument("--skip-qa", dest="skip_qa", action="store_true", default=None)
    parser.add_argument("--no-skip-qa", dest="skip_qa", action="store_false")
    parser.add_argument("--no-docx", dest="no_docx", action="store_true", default=None)
    parser.add_argument("--docx", dest="no_docx", action="store_false")
    parser.add_argument("--docx-section-layout", choices=("top", "left"), default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global TERM
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv or sys.argv[1:])
    TERM = ui.Term(plain=args.plain)
    ensure_managed_data_dirs()
    bundle = args.bundle_dir.expanduser().resolve()
    try:
        if args.check_for_updates:
            report_update_check(
                force=True,
                offer_open=not args.yes and sys.stdin.isatty(),
            )
            return 0
        if args.doctor:
            validate_bundle(bundle)
            if args.fix:
                ensure_venv(bundle, fix=True, assume_yes=args.yes)
                ensure_requirements(bundle, fix=True, assume_yes=args.yes)
            return print_doctor(bundle)
        return run_wizard(args)
    except KeyboardInterrupt:
        TERM.show_cursor()
        print(f"\n  Canceled. Any partial run log is under {logs_dir()}.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
