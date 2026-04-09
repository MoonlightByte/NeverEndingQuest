## Builder Prompt

Implement only the journal cadence hardening described in this change.

Scope constraints:
- Keep the existing transition-based journal write path.
- Add long-rest journal checkpointing only after successful long-rest completion.
- Do not add short-rest journaling by default.
- Do not fold in any location-narrative authority or Malarok/NC05 scene-gating work.
- Keep the implementation fail-open for rest success and additive to existing journal behavior.

Expected artifacts:
- additive checkpoint metadata and idempotency support
- preserved transition journaling
- new long-rest cadence hook
- focused regression coverage for dedupe and fail-open behavior

Verification expectations:
- use `.venv/bin/python` for dependency-sensitive checks
- prove no duplicate journal rows for reprocessed transitions or long rests
- prove long rest still succeeds when journal generation degrades
