# Merged Plan — Issues #159 and #160 (Claude + Codex, 2026-08-16)

> **Superseded operational setting (2026-08-16):** This historical design plan
> proposed T104 default-off during initial risk containment. The reviewed tip
> subsequently shipped `ENABLE_NPC_COHERENCE_REPAIR = True`. The OpenAI
> optimization preserves that enabled state and validates T104 in a complete
> classic build; see `2026-08-16-openai-callsite-optimization-summary.md`.

Merge of two independent plans:
- Claude: `docs/audits/2026-08-16-issues-159-160-plan-claude.md`
- Codex (gpt-5.6-sol): `docs/audits/2026-08-16-issues-159-160-plan-codex.md`

**Codex's plan is the more detailed and correct backbone; Claude concurs and adopts it, adding one
distinct point (the prompt-freeze tension on 159-B) and confirming the shared root-cause analysis.**
Both agree on: #159 is legacy-only (story-first already code-owns these fields), the fix is
restore-from-trusted-stub at the shared canonicalizer, and #160 is a new semantic authority that must
be classic-only + default-off + validated on a real conflict. Doctrine unchanged: code owns
structural fields; the model owns creative content; no prose keyword-matching; acceptance = real
headless play judged on-disk; commit + validate one slice before the next; nothing pushed without
owner direction.

Where the two plans differed, Codex's was more complete and is adopted:
- Codex added **159-B** (fix the misleading prompt/schema semantics) and **159-C** (finalizer
  clear-then-rebuild-from-clean, idempotent) — Claude's draft only had 159-A.
- Codex added the **#160 staged-snapshot integration** (run inside T088's durable transaction on
  in-memory staged payloads, not disk) and **classic-only v1** scoping — stronger than Claude's
  "run after reconcile" and fixture-only validation.
Claude adds: the **prompt-freeze consideration** on 159-B, and confirms A+C alone fully fix #159
(making B optional).

================================================================================
## Issue #159 — model-authored areaConnectivity/areaConnectivityId pollution

### Root cause (both agree, code-confirmed)
`areaConnectivity`/`areaConnectivityId` are code-owned cross-area fields. Story-first already owns
them (`compile_area_binding` writes them into the stub, `compilers.py:325-347`;
`TRUSTED_LOCATION_FIELDS` restores from stub, `validators.py:844-853, 1095-1111`). **Legacy is
polluted** because (1) the T026 prompt/schema tell the model to author them and mislabel
`areaConnectivityId` as "area IDs" (`location_generator.py` LocationPromptGuide + checklist
"AREA CONNECTIVITY RULES"), (2) `_canonicalize_t026_stub_owned_fields` restores locationId/dangerLevel/
coordinates but NOT these two arrays, and (3) `finalize_locations_and_connections` **appends**
code-owned links without first clearing model-authored ones — so both survive (e.g.
`WB001:A03 -> areaConnectivityId ['WW001','B01']`, `WW001` an area ID in a location-ID slot). At
runtime `areaConnectivityId` resolves as a destination location, so this can misroute transitions.

### Fix — three cooperating slices (Codex's structure, adopted)

**159-A — trusted stub authoritative at the T026 boundary** (`location_generator.py`)
In `_canonicalize_t026_stub_owned_fields`, after the ordered-ID preflight succeeds, deep-copy
`areaConnectivity` and `areaConnectivityId` from the trusted stub into every returned location on
every attempt (same pattern as the Item D coordinate restore). Legacy stubs have empty arrays ->
cleared; story-first stubs carry the compiled links -> preserved exactly (order + multiplicity). Add
a small stub validator (both fields are equal-length string lists, no blanks; do not infer/repair
pairings). Keep the existing behavior: a present-but-conflicting ID or suspect order returns the
untouched model response (positional ownership is only safe after identity/order is proven). One
bounded advisory count when values differed; never log model prose.

**159-B — correct the prompt + schema semantics** (`location_generator.py`,
`schemas/loca_generation_schema.json`, `loca_schema.json` descriptions only)
Replace the LocationPromptGuide guidance + checklist "supply other area IDs" with: both cross-area
arrays are code-owned; copy the exact stub values; never add/remove/rename/reorder/reinterpret; and
`areaConnectivityId` holds destination LOCATION IDs. Correct the schema descriptions (shapes/required
unchanged; retain both fields in the strict generation schema).
- **CLAUDE FLAG (owner decision):** CLAUDE.md freezes prompts (gpt-4.1-tuned). This instruction is
  *factually wrong* (it causes the pollution), so fixing it is a correctness improvement, not
  quality-tuning — but it is still a prompt change. **159-A + 159-C fully eliminate the pollution
  regardless of the prompt** (code overwrites/clears model output), so **159-B is OPTIONAL
  prompt-hygiene** (reduces wasted model effort + confusion). Recommend doing it, but it needs owner
  sign-off under the freeze; ship A+C first so correctness does not depend on it.

