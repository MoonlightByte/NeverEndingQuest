# Minimal Parlay Travel Unblock Plan

## Status

- Planned
- Priority: Medium (safety against repeat narrative loop)
- Scope: Minimal engine safeguard only, no module content rewrite

## Context

Observed behavior at `V04` (`Petitioner's Rest`) in Pumpkin King's Curse:

- Party successfully parlayed with Bloodshadow multiple times.
- Travel attempts were repeatedly blocked with hostile encounter guidance.
- Loop eventually broke when player delivered a specific truth statement as a PC.

Narratively this was good, but the state model can still re-loop in similar guardian/parlay scenes.

## Objective

Add a tiny, explicit state hook so peaceful hostile resolution can unblock travel without requiring combat writeback.

## Design (Minimal)

### 1) Add an optional world state marker

Use `party_tracker.json -> worldConditions`:

```json
"resolvedHostilesByLocation": {
  "V04": true
}
```

Notes:

- Additive only.
- Missing key means current behavior unchanged.
- `true` means hostile gate at that location is considered resolved for travel.

### 2) Reuse existing action contract

Do not add a new action type.

- Continue using `updatePartyTracker` to persist `resolvedHostilesByLocation` updates.
- Trigger this only when narration establishes peaceful resolution/yield (for example, guardian grants passage).

### 3) Path analyzer compatibility update

File: `utils/path_encounter_analyzer.py`

Minimal change:

- Add optional input for world conditions (or resolved map).
- Treat location as effectively visited if either:
  - existing encounter-based visited heuristic is true, OR
  - `resolvedHostilesByLocation[location_id]` is true.

Result:

- `blocks_travel` becomes false for resolved locations even when static `monsters` remain in area JSON.

### 4) Transition atlas display parity

File: `core/ai/transition_atlas_builder.py`

Minimal change:

- Apply the same resolution check when composing status markers.
- Optionally render a clear marker, for example `[RESOLVED - SAFE]`.

Reason:

- Keep validation AI context aligned with deterministic blocker logic.

### 5) Action handler wiring

File: `core/ai/action_handler.py`

Minimal change:

- Pass `party_tracker_data.get("worldConditions", {})` into:
  - `analyze_path_for_encounters(...)`
  - transition atlas builder function

No other transition rules change.

## File-Level Change List

1. `utils/path_encounter_analyzer.py`
   - Add optional resolved-hostiles input
   - Update visited/blocking computation
2. `core/ai/transition_atlas_builder.py`
   - Add optional resolved-hostiles input
   - Update marker selection logic
3. `core/ai/action_handler.py`
   - Thread `worldConditions` into analyzer/atlas calls
4. `prompts/system_prompt_compressed.txt` (optional single-line nudge)
   - Clarify that if a hostile guardian grants passage, AI should persist location resolution via `updatePartyTracker`

## Regression Tests (Targeted)

Create: `scripts/test_parlay_travel_unblock.py`

Cases:

1. Unresolved hostile location with monsters blocks travel (baseline unchanged)
2. Same location with `resolvedHostilesByLocation[loc]=true` does not block travel
3. Existing encounter-entry visited logic still works unchanged
4. Missing `resolvedHostilesByLocation` key is fail-open to baseline behavior

Optional integration case:

5. Analyzer + atlas both classify resolved location consistently

## Acceptance Criteria

- No regression for combat-driven travel gating.
- Peacefully resolved hostile locations can be left without looped re-block.
- All changes additive and backward compatible.
- No module data schema changes required.

## Rollout Guidance

- Keep this as a minimal safety patch, not a narrative rewrite.
- Do not remove static `monsters` from module files.
- Preserve emergent roleplay gates (like "PC must speak truth") while preventing infinite state loops.

## Optional Immediate Session Hotfix (Manual)

If a live session loops again before code patch lands, set:

```json
"worldConditions": {
  "resolvedHostilesByLocation": {
    "<CURRENT_LOCATION_ID>": true
  }
}
```

in `party_tracker.json` for the current session state.
