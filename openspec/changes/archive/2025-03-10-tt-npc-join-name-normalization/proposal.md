## Why

Tabletop validation currently blocks valid NPC onboarding when action payloads use short names (for example, `"Kira"`) instead of canonical names (for example, `"Scout Kira"`). Upstream/single-player behavior felt more permissive, but TT validation now combines strict full-name checks with incomplete pre-validation normalization.

This creates a UX regression: the Narrator can produce semantically correct party-join actions that still fail, causing retry loops and making the system feel less intelligent.

## What Changes

MUST changes:
- Add deterministic canonical-name normalization for party-NPC action payloads before LLM validation.
- Apply normalization to `updatePartyNPCs` add/remove payloads and `moveBackgroundNPC` name fields, with unambiguous-only mapping.
- Keep ambiguity fail-closed with explicit operator-facing reason text.
- Align prompt examples and validation guidance so short-name and canonical-name behavior is internally consistent.
- Add regression coverage for the Kira onboarding path and similar short/full-name party-NPC joins.

SHOULD changes:
- Add concise debug logs for canonicalization decisions (normalized, exact, ambiguous-rejected).
- Keep edits additive and limited to validator/name-resolution surfaces.

### Non-goals

- No rewrite of the broader validation architecture.
- No changes to combat flow, module ingest workflows, or storage schemas.
- No loosening of true hallucination checks or off-location arrival fail-closed guarantees.

## Capabilities

### New Capabilities
- `tt-party-npc-action-name-canonicalization`: Deterministic canonicalization contract for party-NPC action names before LLM validation.

### Modified Capabilities
- `tt-narrator-validation-contract`: Extend runtime contract to require canonical-name preprocessing for party-NPC action payloads.
- `tt-npc-arrival-name-resolution`: Ensure short/full alias handling remains consistent between mention detection and action-name evaluation.

## Impact

Affected code (planned):
- `main.py`
- `utils/npc_name_normalizer.py`
- `utils/npc_arrival_validator.py`
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `scripts/test_npc_arrival_state_sync.py`
- `scripts/test_narrator_prompt_validation_refactor.py`

Risk and mitigation:
- Risk: accidental over-normalization could map to wrong NPC.
  - Mitigation: unambiguous-only mapping; ambiguous matches fail closed.
- Risk: prompt and runtime contract drift reappears.
  - Mitigation: regression tests assert short/full-name contract and prompt example consistency.

Merge-safety and compatibility:
- Merge-safe, additive hooks only; preserve upstream single-player behavior.
- TT mode keeps strict arrival-sync guarantees while restoring practical short-name onboarding ergonomics.

Fallback strategy (MUST):
- If regressions occur, rollback normalization for non-`updatePartyNPCs` actions first, keep tests and prompt alignment changes, then narrow mapping scope to partyNPCs-only until stable.