**159-C — finalizer rebuilds classic links from clean staged arrays** (`module_builder.py`)
Make `finalize_locations_and_connections` the sole author: deep-copy area payloads, CLEAR both
cross-area arrays on every staged classic location exactly once, derive the complete ordered
transition set from final T028 (`_plot_ordered_area_transitions`, preserving branch/hub/revisit),
add every expected bidirectional gateway (last-source-location -> first-destination-location),
accumulate all links, then VALIDATE before any write: equal-length parallel arrays; unique pairs;
each target resolves to exactly one location in another area; paired name == target area name; exact
reciprocal pair at the expected endpoint; link set == plot-derived set (no model extras); local
`connectivity` unchanged. Abort the candidate on any invariant failure (no guessed endpoint, no
partial graph). This also makes finalize idempotent against interrupted/resumed candidates.

### Validation (real, on-disk — Codex's battery, adopted)
1. Pin the local Qwen model ID from `/v1/models`. 2. Real isolated T026 with empty classic stubs ->
accepted arrays empty regardless of raw authorship. 3. Real T026 with story-first stubs carrying two
compiled links -> preserved exactly in order. 4. Full 3-area classic Qwen build -> prove all 159-C
invariants from disk; the Step 4.56 route detector reports **0** parallel/reciprocity findings
(currently 7, all this bug). 5. Real story-first hub/branch build -> compiled links survive unchanged,
no hub edge removed. 6. Headless play (`core/headless/client.py`) crossing every boundary both ways +
revisit, judged from `party_tracker.json`/area files. 7. Gemma classic control. 8. Bounded iteration
(<=3 contract revisions; a twice-repeating failure means trace the contract, not add patches).

### Open questions (#159)
1. Multi-area classic module whose final plot names <2 areas: no implicit alphabetical chain; require
   an explicit structural designation for optional plot-free areas, else fail for correction.
2. Promote the pollution-specific route invariants (parallel-array/resolution/reciprocal/exact-link)
   to fail-loud only after real linear/hub/branch/revisit builds pass; keep broader route findings
   report-only.
3. No auto-migration of existing modules (read-only diagnostic only).
4. **159-B prompt change under the freeze — do it now, or ship A+C only and defer B?** (Claude flag.)

================================================================================
## Issue #160 — agentic NPC cross-area role/attitude reconciliation

The Step 4.57 advisory shipped (`feac15b3`). This is the agentic decision half.

### Version-1 scope (Codex, adopted)
Classic/legacy builder ONLY; behind `ENABLE_NPC_COHERENCE_REPAIR = False` (default off); ONE
structured model call over ALL repeated canonical identities in the candidate; one correction attempt
max; applied to T088's in-memory staged snapshot and committed in the SAME durable transaction;
fail-closed when enabled (invalid/unresolved -> no writes, abort candidate); no call + no changes when
there are no repeated canonical identities. **Story-first stays on T101 in v1** (adding a second
post-publication authority would compete with ownership and invalidate its expected-context snapshot).

### Slices (Codex, adopted)
- **160-A** (`core/generators/npc_coherence.py` new; `model_config.py`; `config_template.py`;
  `story_first/execution.py`): build ONE occurrence packet after T088 canonicalizes identities in
  memory, grouping exact-casefold canonical identities across staged areas (never `add_npc`, never
  substring/keyword). Per occurrence: opaque code-generated occurrence ID, canonical name, area/loc
  IDs+names, exact `{name,description,attitude}`, location `dmInstructions`, associated plot data,
  party-name exclusion set. Module prose framed as untrusted evidence. New task ID (confirm registry;
  T111 likely next-free) routed through `capture_and_fanout`/structured execution (provider-native
  schema). Strict response contract (all keys required):
  ```json
  {"decisions":[{"canonicalName":"<enum>","classification":"same_mobile_person|projection_or_manifestation|deliberate_attitude_change|accidental_duplicate|distinct_people_same_label","primaryOccurrenceId":"<enum>","continuityReason":"...","repairs":[{"occurrenceId":"<enum>","keepInRoster":true,"name":"...","description":"...","attitude":"...","dmInstructions":"..."}]}]}
  ```
  Exactly one decision per group; one repair per occurrence; primary belongs to the group; no omitted
  keys; no raw response persisted in production telemetry.
