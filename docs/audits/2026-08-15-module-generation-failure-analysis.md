# Module Generation: Failure Analysis & Fix Directions (2026-08-15)

Consolidated analysis of the module-generation defects found in two live-model builds, the
owner's directions per failure, and the code-level findings behind each. This is an analysis
record only — **no source, schema, or module was changed to produce it.** It is the planning
basis for the fixes; nothing here is implemented yet unless explicitly noted.

Related documents:
- `docs/audits/2026-08-15-generated-module-quality-review.md` — Codex's full module-quality audit.
- `docs/audits/2026-08-15-t026-worldconditions-location-fallback-audit.md` — Codex's T026/worldConditions audit.

## Modules reviewed
- `modules/The_Haunted_Watchtower` — built by **gemma-4-12b-qat** (BEFORE the encounters-stripping fix).
- `modules/The_Haunted_Watchtower_v2` — built by **qwen/qwen3.5-9b** (WITH the encounters-stripping fix).

Codex verdict: **do not ship either as authored.** Both pass strict file-shape schemas, real
headless new-game/state startup, graph reachability, reciprocal internal/cross-area edges, and
plot next-point resolution. All remaining defects are in the **semantic/playability** layer that
schema validation does not check.

--------------------------------------------------------------------------------
## The simple failure list (grouped by type)

1. **False "already-played" encounters on a fresh module** — Gemma only (11/12 locations, dated
   1200/1204 vs party year 1492). Eliminated by the #2 encounters-stripping fix; Qwen v2 is clean.
2. **Plot order does not match the physical map route** (both, BLOCKER) — the story says area A→B→C,
   but door connections force backward entry or skip an area. Graph connected; intended route not encoded.
3. **`module_context.json` is stale and wrong** (both) — missing cross-area connections, wrong area
   names, wrong plot-point ownership; fails the production validator; its own `validation_report.json`
   falsely claims "no issues."
4. **A location's coordinates disagree with its map** (Qwen — A04 at X2Y3 vs map's X1Y2). Issue-#128 class.
5. **Locked doors with no key anywhere** (Qwen — 5 named keys that exist in no location; others blank).
6. **Plot beats / quest items point at things that don't exist** (both) — NPCs in empty rooms, absent
   quest items, a villain authored in 3 places at once with conflicting attitudes.
7. **Same NPCs duplicated across areas with conflicting roles** (both) — e.g. Mother Marrow neutral
   grove-tender in one area, hostile cult leader in another, no travel/projection explanation.
8. **Monster names with no compendium stat source** (both) — **BY DESIGN, not a defect** (see below).
9. **Visible scaffolding / placeholder content** (both) — template prose ("A fallen logs"), every map
   room `purpose: "unknown"`, generic `Mixed Map`/`varied` terrain, map `startRoom` != actual arrival.

**Meta-finding:** the strict schema + current validator prove a module is *well-shaped and connected*,
NOT *accurate, coherent, or playable*. Every failure above except #1 is invisible to schema validation.

--------------------------------------------------------------------------------
## Per-point analysis and owner direction

### #1 — Encounters & dates (owner: all encounters blank on launch; fix prompt+schema)
Owner intent: a fresh module ships with **empty encounters**; the engine stamps a dated encounter
from the party clock only when one actually occurs on first use. Confirmed against the shipped
starters: `The_Thornwood_Watch/*_BU.json` (17 locations) and `Keep_of_Doom/*_BU.json` (36 locations)
all have empty `encounters` arrays. Runtime creates dated encounters at
`core/managers/combat_manager.py` (append) and the T015 departure update in `core/ai/adv_summary.py`.

Root cause — the model is told to author encounters from BOTH directions:
- **Schema requires it:** `schemas/loca_schema.json` lists `encounters` in the location `required`
  array, and each encounter requires `worldConditions {year, month, day(1-28), time}`.
- **Prompt instructs it:** `LocationPromptGuide.encounters` (`core/generators/location_generator.py:829`)
  says "Pre-planned encounters that occurred or may occur here … worldConditions: Date/time when it
  occurred" with example `"day": 15`.
