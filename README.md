# Brightspace Blueprint Runner

```text
         ▄                           ▄
       ▄            ▀                     ▄
     ▄███▄            ▄
   ▄███████▄                  ▄
  ▀▀▀█████▀▀▀
    ███████
    ▄█████▄
  ▄█████████████
  ███████████
  ███████████    █▀▀▀█  █▀▀▀█   █▀▀▀▀▀█
  ███████████    ▀▀▀▀▀ ▄▀▀▀▀▀ ▄ ▀▀▀▀▀▀▀
              ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
                  ██                    ██

      B L U E P R I N T   W I Z A R D
```
Transmute a D2l/ Brightspace Export into a comprehensive, cleanly formatted
course blueprint. Runs completley localy via a series of python scripts and
libraries. **No AI whatsoever**. 

A one-terminal wizard for the adjacent [brightspace-blueprint-bundle](https://github.com/timebeing92/brightspace-blueprint-bundle) project:
it checks the machine, prepares the bundle's `.venv`, walks through the
options, runs the blueprint pipeline with a live step display, and finishes
with a results card. The pipeline itself lives entirely in the bundle — the
wizard wraps its CLI and consumes its progress-event contract
(`coursecraft.progress/1`); it never re-implements extraction logic.

> [!IMPORTANT]
> Do not use GitHub's green **Code -> Download ZIP** button as the one-download
> install. That source ZIP contains only this runner repo, not the companion
> `brightspace-blueprint-bundle` pipeline repo, so the wizard will not run from
> it by itself. For a single download, use the latest
> `blueprint-wizard-vX.Y.zip` from the
> [GitHub Releases page](https://github.com/timebeing92/brightspace-blueprint-runner/releases).

> [!NOTE]
> There are three install options. If you would like to receive updates, or go beyond updates and test the tool and submit change requests or revisions via github, it is recommended that you choose install option two or three.

## Install

Three pathways — pick the one that matches how you like to get software.
Whichever you choose, first run is the same: the wizard checks the machine
and asks permission before installing anything it needs (Python packages go
in a private `.venv`; nothing touches your system Python).

**1. Release zip — recommended for most people.** Download the latest
`blueprint-wizard-vX.Y.zip` from the GitHub Releases page, unzip it, and
double-click `Blueprint Wizard.command` (macOS) or `Blueprint Wizard.bat`
(Windows). Choose this if you just want to use the tool: no git, no terminal
knowledge, and updating means downloading the next zip. (macOS, first run
only: if Gatekeeper warns about an unidentified developer, right-click the
`.command` file and choose Open.)

**2. git clone — for people who want `git pull` updates.** Clone the two
repos as sibling folders, then launch from the runner:

```bash
git clone https://github.com/timebeing92/brightspace-blueprint-runner
git clone https://github.com/timebeing92/brightspace-blueprint-bundle
bash brightspace-blueprint-runner/blueprint_wizard.sh
```

Choose this if you're comfortable with git and want incremental updates and
history instead of re-downloading zips.

**3. Installer script — one command, terminal-first.**

```bash
curl -fsSL https://raw.githubusercontent.com/timebeing92/brightspace-blueprint-runner/main/install_blueprint_wizard.sh | bash
```

Clones both repos into `./blueprint-wizard/` and starts the wizard;
re-running it later updates both repos. Choose this if you live in the
terminal and want the fastest zero-to-wizard path. Requires git — both
repos are public, so this works for anyone.

Maintainers cut the release zip with `python3 scripts/make_release_bundle.py`
(assembles both repos from git HEAD into `dist/blueprint-wizard-vX.Y.zip`,
ready to attach to a GitHub release).

## Run

- **macOS** — double-click `Blueprint Wizard.command`, or from this folder:

  ```bash
  bash blueprint_wizard.sh
  ```

- **Windows** — double-click `Blueprint Wizard.bat`, or from PowerShell:

  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File blueprint_wizard.ps1
  ```

- **Linux** — `bash blueprint_wizard.sh`.

The wizard walks through:

1. **Splash** — a pixel-art wizard drafts the blueprint (any key skips;
   auto-skipped when piped, with `--plain`/`--no-splash`, or under `NO_COLOR`).
2. **The workshop** — checklist of Python 3.11+, the bundle `.venv`, Python
   packages, and the optional LibreOffice/Poppler render tools. Anything
   missing is offered as an install, with a permission prompt first. (Phase
   headings carry a dim `· 1 of 4 ·` marker so you always know where you are.)
3. **The export** — drag the export ZIP/folder into the terminal. The wizard
   peeks inside and shows the course title, module count, the module list
   (first eight, one per line), file count, and size before you commit to it.
4. **The commission** — course title/number/term (these fill the blueprint
   front matter; blank fields stay `Needs review`), the output name (labels
   the results folder and files, e.g. `name__blueprint.docx`), DOCX/QA
   toggles — then one summary card you can edit by number before running
   (including swapping the export itself).
5. **The drafting** — live per-step progress with elapsed times, driven by
   the bundle's `--progress-events` NDJSON stream; raw step output scrolls
   dimmed beneath. Rubric extraction appears as its own step when the export
   contains `rubrics_d2l.xml`. Each step lingers on screen for a moment (with
   its flavor line and a twinkling star) so the story is followable even
   though the pipeline itself runs in a couple of seconds — `--brisk` skips
   the theatrics.
6. **Results** — a completion chime and "✦ The drafting is complete.", then
   the results card: total drafting time, weeks, QA break/warning/note
   counts, optional rubric count/artifacts including the rubric DOCX,
   `Needs review` count, and the generated files with the main deliverable
   marked `← start here`; offers to open the folder or DOCX.
   If a step fails instead, the failure card names the failed step, shows
   the last output lines, and offers to open the full log.

Answers are remembered in `.last_run.json` (git-ignored) and offered as
defaults next time. Every run writes a full log under `logs/`. Ctrl-C
cancels cleanly at any point; the partial run log is kept.

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
- `--brisk` — run the step board at full speed instead of letting each step
  linger ~1s (pacing is display-only and automatically off in plain mode).

## Layout

```text
brightspace-blueprint-runner/
├── Blueprint Wizard.command <- macOS double-click launcher (opens Terminal)
├── Blueprint Wizard.bat     <- Windows double-click launcher (runs the .ps1)
├── blueprint_wizard.sh      <- macOS/Linux launcher: finds/offers Python 3.11+, execs the wizard
├── blueprint_wizard.ps1     <- Windows launcher: same job in PowerShell (winget install offer)
├── install_blueprint_wizard.sh <- curl-able installer: clones both repos, starts the wizard
├── requirements-dev.txt    <- pytest for the runner test suite
└── scripts/
    ├── blueprint_wizard.py  <- the blueprint-specific flow
    ├── ui.py                <- reusable ANSI components (terminal caps, cards, step board)
    ├── art.py               <- splash scene + animation
    └── make_release_bundle.py <- maintainer tool: builds the release zip from both repos
└── tests/                  <- contract tests for command construction, progress events, and results
```

`ui.py` and `art.py` are deliberately free of blueprint knowledge so future
runner wizards (and an eventual multi-tool launcher) can reuse them — see the
render-stack decision record in the workbench `DEVELOPMENT_ROADMAP.md`.

## Running Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

The tests use a fake bundle process for progress-event coverage, so they do not
need a Brightspace export or the sibling bundle checkout.

## Notes

- Python package installs happen inside the bundle's `.venv`.
- Rubric steps and rubric result rows come from the bundle's
  `coursecraft.progress/1` event stream; the runner does not parse D2L XML or
  glob for rubric artifacts. When the bundle reports `outputs.rubrics_docx`,
  the results card shows the standalone rubric review document.
- System tools are installed only after an explicit prompt.
- LibreOffice/`soffice` and Poppler are only required for the optional DOCX
  *visual* render QA. A pure-Python structural check of the DOCX
  (relationships, hyperlinks, tables, titles) runs automatically with no
  extra installs.
- Default bundle location: `../brightspace-blueprint-bundle` (override with
  `--bundle-dir`).
- On Windows, the PowerShell launcher prefers the `py` launcher, filters out
  the Microsoft Store `python` alias, and offers a winget install of Python
  when none is found.
