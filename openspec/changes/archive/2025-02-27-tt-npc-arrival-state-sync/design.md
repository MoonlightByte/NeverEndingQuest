## Context

The party-strip thumbnails use deterministic state, not freeform narration:
- party members and party NPCs from `party_tracker.json`
- location NPCs from current area/location JSON

When narration introduces an off-location NPC without an action (`moveBackgroundNPC` or `updatePartyNPCs` add), GUI and mechanics diverge. This is a contract gap between narration, action payloads, and validator acceptance.

## Goals / Non-Goals

**Goals (MUST):**
- Enforce a response-level contract: off-location NPC arrival claims SHALL be coupled to state action(s) in the same response.
- Reuse existing fail-closed validation retry loop; do not add silent auto-mutations.
- Keep deterministic matching to canonical known NPC names only.
- Preserve all existing behavior for already-present NPC references.

**Guidance (SHOULD):**
- Implement guard logic in a focused helper to keep `main.py` changes small.
- Keep prompt and validator language aligned to reduce retry churn.

**Non-Goals:**
- No redesign of NPC movement system.
- No broad NLP/NER for arbitrary names.
- No combat death-save contract work in this change.

## Decisions

1) Validation-first state-sync guard (MUST)
- Add deterministic guard in `validate_ai_response()` path.
- Guard SHALL parse assistant JSON, compute currently present NPC set, detect mentions of non-present known NPCs in narration, and enforce required state action pairing.
- If contract fails, validator SHALL reject with actionable reason and trigger normal retry.

2) Deterministic mention scope (MUST)
- Mention detection SHALL use canonical known NPC names from module context, not open-ended entity extraction.
- Detection SHALL exclude NPCs already present at current location or already in party NPC roster.
- Mention detection SHALL be case-insensitive and bounded to canonicalized full-name matching.

3) Action pairing rules (MUST)
- For each newly mentioned non-present known NPC, response SHALL include one of:
  - `moveBackgroundNPC` with matching `npcName`, or
  - `updatePartyNPCs` add with matching NPC name.
- Responses lacking required action SHALL fail validation.

4) Dedupe normalization in party strip (MUST)
- Replace substring suppression (`npc_name in member_name`) with canonical equality checks when filtering location NPCs already represented in party display.
- This prevents distinct names from collapsing (for example `Ansel` vs `Anselara`).

5) Fail-closed and compatibility behavior (MUST)
- No auto-write or implicit state mutation by validator.
- Existing responses that reference already-present NPCs remain valid with no extra action requirement.

## Risks / Trade-offs

- [Risk] False positives from mention matching.
  - Mitigation: match only canonical known names, skip partial tokens, and keep retry reason explicit.
- [Risk] Increased retries in narrative-heavy scenes.
  - Mitigation: prompt contract update and validator examples aligned to expected action pairing.
- [Trade-off] Stricter validation can reject creative narration.
  - Accepted for TT reliability where visible state must remain trustworthy.

## Migration Plan

1. Add guard helper and integrate in validation pipeline.
2. Update narrator and validation prompts with explicit arrival-state contract.
3. Harden party-strip dedupe equality.
4. Add focused regression tests and run compile/test gates.

Rollback strategy:
- Revert guard hook in `main.py` if false-positive rate is unacceptable.
- Keep prompt updates if useful, or revert together with guard.
- Revert dedupe normalization independently (isolated risk).

## Open Questions

- Should alias references (for example "Father Ansel") be handled now or deferred to a future alias map?
- Should we require exact per-NPC action pairing when multiple off-location NPCs are mentioned, or allow one broad action plus follow-up turn?
