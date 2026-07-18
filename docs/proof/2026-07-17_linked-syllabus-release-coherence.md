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
- network boundary `allowlisted_best_effort_nonfatal`;
- direct manifest discovery shape `manifest_item_link`; and
- package-local HTML anchor discovery shape `package_html_link`.

Release construction refuses a selected Bundle commit that lacks markers for
the default procedure, authority rule, opt-out, extraction implementation, or
nested package-HTML discovery. Managed-install validation checks the declared
capability and both discovery shapes, then verifies the SHA-256 receipts for
both runtime files before activation. Older release manifests remain valid
because the capability is additive and optional there.

Fixture tests use mocked syllabus HTML and do not depend on a live Brightspace
environment or public syllabus server. Both Runner CI checkout sites are pinned
to tested Bundle commit
`4dc58f9ef0dffe8d563576eaf7f0ed005395799a`; no mutable tag or branch selects
the runtime under test. The Bundle commit was recorded only after its complete
77-test fixture suite passed. This proof note does not authorize a public
release, and the published installer compatibility lock remains unchanged.
