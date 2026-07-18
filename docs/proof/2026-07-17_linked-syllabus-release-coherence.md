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
to the Bundle v1.3.0 release commit
`0b197d95b8b1a5593f92772e664b1d04c5441677`; no mutable tag or branch selects
the runtime under test. The Bundle commit was recorded only after its complete
77-test fixture suite passed.

## Fresh managed-candidate environment proof

After Runner commit `b955b5a9ab29295e82aa6cdad2371cffdd04902e` and
Bundle commit `4dc58f9ef0dffe8d563576eaf7f0ed005395799a` were pushed, the
managed builder produced an unreleased candidate with ZIP SHA-256
`5d9d8e5f60c6b6da209fe6745ff38f32da0a86cc5f36fd953ce73ae353c1db89`.
The candidate was extracted into a fresh temporary install root; no repository
virtual environment was copied into it.

The stable launcher reported both exact commits through `--health`. Its
`--doctor --fix --yes --plain --no-update-check` path then created
`versions/2.7.0/brightspace-blueprint-bundle/.venv`, installed the Bundle
requirements under Python 3.13.3, and reported the core pipeline and structural
DOCX QA ready. A second `--doctor` run without `--fix` remained green, and
`python -m pip check` inside the created environment reported no broken
requirements.

The first dependency attempt was intentionally made under the restricted test
network and failed at package download after successfully creating the virtual
environment. Re-running with package-download access recovered in place and
completed normally. This proves the release setup remains retryable as well as
functional. It does not authorize publication of the candidate.
