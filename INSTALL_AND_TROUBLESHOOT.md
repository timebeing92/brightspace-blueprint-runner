# Install, update, and troubleshoot Blueprint Wizard

This guide covers the recommended managed release, first launch, verified
updates, rollback, and the most common installation or run problems.

## Install the managed release

1. Open the
   [Blueprint Wizard Releases page](https://github.com/timebeing92/brightspace-blueprint-runner/releases).
   On the repository page, **Releases** is also available from the repository
   sidebar.
2. Open the latest release and expand **Assets** if necessary.
3. Download `blueprint-wizard-managed-vX.Y.Z.zip`.
   Do **not** download GitHub's automatically generated **Source code** ZIP,
   and do not use the green **Code > Download ZIP** button. Those archives
   contain this runner repository but omit the paired Blueprint Bundle engine.
4. Unzip the managed release before opening it.
5. Start the Wizard:

   - **macOS:** double-click `Blueprint Wizard.command`.
   - **Windows:** double-click `Blueprint Wizard.bat`.
   - **Linux:** run `bash blueprint_wizard_launcher.sh` from the unzipped
     folder.

The managed ZIP is the one-download distribution. It contains the exact
Blueprint Wizard runner and Blueprint Bundle versions tested together, plus
their release manifest and checksum-backed runtime and contract records.

## Authorize the first launch on macOS

The current release is unsigned and not notarized, so macOS may block the
first launch even when the ZIP came from the official Releases page.

1. Unzip the release and try to open `Blueprint Wizard.command` once.
2. Dismiss the warning.
3. Choose **Apple menu > System Settings > Privacy & Security**. You may need
   to scroll down.
4. Under **Security**, click **Open**, then **Open Anyway**.
5. Enter your Mac login password and confirm the launch.

Apple normally leaves **Open Anyway** available for about an hour after the
blocked attempt. See Apple's
[current unknown-developer instructions](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac).

Use this per-app exception only after confirming that the ZIP came from the
official Blueprint Wizard Releases page. Do not disable Gatekeeper or weaken
system-wide security settings. Institution-managed Macs may require help from
local IT.

## What happens on first run

- The launcher looks for an existing Python 3.11 or newer installation and
  reuses it. It does not reinstall Python when a supported copy is present.
- If Python is missing, the launcher explains what it found and asks before
  offering an installation.
- Required Python packages are installed into the paired Blueprint Bundle's
  private `.venv`, not into the system Python.
- The core blueprint and QA workflow runs locally. First-time dependency
  setup, update checks, opt-in external-link checks, and linked-syllabus
  retrieval are the network-dependent exceptions described in the README.

## What the managed release can do

The managed launcher keeps complete releases under `versions/` and keeps
settings, logs, generated outputs, and update state under `user-data/`.
Program versions can therefore be installed, activated, rolled back, or
removed without deleting user work.

When you approve an update, the launcher verifies the GitHub asset digest,
the published `.sha256` sidecar, repository identities, exact runner and
bundle commits, critical runtime files, and contract hashes before activation.
An update is installed beside the current version; the previous complete
version remains available for rollback. Update checks do not silently replace
the running version.

The smaller `blueprint-wizard-vX.Y.Z.zip` is the portable distribution.
It contains the same tested runner/bundle pair but does not provide the
managed installation's side-by-side activation and rollback workflow.

## Managed-install checks and recovery

Run these commands from the top level of the unzipped managed installation.

macOS or Linux:

```bash
bash blueprint_wizard_launcher.sh --health
bash blueprint_wizard_launcher.sh --list-versions
bash blueprint_wizard_launcher.sh --update
bash blueprint_wizard_launcher.sh --rollback
```

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\blueprint_wizard_launcher.ps1 --health
powershell -NoProfile -ExecutionPolicy Bypass -File .\blueprint_wizard_launcher.ps1 --list-versions
powershell -NoProfile -ExecutionPolicy Bypass -File .\blueprint_wizard_launcher.ps1 --update
powershell -NoProfile -ExecutionPolicy Bypass -File .\blueprint_wizard_launcher.ps1 --rollback
```

`--health` verifies the active release manifest and the receipted runner and
bundle files. `--rollback` changes the active pointer to the retained previous
version; it does not remove the current version or user data.

For a portable or git-based installation, the Wizard's own setup check is:

```bash
bash blueprint_wizard.sh --doctor
bash blueprint_wizard.sh --doctor --fix
```

## Common problems

### The download does not contain the Wizard or Bundle

You probably downloaded the green **Code > Download ZIP** archive or a
GitHub-generated **Source code** ZIP. Return to Releases and download
`blueprint-wizard-managed-vX.Y.Z.zip`.

### macOS says the developer cannot be verified

Confirm the ZIP came from the official Releases page, try to open the command
once, then follow the **Privacy & Security** workflow above.

### Windows shows a trust or policy warning

Confirm the ZIP came from the official Releases page. Follow your
organization's software policy; institution-managed devices may require IT
approval. Do not disable SmartScreen, antivirus, or organization-wide policy.

### Python is already installed, but the launcher cannot find it

Open a new Terminal or PowerShell window after installing Python and rerun the
launcher. The macOS/Linux launcher checks `python3.13`, `python3.12`,
`python3.11`, and `python3`, and also accepts an explicit `PYTHON` path:

```bash
PYTHON=/full/path/to/python3.12 bash blueprint_wizard_launcher.sh
```

Python must be version 3.11 or newer.

### Dependency setup fails

Keep the installation folder writable, confirm the computer can reach the
Python package index, and retry. Proxies, SSL inspection, antivirus, and
institutional network policy can block package downloads. The Wizard asks
before installing and does not place its packages into the system Python.

### An update fails or the active release appears damaged

Run `--health` first. A failed download, checksum, archive, manifest, runtime,
or contract check leaves the current version selected. Use `--rollback` only
when a previous complete version is listed. Do not manually combine runner and
bundle folders from different releases.

### A course run fails or stops partway through

The results or failure card identifies the failed step and offers to open the
full log. In a managed installation, logs are under `user-data/logs/` and
outputs are under `user-data/outputs/`. Portable and git-based runs keep logs
under `brightspace-blueprint-runner/logs/` unless explicitly configured
otherwise. A partial run keeps its log and any producer-approved artifacts.

## Report a problem

[Open a Blueprint Wizard issue](https://github.com/timebeing92/brightspace-blueprint-runner/issues)
and include:

- operating system and version;
- Blueprint Wizard version;
- managed, portable, git, or installer-script setup;
- the step that failed;
- the complete error message; and
- a short description of what you expected to happen.

Do not attach course exports, institutional course content, learner data,
credentials, or other sensitive material. Redact local usernames and private
paths from logs before posting excerpts.
