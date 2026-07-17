# Stable Launcher Acceptance Record — 2026-07-16

Release state: **acceptance passed; publication withheld**. The implementation
is on `feature/stable-launcher`; no tag or GitHub release was created.

## Identities

- Runtime candidate runner: `927debb9c12bdf15194d98641ffe275fe998fc28`
- Runtime candidate bundle: `ec0ba6aad29cd24b0b54094ea69d6546648e526d`
- Managed candidate ZIP SHA-256:
  `e3a56204ca391bb93c5b318d1c3371411e820b495f65ec9d39107b982569d5c4`
- Latest local test/CI commit at the time of this entry:
  `256baddca651b9a7fedd0a10e5f4def2c873e27e`

The commits after the runtime-candidate commit add acceptance documentation,
tests, and CI coverage; they do not change the candidate's runtime modules.

## Local automated proof

Command:

```bash
../brightspace-blueprint-bundle/.venv/bin/python -m pytest -q
```

Result: **64 passed**. Covered behavior includes:

- portable path behavior versus explicitly managed data roots;
- release identity, commit, contract receipt, and required-file validation;
- checksum mismatch, traversal, Windows-reserved paths, symlinks, encryption,
  case collisions, incomplete archives, and existing-version mismatch;
- atomic side-by-side install, activation, rollback, and idempotency;
- cross-process install locking;
- GitHub API asset identity and digest/sidecar agreement;
- one permitted restart only after the atomic pointer selects another version;
- a real child-process A-to-B restart;
- current-version and unproven-rollback cleanup protection; and
- persistent user-data survival after explicit retirement.

## Fresh managed-candidate proof

The candidate was extracted into a new temporary install root. These commands
passed through the top-level stable launcher:

```bash
bash blueprint_wizard_launcher.sh --health
bash blueprint_wizard_launcher.sh --list-versions
bash blueprint_wizard_launcher.sh --version
bash blueprint_wizard_launcher.sh --doctor --fix --yes --plain --no-update-check
```

The health response resolved the exact runner and bundle commits listed above.
Dependency setup created the bundle `.venv` inside `versions/2.7.0/`; doctor
then reported the core pipeline and pure-Python structural DOCX QA ready.

The first dependency attempt occurred inside a network-restricted sandbox and
failed without changing `current.json`. Repeating it with download access
completed normally. This is recorded because failed setup must remain
recoverable, not because it was a product network failure.

## Real course proof

Source export:

`/Users/ehanson8/Downloads/D2LExport_14066_SSW-565-master-201302_20210506104536_202671629.zip`

The non-interactive managed run completed all ten pipeline steps in about
three seconds and reported:

- 8 weeks;
- 19 rubrics;
- 0 QA breaks, 0 QA warnings, and 6 QA notes;
- 0 DOCX structural breaks, 0 structural warnings, and 4 structural notes;
- 184 valid hyperlinks, 50 tables, 2,277 paragraphs, and 38 rubric appendix
  tables; and
- pipeline status `COMPLETE` with no component findings.

All generated artifacts were beneath
`user-data/outputs/stable_launcher_SSWO_565_proof__blueprint_bundle/`; the run
log was beneath `user-data/logs/`, and remembered answers were beneath
`user-data/settings/`. No generated output, run log, setting, or update cache
was found under the active version directory.

Selected artifact hashes:

- Blueprint DOCX:
  `4174328b401c6c33cb33c96b1b544890197975836965650c1728ade532150cb0`
- Rubrics JSON:
  `6589e8d313b76381bdb6afafef2acb96702e9ab2105de7ea4e9bdf973417f549`

## Published ZIP import, rollback, and retirement

The published `blueprint-wizard-v2.6.0.zip` was imported from disk using its
published sidecar. Its verified SHA-256 was
`c6a997cbfc161b34b2ce4dedfea99332ca1244756c3a527cb97bced0d2d18ad8`.

The stable launcher installed it without activation, listed v2.6.0 beside
v2.7.0, activated and launched v2.6.0, rolled back and launched v2.7.0, then
explicitly retired v2.6.0. The final health check selected v2.7.0, its rollback
pointer was clear, a retirement receipt remained, and the SSWO 565 user-data
artifacts were unchanged.

## Live GitHub delivery proof

A separate empty temporary install used the public latest-release API. It
accepted the exact official v2.7.0 ZIP and checksum asset URLs, and verified
that both GitHub's API digest and the sidecar were:

`11f8f48d6e9735b2df585bbd9de149a9c6520b7a9e8b0e653555ce29cefd41bc`

Only then did it install and activate the published pair:

- runner `712b7088f22a6b5907bed07d83c1a02609c69065`;
- bundle `ec0ba6aad29cd24b0b54094ea69d6546648e526d`.

Health, version listing, and a launched `--version` command all passed.

## Platform matrix attempt 1

GitHub Actions run `29548383133` passed the full suite and packaged-candidate
launch on Ubuntu and macOS. Windows passed all 40 selected lifecycle tests and
PowerShell parsing, then exposed a release-builder portability defect before
candidate extraction: Python decoded `git show` using Windows cp1252 even
though the versioned Wizard source is UTF-8 and contains Unicode interface
text. This prevented the Windows package from being built.

The builder now requests UTF-8 explicitly from the git subprocess. A second
full matrix was required before the implementation could be considered
release-ready.

## Platform matrix attempt 2

GitHub Actions run `29548459164` at
`1bbec06d69e35f5bb4acc9acec81f82f66915445` passed:

- the full test and ordinary release-package job;
- the selected 40-test managed lifecycle suite on Windows, macOS, and Ubuntu;
- PowerShell parsing on Windows;
- managed candidate build, extraction, health, and launched version checks on
  Windows; and
- managed candidate build, extraction, health, and launched version checks on
  macOS and Ubuntu.

Run URL:
`https://github.com/timebeing92/brightspace-blueprint-runner/actions/runs/29548459164`

## Final unreleased review candidate

The final candidate was rebuilt from the exact green matrix commit and the
same bundle release commit:

- runner `1bbec06d69e35f5bb4acc9acec81f82f66915445`;
- bundle `ec0ba6aad29cd24b0b54094ea69d6546648e526d`;
- ZIP SHA-256
  `437bb085ee56c84607bad90facccbc7273de15a5839fe2ff6187d99d71b502e0`.

A fresh extraction passed top-level `--health`, `--list-versions`, and
`--version`; the sidecar checksum matched a new SHA-256 calculation.

All recorded acceptance gates now pass. This proof authorizes review of a
future versioned release; it does not authorize merging, tagging, publishing,
or deleting the earlier public release.

## Post-acceptance CI runtime maintenance

GitHub subsequently annotated every job because `actions/checkout@v4` and
`actions/setup-python@v5` still declared the deprecated Node.js 20 action
runtime, even though hosted runners forced them onto Node.js 24 and the jobs
passed. The workflow was moved to `actions/checkout@v6` and
`actions/setup-python@v6`, whose supported runtime is Node.js 24. This is a CI
maintenance change only; it does not alter the Wizard, bundle, contracts, or
candidate lifecycle. The complete test/package and three-platform launcher
matrix remains the required verification gate for the change.
