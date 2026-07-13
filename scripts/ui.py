#!/usr/bin/env python3
"""Reusable pure-stdlib ANSI terminal components for the runner wizards.

Design rule (see the workbench DEVELOPMENT_ROADMAP decision record
2026-07-09): these components carry no blueprint-specific knowledge so future
runners and a multi-tool launcher can reuse them. Rendering degrades cleanly:
no TTY, ``NO_COLOR``, ``TERM=dumb``, or ``--plain`` all fall back to plain
text with the same information content.
"""
from __future__ import annotations

import os
import shutil
import sys
import time


class Term:
    """Terminal capabilities + tiny styling API. All styling no-ops in plain mode."""

    def __init__(self, plain: bool = False) -> None:
        self.is_tty = sys.stdout.isatty()
        self.plain = (
            plain
            or not self.is_tty
            or os.environ.get("NO_COLOR") is not None
            or os.environ.get("TERM", "") == "dumb"
        )
        colorterm = os.environ.get("COLORTERM", "")
        self.truecolor = not self.plain and ("truecolor" in colorterm or "24bit" in colorterm)
        if os.name == "nt" and not self.plain:  # enable VT processing on Windows 10+
            os.system("")

    @property
    def width(self) -> int:
        return min(shutil.get_terminal_size((80, 24)).columns, 100)

    # -- styling ------------------------------------------------------------
    def _wrap(self, code: str, text: str) -> str:
        if self.plain:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def italic(self, text: str) -> str:
        return self._wrap("3", text)

    def fg(self, color256: int, text: str, *, bold: bool = False) -> str:
        prefix = "1;" if bold else ""
        return self._wrap(f"{prefix}38;5;{color256}", text)

    # Palette (256-color indexes; chosen to hold up on light and dark themes)
    def accent(self, text: str, *, bold: bool = False) -> str:   # blueprint cyan
        return self.fg(45, text, bold=bold)

    def good(self, text: str) -> str:
        return self.fg(78, text)

    def bad(self, text: str) -> str:
        return self.fg(203, text)

    def warn(self, text: str) -> str:
        return self.fg(214, text)

    # -- cursor / screen ----------------------------------------------------
    def hide_cursor(self) -> None:
        if not self.plain:
            sys.stdout.write("\x1b[?25l")

    def show_cursor(self) -> None:
        if not self.plain:
            sys.stdout.write("\x1b[?25h")

    def lines_up(self, count: int) -> None:
        if not self.plain and count > 0:
            sys.stdout.write(f"\x1b[{count}F\x1b[0J")


def visible_len(text: str) -> int:
    """Length of a string with ANSI escape sequences removed."""
    length, in_escape = 0, False
    for char in text:
        if in_escape:
            if char.isalpha():
                in_escape = False
        elif char == "\x1b":
            in_escape = True
        else:
            length += 1
    return length


def clip(text: str, width: int) -> str:
    """Truncate to a visible width, keeping ANSI escapes intact.

    In-place redraws count lines, so a line that soft-wraps corrupts the
    display; clipped output gets an ellipsis and a style reset.
    """
    if width <= 0 or visible_len(text) <= width:
        return text
    out: list[str] = []
    length, in_escape, styled = 0, False, False
    for char in text:
        if in_escape:
            out.append(char)
            if char.isalpha():
                in_escape = False
        elif char == "\x1b":
            out.append(char)
            in_escape = True
            styled = True
        else:
            if length >= width - 1:
                break
            out.append(char)
            length += 1
    return "".join(out) + "…" + ("\x1b[0m" if styled else "")


# ---------------------------------------------------------------------------
# Static components
# ---------------------------------------------------------------------------
GLYPH = {
    "ok": ("✓", "[ ok ]"),
    "bad": ("✗", "[MISS]"),
    "todo": ("◌", "[ -- ]"),
    "run": ("◈", "[ .. ]"),
}


def status_line(term: Term, status: str, label: str, detail: str = "") -> str:
    glyph, plain_glyph = GLYPH.get(status, GLYPH["todo"])
    mark = plain_glyph if term.plain else glyph
    if status == "ok":
        mark = term.good(mark)
    elif status == "bad":
        mark = term.bad(mark)
    elif status == "run":
        mark = term.accent(mark)
    text = f"  {mark} {label}"
    if detail:
        text += "  " + term.dim(detail)
    return text


def rule(term: Term, width: int | None = None) -> str:
    return term.dim(("─" if not term.plain else "-") * (width or min(term.width, 72)))


def heading(term: Term, text: str) -> str:
    return "\n" + term.accent(term.bold(text)) + "\n" + rule(term)


def card(term: Term, title: str, rows: list[tuple[str, str]], *, min_width: int = 44) -> str:
    """A boxed key/value panel. Rows with an empty key render as full-width lines."""
    label_width = max((visible_len(k) for k, _ in rows if k), default=0)
    body_lines: list[str] = []
    for key, value in rows:
        if key:
            body_lines.append(f"{key.ljust(label_width)}  {value}")
        else:
            body_lines.append(value)
    inner = max(
        min_width, visible_len(title) + 2, *(visible_len(line) for line in body_lines)
    ) + 2
    inner = min(inner, term.width - 4)
    if term.plain:
        out = [f"-- {title} " + "-" * max(0, inner - visible_len(title) - 2)]
        out.extend("   " + line for line in body_lines)
        out.append("-" * (inner + 3))
        return "\n".join(out)
    top = "╭─ " + term.bold(title) + " " + "─" * max(0, inner - visible_len(title) - 2) + "╮"
    out = [top]
    for line in body_lines:
        pad = " " * max(0, inner - visible_len(line))
        out.append("│ " + line + pad + " │")
    out.append("╰" + "─" * (inner + 2) + "╯")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
