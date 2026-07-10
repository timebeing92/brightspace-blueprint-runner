# Brightspace Blueprint Runner

A one-terminal wizard for the adjacent `brightspace-blueprint-bundle` project:
it checks the machine, prepares the bundle's `.venv`, walks through the
options, runs the blueprint pipeline with a live step display, and finishes
with a results card. The pipeline itself lives entirely in the bundle — the
wizard wraps its CLI and consumes its progress-event contract
(`coursecraft.progress/1`); it never re-implements extraction logic.

## Quickstart

From this folder:

```bash
bash blueprint_wizard.sh
```

The wizard walks through:

1. **Splash** — a pixel-art wizard drafts the blueprint (any key skips;
   auto-skipped when piped, with `--plain`/`--no-splash`, or under `NO_COLOR`).
2. **Preparation** — checklist of Python 3.11+, the bundle `.venv`, Python
   packages, and the optional LibreOffice/Poppler render tools. Anything
   missing is offered as an install, with a permission prompt first.
3. **The export** — drag the export ZIP/folder into the terminal. The wizard
   peeks inside and shows the course title, module count, file count, and
   size before you commit to it.
4. **The commission** — course title/number/term (these fill the blueprint
   front matter; blank fields stay `Needs review`), output label, DOCX/QA
   toggles — then one summary card you can edit by number before running.
5. **The drafting** — live per-step progress with elapsed times, driven by
   the bundle's `--progress-events` NDJSON stream; raw step output scrolls
   dimmed beneath.
6. **Results** — weeks, QA break/warning/note counts, `Needs review` count,
   the generated files with sizes, and offers to open the folder or DOCX.

Answers are remembered in `.last_run.json` (git-ignored) and offered as
defaults next time. Every run writes a full log under `logs/`.

## Non-Interactive Use

```bash
bash blueprint_wizard.sh --yes --export /path/to/export.zip \
  --course-title "Course Title" --course-number "ABC 123" --term "Fall 2026"
```

`--yes` accepts every confirmation and requires `--export`. All pipeline
toggles are available as flags (`--no-docx`, `--skip-qa`,
`--check-external-links`, `--render-docx-check`, `--docx-section-layout`,
`--label`).

## Doctor Mode

```bash
bash blueprint_wizard.sh --doctor          # check the machine
bash blueprint_wizard.sh --doctor --fix    # check and offer to fix
```

## Display Options

- `--plain` — no color, art, or animation (also automatic when output is not
  a terminal, or `NO_COLOR` is set). Same information, plain text.
- `--no-splash` — skip the splash screen only.

## Layout

```text
brightspace-blueprint-runner/
├── blueprint_wizard.sh      <- launcher: finds/offers Python 3.11+, then execs the wizard
└── scripts/
    ├── blueprint_wizard.py  <- the blueprint-specific flow
    ├── ui.py                <- reusable ANSI components (terminal caps, cards, step board)
    └── art.py               <- splash scene + animation
```

`ui.py` and `art.py` are deliberately free of blueprint knowledge so future
runner wizards (and an eventual multi-tool launcher) can reuse them — see the
render-stack decision record in the workbench `DEVELOPMENT_ROADMAP.md`.

## Notes

- Python package installs happen inside the bundle's `.venv`.
- System tools are installed only after an explicit prompt.
- LibreOffice/`soffice` and Poppler are only required for DOCX visual render QA.
- Default bundle location: `../brightspace-blueprint-bundle` (override with
  `--bundle-dir`).
- macOS/Linux shell use. Windows users can run the bundle's `bootstrap.ps1`
  and direct Python command from the bundle README (a native launcher is on
  the backlog).
