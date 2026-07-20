# Blueprint Wizard

Blueprint Wizard turns a Brightspace/D2L course export into a comprehensive,
review-ready course blueprint. It gathers course structure, activities,
rubrics, QA findings, and source-traceable run evidence through one guided
workflow.

Blueprint Wizard is a conventional program that runs on your own computer. It
reads the XML and HTML contained in the Brightspace export package, follows the
IDs and links connecting the pieces, and works through a systematic set of
programmed checks to rebuild the course and flag anything missing, broken, or
unusual. Once its one-time local setup is complete, the core blueprint and QA
workflow needs no internet connection—you could turn off Wi-Fi or work from a
cave and still build the blueprint. Only first-time setup downloads and
network-specific extras—including update checks, external-link checks, and
linked-syllabus retrieval—need a connection. There is no AI involved
whatsoever; this is traditional software built from explicit instructions and
repeatable checks.

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

## What it produces

Depending on the source export and selected options, a run can produce:

- a cleanly formatted course blueprint in Word and Markdown;
- structured course-activity, course-structure, and rubric files;
- QA reports that identify breaks, warnings, and items needing review; and
- a checksum-backed run receipt connecting the deliverables to their source
  export and exact extraction-tool versions.

If a recoverable component or QA step fails, the Wizard preserves producer-
approved deliverables, labels the run **Partial**, and explains what may need
review. Bundle 1.3.1 and later also report fidelity separately: if core evidence
steps fail and the producer says its documents do not mirror the export, the
Wizard presents a failed reading instead of offering those documents as a
blueprint. A faithfully mirrored course with no weekly structure remains usable
and is labeled explicitly.

## How the parts fit