- **Same schema is reused at play time:** `loca_schema.json` is also loaded by `adv_summary.py` (the
  runtime encounter-update path). So the PLAY schema is directing GENERATION.

Current state: the strip `_canonicalize_t026_mechanical_fields` (location_generator.py:192-210, the
#2 fix) runs on ALL three T026 paths (first/retry/repair — lines 1327/1351/1488), so post-fix builds
are clean. Wasteful/fragile to ask for what we discard.

Fix direction (owner-approved shape): create a **generation-specific location schema** (copy of the
play schema) where `encounters` is not-required / constrained empty, and update the T026 prompt so the
model does not author encounters or dates at all. Keep the strip as a safety net. Same treatment for
date/time. Do NOT change the play/runtime schema.

### #2 — Plot order vs physical route (owner: give the build order; does the model have context?)
Story-first build order (`core/generators/story_first/pipeline.py:65` `_STAGES`):
```
1. outline           accepted story beats, promise, opposition, side-threads, creature briefs
2. area_binding      outline -> AREAS + location-role stubs + MAPS
3. plot_derivation   derive plot points / nextPoints from the areas
4. location_fill      T026 fills each location's content (not a "model stage")
5. npc_repair        NPC reconciliation
6. candidate_hardening schema hardening / objective repairs
7. creature_compile  monster compilation
```
Context answer: **the model HAS enough context.** `area_binding` (stage 2, which creates the map/route)
receives the full outline (beat order) and its prompt explicitly says "Anchor successive required
main-path beats in the same location or connected locations" (`stages/area_binding.py:30-42`). The gap
is **enforcement, not context**: nothing verifies the resulting cross-area route direction runs forward
in plot order; backward edges slip through, and there is no route-order check anywhere in the pipeline.

Fix direction: a deterministic route-order check (traverse areas in plot order; confirm forward
reachability from the start; the "next" area's entry should be reachable moving forward, not by
backtracking) that repairs or flags a backward/skip route. This is a new post-generation verification.

### #3 — module_context.json and coordinates (owner questions)
- **What is `module_context.json`?** The **per-module master index** (areas, locations, NPCs, plot
  summary), created during generation at `core/generators/module_generator.py:890` via
  `utils/module_context.py` (`ModuleContext` — "Maintains the master context for module generation").
  **It is NOT the multi-module connector.**
- **The multi-module connector** (what links multiple modules for the game engine) is
  **`world_registry.json`**, managed by `core/generators/module_stitcher.py` (holds cross-module
  `connections`). module_context is within-module; world_registry is cross-module.
- The staleness Codex found is module_context drifting from the live area/plot content — it is not
  re-synced after later stages edit content. Fix direction: rebuild/verify module_context from the
  final live artifacts (deterministic) as the last generation step.
- **Are location coordinates used in the game?** **No.** A grep across `core/ai`, `core/managers`,
  `main.py`, `updates` found zero runtime reads. Coordinates are a build-time map artifact only, so the
  A04 conflict is cosmetic/structural, not gameplay-affecting.
- **Deterministic coordinate generation?** Yes — `MapLayoutGenerator.generate_layout`
  (`core/generators/area_generator.py`) already produces `X{x}Y{y}` from the grid. Fix direction (same
  pattern as encounters): **code owns coordinates from the map; the model does not author them**, which
  removes the map/coordinate disagreement class entirely.

### #4 — Map/coordinate disagreement
Covered by #3 (coordinates are build-time-only, deterministically generatable; code should own them).

### #5 — (deferred by owner)
Return later.

### #6 — Locked doors with no key path (deferred by owner)
Return later. Note: `module_doctor.py` already DETECTS lock/key findings but treats them as advisories
it does not repair (see meta-finding below).

### #7 — NPC name dedup (owner: thought there was a dedup process)
There IS a dedup process: **`NpcReconciler`** (`utils/npc_reconciler.py`) plus the `npc_repair` stage,
wired in `module_builder._reconcile_and_validate_context` (`core/generators/module_builder.py:1926`).
It decides whether two NPC **name labels** refer to the same person
(`build_npc_merge_confirmation_prompt`, npc_reconciler.py:184 — merges e.g. "Captain Valerius" and
"Captain Valerius Thorne"). **But it reconciles NAMES only, not ROLES/ATTITUDES across areas.** Codex's
finding (Mother Marrow neutral grove-tender in one area, hostile cult leader in another) is a semantic
conflict the reconciler does not touch. Gap = cross-area role/attitude coherence, which nothing enforces.

### #8 — Monsters without a stat source (owner: this is a DESIGN FEATURE)
**Not a defect.** Monsters in location `monsters[]` whose names do not resolve to the compendium are
**lazy spawn descriptors**; the **monster builder generates the stat card at runtime**. The production
validator already encodes this exemption at `core/validation/validate_module_files.py:799-801`, and an
empty `modules/<m>/monsters/` is normal for a fresh module. Codex's G4/Q5 findings were wrong on this
point. (Saved to memory so it is not re-flagged.)

### #9 — Scaffolding / placeholder prose (deferred by owner)
Return later. Note: the exact surgical-repair floor string "To be detailed by the module doctor" occurs
in NEITHER module — the #3 surgical ladder did not floor anything in these builds.

--------------------------------------------------------------------------------
## The enforcement-gap meta-finding (answers "I thought each stage ensured this")

The staged, skeleton-first build DOES enforce the structural layer, and Codex verified these all PASS:
unique location IDs, reciprocal internal + cross-area connections, full reachability from the start,
terminating plot chains, matching map room-sets. The skeleton guarantees structure.

There is **no stage that enforces the semantic/playability layer.** A grep of the entire story-first
pipeline for route-order / map-coordinate / key-existence enforcement returned zero matches. The one
stage that could catch it, `core/generators/story_first/module_doctor.py`, is deliberately scoped out:
its docstring states it is "objective-only," it "only repairs an exact unresolved public PPxxx/SQxxx
reference," and "lock/key findings [are] advisories, so they never enter this repair list." So the
doctor DETECTS key/reference problems and chooses not to fix them.

Therefore every non-encounter defect lives in this unenforced gap. The likely resolution is a
**post-generation semantic pass** (deterministic where possible; agentic healing where content is
needed) covering: route order vs physical routing, module_context synchronization, map/location
coordinate agreement, key existence/reachability, quest-prop existence, and NPC role coherence.

--------------------------------------------------------------------------------
## Design features (NOT defects) — do not "fix"
- Lazy monster spawns without a compendium stat source (#8) — runtime monster builder.
- Location coordinates not read at runtime — build-time map artifact.
- Empty `encounters` / `adventureSummary` / `explorationState: unvisited` on fresh locations — correct;
  runtime populates them.
- Area IDs (not location IDs) stored in `plotPoints[].location` / `sideQuests[].involvedLocations` —
  correct for the current T028 runtime contract (`module_builder.py:288-326,1328,1337,1351-1353`;
  `main.py:5825-5836`); the stale schema descriptions in `plot_schema.json:30-33,67-72` are a doc gap.

--------------------------------------------------------------------------------
## Recommended fix ordering (for owner decision)
1. **#1 encounters/dates** — smallest; strip already live, add gen-schema + prompt so the model does
   not author them at all. (mostly done)
2. **#3 coordinates** — code owns coordinates from the deterministic map; removes the disagreement class.
3. **#2 route-order check** — new deterministic post-generation verification (plot order vs physical route).
4. **#3 module_context resync** — rebuild the per-module index from final live artifacts as the last step.
5. **#7 NPC role coherence** — extend reconciliation beyond names to cross-area role/attitude conflicts.
6. **#5, #6 (keys), #9 (scaffolding)** — deferred; the semantic-doctor pass is the likely home.

Deferred: review an OpenAI-generated module with the same analysis to confirm these are build-process
gaps (predicted: same defects, since nothing catches them regardless of model) vs weak-model quality.