- **160-B** (`npc_coherence.py` + existing schema validators): apply only to deep-copied staged
  payloads; code proves target/occurrence/primary/location IDs exact + complete; ONLY roster presence
  + the targeted NPC's `name/description/attitude` + that location's `dmInstructions` may change;
  every original canonical identity keeps >=1 static roster occurrence (none deleted/invented); party
  names never added; changed areas still pass runtime schemas; classification-specific structural
  rules (e.g. `accidental_duplicate` can't keep several unexplained static entries;
  `distinct_people_same_label` can't merge); re-running the advisory reports the resolved/permitted
  state. Per-classification v1 handling: mobile/projection/attitude-change -> one physical primary +
  location `dmInstructions` for the rest; accidental_duplicate -> keep primary, remove others,
  preserve unique prose as guidance; distinct_people_same_label -> no mutation + advisory.
- **160-C** (`utils/npc_reconciler.py`, `utils/module_context.py`, `module_builder.py`): extend
  `_stage_reconciliation_from_snapshot` ordering (identity reconcile -> canonical-name staging ->
  build groups -> optional one T111 call -> validate/apply patch to staged copies -> build context
  from staged copies). Never call the model holding only the context lock (keep refresh->context
  order + source revalidation). **Generalize `ModuleContext.from_artifacts` to consume STAGED
  payloads** (reading disk would rebuild from unpatched images). Commit every changed area +
  `module_context.json` in the SAME T088 durable transaction (reuse pending record, revalidation,
  commit verify, rollback, recovery). Any failure -> restore in-memory context, write nothing, retain
  last accepted disk state. Move/repeat Step 4.57 after accepted staging for final telemetry.
- **160-D** (`module_builder.py`, `config_template.py`): pass final classic plot/context into the
  staged coherence phase only when the flag is explicitly true; enabled-unresolved = candidate
  failure (not warn+publish); explicitly skip story-first in v1; leave T101 unchanged.

### Validation (real, predeclared — Codex, adopted)
Declare the protocol before any call; never retry until a convenient output appears. Three real
natural concepts (one travel, one projection, one relationship change), each requesting a recurring
named NPC across three areas. Run flag-OFF first; if no candidate produces a repeated canonical
identity on disk, report the live trigger BLOCKED (do not manufacture a conflict). For a real
conflicting candidate: rerun flag-ON with a real T111 call; inspect all area files +
`module_context.json` before/after; prove only permitted paths changed, identity conserved, context ==
final areas, no pending T088 transaction left. Plus: a real no-conflict flag-ON run (0 T111 calls, no
diffs); an externally-induced provider failure (no writes, clean abort/recovery, truthful message, no
monkeypatch); one bounded correction max then fail-closed; headless play interacting with the NPC in
natural language across areas + save/resume, judged on-disk; a story-first Qwen control (new phase
makes no call, T101/publication unchanged); a Gemma classic control. Record call/attempt count,
classification, latency, allowed on-disk diffs. Not shippable until a genuine conflict reaches the new
phase in a real build.

### Open questions (#160)
1. v1 path scope: classic only (story-first unified later at T101, before expected-context). 2.
Projection/mobile NPC: one physical primary + instructions in v1 (multiple active static copies need
runtime semantics first). 3. distinct_people_same_label: preserve + advise (auto-rename invents
identity). 4. Model tier: the module's main semantic model (gpt-5.6-luna|high) initially, reduce after
measured runs. 5. Enabled-unresolved: abort candidate after one correction; default-off protects
production until the real battery passes.

================================================================================
## Delivery order (merged)
1. **159-A + 159-B** together (shared ownership boundary + truthful prompt/schema — B pending the
   owner freeze decision; A can ship alone if B is deferred).
2. **159-C**, then the full #159 classic/story-first/headless battery before promoting any route
   invariant to fail-loud.
3. **160-A + 160-B** as pure staged transforms + strict contracts.
4. **160-C** on T088's existing snapshot/lock-order/durable-transaction/recovery/final-context.
5. **160-D** default-off classic wiring.
6. The predeclared real conflict battery; keep the feature OFF unless genuine-conflict, no-conflict,
   provider-failure, story-first-regression, save/resume, and on-disk atomicity ALL pass.

#159 and #160 stay separate commits + review gates. #159 is a deterministic ownership defect
(promote after real path validation). #160 adds a new semantic authority and must not be enabled just
because its schema/fixtures pass. Branch-unification of the two reconcile branches remains a separate
cleanup follow-up. Nothing pushed without owner direction.

## Agreement attestation
Claude and Codex independently traced current `main-merge` (post A-F) and agree on the root causes,
the fix seams, the cross-path safety analysis, and the sequencing above. The only additions in this
merge over Codex's draft are Claude's 159-B prompt-freeze flag and the note that 159-A+C fully fix
#159 independent of the prompt.

================================================================================
## VALIDATION FINDINGS & REQUIRED AMENDMENTS (2026-08-16)

Both sides ran independent agents against `.worktrees/main-merge` (post A-F): Claude dispatched 4
feature-dev agents (#159 architecture, #160 architecture, code-reference accuracy, runtime/gameplay
tracing); Codex ran 3 (#159, T088, gameplay/save). **Combined verdict: the core ownership strategy is
CONFIRMED sound, but the plan is NOT 100% implementable as written — it must be revised for the
BLOCKERS below before any code is touched.** Code references were otherwise unusually accurate.

### Confirmed sound (both sides)
- 159-A (restore areaConnectivity/areaConnectivityId from the trusted stub) is safe for BOTH paths,
  gated by the existing identity preflight (`location_generator.py:110-131`); classic stays empty,
  story-first keeps its compiled links. Root cause verified: prompt + schema mislabel
  areaConnectivityId as "area IDs".
- Classic-only + default-off for #160; T088 durable-transaction reuse; save/reset ordering.
- **Gameplay safety (stronger than the plan stated):** T088/#160 has NO live-play caller (runs only
  at build time, before any save exists). `dmInstructions` is pure prose (`main.py:1738`);
  `npcs[].description/attitude` are already mutated live during play (`action_handler.py:3567,3571`);
  `keyNPCs` has no runtime reader; no encounter/character-file/save structural coupling.
- **#159 is a RISK REDUCTION, not cosmetic:** the live movement authority is `pre_validate_transition`
  -> `path_encounter_analyzer.build_active_module_snapshot`; a polluted entry that fails the area-id
  fallback makes `is_valid=not issues` false, and `find_path_in_snapshot` then refuses to route
  ANYTHING (`path_encounter_analyzer.py:516,542-544`) — i.e. whole-module travel outage. The fix
  always lands in the trusted location-id branch.

### #159 — REQUIRED AMENDMENTS
- **[BLOCKER] Shared nextPoints-aware route extractor.** `_plot_ordered_area_transitions`
  (`module_builder.py:2283-2304`) walks adjacent plotPoints ONLY and ignores `nextPoints`; the
  report-only detector separately adds nextPoints edges (`validators.py:1504-1532`). 159-C must NOT
  reuse the current helper — introduce ONE shared expected-edge extractor (nextPoints authoritative +
  a deliberate legacy fallback) used by BOTH finalizer and detector, or finalize will miss branch
  edges the detector then flags.
- **[BLOCKER] No cross-file graph atomicity.** Per-area `_atomic_save_json`
  (`module_builder.py:2347-2351`) is not multi-file atomic; a crash leaves half a reciprocal graph.
  Narrow the claim to deterministic rerun inside the unpublished managed candidate (its lifecycle
  aborts/hides candidates), OR add a durable multi-file journal. Do NOT claim cross-file atomicity.
- **[CHANGE] Third stale schema.** Add `schemas/locationfile_schema_strict.json:100-108` to 159-B
  (same mislabel, used by the full-module validator).
- **[CHANGE] Non-T026 write path.** `module_stitcher.py` (~1497-1498, 4046, 4342) also writes
  areaConnectivity when stitching added areas — 159-A's T026-boundary fix does not cover it; 159-C's
  finalizer-owns-clean model or an explicit note must address it.
- **[CHANGE] Prompt-freeze attribution.** The current worktree `CLAUDE.md` has no prompt-freeze rule
  (it is in the model-refactor root context). 159-B still likely needs owner approval, but do not
  attribute the freeze to the current file. 159-A alone already blanks the classic T026 array, so
  159-B remains optional for correctness.
- **[CHANGE] Wording.** TRUSTED_LOCATION_FIELDS *validates exact equality and raises*
  (`validators.py:1095-1111`), it does not "restore." And "always misroutes" is too absolute — a
  legacy area-id fallback exists (see risk-reduction note above).
- **[OWNER CONTRACT] Plot-free areas.** No optional-plot-free-area designation exists; the current
  fallback is alphabetical (`module_builder.py:2292-2293,2323-2332`). Lock that structural contract
  before exact-set gating, else the implementation must guess whether an uncovered area is intentional.
- "Currently 7 findings" is UNVERIFIED by static read (plausible; re-run against a real polluted build).

### #160 — REQUIRED AMENDMENTS
- **[GAMEPLAY BLOCKER] Secondary-roster deletion breaks cross-area interaction.** Runtime presence
  comes from `location.npcs` (`main.py:1021-1051`); interactions may use only PRESENT NPCs, an NPC
  cannot be in multiple locations, and background movement is same-area only
  (`action_handler.py:3293-3303,3491-3499,3580-3600`). `dmInstructions` does NOT make an NPC
  mechanically present. So "one physical primary + dmInstructions at secondaries" makes a legitimately
  recurring NPC mechanically ABSENT elsewhere. For `same_mobile_person` / `projection_or_manifestation`
  / `deliberate_attitude_change`, v1 must RETAIN the cross-area roster occurrences and HARMONIZE their
  fields (or narrow v1 to primary-location interaction only). **Secondary deletion is safe ONLY for
  `accidental_duplicate`.**
- **[BLOCKER] Staged NPC membership projector.** `ModuleContext.from_artifacts` copies npcs/references
  VERBATIM (`module_context.py:310-332`); a roster patch would leave `npcs[*].appears_in`,
  `areas[*].npcs`, `locations[*].npcs` STALE. Add a staged projector that preserves canonical
  identity/aliases but clears+reconstructs all three membership projections from the patched staged
  rosters via the existing canonical map; reject unmatched labels; never call `add_npc` (regex/special
  -case identity, `module_context.py:67-105`). Always stage context when #160 changes an area (staging
  is currently conditional, `npc_reconciler.py:516-521`).
