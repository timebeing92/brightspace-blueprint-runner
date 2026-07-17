# Stable Launcher Review-Kit Build Record — 2026-07-16

Status: **unreleased review artifact**. This record does not authorize merge,
tagging, publication, or production use.

## Artifact

- Filename:
  `UNRELEASED-blueprint-wizard-stable-launcher-review-c5b60a6.zip`
- Runner: `c5b60a672fe62b7f331f35f64454ceab61025139`
- Bundle: `ec0ba6aad29cd24b0b54094ea69d6546648e526d`
- Outer review-kit SHA-256:
  `8a9f822c378d74d14c60b605f2899d6c66edc43f6eaf2aaf7dfd8416d2cb75e4`
- Inner deterministic candidate SHA-256:
  `e8e394526dabe87bc96573e4f2fc51ea4ca680c8d7f3bfa40f0bff87b5e7693f`

The artifact was built from clean explicit commits. Its outer name and root
folder are prefixed `UNRELEASED`; the public version number is intentionally
absent from the outer filename to prevent confusion with a published release.

## Contents and verification

The one-unzip kit contains:

- the extracted managed candidate under
  `Blueprint Wizard - UNRELEASED REVIEW/`;
- `READ_ME_FIRST.txt` with exact identities and limitations;
- `TEST_CHECKLIST.md`;
- `REPORT_TEMPLATE.md`;
- `PROVENANCE.json`; and
- `INSTALL_TREE_MANIFEST.json`.

Verification passed:

- 67 local tests;
- workflow YAML parse;
- outer SHA-256 sidecar agreement;
- 124 pre-run install-tree files with zero hash mismatches;
- top-level stable-launcher `--health` through a path containing spaces;
- version listing showing only v2.7.0 as current; and
- launched Wizard `--version` reporting v2.7.0.

The provenance receipt explicitly records `macos_code_signed: false`,
`macos_notarized: false`, and `windows_code_signed: false`. Reviewers are
instructed to record security prompts, never weaken system-wide security, and
stop if institutional policy provides no approved continuation.
