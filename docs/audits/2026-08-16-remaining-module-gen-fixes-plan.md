# Remaining Module-Generation Fixes — Consolidated Plan (2026-08-16)

Covers everything left after Items 1 & 2: the newly-surfaced T088 lock-inversion blocker,
the Item 2 route detector, #3a/#3b/#7 from the original plan, and the queued sanitization pass.
Root causes below are code-confirmed in `.worktrees/main-merge`, not assumed. Doctrine unchanged:
code owns mechanical/structural fields; model owns creative content; no prose keyword-matching;
acceptance = real headless build judged on-disk; commit + validate ONE item before the next.

Baseline commits already landed (local, unpushed): `82ffda6a`/`4e1b82fe` (Item 1 encounters +
gen schema), `f0e8e4e1` (model eval), `76da367a`/`dbc93723` (luna|high T026 binding), `0f8afe90`
(Item 2 plot-ordered cross-area linking).

--------------------------------------------------------------------------------
## Item A (BLOCKER, do first) — T088 legacy reconcile lock inversion

**Symptom:** every legacy `build_module` aborts at Step 6.5 with
`ERROR: [NpcReconciler] Refusing target -> refresh lock inversion` then
`OSError: NPC identity reconciliation did not commit` (`module_builder.py:2001`).

**Root cause (confirmed):** `_reconcile_and_validate_context` has two branches:
- story-first (`expected_context is not None`, `module_builder.py:1948-1980`) acquires
  `module_refresh_lock()` -> `path_transaction_lock(context_path)`, then calls the
  **unlocked** `reconciler._reconcile_all_areas_unlocked()` (`npc_reconciler.py:868`,
  which asserts both locks are already held). CORRECT.
- legacy (`expected_context is None`, `module_builder.py:1982-2001`) acquires ONLY
  `path_transaction_lock(context_path)` (no refresh), then calls the **locked**
  `reconciler.reconcile_all_areas()` (`npc_reconciler.py:715`). That method's guard
  (`:731-738`) sees `path_transaction_lock_owned and not module_refresh_lock_owned`
  -> declares a lock-order inversion -> returns False -> build raises. BUG.

**Fix (Codex-agreed — MINIMAL legacy-branch patch, NOT a branch collapse in the blocker
slice):** wrap the legacy branch in `module_refresh_lock()` first, check acquisition, then
`path_transaction_lock(context_path)`, preserve `_recover_pending_transaction` -> publish ->
reconcile -> reload -> validate and the atomic/backup semantics, and call
`_reconcile_all_areas_unlocked()` (not the locked variant). Leave the already-validated
story-first branch untouched; branch **deduplication is deferred to Item C** once both branches
share one projection contract. Do NOT weaken the inversion guard (it is correct; the caller was
wrong).

**Regression note (Codex):** `_reconcile_all_areas_unlocked` performs T088 model work while the
outer refresh+context locks are held (story-first already does this) — correctness is sound but
local-model latency holds the global module-refresh lock longer.

**Validate:** real qwen legacy 3-area headless build runs to completion (context reconciled,
`_BU.json` backups created, `build_module returned OK`, `[ACCEPTANCE PASS]`). **Do NOT test only
the happy path** — also exercise (a) crash/interrupt recovery (a staged pending T088 is recovered
on the next build) and (b) a second concurrent module-refresh attempt while one build holds the
lock (must wait/refuse cleanly, no inversion, no corruption).

--------------------------------------------------------------------------------
## Item B — Item 2 route-agreement detector (hardening)

Item 2 fixed the root cause (plot-ordered linking). This adds the belt-and-suspenders
detector from the original plan so a future regression is caught, not silently shipped.

**Change (Codex-amended — area reachability ALONE is insufficient):** a bare reachability check
is useless because cross-area edges are bidirectional (the buggy OR<->SP link is "reachable"
either way and looks valid). The detector must instead:
- **B1 gateway endpoints:** derive the expected ordered transition PAIRS from T028 `plotPoints`,
  then assert the exact code-owned gateway endpoints Item 2 creates — source area's LAST location
  -> destination area's FIRST location, reciprocal at both endpoints. For hub/revisit, collapse
  adjacent duplicate areas but preserve the ordered transition set from **every `nextPoints`
  path**; do not flatten branches into one total order.
- **B2 coverage / fallback:** T028 validates that referenced areas are real but does NOT require
  every generated area to appear (`module_builder.py:261-335`); Item 2's fallback reintroduces an
  alphabetical chain when <2 distinct plot areas appear (`module_builder.py:2242-2255`). The
  detector must report **missing plot-area coverage** and an **unexplained alphabetical fallback**
  on a multi-area module. Whether a deliberately plot-free optional area is allowed must be
  encoded structurally, never inferred from prose.
- **B3 reciprocity (parallel arrays):** `areaConnectivity` and `areaConnectivityId` are parallel
  arrays and the existing local reciprocity check ignores them (`validate_module_files.py:583-675`).
  Assert: equal lengths, no duplicate target, target ID resolves in another area, matching
  destination area NAME at the same index, and the reciprocal endpoint carries the source ID/name.

