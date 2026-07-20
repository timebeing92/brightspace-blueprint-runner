from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import blueprint_wizard as wizard  # noqa: E402
import update_check  # noqa: E402
import ui  # noqa: E402


def test_build_command_uses_progress_events_and_docx_layout(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    export = tmp_path / "course.zip"
    options = {
        "label": "demo_course",
        "course_title": "Demo Course",
        "course_number": "DEMO 100",
        "term": "Fall 2026",
        "run_qa": True,
        "check_external": False,
        "render_docx": True,
        "layout": "left",
        "render_qa": False,
    }

    cmd = wizard.build_command(bundle, export, options)

    assert cmd[0] == str(wizard.venv_python(bundle))
    assert cmd[1] == str(bundle / "scripts" / "build_blueprint_bundle.py")
    assert str(export) in cmd
    assert "--progress-events" in cmd
    assert cmd[cmd.index("--label") + 1] == "demo_course"
    assert cmd[cmd.index("--course-title") + 1] == "Demo Course"
    assert cmd[cmd.index("--docx-section-layout") + 1] == "left"
    assert "--no-docx" not in cmd
    assert "--skip-qa" not in cmd


def test_build_command_can_skip_docx_and_qa(tmp_path: Path) -> None:
    options = {
        "label": "json_only",
        "course_title": "",
        "course_number": "",
        "term": "",
        "run_qa": False,
        "check_external": False,
        "render_docx": False,
        "layout": "top",
        "render_qa": False,
    }

    cmd = wizard.build_command(tmp_path / "bundle", tmp_path / "course.zip", options)

    assert "--skip-qa" in cmd
    assert "--no-docx" in cmd
    assert "--docx-section-layout" not in cmd


def test_managed_mode_keeps_state_logs_and_outputs_outside_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    install_root = tmp_path / "Blueprint Wizard"
    data = install_root / "user-data"
    output = data / "outputs"
    monkeypatch.setenv(wizard.INSTALL_ROOT_ENV, str(install_root))
    monkeypatch.setenv(wizard.DATA_ROOT_ENV, str(data))
    monkeypatch.setenv(wizard.OUTPUT_ROOT_ENV, str(output))
    launcher = install_root / "launcher" / "stable_launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setenv(wizard.LAUNCHER_PATH_ENV, str(launcher))

    assert wizard.managed_mode()
    assert wizard.managed_launcher_path() == launcher
    assert wizard.state_path() == data / "settings" / "last_run.json"
    assert wizard.update_cache_path() == data / "update-cache" / "release_check.json"
    assert wizard.logs_dir() == data / "logs"
    assert wizard.configured_output_root() == output

    wizard.ensure_managed_data_dirs()
    assert (data / "settings").is_dir()
    assert (data / "logs").is_dir()
    assert output.is_dir()
    assert (data / "update-cache").is_dir()

    options = {
        "label": "managed",
        "course_title": "",
        "course_number": "",
        "term": "",
        "run_qa": True,
        "check_external": False,
        "render_docx": True,
        "layout": "top",
        "render_qa": False,
    }
    cmd = wizard.build_command(
        tmp_path / "versions" / "2.8.0" / "brightspace-blueprint-bundle",
        tmp_path / "course.zip",
        options,
    )
    assert cmd[cmd.index("--output-dir") + 1] == str(output)


def test_portable_mode_preserves_existing_local_paths(
    monkeypatch,
) -> None:
    monkeypatch.delenv(wizard.INSTALL_ROOT_ENV, raising=False)
    monkeypatch.delenv(wizard.DATA_ROOT_ENV, raising=False)
    monkeypatch.delenv(wizard.OUTPUT_ROOT_ENV, raising=False)
    monkeypatch.delenv(wizard.LAUNCHER_PATH_ENV, raising=False)

    assert not wizard.managed_mode()
    assert wizard.state_path() == wizard.runner_root() / ".last_run.json"
    assert wizard.update_cache_path() == wizard.runner_root() / ".update_check.json"
    assert wizard.logs_dir() == wizard.runner_root() / "logs"
    assert wizard.configured_output_root() is None
    assert wizard.managed_launcher_path() is None


def test_advanced_render_preview_requires_explicit_option(tmp_path: Path) -> None:
    options = {
        "label": "advanced_preview",
        "course_title": "",
        "course_number": "",
        "term": "",
        "run_qa": True,
        "check_external": False,
        "render_docx": True,
        "layout": "top",
        "render_qa": True,
    }

    cmd = wizard.build_command(tmp_path / "bundle", tmp_path / "course.zip", options)

    assert "--render-docx-check" in cmd


def test_core_setup_excludes_visual_preview_dependencies() -> None:
    assert ("pdf2image", "pdf2image") not in wizard.REQUIRED_MODULES
    assert [package for _, package in wizard.REQUIRED_MODULES] == [
        "openpyxl",
        "python-docx",
        "jsonschema",
    ]


def test_remembered_visual_preview_is_not_reactivated(
    tmp_path: Path, monkeypatch
) -> None:
    args = argparse.Namespace(
        yes=False,
        label=None,
        course_title=None,
        course_number=None,
        term=None,
        no_docx=None,
        docx_section_layout=None,
        skip_qa=None,
        check_external_links=None,
        render_docx_check=False,
    )
    export = tmp_path / "course.zip"
    export.write_bytes(b"fixture")
    monkeypatch.setattr(
        wizard,
        "load_last_answers",
        lambda: {
            "label": "remembered",
            "render_docx": True,
            "layout": "top",
            "run_qa": True,
            "check_external": False,
            "render_qa": True,
        },
    )
    monkeypatch.setattr(wizard.ui, "confirm", lambda *args, **kwargs: True)

    options = wizard.gather_options(args, export, {"title": "Demo"})

    assert options["render_qa"] is False
    assert all(
        label != "8. Visual render QA"
        for label, _ in wizard.options_rows(export, options)
    )


def test_missing_advanced_preview_tools_do_not_affect_core_setup(
    tmp_path: Path,
) -> None:
    missing = wizard.missing_advanced_render_tools(tmp_path)

    assert "pdf2image (requirements-render.txt)" in missing
    with pytest.raises(SystemExit, match="Normal DOCX generation and structural QA"):
        wizard.require_advanced_render_tools(tmp_path)


def test_update_check_cli_controls_are_explicit() -> None:
    forced = wizard.parse_args(["--check-for-updates"])
    disabled = wizard.parse_args(["--no-update-check"])

    assert forced.check_for_updates is True
    assert forced.no_update_check is False
    assert disabled.no_update_check is True
    assert disabled.check_for_updates is False


def test_available_update_is_reported_without_replacing_files(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    wizard.TERM = ui.Term(plain=True)
    monkeypatch.setattr(wizard, "update_cache_path", lambda: tmp_path / "cache.json")
    monkeypatch.setattr(
        wizard.update_check,
        "check_latest_release",
        lambda **kwargs: update_check.UpdateStatus(
            state="update_available",
            current_version=wizard.VERSION,
            latest_version="9.1.0",
            latest_tag="v9.1.0",
            release_name="Blueprint Wizard v9.1.0",
            release_url="https://github.com/example/releases/tag/v9.1.0",
        ),
    )
    monkeypatch.setattr(wizard.update_check, "notice_is_due", lambda *args, **kwargs: True)
    notified: list[str] = []
    monkeypatch.setattr(
        wizard.update_check,
        "mark_notified",
        lambda *args, **kwargs: notified.append(kwargs["latest_version"]),
    )
    monkeypatch.setattr(wizard.ui, "confirm", lambda *args, **kwargs: False)

    wizard.report_update_check(force=False, offer_open=True)
    out = capsys.readouterr().out

    assert "Blueprint Wizard update available" in out
    assert f"v{wizard.VERSION}" in out
    assert "v9.1.0" in out
    assert "no files were replaced" in out
    assert notified == ["9.1.0"]


def test_forced_offline_update_check_reports_but_does_not_fail(
    monkeypatch,
    capsys,
) -> None:
    wizard.TERM = ui.Term(plain=True)
    monkeypatch.setattr(
        wizard.update_check,
        "check_latest_release",
        lambda **kwargs: update_check.UpdateStatus(
            state="unavailable",
            current_version=wizard.VERSION,
            error="offline",
        ),
    )

    wizard.report_update_check(force=True, offer_open=False)
    out = capsys.readouterr().out

    assert "Update check unavailable" in out
    assert "still usable" in out


def test_managed_update_installs_through_stable_launcher_and_requests_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wizard.TERM = ui.Term(plain=True)
    install_root = tmp_path / "Blueprint Wizard"
    launcher = install_root / "launcher" / "stable_launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setenv(wizard.INSTALL_ROOT_ENV, str(install_root))
    monkeypatch.setenv(wizard.LAUNCHER_PATH_ENV, str(launcher))
    confirmations = iter([True, True])
    monkeypatch.setattr(
        wizard.ui,
        "confirm",
        lambda *args, **kwargs: next(confirmations),
    )
    commands: list[list[str]] = []

    def fake_run(command, *, check):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(wizard.subprocess, "run", fake_run)
    monkeypatch.setattr(wizard, "update_cache_path", lambda: tmp_path / "cache.json")
    monkeypatch.setattr(
        wizard.update_check,
        "check_latest_release",
        lambda **kwargs: update_check.UpdateStatus(
            state="update_available",
            current_version=wizard.VERSION,
            latest_version="2.8.0",
            latest_tag="v2.8.0",
            release_name="Blueprint Wizard v2.8.0",
            release_url="https://github.com/timebeing92/releases/tag/v2.8.0",
        ),
    )
    monkeypatch.setattr(wizard.update_check, "notice_is_due", lambda *args, **kwargs: True)
    monkeypatch.setattr(wizard.update_check, "mark_notified", lambda *args, **kwargs: None)

    restart = wizard.report_update_check(force=True, offer_open=True)

    assert restart is True
    assert commands == [
        [
            sys.executable,
            str(launcher),
            "--install-root",
            str(install_root),
            "--update",
            "--expected-version",
            "2.8.0",
        ]
    ]


def test_managed_update_failure_keeps_running_version_active(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    wizard.TERM = ui.Term(plain=True)
    install_root = tmp_path / "Blueprint Wizard"
    launcher = install_root / "launcher" / "stable_launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setenv(wizard.INSTALL_ROOT_ENV, str(install_root))
    monkeypatch.setenv(wizard.LAUNCHER_PATH_ENV, str(launcher))
    monkeypatch.setattr(
        wizard.subprocess,
        "run",
        lambda command, *, check: subprocess.CompletedProcess(command, 1),
    )

    assert wizard.install_managed_update("2.8.0") is False
    assert "current Wizard remains active" in capsys.readouterr().out


def test_run_pipeline_consumes_progress_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(wizard, "runner_root", lambda: tmp_path)
    wizard.TERM = ui.Term(plain=True)
    fake = tmp_path / "fake_bundle.py"
    run_end = {
        "event": "run_end",
        "status": "ok",
        "bundle_dir": str(tmp_path / "out"),
        "outputs": {
            "markdown": str(tmp_path / "out" / "demo.md"),
            "json": str(tmp_path / "out" / "demo.json"),
            "docx": str(tmp_path / "out" / "demo.docx"),
            "workbook": str(tmp_path / "out" / "activities.xlsx"),
            "rubrics_json": str(tmp_path / "out" / "rubrics.json"),
            "rubrics_workbook": str(tmp_path / "out" / "rubrics.xlsx"),
            "rubrics_docx": str(tmp_path / "out" / "rubrics.docx"),
            "qa_report": None,
            "render_qa_dir": None,
        },
        "summary": {"weeks": 2, "rubrics": 1, "diagnostics": 0, "needs_review": 0, "qa": None},
    }
    fake.write_text(
        "\n".join(
            [
                "import json",
                "events = [",
                "  {'event': 'run_start', 'schema': 'coursecraft.progress/1', 'total': 1, 'steps': ['Render rubrics DOCX']},",
                "  {'event': 'step_start', 'index': 1, 'label': 'Render rubrics DOCX'},",
                "  {'event': 'step_end', 'index': 1, 'label': 'Render rubrics DOCX', 'status': 'ok', 'seconds': 0.01},",
                f"  {run_end!r},",
                "]",
                "for event in events:",
                "    print(json.dumps(event), flush=True)",
            ]
        ),
        encoding="utf-8",
    )

    code, parsed_end, recent, log_path, failed_step = wizard.run_pipeline(
        tmp_path,
        [sys.executable, str(fake)],
        {"label": "demo"},
        pace=False,
    )

    assert code == 0
    assert parsed_end == run_end
    assert failed_step is None
    assert recent == []
    assert log_path.exists()
    assert "run_end" in log_path.read_text(encoding="utf-8")


def test_show_results_lists_rubric_docx(tmp_path: Path, capsys) -> None:
    wizard.TERM = ui.Term(plain=True)
    bundle_dir = tmp_path / "demo__blueprint_bundle"
    bundle_dir.mkdir()
    outputs = {}
    for key, name in {
        "docx": "demo__blueprint.docx",
        "markdown": "demo__blueprint.md",
        "json": "demo__blueprint.json",
        "workbook": "demo__course_activities.xlsx",
        "rubrics_docx": "demo__rubrics.docx",
        "rubrics_workbook": "demo__rubrics.xlsx",
        "rubrics_json": "demo__rubrics.json",
        "run_identity": "demo__run_identity.json",
    }.items():
        path = bundle_dir / name
        path.write_text("demo", encoding="utf-8")
        outputs[key] = str(path)

    run_end = {
        "outputs": outputs,
        "summary": {"weeks": 2, "rubrics": 1, "needs_review": 0},
        "bundle_dir": str(bundle_dir),
    }
    args = argparse.Namespace(yes=True)

    wizard.show_results(run_end, tmp_path / "run.log", args, 12.0)
    out = capsys.readouterr().out

    assert "Rubrics" in out
    assert "Rubrics DOCX" in out
    assert "demo__rubrics.docx" in out
    assert "Run identity" in out
    assert "demo__run_identity.json" in out


def test_show_results_surfaces_partial_status_and_report(tmp_path: Path, capsys) -> None:
    wizard.TERM = ui.Term(plain=True)
    bundle_dir = tmp_path / "demo__blueprint_bundle"
    bundle_dir.mkdir()
    markdown = bundle_dir / "demo__blueprint.md"
    status_report = bundle_dir / "demo__pipeline_status.md"
    markdown.write_text("# Demo\n", encoding="utf-8")
    status_report.write_text("# Pipeline Status\n", encoding="utf-8")
    run_end = {
        "status": "partial",
        "outputs": {
            "markdown": str(markdown),
            "status_report": str(status_report),
        },
        "issues": [
            {
                "step": "Check DOCX structure",
                "status": "failed",
                "message": "A component check failed, but the blueprint remains usable.",
            }
        ],
        "summary": {"weeks": 2, "rubrics": 1, "needs_review": 0},
        "bundle_dir": str(bundle_dir),
    }
    args = argparse.Namespace(yes=True)

    wizard.show_results(run_end, tmp_path / "run.log", args, 12.0)
    out = capsys.readouterr().out

    assert "Partial" in out
    assert "Check DOCX structure" in out
    assert "Pipeline status" in out
    assert "demo__pipeline_status.md" in out


@pytest.mark.parametrize("raw", [False, "false", "no", "0", ""])
def test_unusable_delivery_never_broadens_falsy_known_values(raw) -> None:
    reason = wizard.unusable_delivery(
        {
            "status": "partial",
            "delivery": {
                "usable": raw,
                "empty": True,
                "core_failures": ["Probe manifest"],
            },
        }
    )

    assert reason == "Core evidence steps failed: Probe manifest"


def test_delivery_reader_preserves_legacy_and_ignores_unknown_keys() -> None:
    assert wizard.unusable_delivery({"status": "partial"}) is None
    assert wizard.unusable_delivery({"status": "partial", "delivery": None}) is None
    assert wizard.unusable_delivery(
        {
            "delivery": {
                "usable": True,
                "empty": False,
                "core_failures": [],
                "future_addition": {"safe": True},
            }
        }
    ) is None


def test_core_failure_names_are_coerced_and_capped() -> None:
    reason = wizard.unusable_delivery(
        {
            "delivery": {
                "usable": False,
                "core_failures": [None, 42, "x" * 100, "c", "d", "e", "f", "g"],
            }
        }
    )

    assert "42" in reason
    assert "x" * 80 in reason
    assert "x" * 81 not in reason
    assert reason.endswith("c, d, e, f")
    assert ", g" not in reason


def test_show_results_names_a_producer_approved_empty_course(tmp_path: Path, capsys) -> None:
    wizard.TERM = ui.Term(plain=True)
    bundle_dir = tmp_path / "empty__blueprint_bundle"
    bundle_dir.mkdir()
    markdown = bundle_dir / "empty__blueprint.md"
    markdown.write_text("# Empty course\n", encoding="utf-8")
    run_end = {
        "status": "ok",
        "delivery": {"usable": True, "empty": True, "core_failures": []},
        "outputs": {"markdown": str(markdown)},
        "summary": {"weeks": 0},
        "bundle_dir": str(bundle_dir),
    }

    wizard.show_results(run_end, tmp_path / "run.log", argparse.Namespace(yes=True), 2.0)
    out = capsys.readouterr().out

    assert "mirrors an empty course" in out
    assert "empty__blueprint.md" in out


def test_unusable_delivery_card_never_offers_emitted_documents(tmp_path: Path, capsys) -> None:
    wizard.TERM = ui.Term(plain=True)
    emitted = tmp_path / "hollow__blueprint.md"
    emitted.write_text("# Hollow\n", encoding="utf-8")
    run_end = {
        "status": "partial",
        "delivery": {
            "usable": False,
            "empty": True,
            "core_failures": ["Probe manifest", "Reconstruct course structure"],
        },
        "outputs": {"markdown": str(emitted)},
    }

    wizard.show_unusable_delivery(
        run_end, tmp_path / "run.log", argparse.Namespace(yes=True)
    )
    out = capsys.readouterr().out

    assert "documents do not mirror the export" in out
    assert "Probe manifest" in out
    assert "Reconstruct course structure" in out
    assert emitted.name not in out
