# Implementation Notes: tt-transition-time-failopen-sync

## Files Changed

1. **main.py** (lines 2193-2243)
   - Added runtime fail-open fallback logic for `transitionLocation` without `updateTime`
   - Detects per-response action bundles
   - Injects synthetic `updateTime` action deterministically
   - Logs STATE_SYNC for observability

2. **prompts/system_prompt_compressed.txt** (line 91)
   - Added `travelBundle: REQUIRED` rule to `@TIME` block
   - Reinforces that `transitionLocation` MUST include `updateTime` in same response

3. **prompts/validation/validation_prompt_compressed.txt** (lines 106-110)
   - Added `@TRAVEL_TIME_BUNDLE` block with:
     - Explicit pairing rule
     - Missing-pair violation
     - Valid bundled example
     - Invalid transition-only example

4. **prompts/validation/validation_prompt.txt** (lines 240-244)
   - Added `TRAVEL-TIME BUNDLE VALIDATION` section
   - Parity with compressed validator rules and examples

5. **scripts/test_transition_time_failopen.py** (new, 200+ lines)
   - 8 comprehensive regression tests
   - Tests fallback injection, explicit time preservation, non-transition safety

## Fallback Trigger Contract

When processing AI response actions:
1. Check if any action has `action == "transitionLocation"` -> has_transition
2. Check if any action has `action == "updateTime"` -> has_update_time
3. If `has_transition and not has_update_time`:
   - Find target location from `transitionLocation.parameters.newLocation`
   - Use `location_graph.nodes[target_location]['area_id']` to determine area
   - Compare with `party_tracker.worldConditions.currentAreaId`

## Deterministic Minute Policy

| Transition Type | Minutes | Determination Logic |
|-----------------|---------|---------------------|
| Same-area | 10 | Target area == Current area |
| Cross-area | 20 | Target area != Current area |
| Unknown location | 20 | Graph lookup failure (safe default) |

## Logging Contract

When fallback is applied:
```
STATE_SYNC: Auto-applied updateTime=<N> due to transitionLocation without updateTime (cross_area=<bool>)
```

- ASCII only
- Includes minute value and cross_area flag
- Logged via `info()` with category="time_sync"

## Test Coverage Summary

8 tests in `scripts/test_transition_time_failopen.py`:

1. `test_injects_update_time_when_transition_missing_time_same_area`
   - Same-area gets 10 minutes

2. `test_injects_update_time_when_transition_missing_time_cross_area`
   - Cross-area gets 20 minutes

3. `test_does_not_inject_when_update_time_already_present`
   - No double injection

4. `test_no_injection_for_non_transition_turn`
   - Non-movement turns unchanged

5. `test_graph_lookup_failure_defaults_cross_area_minutes`
   - Unknown location defaults to 20 (cross-area)

6. `test_multiple_transitions_same_response`
   - Single fallback for multiple transitions

7. `test_transition_with_existing_update_time_preserved`
   - Original explicit time preserved

8. `test_log_format_ascii_only`
   - Log uses ASCII characters only

All tests: **8/8 PASS**

## Implementation Notes

- Synthetic `updateTime` is inserted at the BEGINNING of `other_actions`
- This ensures time advances before location transition processes
- Uses `location_graph` from main.py global scope for area lookups
- Fail-safe: unknown locations default to cross-area (20 min) for safety
- No schema changes - works within existing action contracts
- Merge-safe: changes marked with `# TABLETOP MODE:` comments

## Known Limitations

- Area detection requires `location_graph` to be initialized
- If location graph is None, defaults to cross-area minutes
- Does not handle multi-hop transitions specially (counts as single transition)
