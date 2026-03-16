## Context

The current runtime has multiple state assembly paths that partially overlap but do not share a single machine-readable contract. `main.py` assembles validation context from party tracker state, area data, conversation snippets, and on-demand helper output. `utils/multi_pc_dm_note.py` assembles player-facing state context separately. This has allowed narrator-facing, validator-facing, and persistence-facing truth to diverge in soft world-state domains even when no hard 5e contradiction exists.

The gametest lane does not need the full long-term architecture yet. It needs the smallest useful foundation that lets later reconcile-first travel and NPC work read from a common truth surface. This change therefore introduces only a narrow authoritative packet for the domains already implicated in current immersive-play failures: location/module truth, party composition, party NPC composition, and nearby topology context.

Constraints:
- Preserve upstream structure where possible.
- Use additive helpers and thin host-file hooks marked with `# TABLETOP MODE:` comments.
- Preserve current JSON/action schema behavior.
- Avoid broad prompt changes or validator rewrites in this slice.
- Keep ASCII-only Python user-facing strings.

## Goals / Non-Goals

**Goals:**
- Establish a canonical machine-readable packet for current runtime truth in the touched domains.
- Make DM Note rendering and touched validation assembly consume the same packet fields.
- Reduce state duplication without changing the existing action protocol.
- Provide a safe foundation for later `travel-reconcile-first-autocommit` work.
- Preserve SP/MP compatibility and merge-safe extension patterns.

**Non-Goals:**
- No full world-delta reconciler.
- No event ledger.
- No Titans/EGO background runtime integration.
- No broad prompt contract rewrite.
- No replacement of all existing validator logic.
- No gameplay semantic change outside state-packet consumers touched by this slice.

## Decisions

### Decision 1: Introduce a narrow additive packet helper instead of rewriting all state assembly

The implementation SHALL add a new helper module, likely `utils/authoritative_state_packet.py`, that builds a narrow packet from existing runtime truth sources.

Rationale:
- This keeps the change small enough for gametest stabilization.
- It avoids dangerous broad rewrites in `main.py`.
- It allows later changes to adopt the packet incrementally.

Alternative considered:
- Full immediate replacement of all state assembly paths.
- Rejected because it is too risky for the pre-tester release window.

### Decision 2: Packet scope stays limited to location, party, party NPCs, and topology-adjacent truth

The first packet version SHALL include only the fields needed for current gametest pain points:
- module/current area/current location truth,
- current party roster,
- current party NPC roster,
- nearby/reachable location context,
- optional packet metadata needed by validators and DM Note.

Rationale:
- Narrow scope reduces regression risk.
- These are the domains required for later travel/NPC reconciliation.
- Mechanical combat/resource truth already has multiple hardened paths and is not the target of this foundation slice.

Alternative considered:
- Include full combat/resource/mechanical packet in v1.
- Rejected as too broad for the minimum slice.

### Decision 3: DM Note shall become a packet consumer, not a second truth builder

The touched DM Note assembly paths SHALL read from packet fields for overlapping truths instead of reconstructing those truths independently.

Rationale:
- DM Note drift is one source of narrator confusion.
- The player-visible/narrator-visible truth surface should match the validator-visible truth surface in the touched domains.

Alternative considered:
- Leave DM Note untouched and use the packet only for validators.
- Rejected because parity is one of the main motivations for the foundation.

### Decision 4: Validation handoff shall use packet truth in packet-enabled domains only

The touched validation assembly in `main.py` SHALL consume packet truth for packet-enabled domains, but this change SHALL NOT attempt a broad rewrite of all validation logic.

Rationale:
- We need a usable foundation now, not a full validator redesign.
- Narrowing the change avoids cross-cutting regressions.

Alternative considered:
- Global validator authority reset now.
- Rejected; that belongs to a later staged change.

### Decision 5: Preserve explicit action schema as compatibility surface

This change SHALL preserve the existing explicit JSON/action schema and SHALL treat the packet as runtime truth infrastructure, not as a replacement for the action protocol.

Rationale:
- The gametest lane should be evolutionary, not a protocol break.
- Later reconcile-first work can reduce dependence on perfect action emission without discarding the existing schema.

## Risks / Trade-offs

- [Risk] Packet fields could drift from current runtime expectations if the helper becomes too broad too early.
  -> Mitigation: keep packet v1 intentionally narrow and add regression tests for the exact expected fields.

- [Risk] DM Note parity work could accidentally alter unrelated narration behavior.
  -> Mitigation: limit parity changes to overlapping truth surfaces and verify non-travel/non-NPC behavior remains stable.

- [Risk] Validation assembly may still depend on some legacy ad hoc context.
  -> Mitigation: allow mixed-mode assembly during the foundation slice; later changes can reduce remaining ad hoc inputs.

- [Risk] This could be mistaken for an upstream rollback.
  -> Mitigation: preserve current action schema, maintain hard mechanics, and keep the packet as stronger runtime reconciliation infrastructure than upstream had.

## Migration Plan

1. Add contract tests or source-contract coverage for the packet fields and touched consumers.
2. Implement the narrow packet helper with no behavior change by itself.
3. Wire `main.py` touched validation assembly to consume packet truth in the selected domains.
4. Wire `utils/multi_pc_dm_note.py` touched render paths to consume packet truth in overlapping domains.
5. Run targeted regressions and compile checks.
6. Preserve the helper even if some consumer wiring must be rolled back.

Rollback strategy:
- Revert consumer wiring in `main.py` and/or `utils/multi_pc_dm_note.py` while leaving the additive packet helper and tests intact.
- Preserve the OpenSpec contract so later work can continue from the same foundation.

## Open Questions

- Whether packet v1 should include nearby background NPC location candidates or only current party/party-NPC truth.
- Whether the first consumer tests should be pure source-contract tests or runtime fixture tests that build representative packet payloads.
- Whether a small helper for packet caching per turn is warranted now, or should be deferred until later reconcile-first changes prove the need.
