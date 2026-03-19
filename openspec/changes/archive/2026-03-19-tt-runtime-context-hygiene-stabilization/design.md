## Context

The live runtime currently assembles narrator context from multiple overlapping sources: current location packets, preserved raw conversation turns, derived `[SUMMARY OF EVENTS AT THIS LOCATION]` blocks, `=== LOCATION CHRONICLE ===` blocks, companion-memory packets, and module-integration side effects. This layering improved narrative richness at first, but there is no strong provenance or invalidation contract on derived location-memory blocks, and failed module integration can still run in the ordinary gameplay hot path. As a result, one stale or mislabeled summary can be preserved, reinjected, and later consumed by both the narrator and the reconciler as if it were authoritative truth.

The Thornwood/Gorvek failure demonstrates the compound effect:
- current scene packet correctly said `TW05` / Bandit Stronghold with Gorvek present,
- a preserved `[SUMMARY OF EVENTS AT THIS LOCATION]` block labeled as `TW05` actually summarized `TW02` ambush events,
- the narrator then replayed arrival/parley beats as if Gorvek had not already been encountered,
- the reconciler later used that poisoned summary for `TW05` monster-state decisions.

This change is cross-cutting because it touches derived-memory producers, live narrator consumers, reconciliation consumers, and module integration lifecycle.

## Goals / Non-Goals

**Goals:**
- MUST ensure derived location summaries and chronicles carry explicit provenance and are rejected when that provenance does not match the current scene.
- MUST prevent automatic module integration attempts from running in normal live-turn processing.
- MUST prevent failed module integration from repeatedly injecting noise into narrator/reconciler context.
- MUST narrow location reconciliation to same-location authoritative evidence only.
- MUST preserve current-scene truth (`module`, `area`, `location`, current raw turns) as higher authority than stale derived memory blocks.
- SHOULD preserve narrator flexibility by dropping bad context instead of over-constraining narration logic.
- SHOULD add transcript regressions based on the Thornwood/Gorvek continuity break.

**Non-Goals:**
- MUST NOT redesign the full memory system or replace all compression mechanisms.
- MUST NOT remove canonical raw history from storage.
- MUST NOT change combat mechanics, inventory authority, or unrelated transition rules in this slice.
- MUST NOT re-enable dormant seamless-transition beautifier layers.

## Decisions

### Decision: Add explicit provenance metadata for derived location-memory blocks
- MUST attach machine-checkable provenance to every derived location summary/chronicle block:
  - `module`
  - `area_id`
  - `location_id`
  - `source_kind`
- MUST validate this provenance before derived blocks are reused by narrator or reconciler paths.
- SHOULD prefer additive metadata embedding that preserves existing human-readable block text.

Rationale:
- Derived memory is useful, but only if it can be proven to belong to the active scene.
- Provenance lets the runtime drop mismatched blocks deterministically instead of heuristically guessing.

Alternatives considered:
- Continue parsing human-readable headers only -> rejected, too brittle.
- Delete all derived location memory from canonical history -> rejected, destroys potentially useful continuity artifacts.

### Decision: Quarantine module integration from the live gameplay hot path
- MUST stop `detect_new_modules()` / integration attempts from running during ordinary turn processing and history refresh cycles.
- MUST restrict module integration to startup preflight or explicit operator/admin workflows.
- SHOULD debounce failed module integration so a single failure is logged once per session/module state rather than retried repeatedly every turn.

Rationale:
- Runtime play should not repeatedly perform module-stitcher work unrelated to the active scene.
- Failed Keep_of_Doom safety validation is currently contaminating active turns with irrelevant travel/integration noise.

Alternatives considered:
- Leave integration active but hide logs -> rejected, side effects still occur even if the logs are quieter.
- Disable all module integration permanently -> rejected, removes a needed workflow instead of isolating it correctly.

### Decision: Reconciler SHALL consume same-location authoritative evidence only
- MUST require location reconciliation inputs to match the location being reconciled.
- MUST ignore derived summaries/chronicles whose provenance does not match the target `module + locationId`.
- SHOULD prefer current-location raw turns and current location packet over older summaries.

Rationale:
- Reconciler errors become dangerous when stale summaries are treated as canonical scene evidence.
- Same-location-only evidence narrows the blast radius of prompt contamination.

Alternatives considered:
- Keep using all preserved context and hope the model sorts it out -> rejected, already demonstrated to fail.

### Decision: Live narrator payload SHALL prefer current-scene truth over preserved derived summaries
- MUST keep current scene packet (`Current Location`, current module, recent raw turns) as the highest authority for live narration.
- MUST exclude derived location-memory blocks when provenance is missing, mismatched, or stale relative to the current scene.
- SHOULD preserve canonical stored history while applying hygiene only at payload assembly time.

Rationale:
- This extends existing narrator scene hygiene without rewriting history.
- It keeps flexibility while sharply reducing false continuity replays.

Alternatives considered:
- Rewrite canonical history in place to remove all stale summaries -> rejected, too risky and destructive.

## Risks / Trade-offs

- [Over-filtering drops helpful continuity] -> Mitigation: current location packet and recent raw turns remain primary context even when derived summaries are excluded.
- [Provenance metadata rollout leaves mixed old/new history blocks] -> Mitigation: unprovenanced legacy derived blocks fail closed for live reuse when they cannot be matched confidently.
- [Module integration quarantine hides real onboarding issues] -> Mitigation: keep dedicated startup/admin diagnostics and explicit operator visibility outside the hot path.
- [Regression coverage misses another continuity shape] -> Mitigation: encode the exact Thornwood/Gorvek transcript shape plus a same-location monster reconciliation guard.
- [Merge-safety erosion from touching multiple runtime files] -> Mitigation: isolate new hygiene helpers and keep host edits thin and marked with `# TABLETOP MODE:` comments.

## Migration Plan

1. Add provenance metadata contract for derived location summary and chronicle emitters.
2. Add validation helpers that filter derived blocks by current `module/area/location` before narrator and reconciler reuse.
3. Remove or gate module auto-integration from ordinary live-turn execution paths.
4. Add failed-integration quarantine/debounce so invalid modules do not retry every turn.
5. Narrow reconciler input assembly to same-location authoritative evidence only.
6. Add transcript-based regressions for:
   - Thornwood/Gorvek no-second-arrival continuity
   - `TW05` reconciler ignoring `TW02`-derived summary contamination
   - no repeated Keep_of_Doom integration noise during ordinary turns
7. Rollback strategy: disable provenance filtering helpers and restore previous hot-path gating only if a severe regression occurs, while preserving test artifacts and diagnostics for rework.

## Open Questions

- Should provenance live in explicit JSON metadata lines embedded in assistant/system messages, or in sidecar/runtime-only structures reconstructed during update history flow?
- Should failed module integration quarantine reset only on process restart, or also when filesystem state changes under `modules/`?
- Which existing legacy derived blocks can be safely recognized heuristically versus dropped by default?
