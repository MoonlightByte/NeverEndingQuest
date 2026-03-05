## Context

`validate_npc_arrival_state_sync()` currently validates NPC mention-to-action consistency using strict lowercase equality. In Pumpkin King and mixed NPC datasets, runtime state often stores full names while narration and action payloads use short names. This mismatch can produce false validation failures despite correct arrival actions, causing the 5-attempt validator loop to stop execution.

The requested policy for ambiguous short-name aliases is fail-open.

## Goals / Non-Goals

### Goals

- Ensure unambiguous short/full NPC aliases map to one identity for arrival sync checks.
- Preserve fail-closed rejection for true unambiguous missing arrival actions.
- Implement ambiguous alias handling as fail-open to avoid false hard-fails.
- Keep changes additive and limited to validator + tests.

### Non-Goals

- No prompt contract rewrite.
- No changes to action schema or command semantics.
- No broad refactor of unrelated validation logic.

## Decisions

1. Identity resolver in validator MUST support exact and token-based unambiguous matching.
   - Implement local canonicalization helper(s) in `utils/npc_arrival_validator.py` that:
     - normalize case/spacing/punctuation consistently,
     - first attempt exact match,
     - then attempt unique token-subset match against candidate identity set.

2. Mention/presence/action checks MUST use the same resolver path.
   - The same identity matching function SHALL be applied when:
     - deciding whether a mentioned NPC is already present,
     - determining whether an arrival action corresponds to a mentioned NPC.

3. Ambiguous aliases MUST fail-open.
   - If a mentioned short alias maps to multiple candidate identities, validator SHALL not reject solely on that ambiguous mention.
   - Ambiguous names SHOULD be tracked internally for diagnostics but MUST NOT produce hard-fail reason text by themselves.

4. Unambiguous misses MUST still fail-closed.
   - If a mentioned NPC resolves unambiguously and is not present, validator SHALL require a matching `moveBackgroundNPC` or `updatePartyNPCs add` action.

5. Existing safety invariants MUST remain.
   - Party member exemption remains unchanged.
   - Case-insensitive behavior remains unchanged.
   - ASCII-only logs/messages in Python files remain unchanged.

## Risks / Trade-offs

- Trade-off: fail-open ambiguity may let some truly missing arrivals pass when naming is underspecified.
  - Accepted by user preference to reduce false hard-fails during live play.
- Risk: over-broad token matching could create accidental matches.
  - Mitigation: require uniqueness for token-based mapping; otherwise classify as ambiguous.

## Migration Plan

1. Add/adjust resolver helpers in `utils/npc_arrival_validator.py`.
2. Route both presence and action checks through unified resolver.
3. Add regression tests for:
   - short mention + full action,
   - short mention + full present-state,
   - ambiguous alias fail-open,
   - preserved fail-closed unambiguous missing action.
4. Run focused tests and compile checks.

## Open Questions

- None for this pass. Policy decision for ambiguity is explicitly fail-open.
