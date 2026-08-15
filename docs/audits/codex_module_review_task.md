# Codex task: review two generated modules (accuracy / quality / playability)

Read-only review. The owner wants your independent verdict before he considers committing
the fixes. Work on the `.worktrees/main-merge` worktree (branch off main tip). Do NOT modify
anything except writing your findings to `docs/audits/`.

## Modules to review
1. `modules/The_Haunted_Watchtower` — built by **gemma-4-12b-qat** (2 areas: OR001, SP001)
2. `modules/The_Haunted_Watchtower_v2` — built by **qwen/qwen3.5-9b** WITH the new #2
   encounters-stripping fix (3 areas: HWG001, IPA001, STS001)

## Review dimensions
1. **Full schema conformance** across ALL files — areas, module json, `module_plot.json`,
   `characters/`, NPCs — not just areas (I only spot-checked areas = VALID against
   `schemas/locationfile_schema_strict.json`).
2. **Structural integrity** — `areaConnectivity` / `areaConnectivityId` resolve to real
   locations/areas; locationId scheme correct; map layout coherent; no dangling connections
   (issue #128 class); coordinates/connectivity consistent.
3. **Playability** — valid start location; plot points reference existing locations; NPC/monster
   allowlist compliance; keys/passphrases/answers present where locked doors need them;
   confirm `encounters` are EMPTY on fresh locations (EXPECTED — the #2 fix strips them and
   runtime creates dated encounters on first use; this is correct, NOT a defect — verify it is
   truly empty everywhere and matches the shipped starters The_Thornwood_Watch / Keep_of_Doom).
4. **Content quality** — coherent descriptions, sensible dmInstructions/plotHooks, no
   placeholder/floor text such as `To be detailed by the module doctor` (that string would be a
   surgical-repair floor — flag every occurrence with file + path).
5. **gemma vs qwen** — compare the two honestly; which is the better, more playable module.

## Output
Write `docs/audits/2026-08-15-generated-module-quality-review.md` with: per-module findings,
every defect cited by file + JSON path, the gemma-vs-qwen comparison, and a clear verdict —
are these good enough to ship. Post a short summary to the room when done. Use sol medium.
