## Context

G1-G4 already established three important rules in the current runtime: packet-backed truth surfaces, reconcile-first travel, and reconcile-first NPC scene presence. The remaining bug class is narrower: narration can clearly place the party at a known location scene while runtime leaves `party_tracker.json` at the prior location because no explicit `transitionLocation` was emitted.

The Maelo/Hermit's Refuge transcript is the proof case. The narrator described the party stepping into the clearing and reaching the lodge, yet `update_conversation_history` still reloaded `RO01` and the GUI top bar stayed stale. This means the missing behavior is not a new travel philosophy. It is a missing location-commit bridge between clear narrated arrival and canonical location state.

Constraints:
- MUST keep the heuristic narrower than generic scene inference.
- MUST preserve explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId` precedence.
- MUST fail open on ambiguity or progress-only travel.
- MUST keep host-file edits additive and marked with `# TABLETOP MODE:` comments.
- SHOULD avoid prompt changes unless runtime validation parity proves necessary.

## Goals / Non-Goals

**Goals:**
- Commit party location when narration explicitly places the party at one known location.
- Use module-level location truth so cross-area destinations like Hermit's Refuge can resolve safely.
- Prevent stale GUI/world-state drift after clear narrated arrival.
- Lock the Hermit's Refuge transcript with deterministic tests before implementation is considered done.

**Non-Goals:**
- No broad fuzzy scene resolver.
- No multi-destination inference.
- No cross-module location jump inference beyond current active module.
- No event-ledger or version-2 architecture work.

## Decisions

### Decision 1: Narrated arrival reconciliation triggers only on one uniquely resolved known location

The runtime SHALL infer party location commit only when narration strongly implies arrival into one known active-module location.

Rationale:
- Prevents wrong canon commits from vague or poetic scene prose.
- Keeps this fix narrower than G2 travel reconciliation.

Alternative considered:
- Infer from any clearing/building/hut scene language.
- Rejected because it would overfit prose and create false commits.

### Decision 2: Explicit location actions remain authoritative when present

If the response already includes `transitionLocation` or `updatePartyTracker.currentLocationId`, runtime SHALL not add a second inferred location commit.

Rationale:
- Keeps the new behavior additive.
- Avoids duplicate state mutations and validator confusion.

Alternative considered:
- Normalize every location change through the new inference path.
- Rejected because explicit protocol already exists and works when emitted.

### Decision 3: Module-wide location catalog becomes part of authoritative packet topology

The authoritative packet SHALL expose module-level location metadata needed to resolve known destinations outside the current area.

Rationale:
- Current-area-only topology is too narrow for destinations like Hermit's Refuge.
- Packet-backed topology keeps the fix aligned with G1 packet truth rather than adding ad hoc file walks in every caller.

Alternative considered:
- Have the narrated-arrival helper rescan module files independently.
- Rejected because it duplicates truth assembly and bypasses the packet foundation.

### Decision 4: Progress-only narration remains non-committal

Narration such as "almost there", "just ahead", or "quarter mile away" SHALL NOT trigger party location commit.

Rationale:
- Prevents premature state movement.
- Matches current reconcile-first philosophy: commit only when prose justifies it.

Alternative considered:
- Commit nearest likely destination anyway.
- Rejected because progress narration is not arrival narration.

## Risks / Trade-offs

- [Risk] Strong arrival prose may still be ambiguous between multiple known locations.
  -> Mitigation: require exactly one resolved destination or fail open.

- [Risk] Module-wide location catalog increases packet size slightly.
  -> Mitigation: keep entries minimal (`id`, `name`, `area_id`, `area_name`).

- [Risk] Narrated-arrival reconciliation could overlap with direct NPC scene sync.
  -> Mitigation: run narrated-arrival logic before the narrower NPC-driven scene sync and preserve explicit-action precedence.

## Migration Plan

1. Add transcript-driven regression coverage for Hermit's Refuge narrated arrival.
2. Extend the authoritative packet with module-level location catalog.
3. Add narrated-location-arrival inference helper.
4. Wire helper into `main.py` pre-validation reconciliation path.
5. Run targeted travel, packet, and NPC scene regression suites.

Rollback strategy:
- Revert narrated-arrival inference while keeping packet catalog and tests if the heuristic proves too permissive.

## Open Questions

- Whether the first implementation should support deterministic alias normalization (`Hermit's lodge` -> `Hermit's Refuge`) or require exact canonical location names only.
- Whether a later follow-up should unify narrated-arrival and direct-NPC scene sync under one shared scene-commit helper once this narrower bug is stable.
