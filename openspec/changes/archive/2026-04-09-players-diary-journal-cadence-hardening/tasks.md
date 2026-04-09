Reconciliation note (2026-04-09):
- This change implementation is complete.
- Journal cadence hardening is now wired for transition checkpoint metadata and long-rest checkpoints in `journal.json`.

## 1. Checkpoint identity foundation

- [x] 1.1 Add additive journal checkpoint metadata support so journal rows can identify whether they were created by a transition or long rest.
- [x] 1.2 Add a shared idempotency check that can determine whether a candidate transition or long-rest checkpoint has already been journaled.
- [x] 1.3 Verify checkpoint metadata/idempotency helpers with focused tests and `.venv/bin/python -m py_compile`.

## 2. Preserve transition cadence

- [x] 2.1 Keep the existing transition-driven journal write path active.
- [x] 2.2 Update transition-created journal rows to carry the new additive checkpoint metadata.
- [x] 2.3 Verify transition journaling still writes exactly one checkpoint per valid processed transition.

## 3. Add long-rest cadence

- [x] 3.1 Add a long-rest journal checkpoint hook that runs only after successful long-rest completion.
- [x] 3.2 Reuse the existing summary-generation path so long-rest checkpointing stays additive and KISS.
- [x] 3.3 Suppress long-rest journal writes when the candidate checkpoint is duplicate or has no meaningful unjournaled delta.
- [x] 3.4 Ensure long-rest journaling is fail-open and never blocks or rolls back a successful rest.

## 4. Verification

- [x] 4.1 Add focused regression coverage for: transition preserved, long-rest checkpoint created, duplicate long-rest suppressed, and no-op when no meaningful delta exists.
- [x] 4.2 Run all dependency-sensitive verification commands with `.venv/bin/python`.
- [x] 4.3 Perform a manual smoke pass covering: transition checkpoint, same-location long-rest checkpoint, and rest success when journal generation degrades.

SHOULD: Keep short rests out of the default cadence in this change.
SHOULD: Keep this change strictly scoped to journal cadence; do not fold location-narrative authority work into it.