Wire **report-only** first; escalate to fail-loud **only after** the endpoint/coverage/parallel-
array checks pass on real linear, hub, branch, revisit, AND dial-down builds (report-only is
temporary, not permanent).

**Validate:** deterministic fixtures (linear/backward/skip/hub/branch/revisit) are dev aids; the
real Item-A build passes the detector; a synthetic wrong-gateway and a backward fixture are both
flagged.

--------------------------------------------------------------------------------
## Item C (#3a) — module_context.json deterministic resync (legacy gap)

**Root cause:** story-first already rebuilds context from artifacts and hard-compares
(`expected_context_projection` + `validate_reconciled_context`, `compatibility.py`). The legacy
branch just publishes the in-memory context (`module_builder.py:1994`), so it can drift from the
final area/plot artifacts (Codex found stale cross-area connections, wrong area names, wrong plot
ownership; `validation_report.json` then falsely says "no issues").

**Change (Codex-corrected):**
- **C1 — my `references` source was WRONG.** The active `ModuleBuilder` does NOT write
  `[module]_module.json` (`module_generator.py:1059` states `*_module.json` is not used; the two
  audited candidates have none). So `from_artifacts` CANNOT read `mainPlot.plotStages.keyNPCs`
  from a file. Instead: derive ALL structural relationships from active `areas/*.json` +
  `module_plot.json`; carry existing `references` records forward ONLY when they resolve through
  the **reconciled canonical NPC map**; accept the builder's in-memory `module_data`/source
  context as **optional** build-time reference input. **Never call `ModuleContext.add_npc` while
  projecting** — its hard-coded/syntactic identity logic is unsuitable for projection.
- **C2 — shared projector must handle both ID contracts.** `expected_context_projection` currently
  assumes story-first plot locations are LOCATION IDs (`compatibility.py:214-279`). The shared
  projector must explicitly support classic **T028 area IDs** AND story-first **location IDs**,
  fail on ambiguous/unknown values, and its post-T088 validator must allow only the documented
  alias merge. It cannot call the current function unchanged.
- Legacy branch: replace the pre-reconciliation in-memory publish with the artifact projection;
  preserve NpcReconciler aliases (do NOT replace the post-reconcile `ModuleContext.load`).
  Order: pre-image projection -> reconcile (identity preserved) -> reload -> validate -> atomic
  publish. This is also where Item A's two branches unify onto one projection contract.

**Validate:** after a real build, `module_context.json` cross-area connections / area names /
plot ownership exactly match live artifacts; `validation_report.json` no longer falsely clean.

--------------------------------------------------------------------------------
## Item D (#3b) — coordinate ownership fail-loud (legacy gap)

