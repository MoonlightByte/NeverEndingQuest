## Context

The previous combat coherence repair fixed multi-PC turn authority, but the next live test showed that broader runtime authority still diverges after narration is already logically correct. Three deterministic failures remain coupled: hidden authored NPCs can be recognized by validation context yet fail `moveBackgroundNPC` lookup, stale `currentLocationId` can survive deeper room progression because explicit location actions are omitted, and `updatePlot` can emit alias statuses like `resolved` that fail schema validation instead of converging onto canonical plot state.

This change stays inside the existing TABLETOP MODE reconciliation architecture. It does not introduce new persistence backends or broaden module schema. The design must preserve merge-safe host edits, fail-open location repair for ambiguous evidence, and fail-closed behavior for ambiguous NPC identity.

## Goals / Non-Goals

**Goals:**
- MUST make hidden or revealable authored NPC identities resolvable by runtime move lookup using the same canonical strict-first/fallback path as visible NPCs.
- MUST canonicalize plot status aliases to the existing schema enum before persistence and validation.
- MUST add deterministic location reconciliation from unique same-turn plot evidence when explicit location actions are missing.
- SHOULD keep the implementation near existing reconciliation hooks (`main.py`, `travel_state_sync_guard.py`, `action_handler.py`, `plot_update.py`) instead of creating a second authority path.
- SHOULD emit operator-readable logs that distinguish canonicalization from authored state mutation.

**Non-Goals:**
- MUST NOT change the plot schema enum set.
- MUST NOT infer location from vague progress narration, multi-target plot updates, or ambiguous scene evidence.
- MUST NOT promote background NPCs into party NPCs implicitly.
- MUST NOT rewrite narrator prompts or validation contracts beyond what current deterministic runtime needs.

## Decisions

### Decision: Plot status aliases will be normalized at runtime boundaries, not by widening schema
- MUST keep `schemas/plot_schema.json` unchanged with canonical values `not started`, `in progress`, and `completed`.
- MUST normalize known aliases such as `resolved` before `update_plot(...)` writes or validates.
- SHOULD also re-normalize AI-returned plot update payloads inside `updates/plot_update.py` so the write path remains safe even if upstream callers miss normalization.
- Why: this preserves one canonical stored vocabulary and fixes retry loops without weakening validation.
- Alternative considered: adding `resolved` to the schema. Rejected because it expands durable state vocabulary and increases downstream branching.

### Decision: Location reconciliation will piggyback on the existing travel-state sync layer
- MUST implement plot/location reconciliation alongside existing travel and scene reconciliation helpers rather than inside unrelated post-processing.
- MUST only inject `updatePartyTracker` when one unique plot-point or encounter-derived location can be resolved and no explicit location action is already present.
- SHOULD use active-module `module_plot.json` plus known module locations to map `updatePlot.plotPointId` to a canonical location.
- Why: `travel_state_sync_guard.py` already centralizes deterministic location repair with fail-open behavior and additive inferred actions.
- Alternative considered: committing location directly inside `update_plot`. Rejected because plot persistence is not the authoritative place for scene/location decisions and lacks full response/action context.

### Decision: Hidden NPC move resolution will reuse authored hook extraction, not a separate NPC registry
- MUST extend the NPC move lookup candidate set to include hidden/revealable identities from authored investigation hooks.
- MUST preserve strict location-hint precedence, then canonical fallback, then ambiguity-safe failure.
- SHOULD reuse the same hidden identity extraction shape already used by validation context (`extract_hidden_npcs_from_location`) so authored truth is consistent.
- Why: Father Aldric is already authored in location hooks; duplicating a second manual registry would drift again.
- Alternative considered: adding hidden NPCs to `party_tracker.json` or forcing prompt-side workaround. Rejected because this would blur background NPC persistence and move the fix away from authoritative module data.

## Risks / Trade-offs

- [False-positive location commit] -> Mitigation: require one unique plot-point location, skip when explicit location action already exists, and fail open on ambiguity.
- [Over-normalizing plot statuses] -> Mitigation: normalize only a small explicit alias map and leave unknown values blocking with clear logs.
- [Hidden NPC ambiguity across locations] -> Mitigation: preserve existing canonical ambiguity failure path and add regression tests for multi-match cases.
- [Merge drift in host files] -> Mitigation: keep host edits limited to existing TABLETOP MODE reconciliation import/call sites.

## Migration Plan

1. Add OpenSpec delta specs for hidden NPC lookup, plot status normalization, and scene/plot location reconciliation.
2. Implement runtime helpers and targeted host wiring.
3. Add regression tests covering hidden authored NPC lookup, plot alias normalization, and plot-driven location sync.
4. Run targeted compile/tests.
5. If a regression appears, rollback by removing the new inferred-action hook and alias map while leaving schema unchanged.

## Open Questions

- None for this slice. The remaining decisions are implementation-level and can be validated with targeted regression tests.
