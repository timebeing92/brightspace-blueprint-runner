# Blueprint Wizard changelog

This file preserves the user-visible release history without making the main
README double as a changelog. Exact release assets, checksums, and verification
evidence remain attached to the corresponding
[GitHub releases](https://github.com/timebeing92/brightspace-blueprint-runner/releases).

## v2.8.0 — 2026-07-17

Added the stable managed launcher. Complete Runner/Bundle pairs install side by
side, a small atomic pointer selects the active version, and settings, logs,
update evidence, and generated outputs remain outside replaceable version
folders. After confirmation, managed installations download and verify a new
release, activate it, and restart once while keeping the previous complete
version available for rollback. The portable one-folder ZIP remains supported.
This release also carries Bundle v1.3.0's run-identity contracts and resilient
direct-or-nested linked-syllabus supplementation.

See the [detailed v2.8.0 release notes](docs/releases/v2.8.0.md).

## v2.7.0 — 2026-07-16

Added a quiet release check for colleagues using the one-download ZIP. After
ordinary setup succeeds, an interactive Wizard checks GitHub at most once per
day and displays a clear card when a newer verified Wizard release is
available. The check uses no account or token, never replaces local files, and
cannot block blueprint generation when the network is offline. Users can open
the release page from the card, force a check with `--check-for-updates`, or
disable automatic checks with `--no-update-check`.

## v2.6.0 — 2026-07-16

Removed LibreOffice, Poppler, and `pdf2image` from the ordinary Wizard workflow.
Default pure-Python structural DOCX QA remains enabled. The Wizard no longer
checks, prompts, or offers to install visual-render tools, and the commission
no longer includes a visual-render question. The existing
`--render-docx-check` flag remains available only as an explicit maintainer
preview whose generated pages require human inspection.

## v2.5.4 — 2026-07-16

Extended the terminal-readability pass to course-preview lists. Module titles
and the “+N more” line in “The wizard peers into the scroll” now use a legible
steel blue instead of dim gray, preserving separation from the card's white
labels and borders.

## v2.5.3 — 2026-07-16

Improved terminal readability. Interactive choice/default cues such as
`[y/N]`, `[Y/n]`, and `(default)`, along with the active-step narration such as
“The wizard holds the scroll to the light…”, now use the terminal's normal
foreground intensity instead of ANSI dim/faint styling. Decorative metadata
and raw diagnostic output remain subdued.

## v2.5.2 — 2026-07-16

Added verification for the runner-folder launch surface itself: the macOS and
POSIX launchers execute the current Wizard, the Windows batch file delegates
and preserves its exit status, and the PowerShell launcher safely retains both
one-part commands such as `python3` and two-part commands such as `py -3.12`.
The curl installer now installs a generated, commit-verified Runner/Bundle pair
and records the installed identities instead of pulling two unrelated moving
branch heads.

## v2.5.1 — 2026-07-16

Made recoverable component or QA failures preserve usable blueprints. The
results card labels the run **Partial**, lists the affected steps, links the
pipeline-status report, and still presents every Markdown, DOCX, workbook,
rubric, and QA artifact that was successfully produced.

## Earlier releases

Tags v2.1 through v2.5 remain available in the
[GitHub release archive](https://github.com/timebeing92/brightspace-blueprint-runner/releases).
