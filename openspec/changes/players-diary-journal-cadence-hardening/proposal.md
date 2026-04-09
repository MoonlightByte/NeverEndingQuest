## Why

The current journal cadence is too sparse for long stretches of same-location play. `journal.json` only advances when a processed location transition produces a summary, which means multiple sessions of meaningful gameplay inside one location can leave the journal and the confirmed Players Diary materially behind the true campaign state.

This change is needed to harden the cadence of journal checkpoint creation without turning the journal into a per-turn log. The desired in-world model is simple and believable: a party diarist writes after travel and during major downtime, especially at long rests. That means transition checkpoints should remain, and long rests should become an additional journal checkpoint opportunity.

## What Changes

- MUST preserve transition-based journal checkpoint generation.
- MUST add long-rest journal checkpoint generation as an additional cadence trigger.
- MUST keep journal generation out of combat-turn and ordinary per-turn gameplay flow.
- MUST keep long-rest journaling fail-open so a successful rest is never blocked by summary or journal write degradation.
- MUST make checkpoint creation idempotent so the same transition or long rest cannot append duplicate near-identical journal rows on retries, re-entry, or resume flows.
- SHOULD use additive checkpoint metadata in journal entries so transition and long-rest checkpoints can be identified and deduplicated deterministically.
- SHOULD avoid generating a long-rest checkpoint when there is no meaningful new gameplay delta since the last successful journal checkpoint.
- SHOULD leave short rests out of the default cadence to avoid over-journaling and low-signal diary spam.

**Non-Goals**
- This change does NOT address location-narrative authority, boss-location exclusivity, or Malarok scene gating.
- This change does NOT replace `journal.json` as the source of record for the Players Diary.
- This change does NOT introduce per-turn journaling.
- This change does NOT redesign the Players Diary markdown artifact architecture.

## Capabilities

### New Capabilities
- `journal-cadence-transition-and-long-rest-checkpoints`: Create journal checkpoints from both location transitions and completed long rests.
- `journal-cadence-idempotent-dedupe`: Prevent duplicate journal rows for the same transition or long-rest checkpoint.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `main.py`
  - `core/ai/cumulative_summary.py`
  - `core/ai/action_handler.py`
  - diary/journal-focused tests under `scripts/`
- Affected systems:
  - journal checkpoint creation cadence
  - confirmed Players Diary freshness (indirectly, via `journal.json`)
- Runtime/storage:
  - `journal.json` entries may gain additive checkpoint metadata fields for idempotency
- Interpreter requirement:
  - dependency-sensitive verification commands for this change MUST use `.venv/bin/python`
- Risks:
  - long-rest checkpointing could create duplicate or low-signal rows if idempotency is weak
  - coupling cadence too tightly to rest flow could accidentally block or delay gameplay if not kept fail-open
- Fallback:
  - if long-rest checkpoint generation fails, the long rest still succeeds and no duplicate/stale journal metadata is committed
