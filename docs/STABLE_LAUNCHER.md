# Stable Launcher Development Note

Status: local candidate only. This surface is not part of the published v2.7.0
release and must not be released until every gate in
`plans/2026-07-16_stable_launcher.md` has recorded evidence.

## Why this exists

Portable release ZIPs make the Wizard easy to download, but each update is a
new folder. The durable launcher gives that audience one permanent entry point
without introducing git. Complete runner/bundle releases live side by side;
an atomic JSON pointer selects one pair, and persistent work lives outside all
replaceable version folders.

The launcher intentionally treats a release as one indivisible unit. It never
updates the runner and bundle independently, and it verifies the release
manifest, both repository identities and commits, contract hashes, archive
layout, GitHub asset digest, and published checksum before activation.

## Lifecycle

1. The active Wizard checks the public stable-release feed.
2. With explicit user confirmation, the durable launcher downloads the exact
   versioned ZIP and checksum into `staging/`.
3. The installer validates and extracts into a unique staging directory, then
   atomically promotes the complete release to `versions/<version>`.
4. Only after promotion does it atomically update `current.json`. The prior
   version remains the rollback target.
5. If the user chooses restart, the child returns exit code 75. The durable
   parent verifies that the active version actually changed and relaunches
   once. It will not enter a restart loop.
6. A successful launch receipt proves the replacement. Old-version removal is
   a separate explicit command; current and unproven rollback versions are
   rejected as cleanup targets.

Any download, trust, extraction, activation, or restart failure leaves the
previous complete version and all `user-data/` content in place.

## Candidate commands

From an extracted managed candidate:

```bash
bash blueprint_wizard_launcher.sh --health
bash blueprint_wizard_launcher.sh --list-versions
bash blueprint_wizard_launcher.sh --rollback
bash blueprint_wizard_launcher.sh --remove-version 2.7.0
```

Local/offline release import remains available for institutional proxies and
fixture testing:

```bash
bash blueprint_wizard_launcher.sh \
  --install-release /path/to/blueprint-wizard-v2.8.0.zip \
  --checksum /path/to/blueprint-wizard-v2.8.0.zip.sha256 \
  --expected-version 2.8.0
```

The `--remove-version` command is deliberately strict: it cannot remove the
active version, cannot accept paths, and cannot remove the rollback version
until the current activation has a successful launch receipt. Settings, logs,
outputs, update cache, and receipts are outside `versions/` and are never
cleanup candidates.

## Human review kit

Do not hand reviewers the generic managed candidate from `dist/`. Build the
one-unzip review kit from explicit clean commits instead:

```bash
python3 scripts/make_managed_review_kit.py \
  --runner-ref "$(git rev-parse HEAD)" \
  --bundle-ref "$(git -C ../brightspace-blueprint-bundle rev-parse HEAD)"
```

The output under `dist/review/` is prefixed `UNRELEASED`, omits the public
version number from the outer filename, and contains the already-extracted
candidate, tester checklist, report template, provenance receipt, install-tree
hash manifest, and outer ZIP checksum. The kit also records that the current
review build is unsigned and not notarized. Building a review kit does not
create or authorize a release.

## Stable-launcher compatibility boundary

The top-level launcher is smaller and more conservative than any versioned
Wizard. Release manifests currently target launcher protocol 1. If a future
release needs a new protocol, it must ship through a separately designed and
tested launcher-upgrade path; versioned code may not silently overwrite the
durable launcher that is running it.
