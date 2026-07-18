# Nested Inline Heading Coherence Proof

Date: 2026-07-17

Real EDU 807 and EDU 831 pages use outcome headings whose visible text is
wrapped in inline markup, including:

    <h2><strong>Student Learning Outcomes:</strong></h2>
    <h2><span>Learning Outcomes</span></h2>

A separate curriculum-mapping parser lost the heading type when the inner
element closed. The CourseCraft workbench and Blueprint Bundle extractor were
already safe because they identify the enclosing heading before flattening its
inner markup. Matching regression tests now prove that the heading level and
text survive and that the resulting segments route to Learning Objectives and
Learning Materials.

The runner does not duplicate this parser. A one-download or managed release
contains an explicit Blueprint Bundle commit. Its release manifest records the
two repository commits, contract hashes, and now SHA-256 receipts for:

- `brightspace-blueprint-bundle/scripts/build_blueprint_bundle.py`; and
- `brightspace-blueprint-bundle/scripts/reconstruct_course_structure.py`.

Managed-install validation checks those bytes before activation. This keeps the
fix and regression gate in the upstream workbench, the distributed bundle, and
the runner's verified packaging path without creating a third parser copy.
