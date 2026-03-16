## Context

The current validator has three distinct blind spots that together allow playable movement failures to ship:

1. The runtime location graph loads intra-area edges from `locations[*].connectivity` in area files.
2. Map files maintain a second room graph via `rooms[*].connections`, but validator flow does not compare that graph against area connectivity.
3. The CLI validation entrypoint runs schema/reference checks but does not invoke the full validation set in both reporting modes, so some checks never execute during normal operator use.

The result is a structural-pass / gameplay-fail split: JSON is valid, but the module cannot be traversed as authored.

## Goals / Non-Goals

**Goals:**
- Add deterministic, runtime-aligned checks for room reachability inside area files.
- Add deterministic parity checks between area room connectivity and map room connectivity.
- Add deterministic progression checks that ensure module start, plot beats, and declared branch paths are graph-valid.
- Ensure CLI validation uses one canonical execution path for both human and JSON output.
- Keep the implementation bounded, additive, and suitable for preflight tooling reuse.

**Non-Goals:**
- No broad rewrite of `LocationGraph` runtime behavior.
- No gameplay simulation, transcript playback, or LLM-based module testing.
- No expansion into subjective narrative-quality audits.
- No schema overhaul unless a narrow optional field clarification is required later.

## Decisions

### Decision 1: Reuse runtime graph semantics as validator truth source

The validator SHALL evaluate intra-area room traversal using the same contract the runtime graph consumes: `locations[*].connectivity` and existing cross-area fields where present.

Rationale:
- This prevents validator/runtime drift.
- The recent Night bug existed precisely because map-only connectivity was not the runtime truth source.

Alternative considered:
- Validate only `map_*.json` room graphs.
- Rejected because runtime movement does not currently use map files as authoritative traversal data.

### Decision 2: Add an explicit parity layer rather than silently hydrating area connectivity from maps

The validator SHALL compare area and map graphs and fail when they disagree, rather than mutating one from the other.

Rationale:
- Validation should surface authoring mistakes, not auto-rewrite canonical content.
- Auto-healing would hide source-of-truth ambiguity and make regressions harder to diagnose.

Alternative considered:
- Auto-backfill missing `connectivity` from map files inside the validator.
- Rejected because it changes module data during validation and weakens fail-closed guarantees.

### Decision 3: Plot progression validation remains graph-based and explicit

The validator SHALL validate only explicit progression artifacts:
- module starting location
- `plotPoints[*].location`
- explicit branch metadata `path` arrays and `bypass` arrays when present
- finale/conclusion reachability from earlier beats

Rationale:
- These are deterministic and machine-checkable.
- This avoids widening into freeform story interpretation.

Alternative considered:
- Infer intended progression from descriptions.
- Rejected as too ambiguous and brittle.

### Decision 4: One canonical CLI validation path

The CLI SHALL route both human-readable and JSON reporting through the same full validation method before formatting output.

Rationale:
- The current split is a root cause of silent skipped checks.
- One path reduces future drift and makes tests simpler.

### Decision 5: Single-area modules need room-level validation, not area-level exemptions

Area-to-area connectivity checks may remain useful for multi-area modules, but the validator SHALL add room-level reachability checks that also apply to single-area modules.

Rationale:
- Many imported adventures are single-area dungeons where the core risk is broken room traversal, not area travel.

## Risks / Trade-offs

- [Risk] False positives from optional branch metadata that is not intended as a strict traversal contract.
  -> Mitigation: only validate well-formed explicit arrays such as `path` and `bypass`; ignore prose-only metadata.

- [Risk] Existing modules may have minor map/area drift that becomes newly blocking.
  -> Mitigation: provide clear error output with room IDs and source files so fixes are surgical.

- [Risk] Graph validation duplicates parts of `utils/location_path_finder.py` in a fragile way.
  -> Mitigation: prefer extracting a narrow helper or reusing the same parsing semantics rather than re-implementing graph rules independently.

- [Risk] JSON and human-report modes diverge again later.
  -> Mitigation: add regression tests that assert both modes run the same validation suite.

## Migration Plan

1. Lock contract coverage first with validator-focused spec and regression tests.
2. Refactor validator CLI entry so one full validation path feeds both report styles.
3. Add intra-area reachability validation for start-to-room and room-to-room graph integrity.
4. Add map/area parity checks using explicit room ID comparison.
5. Add plot progression reachability checks for start location, plot points, and branch metadata.
6. Run targeted validation on the known Night regression module and at least one healthy comparison module.

Rollback strategy:
- Revert the new deterministic validation sections independently if they prove too noisy.
- Preserve the canonical CLI execution-path unification unless it directly causes regression, because that fix removes existing drift even if specific checks are narrowed.

## Open Questions

- Whether finale/conclusion detection should rely only on graph reachability plus explicit prerequisites, or also enforce a naming-based heuristic (`Conclusion`, `Return`, etc.) in validator warnings.
- Whether explicit branch metadata coverage should eventually move into schema-level optional structures for stronger import-time guarantees.