- **[BLOCKER] Complete immutable T111 read set.** The packet uses plot + party facts, but T088
  snapshots/revalidates only context + areas (`npc_reconciler.py:430-505`). Add `module_plot.json` and
  `party_tracker.json` as read-only snapshot members (path/digest revalidation, no transaction writes),
  or remove those facts. Passing live builder values breaks the immutable T088 contract.
- **[CHANGE] Canonical-name freeze.** T111 must NOT rename NPCs (arbitrary renames orphan
  filename/name-keyed character sheets, codex/party refs, plot prose). Make the response `name` an
  exact const == the post-T088 canonical name, or remove it. #160 owns roster presence, description,
  attitude, dmInstructions ONLY.
- **[CHANGE] Retry-loop call cap.** The outer `_T088_SOURCE_RETRY_LIMIT` loop re-invokes staging up to
  3x on source drift, so "one T111 call" needs an explicit cap on TOTAL invocations across attempts.
  Also pull a first-touched area's "before" image from the pristine snapshot, not a name-staged copy.
- **[CHANGE] Lock duration.** The classic builder HOLDS the global refresh+context locks while
  `_reconcile_all_areas_unlocked` does model work (`module_builder.py:2043-2077`); a main-model T111
  call could block reset/other module work for minutes. Prefer the optimistic snapshot/release/
  revalidate path, or explicitly accept + test the global hold.
