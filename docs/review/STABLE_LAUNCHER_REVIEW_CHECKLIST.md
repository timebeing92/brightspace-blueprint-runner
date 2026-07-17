# Blueprint Wizard Stable-Launcher Review Checklist

This is an unreleased test. Use a copied course export that your institution
permits you to process locally. Do not send course exports, generated course
content, or screenshots containing student information with your report.

## 1. Record the test environment

- [ ] Record macOS or Windows version in `REPORT_TEMPLATE.md`.
- [ ] Record whether the computer is institution-managed.
- [ ] Record whether the kit is in Downloads, Documents, OneDrive, or another
      location.
- [ ] Confirm this is a new extracted folder, not an existing Wizard install.

## 2. First launch

- [ ] Open `READ_ME_FIRST.txt` and confirm the commit identities are present.
- [ ] Enter the `Blueprint Wizard - UNRELEASED REVIEW` folder.
- [ ] macOS: double-click `Blueprint Wizard.command`.
- [ ] Windows: double-click `Blueprint Wizard.bat`.
- [ ] Copy the exact text of any Gatekeeper, SmartScreen, antivirus, or
      institutional-policy message into the report.
- [ ] Record whether you could proceed and whether the instructions were clear.
- [ ] Allow the Wizard to create its private Python environment and install
      required Python packages when prompted.

Do not weaken system-wide security settings for this test. On macOS, the
documented right-click/Open path is acceptable for this unsigned review build.
On Windows, record a SmartScreen block before choosing any available review or
run-anyway option. If institutional policy offers no safe continuation, stop
and report that result.

## 3. Ordinary course build

- [ ] Choose a representative Brightspace export.
- [ ] Review the course preview and confirm its module list is readable.
- [ ] Complete the ordinary commission without maintainer-only flags.
- [ ] Confirm the Wizard produces a blueprint even if it reports a component
      finding.
- [ ] Open the primary DOCX and at least one rubric or activity artifact.
- [ ] Record whether filenames, output locations, and review guidance are clear.

## 4. Persistence and relaunch

- [ ] Close the Wizard and launch it again from the same top-level launcher.
- [ ] Confirm prior answers are offered as defaults.
- [ ] Run a second export or a second label for the same export.
- [ ] Confirm the first output remains intact.
- [ ] Confirm outputs are under `user-data/outputs/` and logs under
      `user-data/logs/`, outside `versions/`.

## 5. Non-destructive update behavior

- [ ] From Terminal or PowerShell, run the update check shown below.
- [ ] Confirm an unavailable network does not prevent later Wizard use.
- [ ] Confirm the check reports no newer public stable version during this
      v2.7.0 review.

macOS or Linux:

```bash
bash blueprint_wizard_launcher.sh --check-for-updates
```

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\blueprint_wizard_launcher.ps1 --check-for-updates
```

## 6. Optional portability check

- [ ] Close the Wizard.
- [ ] Move the entire extracted review-kit folder to another user-owned
      location whose path contains spaces.
- [ ] Launch it again and confirm `--health` and ordinary startup still work.

Do not run `--remove-version`: this review kit contains only one version. A
separate controlled A/B rehearsal is used for update, restart, rollback, and
retirement testing.
