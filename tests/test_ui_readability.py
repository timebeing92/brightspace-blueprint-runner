from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ui  # noqa: E402


def color_term() -> ui.Term:
    term = ui.Term(plain=True)
    term.plain = False
    return term


def test_confirmation_choice_uses_normal_intensity() -> None:
    term = color_term()
    with patch("builtins.input", return_value="") as mocked_input:
        assert ui.confirm(term, "Continue?", default=False) is False

    rendered_prompt = mocked_input.call_args.args[0]
    assert "\x1b[22m[y/N]\x1b[0m" in rendered_prompt
    assert "\x1b[2m[y/N]\x1b[0m" not in rendered_prompt


def test_text_default_uses_normal_intensity() -> None:
    term = color_term()
    with patch("builtins.input", return_value="") as mocked_input:
        assert ui.prompt_text(term, "Course title", default="Demo") == "Demo"

    rendered_prompt = mocked_input.call_args.args[0]
    assert "\x1b[22m [Demo]\x1b[0m" in rendered_prompt
    assert "\x1b[2m [Demo]\x1b[0m" not in rendered_prompt


def test_active_flavor_line_is_readable_but_still_italic() -> None:
    term = color_term()
    flavor = "The wizard holds the scroll to the light…"
    board = ui.StepBoard(term, ["Probe manifest"], flavor={"Probe manifest": flavor})
    board.current = 0
    board.state[0] = "run"
    board.started = time.monotonic()

    output = io.StringIO()
    with patch("sys.stdout", output):
        board.draw()

    rendered = output.getvalue()
    assert f"\x1b[3m\x1b[22m{flavor}\x1b[0m\x1b[0m" in rendered
    assert f"\x1b[2m\x1b[3m{flavor}" not in rendered


def test_plain_mode_keeps_identical_words_without_ansi() -> None:
    term = ui.Term(plain=True)
    assert term.secondary("[y/N]") == "[y/N]"
    assert term.secondary("The wizard holds the scroll to the light…") == (
        "The wizard holds the scroll to the light…"
    )
