# Plans for Issues #159 and #160 (Claude draft, 2026-08-16)

Full implementation plans for the two out-of-scope issues surfaced during the module-generation
coherence campaign. Root causes are code-confirmed in `.worktrees/main-merge`. Doctrine unchanged:
code owns mechanical/structural fields; the model owns creative content; no prose keyword-matching;
acceptance = real headless play judged on-disk; commit + validate one item before the next.

--------------------------------------------------------------------------------
## Issue #159 — Model-authored areaConnectivity/areaConnectivityId pollution

### Root cause (confirmed)
`areaConnectivity`/`areaConnectivityId` are **code-owned** cross-area fields. Two paths, only one guards them:
- **Story-first ALREADY code-owns them.** `compile_area_binding` writes the code-owned cross-area
  connections into the stub (`compilers.py:277-278, 340-347`), and `TRUSTED_LOCATION_FIELDS`
  (`validators.py:850-851`) restores them from the trusted stub after generation (`:1107`). Any
  model drift is overwritten. **Story-first is clean.**
- **Legacy is polluted.** Legacy stubs come from map rooms (`location_generator.py:1558-1566`) and
  carry only `locationId/name/type/connections/coordinates` — NO areaConnectivity. Nothing restores
  or clears the field, so the T026 model's guessed `areaConnectivity`/`areaConnectivityId` survives,
  and `finalize_locations_and_connections` (Step 4.55) then **appends** the correct entry — leaving
  both (e.g. `WB001:A03 -> ['WW001','B01']`, where `WW001` is an area ID in a location-ID field).

### Fix (recommended): treat areaConnectivity/areaConnectivityId as stub-owned in the shared canonicalizer
In `_canonicalize_t026_stub_owned_fields` (`location_generator.py`), restore both fields from the
stub — exactly the pattern just used for `coordinates` (Item D):
- **Legacy:** the stub has no `areaConnectivity` key -> set to `[]` (clears the model pollution).
  `finalize` remains the sole deterministic author at Step 4.55.
- **Story-first:** the stub carries the code-written `areaConnectivity` -> restore it (identical
  outcome to the existing `TRUSTED_LOCATION_FIELDS` restore, just earlier and consistent).
This makes the fields code-owned in BOTH paths at one seam, and the identity preflight already
guarantees `locationId==position` before restore so it cannot mask a reorder.

### Why this is safe for story-first (the key risk to verify)
Story-first's `TRUSTED_LOCATION_FIELDS` restore runs in `restore_repaired`/`restore_hardened` in the
`location_fill` stage, AFTER `generate_location_batch` returns. So even if the canonicalizer cleared
the field, story-first re-restores from its trusted stub. Restoring-from-stub in the canonicalizer
just makes them agree earlier. **Verification required before merge:** confirm no story-first stage
reads model-authored `areaConnectivity` between generation and the trusted restore.

### Alternatives (rejected)
- Legacy-only clear inside `finalize`: misses pollution on non-gateway locations and duplicates
  ownership logic; the canonicalizer seam is the single correct home.
- Silent post-hoc scrub in the validator: hides the root cause; every ownership guard here is
  restore/clear at generation, not mutate-on-validate.

### Validation
- Deterministic: a stub without areaConnectivity + a model location that authored
  `areaConnectivityId:['WW001']` -> canonicalizer clears it; a story-first-style stub WITH
  areaConnectivity -> restored.
- Real qwen legacy build: the Step 4.56 route detector reports **0** `route/parallel`/`route/reciprocity`
  findings (currently 7 all trace to this); routing ACCEPTANCE still PASS.
- Real story-first (dial-up) build: areaConnectivity intact and identical to pre-fix (no regression).

### Follow-on
Once legacy is clean, the Item B route detector can escalate one step toward fail-loud on the
parallel-array checks (per its escalation criteria).

--------------------------------------------------------------------------------
## Issue #160 — Agentic NPC cross-area role/attitude reconciliation

The deterministic advisory shipped (`feac15b3`, Step 4.57). This plan is the **agentic decision**
half — the semantic authority Codex identified as the only compliant way to reconcile role/faction
(which lives in prose, not a schema field).

### Trigger
After T088 name reconciliation (Step 6.5), group final NPC appearances by canonical identity
(`duplicate_npc_placements`, exact casefold — used ONLY to GROUP post-reconcile, never as the
identity classifier). If a canonical identity appears across **>1 area**, it is a candidate.

### The one structured model call (per candidate identity)
Inputs: canonical name + aliases; every appearance (areaId, locationId, exact name/description/
attitude, that location's dmInstructions); any plot beats that reference the NPC. The model returns
a **strict patch contract** deciding the fact code cannot derive:
- classification: `same_mobile_person | projection_or_manifestation | intentional_attitude_change |
  accidental_duplicate`
- a **primary placement** (areaId/locationId) for the canonical identity
- for each occurrence: the corrected `name/description/attitude` and an explicit
  continuity/projection/mobility note appended to that location's `dmInstructions`
- never a new NPC id; never removes a recurring antagonist/guide (keeps a primary + explicit note)

Model config: a per-callsite entry in `model_config.py` per provider (T-id TBD), following the
migration doctrine (branch on `MODEL_PROVIDER`, Gemini `response_schema` from the patch schema).

### Code applies fail-closed
- Only `npcs[].name/description/attitude` and location `dmInstructions` may change.
- Identity set preserved (no new/dropped canonical identities); no new location/area IDs.
- Atomic via the existing T088 machinery (`_reconcile_all_areas_unlocked` transaction), one bounded
  correction pass then abort; schema-validate the patch before apply; reject + log on any violation.
- Wired behind a **default-OFF flag** (e.g. `ENABLE_NPC_ROLE_RECONCILIATION`) until validated.

### Validation (the hard part — conflicts are stochastic)
Do NOT rely on generating a conflict. Instead: craft a **fixture module on disk** with a known
same-name cross-area divergent NPC (Mother Marrow: neutral grove-tender in area A, hostile cult
leader in area B), run the real reconciliation pass against it, and judge the on-disk result:
one coherent primary + explicit continuity; the other occurrence carries a projection/change note;
no NPC erased; no party member added; a genuinely-distinct same-name pair (two different "Guard"
NPCs) is left alone. Then a real qwen build as a smoke test (flag on) to confirm no regression when
no conflict exists.

### Open questions for owner
1. Default-OFF flag now, enable after fixture + one real build? (Recommended.)
2. Which model tier for the reconciliation call — full (gpt-5.6-luna|high, matching T026) or a
   cheaper mini? (Recommend luna|high; it is a semantic judgment.)
3. Should `accidental_duplicate` ever DELETE an occurrence, or always keep + annotate? (Recommend
   keep + annotate; never auto-erase.)

--------------------------------------------------------------------------------
## Sequencing
#159 first (small, safe, resolves all current detector findings, unblocks Item B escalation), then
#160 (larger, gated, needs the fixture harness). Each: commit baseline, implement, validate on-disk
(real qwen + gemma/story-first control where a path is touched), commit. Nothing pushed without owner
direction. Branch-unification of the two reconcile branches remains a separate cleanup follow-up.