A one-terminal wizard for the adjacent [brightspace-blueprint-bundle](https://github.com/timebeing92/brightspace-blueprint-bundle) project:
it checks the machine, prepares the bundle's `.venv`, walks through the
options, runs the blueprint pipeline with a live step display, and finishes
with a results card. The pipeline itself lives entirely in the bundle — the
wizard wraps its CLI and consumes its progress-event contract
(`coursecraft.progress/1`); it never re-implements extraction logic.

## Current release

The current release is **Blueprint Wizard v2.8.1**, paired with **Blueprint
Bundle v1.3.2**. Most users should choose the managed release ZIP described
below. See the [v2.8.1 release notes](docs/releases/v2.8.1.md) for checksums,
verification evidence, and exact component identities. Version-by-version
changes now live in the [changelog](CHANGELOG.md) rather than interrupting this
guide.

> [!IMPORTANT]
> Do not use GitHub's green **Code -> Download ZIP** button as the one-download
> install. That source ZIP contains only this runner repo, not the companion
> `brightspace-blueprint-bundle` pipeline repo, so the wizard will not run from
> it by itself. For a single download, use the latest
> `blueprint-wizard-managed-vX.Y.Z.zip` from the
> [GitHub Releases page](https://github.com/timebeing92/brightspace-blueprint-runner/releases).

> [!NOTE]
> The managed release ZIP is the recommended installation for colleagues who
> do not use git. It can apply future verified releases without replacing user
> work. Git clone remains the contributor path.

## Install

Three pathways — pick the one that matches how you like to get software.
Whichever you choose, first run is the same: the wizard checks the machine
and asks permission before installing anything it needs (Python packages go
in a private `.venv`; nothing touches your system Python).

**1. Managed release ZIP — recommended for most people.** Download the latest
`blueprint-wizard-managed-vX.Y.Z.zip` from the GitHub Releases page, unzip it,
and double-click `Blueprint Wizard.command` (macOS) or `Blueprint Wizard.bat`
(Windows). Choose this if you just want to use the tool: no git and no terminal
knowledge. A future update is installed only after confirmation, verified as a
complete Runner/Bundle pair, and kept beside the current version so rollback
remains possible. Settings, logs, and generated outputs stay in `user-data/`
and are not removed during version cleanup.

The release also includes `blueprint-wizard-vX.Y.Z.zip`, the original portable
one-folder distribution. Existing portable users may continue with it, and the
managed updater uses that exact asset as its version payload. Portable folders
show update notices but do not replace themselves.

The v2.8.1 ZIPs are unsigned and are not notarized. On macOS, Gatekeeper may
require right-clicking `Blueprint Wizard.command` and choosing Open on first
launch. Windows or institution-managed devices may show an equivalent trust
prompt. Do not weaken system-wide security settings.

**2. git clone — for contributors and people following development.** Clone
the two repos as sibling folders, then launch from the runner:

```bash
git clone https://github.com/timebeing92/brightspace-blueprint-runner
git clone https://github.com/timebeing92/brightspace-blueprint-bundle
bash brightspace-blueprint-runner/blueprint_wizard.sh
```

Choose this if you're comfortable with git and intentionally want the current
development branches and their history instead of a pinned release pair.

**3. Installer script — one command, terminal-first.**

```bash
curl -fsSL https://raw.githubusercontent.com/timebeing92/brightspace-blueprint-runner/main/install_blueprint_wizard.sh | bash
```

Clones both repos into `./blueprint-wizard/` and starts the wizard. The
installer reads `installer-compatibility.lock`, verifies the published tag
commits, checks out that recorded runner/bundle pair, and writes
`INSTALL_RECEIPT.txt`. Re-running it later installs the newly recorded
compatible pair without combining two independent moving `main` branches.
Choose this if you live in the terminal and want the fastest zero-to-wizard
path. Requires git — both repos are public, so this works for anyone.

Maintainers cut both release ZIPs from the same explicit commits:

```bash
python3 scripts/make_release_bundle.py \
  --runner-ref "$(git rev-parse HEAD)" \
  --bundle-ref "$(git -C ../brightspace-blueprint-bundle rev-parse HEAD)"

python3 scripts/make_managed_install_bundle.py \
  --runner-ref "$(git rev-parse HEAD)" \
  --bundle-ref "$(git -C ../brightspace-blueprint-bundle rev-parse HEAD)"
```

The builders refuse dirty worktrees by default and write
`RELEASE_MANIFEST.json` inside each version payload with both repository
commits and the bundle contract hashes. New manifests also checksum the shipped
pipeline entry point and course-structure extractor, so managed installs reject
runtime-file drift even when the surrounding folder still looks complete. The
manifest also declares the linked-syllabus supplement capability and refuses
to package a bundle missing its authority, opt-out, or non-fatal extraction
markers. A sibling `.sha256` file records each ZIP checksum.
After publishing a compatible pair, refresh the installer record with:

```bash
python3 scripts/update_installer_compatibility.py \
  --runner-ref vX.Y.Z \
  --bundle-ref vA.B.C
```

The generated lock is reviewed and committed; it is not edited by hand.

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
2. **The workshop** — checklist of Python 3.11+, the bundle `.venv`, and the
   core Python packages. Anything missing is offered as an install, with a
   permission prompt first. After setup succeeds, an interactive run performs
   the cached, non-blocking update check unless it was disabled. (Phase
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
   `Needs review` count, the producer run-identity receipt, and the generated files with the main deliverable
   marked `← start here`; offers to open the folder or DOCX.
   If a step fails instead, the failure card names the failed step, shows
   the last output lines, and offers to open the full log.

Answers are remembered in `.last_run.json` (git-ignored) and offered as
defaults next time. Every run writes a full log under `logs/`. Ctrl-C
cancels cleanly at any point; the partial run log is kept.

## Update Checks

Interactive runs check the public Blueprint Wizard GitHub release feed at most
once every 24 hours, after the local Python environment and core packages are
ready. If a newer release exists, the Wizard shows the installed and available
versions. Portable installations can open the verified release page but never
replace their own files. Managed installations can, after explicit
confirmation, download and verify the complete new release beside the current
version, activate it atomically, and restart once.

```bash
bash blueprint_wizard.sh --check-for-updates  # force a check and exit
bash blueprint_wizard.sh --no-update-check    # skip the automatic check
```

The result is cached in `.update_check.json` (git-ignored). GitHub, like any
site contacted over the internet, receives the requesting IP address and
request metadata. No GitHub account or access token is used. Network, timeout,
rate-limit, malformed-response, and read-only-cache failures are non-fatal; an
ordinary automatic check stays silent and the Wizard continues.

Managed updates compare GitHub's asset digest with the downloaded ZIP, verify
the independent `.sha256` sidecar, then validate the release manifest,
repository/commit identities, archive layout, critical runtime files, and all
six schema hashes before activation. Any network, checksum, extraction, or
validation failure leaves the current version selected. The previous complete
version remains the rollback target until the replacement has launched
successfully; removal of an old version is a separate explicit action.

For an installation created by `install_blueprint_wizard.sh`, rerunning that
installer obtains the currently recorded verified runner/bundle pair. Portable
release users should download and unzip the newer `blueprint-wizard-vX.Y.Z.zip`
from the release page.

## Non-Interactive Use

```bash
bash blueprint_wizard.sh --yes --export /path/to/export.zip \
  --course-title "Course Title" --course-number "ABC 123" --term "Fall 2026"
```

`--yes` accepts every confirmation and requires `--export`. Normal pipeline
toggles are available as flags (`--no-docx`, `--skip-qa`,
`--check-external-links`, `--docx-section-layout`, `--label`).

Maintainers can explicitly pass `--render-docx-check` after installing the
bundle's `requirements-render.txt`, LibreOffice, and Poppler. The Wizard does
not install or prompt for those optional preview tools.

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
├── install_blueprint_wizard.sh <- curl-able installer: verifies and installs the recorded release pair
├── installer-compatibility.lock <- generated compatible runner/bundle tag and commit identities
├── launcher/               <- stable managed install/update/rollback core
├── requirements-dev.txt    <- pytest for the runner test suite
├── scripts/
    ├── blueprint_wizard.py  <- the blueprint-specific flow
    ├── update_check.py      <- cached, non-blocking public release check
    ├── ui.py                <- reusable ANSI components (terminal caps, cards, step board)
    ├── art.py               <- splash scene + animation
    ├── make_release_bundle.py <- maintainer tool: builds the release zip from both repos
    ├── make_managed_install_bundle.py <- builds the stable managed release zip
    └── update_installer_compatibility.py <- generates the installer compatibility record
└── tests/                  <- contract and launcher tests
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
- Automatic update checks run only in interactive Wizard sessions, no more
  than once daily. `--yes` automation does not gain an implicit network call.
- Managed installs can apply a verified release only after confirmation. The
  stable launcher retains the prior complete version for rollback and never
  places user data inside a removable version folder.
- The bundled extractor separately inventories the syllabus item normally
  carried inside the export's welcome module. It makes a non-fatal best-effort
  fetch only from allow-listed syllabus hosts so missing descriptions,
  materials, or course outcomes can be supplemented with checksum-bound
  evidence. Package-local text remains primary. Advanced CLI runs can use
  `--no-syllabus-fetch`; a failed or unfamiliar source never stops output.
- Rubric steps and rubric result rows come from the bundle's
  `coursecraft.progress/1` event stream; the runner does not parse D2L XML or
  glob for rubric artifacts. When the bundle reports `outputs.rubrics_docx`,
  the results card shows the standalone rubric review document.
- Run identity also comes only from `coursecraft.progress/1`; release ZIP
  receipts now bind the activity, structure, and run schemas alongside the
  blueprint, rubric, and progress schemas.
- Normal runs have no LibreOffice or Poppler dependency. A pure-Python
  structural check of the DOCX (relationships, hyperlinks, tables, titles)
  runs automatically.
- The backward-compatible `--render-docx-check` flag is an advanced manual
  compatibility preview, not part of the ordinary Wizard commission or doctor
  setup.
- Default bundle location: `../brightspace-blueprint-bundle` (override with
  `--bundle-dir`).
- On Windows, the PowerShell launcher prefers the `py` launcher, filters out
  the Microsoft Store `python` alias, and offers a winget install of Python
  when none is found.
