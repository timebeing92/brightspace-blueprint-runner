# Run Identity Consumer Proof

Status: local consumer implementation verified 2026-07-17. This is not a
release receipt.

The Blueprint Wizard now displays the portable bundle's
`coursecraft.run/1` receipt in its results card. It consumes only the path
advertised by `coursecraft.progress/1`; it does not parse exports, glob for the
receipt, or construct a competing identity.

The combined release builder now includes checksums for all six portable
schemas in its embedded source receipt: activity, blueprint, progress, rubric,
run identity, and structure. This keeps a future release ZIP's producer pair
and contract family auditable together.

Verification: the full runner suite passes with 67 tests. No release was
published and no live Brightspace operation was performed.