**Root cause:** story-first code-owns coordinates and re-asserts equality fail-loud at three
stages (`TRUSTED_LOCATION_FIELDS`, `restore_repaired`, `restore_hardened`). The legacy path writes
T026 output straight to disk (`module_builder.py:1136`) with no coordinate re-check, so a model
coordinate hallucination (issue-#128 class; e.g. A04 at X2Y3 vs map X1Y2) ships.

**Change (Codex-corrected — seam placement was WRONG):** do NOT call
`validate_story_first_location_result` after the legacy area is written — it needs
outline/seed/blocklist and checks far more than coordinates, and once `generate_location_batch`
has RETURNED the T026 retry ladder is already over, so a late failure cannot route through it.
Instead:
- Extract a small shared **trusted-stub comparator** (coordinates + other code-owned stub fields
  vs the deterministic `MapLayoutGenerator.generate_layout` output).
- Invoke it INSIDE `LocationGenerator.generate_location_batch`, after ordered-ID/cardinality
  validation and BEFORE acceptance. Register coordinate drift as a **per-location semantic issue**
  so the existing targeted complete-location replacement gets its one bounded repair; repeat drift
  fails loud. Do NOT silently coerce (map-wins overwrite hides the root cause + risks
  shipped-module/save BC).
- The final pre-backup map/location equality assertion MAY remain as defense-in-depth, but it is
  NOT the retry seam.
- Optional: a read-only `validate_coordinate_ownership` report in `ModuleValidator` for auditing
  already-generated modules (never mutates).

**Validate:** a build with an injected coordinate hallucination triggers the bounded per-location
repair inside T026; repeat drift fails loud; final coordinates equal map rooms; existing shipped
modules are not mutated.

--------------------------------------------------------------------------------
## Item E (#7) — NPC cross-area role/attitude coherence (agentic)

**Root cause:** `NpcReconciler` reconciles NAMES only (`npc_reconciler.py:411-428`). Location NPC
entries are `{name, description, attitude}` — there is NO `role`/`faction` field, so inferring role
from free-text `description` would violate the no-prose-matching prohibition. Same-name NPCs with
conflicting roles across areas (e.g. Mother Marrow: neutral grove-tender vs hostile cult leader)
ship unreconciled.

**Change (agentic, the only compliant path):** the structured MODEL call is the semantic
authority; code validates targets/fields/identity-conservation/schema/atomicity only.
- After name reconciliation, group final appearances by canonical identity. **Codex caveat:**
  `duplicate_npc_placements` (`validators.py:1205-1223`) is exact casefold grouping only — use it
  to group AFTER an agentic identity decision, NOT as the identity classifier. Do NOT reuse
  `ModuleContext.add_npc`'s special case or T088's substring prefilter as the classifier.
- If a repeated cross-area identity exists, make ONE structured model call over the complete
  occurrence set that decides the fact code cannot derive (same mobile person / projection /
  deliberate attitude change / accidental duplicate) and returns a strict patch contract.
- Code applies fail-closed: only `npcs[].name/description/attitude` and location `dmInstructions`
  may change; no new IDs; identity set preserved; atomic via T088; one bounded correction then
  abort. Recurring antagonists/guides kept via a primary placement + explicit projection note.
- **`validate_npc_role_coherence()` is ADVISORY only (Codex):** role lives in prose, so it CANNOT
  be validated deterministically. It may report repeated canonical identities and exact attitude
  differences as coverage facts, but same attitudes can hide conflicting roles and different
  attitudes can be intentional — so it never gates; the model decision remains authority.

**Validate:** same-name NPCs with divergent attitudes get one coherent primary + explicit
continuity; no false positives on legitimately distinct same-name NPCs; no party member added.

--------------------------------------------------------------------------------
## Item F — Non-ASCII sanitization pass (queued issue)

**Root cause:** the blind eval showed several models emit non-ASCII smart quotes / em-dashes in
generated location content (stochastic; Windows cp1252 crash risk). Generation output is not
guaranteed ASCII-clean.

**Change (Codex-corrected):** `utils.encoding_utils.sanitize_text` is NOT an ASCII guarantee — it
leaves many code points above 159 after NFKD. Story-first already uses `normalize_ascii_typography`
(`compilers.py:173-195`) but that mapping omits the ellipsis and differs from encoding_utils for the
em dash. So: consolidate ONE canonical deep normalizer for known-lossless typography (curly quotes
-> straight, em/en-dash -> `--`/`-`, **add ellipsis -> `...`**), then **fail/retry on any remaining
non-ASCII** rather than silently deleting or mangling names (a silent strip could corrupt a proper
noun). Apply only at generation RESPONSE boundaries. Do NOT change prompts. Existing modules receive
a **read-only validator/advisory, not mutation**.

**Validate:** re-generate a batch with a model that previously emitted smart quotes; published area
files are pure ASCII (typography losslessly mapped, no mangled names); a deliberately non-mappable
non-ASCII char triggers retry, not silent deletion; no content meaning changed.

--------------------------------------------------------------------------------
## Sequencing (Codex-agreed order; one item, complete + validated, before the next)
1. **Item A** (blocker) — mandatory first; every later real-build validation depends on it.
2. **Item B** — route detector (after the B1/B2/B3 contract amendments; report-only first).
3. **Item D** (#3b coordinates) — next, so bad coordinates never enter later artifacts.
4. **Item C** (#3a context resync) — so Item E has a truthful context/transaction base; also
   unifies Item A's two reconcile branches onto the shared projection contract.
5. **Item E** (#7 NPC coherence).
6. **Item F** — sanitization, last.

Each item: commit baseline first, implement, validate via a **real qwen legacy build AND one gemma
control**, judged on-disk (deterministic fixtures are dev aids, NOT acceptance), commit, then
proceed. Nothing pushed without owner direction.

## Reused utilities (do not reinvent)
`_reconcile_all_areas_unlocked` / `reconcile_all_areas` / `duplicate_npc_placements` (npc_reconciler.py,
validators.py); `validate_story_first_location_result` / `TRUSTED_LOCATION_FIELDS` /
`validate_plot_route_agreement`(new) (story_first/validators.py); `expected_context_projection` /
`validate_reconciled_context` (story_first/compatibility.py); `ModuleContext` + `validate_all`
(utils/module_context.py); `MapLayoutGenerator.generate_layout` (area_generator.py); `encoding_utils`.

## Cross-validation status
Codex (gpt-5.6-sol) cross-validated this plan 2026-08-16. **Item A root cause CONFIRMED exactly.**
All amendments above (B1/B2/B3, C1/C2, D seam placement, E advisory-only, F canonical normalizer)
are folded in and agreed by both. Claude and Codex agree on direction and the A,B,D,C,E,F order.
No files were changed during the review.

## Resolved decisions (Codex-agreed)
1. Item A: **minimal legacy-branch patch now**; unify the two branches in Item C once the shared
   projection contract exists (not a collapse in the blocker slice).
2. Item B detector: **report-only is temporary**; escalate to fail-loud only after the
   endpoint/coverage/parallel-array checks pass real linear/hub/branch/revisit/dial-down builds.
3. Item F: **generation-only**; no automatic migration of existing modules (read-only advisory).
