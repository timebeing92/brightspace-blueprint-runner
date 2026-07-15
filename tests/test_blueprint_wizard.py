from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import blueprint_wizard as wizard  # noqa: E402
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