def prompt_text(term: Term, prompt: str, *, default: str = "") -> str:
    suffix = term.dim(f" [{default}]") if default else ""
    try:
        reply = input(f"  {term.accent('?')} {prompt}{suffix}: ").strip()
    except EOFError:
        print("")
        return default
    return reply or default


def confirm(term: Term, prompt: str, *, default: bool = False, assume_yes: bool = False) -> bool:
    if assume_yes:
        print(f"  {term.accent('?')} {prompt} {term.dim('yes (--yes)')}")
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        reply = input(f"  {term.accent('?')} {prompt} {term.dim(suffix)} ").strip().lower()
    except EOFError:
        print("")
        return default
    if not reply:
        return default
    return reply in {"y", "yes"}


def choose(term: Term, prompt: str, options: list[tuple[str, str]], *, default: str) -> str:
    """Numbered single-choice menu; returns the chosen option key."""
    print(f"  {term.accent('?')} {prompt}")
    keys = [key for key, _ in options]
    for index, (key, label) in enumerate(options, start=1):
        marker = term.dim(" (default)") if key == default else ""
        print(f"      {term.bold(str(index))}. {label}{marker}")
    while True:
        try:
            reply = input(f"    choice [{keys.index(default) + 1}]: ").strip()
        except EOFError:
            print("")
            return default
        if not reply:
            return default
        if reply.isdigit() and 1 <= int(reply) <= len(options):
            return keys[int(reply) - 1]
        if reply in keys:
            return reply
        print(term.dim(f"    enter 1-{len(options)}"))


# ---------------------------------------------------------------------------
# Live step board
# ---------------------------------------------------------------------------
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
# A small star drifting across the flavor line while a step runs.
SPARKLE = ["✦ · ·", "· ✦ ·", "· · ✦", "· ✦ ·"]


class StepBoard:
    """Live display for pipeline steps driven by progress events.

    TTY mode redraws in place; plain mode prints one line per state change.
    """

    def __init__(self, term: Term, steps: list[str], flavor: dict[str, str] | None = None) -> None:
        self.term = term
        self.steps = steps
        self.flavor = flavor or {}
        self.state = ["todo"] * len(steps)
        self.seconds = [0.0] * len(steps)
        self.current = -1
        self.started = 0.0
        self.tail: list[str] = []
        self._drawn_lines = 0
        self._spin = 0

    # -- event handlers -----------------------------------------------------
    def step_start(self, index: int) -> None:
        self.current = index - 1
        if 0 <= self.current < len(self.steps):
            self.state[self.current] = "run"
            self.started = time.monotonic()
        if self.term.plain:
            print(f"[{index}/{len(self.steps)}] {self.steps[index - 1]} ...", flush=True)
        else:
            self.draw()

    def step_end(self, index: int, status: str, seconds: float) -> None:
        slot = index - 1
        if 0 <= slot < len(self.steps):
            self.state[slot] = "ok" if status == "ok" else "bad"
            self.seconds[slot] = seconds
        if self.term.plain:
            print(f"[{index}/{len(self.steps)}] {'done' if status == 'ok' else 'FAILED'} "
                  f"({seconds:.1f}s)", flush=True)
        else:
            self.draw()

    def output_line(self, line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        self.tail.append(line)
        self.tail = self.tail[-4:]
        if not self.term.plain:
            self.draw()

    def tick(self) -> None:
        if not self.term.plain and 0 <= self.current < len(self.steps):
            self._spin += 1
            self.draw()

    # -- rendering ----------------------------------------------------------
    def draw(self) -> None:
        term = self.term
        term.lines_up(self._drawn_lines)
        lines: list[str] = []
        for index, label in enumerate(self.steps):
            state = self.state[index]
            if state == "run":
                mark = term.accent(SPINNER[self._spin % len(SPINNER)])
                elapsed = time.monotonic() - self.started
                suffix = term.dim(f"{elapsed:5.1f}s")
                lines.append(f"  {mark} {term.bold(label)}  {suffix}")
                flavor = self.flavor.get(label)
                if flavor:
                    twinkle = SPARKLE[(self._spin // 2) % len(SPARKLE)]
                    lines.append("")
                    lines.append(
                        "        " + term.dim(term.italic(flavor)) + "  " + term.accent(twinkle)
                    )
                    lines.append("")
            elif state == "ok":
                lines.append(f"  {term.good('✓')} {label}  {term.dim(f'{self.seconds[index]:5.1f}s')}")
            elif state == "bad":
                lines.append(f"  {term.bad('✗')} {term.bold(label)}")
            else:
                lines.append(term.dim(f"  ○ {label}"))
        if self.tail:
            lines.append(term.dim("  ┆ " + "·" * 3))
            width = term.width - 6
            for raw in self.tail:
                lines.append(term.dim("  ┆ " + raw[:width]))
        limit = max(20, term.width - 2)
        lines = [clip(line, limit) for line in lines]
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        self._drawn_lines = len(lines)

    def finish(self) -> None:
        self.current = -1
        if not self.term.plain:
            self.draw()
