# Stable Launcher And Versioned Update Plan

Status: local development only; do not release until the acceptance gates below
pass against a fixture release sequence and a real packaged Wizard.

## Objective

Give non-git installations one durable launcher that can stage, verify,
activate, restart into, roll back from, and eventually retire complete
runner/bundle release pairs without overwriting a running installation or
placing user work inside disposable version directories.

## Safety Boundary

- A release is a complete runner/bundle pair. Never update either repository
  independently.
- Download into staging, verify before extraction, and activate only by an
  atomic pointer-file replacement.
- Keep the previous complete release until the replacement has launched and
  passed its health check.
- Never archive or delete outputs, source exports, settings, logs, receipts, or
  update evidence.
- Never require administrator privileges; the install root remains user-owned.
- Network, verification, extraction, migration, activation, and cleanup
  failures leave the current version runnable.
- Portable release folders remain supported. Managed behavior activates only
  when the stable launcher supplies an explicit install-root environment.

## Target Layout

```text
Blueprint Wizard/
├── Blueprint Wizard.command
├── Blueprint Wizard.bat
├── blueprint_wizard_launcher.ps1
├── launcher/
│   └── stable_launcher.py
├── current.json
├── versions/
│   ├── 2.7.0/
│   │   ├── brightspace-blueprint-runner/
│   │   ├── brightspace-blueprint-bundle/
│   │   └── RELEASE_MANIFEST.json
│   └── 2.8.0/
├── user-data/
│   ├── settings/
│   ├── logs/
│   ├── outputs/
│   └── update-cache/
├── receipts/
└── staging/
```

Each version keeps its own bundle `.venv`. This costs more disk space but makes
rollback deterministic. Cleanup may remove an old version and its private
environment only after a newer version is proven.

## Implementation Stages

1. Persistent-data separation
   - Teach the runner to honor an explicit managed data root.
   - Put remembered answers, update cache, logs, and default output bundles
     beneath `user-data/` in managed mode.
   - Preserve current paths in portable mode.

2. Stable launcher and pointer
   - Validate `current.json` against a version-pointer schema.
   - Resolve only paths beneath `versions/`.
   - Validate the selected runner, bundle, and release manifest before launch.
   - Set managed data/output environment values and run the selected version.

3. Side-by-side installer/updater
   - Accept a local release ZIP first so every mutation path is fixture-backed
     without network access.
   - Validate SHA-256, release manifest, expected version, safe ZIP members,
     and required launch files.
   - Extract into staging, atomically promote to `versions/<version>`, and
     atomically update `current.json`.
   - Refuse to overwrite an existing version with different content.

4. Health, restart, rollback, and retention
   - Record launch attempts and successful setup/health markers in receipts.
   - Expose version listing, activation, and rollback commands.
   - Keep current plus previous by default; make deletion explicit until the
     successful-launch policy has substantial fixture coverage.
   - Add restart-to-complete only after macOS, Windows, and POSIX process
     behavior is covered.

5. Network delivery
   - Connect the existing latest-release check to the local verified installer.
   - Download the release ZIP and compare both the API asset digest and sidecar
     checksum before calling the same local install path.
   - Retain manual ZIP import for proxies and offline institutional networks.

## Acceptance Gates Before Release

- Portable v2.7 behavior remains unchanged unless managed-mode environment
  values are supplied.
- Managed outputs, logs, settings, and cache remain outside every version
  directory.
- A fixture sequence installs version A, runs it, installs version B, activates
  B, and rolls back to A without altering either version.
- Corrupt checksum, wrong manifest identity, unexpected layout, traversal path,
  interrupted staging, and existing-version mismatch fixtures all leave A
  current and runnable.
- Cleanup cannot select current, previous-unproven, or any user-data path.
- macOS/POSIX launchers pass locally; Windows launcher behavior passes a CI
  matrix or an equivalent PowerShell fixture test.
- A real release ZIP can be imported, launched, and rolled back locally.
- The branch remains unreleased until the implementation log records the exact
  evidence for every gate.

## Deferred Decisions

- Code signing/notarization and an independent release-signing key.
- Prerelease or departmental update channels.
- Automatic deletion without an explicit user action.
- Shared virtual environments across versions.
