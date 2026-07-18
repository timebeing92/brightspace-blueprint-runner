# Linked Syllabus Release Coherence Proof

Date: 2026-07-17

## Promise

The ordinary Blueprint Wizard must recognize the syllabus item carried inside
the export's welcome/getting-started module. A recognized linked syllabus may
supplement an otherwise-missing course description, required-materials field,
or course outcomes, but package-local course content remains primary. Fetch or
unseen-page failures must remain non-fatal.

## Ownership

- The master CourseCraft workbench owns discovery, allow-listed best-effort
  fetch, exact-byte/SHA-256 retention, heading-based extraction, authority
  ordering, and sanitized tests.
- The standalone Blueprint Bundle carries that same structure extractor and
  the corresponding blueprint fallback/comparison logic. It provides
  `--no-syllabus-fetch`, `--syllabus-timeout`, and `--syllabus-host` controls.
- The runner does not duplicate the parser. It packages one explicit Bundle
  commit and receipts the exact bundle orchestrator and structure extractor.

## Release gate

New `coursecraft.runner_release/1` manifests declare a
`linked_syllabus_supplement` capability with:

- status `enabled_by_default`;
- evidence role `supplemental_linked_syllabus`;
- primary authority `package_local_export`; and
- network boundary `allowlisted_best_effort_nonfatal`.

Release construction refuses a selected Bundle commit that lacks markers for
the default procedure, authority rule, opt-out, or extraction implementation.
Managed-install validation checks the declared capability shape and verifies
the SHA-256 receipts for both runtime files before activation. Older release
manifests remain valid because the capability is additive and optional there.

Fixture tests use mocked syllabus HTML and do not depend on a live Brightspace
environment or public syllabus server. Both Runner CI checkout sites are pinned
to promoted Bundle commit
`9de763e6815f4305b7cbe137fb4651ce8d799514`; no mutable tag or branch selects
the runtime under test.
