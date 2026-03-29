## Context

Runtime already has several narrow reconcile-first location repair paths:
- clear travel-intent autocommit
- explicit narrated arrival sync
- same-turn scene/plot reconciliation
- startup scene location recovery

The cathedral drift bug sits between those paths. The narration established a descent from `NIG02` into the catacombs below, but it did so directionally rather than by naming `NIG03`. Combat then concluded without canonical location ever leaving `NIG02`, so restart recap truth remained upstairs.

This design has two stakeholders:
- live players and facilitators, who need canonical location truth to match narrated descent without extra repair work
- future module publication tooling, which should eventually make these descent cues explicit and auditable rather than relying only on runtime heuristics

Constraints:
- The fix MUST stay merge-safe and localized to existing TABLETOP MODE reconciliation hooks.
- The fix MUST preserve single-player and tabletop compatibility.
- Runtime MUST keep explicit location actions authoritative.
- Python state remains ground truth; narration may imply movement, but canonical location truth must only change when one safe authored target is provable.

## Goals / Non-Goals

**Goals:**
- Add a narrow runtime inference path for implicit same-module sublocation descent when one adjacent authored target is uniquely provable.
- Ensure inferred location commit can apply before same-turn encounter creation anchors combat to a stale parent room.
- Preserve fail-open behavior for ambiguous or progress-only prose.
- Preserve direct DM adjudication and repair-question UX unchanged.
- Add regression locks for the Night of the Restless Dead cathedral descent case.

**Non-Goals:**
- Building a generic fuzzy scene resolver for arbitrary narration.
- Reworking cross-module travel behavior.
- Replacing explicit `transitionLocation` as the preferred happy path.
- Solving all module semantic aliasing gaps in this change.
- Replacing module publication work; this change only reduces runtime burden for a specific live-play class of drift.

## Decisions

### Decision: Use adjacent-authored-target inference instead of broad location guessing
**MUST** keep inference bounded to authored adjacent destinations from the current canonical room.

Rationale:
- The failure mode is local sublocation descent, not arbitrary scene relocation.
- Adjacent-only scope sharply reduces false positives.
- This aligns with authored topology already used for same-module transition validation.

Alternatives considered:
- Scan all module locations for the "best" lower-depth match.
  - Rejected: too broad, too easy to over-commit from atmospheric prose.
- Rely only on named destination mentions.
  - Rejected: does not solve the live lock case where players and DM use directional descent prose.

### Decision: Distinguish descent/entry cues from generic travel-progress cues
**MUST** require stronger scene evidence than ordinary in-transit narration.

Rationale:
- Existing reconcile-first travel already handles clear named travel and progress.
- This change is specifically for local descent into a sublocation that has effectively been entered, not merely approached.
- Stronger cues reduce accidental commits when the DM is only building tension.

Expected cue classes:
- player or narration mentions descent: `descend`, `climb down`, `down the crevice`, `beneath`, `below`
- room-entry phrasing: `the passage opens into`, `enter the chamber`, `step into`
- authored lock-case references: `behind the altar`, `base of the fissure`, `catacombs below`

Alternatives considered:
- Treat any lower-depth wording as location commit.
  - Rejected: too permissive for foreshadowing prose.

### Decision: Inferred location commit SHALL precede same-turn encounter creation
**MUST** order inferred `updatePartyTracker.currentLocationId` before `createEncounter` when both occur on the same turn.

Rationale:
- If combat anchors first, encounter IDs, post-combat summary, and restart state all inherit the stale parent room.
- Fixing only post-combat summaries would be downstream repair, not root-cause correction.

Alternatives considered:
- Repair encounter location after combat concludes.
  - Rejected: higher drift risk, more moving parts, weaker truth model.
- Require prompt changes so the LLM always emits explicit transition before combat.
  - Rejected: runtime still needs protection when the model misses the action.

### Decision: Add optional authored transition-hint metadata, but keep runtime fallback narrow
**SHOULD** support additive authored transition-hint metadata for lock cases like `NIG02 -> NIG03`.
**MUST** keep runtime functional even if the metadata is absent, provided one adjacent target is still uniquely provable from safe local evidence.

Rationale:
- Publication work should eventually formalize semantic transition hints.
- A narrow runtime fallback solves the live bug now without waiting for full publishability infrastructure.

Alternatives considered:
- Hardcode Night of the Restless Dead descent logic in runtime.
  - Rejected: module-specific hack, poor reuse.
- Require metadata before any runtime fix ships.
  - Rejected: blocks immediate repair for active tester bug.

### Decision: Preserve DM-question repair flow as fallback, not failure
**MUST** keep the current direct adjudication path valid when players ask why state drift occurred.

Rationale:
- This is strong UX and helps the table recover from residual edge cases.
- Runtime hardening should reduce the need for it, not eliminate it.

Alternatives considered:
- Force immediate automatic repair whenever a drift question is asked.
  - Rejected: erodes the DM adjudication contract and can over-correct ambiguous scenes.

## Risks / Trade-offs

- [False positive local commit from flavorful descent prose] -> Mitigation: require one uniquely resolvable adjacent authored target plus stronger descent/entry cues; fail open otherwise.
- [Inference ordering breaks existing explicit action flow] -> Mitigation: explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId` remain authoritative and suppress inferred injection.
- [Combat still anchors to stale room because ordering hook is too late] -> Mitigation: place inferred action injection in the main reconciliation path before action processing consumes `createEncounter`.
- [Module-specific scene phrases remain under-specified] -> Mitigation: allow additive authored transition hints now and defer broader semantic enrichment to publication follow-up.
- [Regression overlap with startup or narrated-arrival logic] -> Mitigation: add targeted transcript locks and rerun existing scene/travel/location regression suites.

## Migration Plan

1. Add transcript-first regression coverage for the cathedral descent and same-turn descent-plus-combat lock cases.
2. Implement narrow implicit-sublocation inference helper in `utils/travel_state_sync_guard.py`.
3. Wire inferred location commit injection into existing reconciliation flow in `main.py` before encounter processing.
4. If required for determinism, add additive authored transition-hint metadata to the Night of the Restless Dead lock case.
5. Run compile, regression, and OpenSpec validation gates.

Rollback strategy:
- Remove the new inference helper and its call site while leaving existing travel/narrated-arrival reconciliation paths intact.
- Keep any additive module metadata harmless if the runtime reader is removed.

## Open Questions

- Should authored transition hints live directly in area location JSON, or in a separate semantic layer added by future publication tooling?
- Is the existing action-processing order already sufficient once inferred actions are appended, or does `createEncounter` need an explicit pre-processing ordering safeguard?
- Should the first implementation match only adjacent lower-depth rooms, or allow one hop beyond adjacency when authored descent text names a unique downstream chamber?