- **[CHANGE] Task ID = T104, not T111.** Registrations end at T103 (`story_first/execution.py:19-24`);
  T104-T110 do not exist in this worktree. `register_callsite` has NO uniqueness check (silent
  overwrite), so re-confirm at implementation time and use T104. It is one callsite but up to TWO
  provider requests (one correction). T111/T104 needs its OWN named provider configs — DM_MAIN is
  gpt-5.2; luna|high is T026-specific — do not describe it as "the module-main model."
- **[CHANGE] Step 4.57 final telemetry** can't read `self.areas_data` after T088 (builder reloads only
  `self.context`, `module_builder.py:2079-2083`) — report from the committed payloads.
- **[WORDING] "any failure writes nothing"** is too strong (post-marker recovery may converge to the
  AFTER state); StageEvidence non-persistence is not absolute under multi-model capture. Say "no
  partial state is accepted," and have T111 redact capture if enabled.
- **[NONBLOCKING] MODULE_SUMMARY** is built before T088 (`module_builder.py:585-602`) so #160 edits
  make it stale — regenerate after accepted T088, or document as cosmetic.

### Net
Ship-order unchanged (#159 first, then #160), but **both issues need the plan revised per the BLOCKERS
above before implementation.** #159's revisions are contained (shared extractor, honest crash
semantics, third schema, stitcher note). #160's revisions are more substantial and center on the
gameplay contradiction (retain cross-area occurrences) + the staged membership projector + immutable
read set + name freeze. Claude and Codex agree on all of the above.
