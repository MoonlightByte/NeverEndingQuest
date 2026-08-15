# Module Generation Coherence Fix Plan

Date: 2026-08-15  
Status: implementation plan only; no product code changed  
Basis: `docs/audits/2026-08-15-module-generation-failure-analysis.md`

## 1. Goal and boundaries

This plan fixes four demonstrated generation defects without taking story design away from the
model:

1. T026 must never author fresh-location encounters or invented dates.
2. The physical route must contain a canonical path that follows accepted plot order.
3. Location coordinates and `module_context.json` must be rebuilt from final authoritative
   artifacts, not stale intermediate state.
4. Repeated NPCs must have coherent identity, role, and attitude continuity across areas.

The model remains responsible for names, descriptions, plot, locations, NPC characterization,
and dramatic choices. Code owns schemas, identifiers, maps, coordinates, graph invariants,
fresh-state fields, artifact projections, atomic writes, and bounded failure behavior.

The two audited Qwen/Gemma candidates are legacy/dial-down publications, not successful
story-first publications. Accordingly, every applicable fix below has an explicit legacy path.
Story-first already has stronger context projection and trusted-field checks; fixing that path
alone would not fix the reproduced failures.

Explicit non-goals:

- Do not change `schemas/loca_schema.json` or the runtime T015/encounter contract.
- Do not generate encounter history during module creation.
- Do not treat lazy monster descriptors as missing stat cards; runtime monster generation is an
  intentional design.
- Do not change the classic T028 contract: classic `plotPoints[].location` contains an area ID.
  Story-first plot points continue to contain location IDs.
- Do not solve the deferred lock/key, quest-prop, or prose-quality findings in this change.
- Do not remove optional map links merely because they permit exploration or shortcuts. The new
  route invariant concerns the canonical required-story route.

## 2. Delivery order and common acceptance gates

Implement in this order:

1. Generation-only location schema and T026 prompt.
2. Code-owned coordinates and final map/location consistency check.
3. Deterministic route-order check and bounded repair.
4. Deterministic final `module_context.json` projection.
5. Agentic NPC continuity reconciliation with code-owned patch validation.
6. Qwen iterative battery, Gemma control builds, and real headless play.

Every slice must preserve these gates:

- The runtime location schema remains byte-for-byte unchanged.
- A freshly built location always ends with `encounters: []`, `adventureSummary: ""`, and
  `explorationState.status: "unvisited"`.
- All trusted IDs, local edges, cross-area edges, and maps remain reciprocal and resolvable.
- No repair loop is unbounded. A failed bounded correction ends the candidate honestly; it does
  not silently publish stale or contradictory artifacts.
- Acceptance comes from real generated modules loaded and played through headless mode and from
  their on-disk files. Pure-function graph/projection checks are development aids, not ship proof.

## 3. Item 1 - generation-only location schema and T026 prompt

### 3.1 Files

- Add `schemas/loca_generation_schema.json`.
- Change `core/generators/location_generator.py`:
  `LocationGenerator.load_schema` (currently lines 1006-1009),
  `LocationPromptGuide.encounters` (829-853), the T026 complete-location checklist
  (1133-1173), `_t026_request_options` (414-452), and the first/retry/replacement
  validation seams in `generate_location_batch` (1263-1268, 1327-1371, 1488-1498).
- Change `core/generators/story_first/pipeline.py`: schema loading and the schema pair passed to
  `location_fill` (the current call is around 730-750).
- Change `core/generators/story_first/stages/location_fill.py`: its `run` contract and validations
  (69-173).
- Add focused schema-contract tests under `tests/` and include the new schema in any schema
  packaging/distribution manifest that enumerates files.

### 3.2 Contract

`loca_generation_schema.json` is the T026 output schema. It mirrors the full runtime location
shape except for fresh-state fields:

- Keep `encounters` present and required, but constrain it to an empty array (`type: array`,
  `maxItems: 0`). Keeping the field makes the accepted T026 result immediately compatible with
  downstream `locationfile_schema_strict.json` consumers and avoids a second shape.
- Keep `adventureSummary` required and constrain it to the empty string.
- Keep `explorationState` at its one fresh value, `{"status": "unvisited"}`.
- The generation schema contains no encounter item schema and therefore no `worldConditions`,
  year, month, day, or time for the model to fill.
- Preserve every other property, requirement, enum, and nesting rule from
  `loca_schema.json`. Add a drift test which compares the two schemas after excluding only the
  three intentional fresh-state differences.

Use the generation schema for all T026 model-facing operations: initial structured response,
full retry, targeted complete-location repair, and T025 field repair. Validate the canonicalized
accepted result once more with the unchanged runtime `loca_schema.json` before publishing it.
This requires `LocationGenerator` to hold two explicit schemas, for example
`generation_schema` and `runtime_schema`, instead of overloading `self.schema`.

Story-first currently passes the runtime schema to `location_fill`, which validates every area
again. Pass both schemas explicitly:

- generation schema for the model response boundary;
- runtime schema for the completed accepted location file and area wrapper.

The classic builder obtains the same behavior from `LocationGenerator`; it needs no separate
schema fork.

### 3.3 Prompt changes

Replace `LocationPromptGuide.encounters` and the encounter portion of the T026 checklist with a
short, unambiguous rule:

> This is an unplayed location. Return `encounters` as `[]`. Do not invent encounter history,
> dates, times, years, months, or days. Put possible future scenes in `dmInstructions`,
> `plotHooks`, `monsters`, or other authored guidance.

Keep the existing story-first `context_header` fresh-state instruction. Remove the example dated
encounter entirely so weak models do not imitate data that will be discarded.

### 3.4 Safety net and telemetry

Retain `_canonicalize_t026_mechanical_fields` (178-236) as a final code-owned safety net. It must
continue to force the three fresh-state values on every T026 path, including legacy/non-strict
providers. Remove the now-dead encounter-ID/month-normalization loop after the empty-array
assignment, but only after tests show there is no alternate runtime caller.

Record structured generation metrics, without logging prompt content:

- whether a provider returned a non-empty encounter array before canonicalization;
- whether any fresh-state field was missing or corrected;
- full retry, surgical repair, and floor counts.

These are diagnostics, not additional retries.

### 3.5 Edge cases

- A provider ignores `maxItems: 0`: strip to `[]`, count the correction, and continue if the
  rest of the result is valid.
- A provider omits `encounters`: the canonicalizer inserts it before runtime validation.
- A provider/API rejects the generation schema dialect: use the existing provider-specific
  schema adaptation, not a looser runtime schema. Fail after the existing bounded call ladder.
- Legacy saved modules with real encounter history are unaffected because only module generation
  uses the new schema.
- T015 and combat continue validating/appending runtime encounters through
  `schemas/loca_schema.json`.

## 4. Item 2 - plot order versus physical route

### 4.1 Files and insertion points

- Add a shared deterministic utility, preferably
  `core/generators/module_route_integrity.py`.
- Change `core/generators/story_first/validators.py` to expose route findings alongside
  `validate_compiled_world` (753-841) and `semantic_plot_checks` (1245 onward).
- Change `core/generators/story_first/pipeline.py`:
  run the route gate after `area_binding` has compiled maps/locations and before T026; repeat the
  read-only assertion during final candidate hardening.
- Change `core/generators/story_first/compilers.py` only if a unique repaired cross-area link must
  be recompiled from `crossAreaLinks` (325-347).
- Change `core/generators/module_builder.py`: run the classic adapter after per-area plots and the
  T028 unified plot exists. Specifically, replace the current pre-plot alphabetical finalization at
  `build_module` 503-505 and `finalize_locations_and_connections` 2174-2197 with plot-ordered
  finalization after `unify_plots` (511-513), before plot-hook updates, party tracker, context, and
  backups.
- Add route metrics to the existing story-first evidence/manifest and classic build log.

### 4.2 Canonical graph and ordered anchors

Build one undirected location graph from:

- local `connectivity` edges;
- cross-area `areaConnectivityId` edges;
- the location-to-area index.

Validate reciprocity and resolvability first. Then adapt the two plot contracts separately:

- **Story-first:** accepted outline prerequisite order plus `beat_locations` is authoritative.
  `compile_plot_skeleton` already maps each beat to a location (compilers.py:356-405).
- **Classic:** final T028 gives ordered area IDs by first appearance, while the already-generated
  per-area plots in `self.plots_data` supply location anchors inside each area. Do not reinterpret
  T028 area IDs as location IDs.

The reproduced classic cause is concrete: `finalize_locations_and_connections` sorts area IDs
alphabetically (2180), then `_create_bidirectional_connection` links each sorted area's last location
to the next sorted area's first (2129-2172), before T028 plot order exists. Gemma consequently linked
OR to SP while its plot starts SP then OR; Qwen linked HWG to IPA to STS while its plot starts IPA,
then HWG, then STS. The new classic adapter derives ordered unique area blocks from final T028 and
rejects a non-contiguous repeat such as A-B-A unless the accepted plot explicitly encodes a revisit.

From those facts, derive a canonical sequence of required waypoints. Validate that at least one
simple path can visit them in accepted order without entering a future required area before its
first anchor or requiring a completed area to be re-entered. Repeated locations/areas explicitly
present in the accepted story are valid revisits; accidental backtracking is not.

This is not a directed-door rule: physical edges remain bidirectional. "Forward" means the chosen
canonical story path respects ordered waypoints. Optional branches and shortcuts can remain as long
as a valid canonical required path exists.

### 4.3 Bounded repair

Repair only a uniquely inferable bad cross-area gateway:

1. Determine the last required anchor in the current area and the first required anchor in the next
   area.
2. If those locations are unique and the only defect is the cross-area endpoint, replace the
   reciprocal gateway pair with that pair.
3. Update both `areaConnectivityId` arrays and their parallel `areaConnectivity` names atomically.
4. Re-run graph, reciprocity, map, and ordered-route validation.

For the legacy path, remove only the cross-area pairs previously created by the code-owned
finalization step, then recreate consecutive plot-area pairs using the source area's final local
plot anchor (falling back to its last generated location only when no per-area anchor exists) and the
destination area's first local plot anchor (same bounded fallback). Do not preserve an alphabetic
skip pair. Save both endpoint areas and update `self.locations_data` in the same operation, then run
the final route assertion. Do not touch model-authored local room edges.

For story-first, when the correct consecutive area pair exists but its endpoints are wrong, retarget
the compiled link to the source area's last required beat anchor and destination's first required
beat anchor while preserving its `narrativeReason`. A wrong or missing area pair is a semantic T099
failure and goes through `area_binding.py:75-103` under the existing maximum of three attempts
(`settings.py:19-28`); code does not invent narrative intent.

Do not change local room edges, plot order, beat ownership, or prose. If anchors are ambiguous,
the plot explicitly branches without a unique order, or repair would erase a meaningful required
link, emit a structured route finding:

- Story-first feeds the finding into the existing bounded `area_binding` semantic gate, then
  recompiles the world.
- Classic fails the candidate with exact area/location evidence rather than guessing. A later
  enhancement may add a bounded classic area-binding correction, but this plan does not add a new
  creative callsite merely to conceal an ambiguous map.

The final assertion is mandatory even when a repair reports success.

### 4.4 Edge cases

- Single-area modules pass without cross-area checks.
- Several beats at one location collapse into one waypoint.
- Parallel plot branches are checked per prerequisite path, not forced into an arbitrary total
  order.
- Explicit revisits remain valid when represented in accepted beat dependencies/T028 order.
- Multiple equally valid gateways are not silently rewritten.
- Disconnected graphs, dangling IDs, one-way edges, or a required skip fail before repair.
- Optional links remain valid only when they do not bypass a required prerequisite. A shortcut that
  makes a future required area reachable before its prerequisite is a blocker unless the accepted
  plot explicitly permits that branch.

## 5. Item 3 - coordinate ownership and deterministic context resync

### 5.1 Code-owned coordinates

#### Files and reused seams

- Change `core/generators/location_generator.py` at
  `_canonicalize_t026_stub_owned_fields` (91-163) and `_T026_STRUCTURAL_STUB_FIELDS` (931-934).
- Reuse `core/generators/area_generator.py:280-364` (`MapLayoutGenerator.generate_layout`) and
  the map-to-stub projection at 594-642 as the classic authority.
- Reuse `core/generators/story_first/compilers.py:239-353` (`compile_area_binding`) and
  `core/generators/story_first/validators.py:753-841` (`validate_compiled_world`) as the
  story-first authority.
- Add a shared final verifier, preferably `utils/module_map_projection.py`, used by both builders
  before context projection and backups.

#### Change

After T026 proves output cardinality and ordered location IDs, overlay all code-owned structural
fields from the matching trusted stub. In particular, coordinates are always copied from the stub;
a model-authored but schema-valid alternative must not survive. Preserve model authorship only for
creative fields. The current helper restores omitted IDs and danger only and therefore cannot stop
Qwen's valid-looking `X2Y3` drift.

The shared final verifier indexes every area map by room ID and:

1. derives each coordinate from the map layout cell;
2. confirms the map room coordinate agrees with that cell;
3. writes that coordinate into the corresponding final location;
4. confirms room sets and internal connections agree between map and area;
5. fails on duplicate/missing IDs or a room that appears twice in the layout.

Story-first already performs most checks in `validate_compiled_world`; extract/reuse those checks
rather than creating a second interpretation. The final pass is still required because T026 and
later repair stages run after compilation. Coordinates remain in the published format for tools and
compatibility even though the gameplay runtime does not consume them.

#### Edge cases

- Non-rectangular or duplicate-cell maps fail; code does not guess a coordinate.
- A location absent from a map, or a map room absent from its area, fails the candidate.
- Cross-area destinations do not affect local grid coordinates.
- Existing modules are not migrated by this generation change.
- A valid coordinate authored by the model is still replaced because ownership, not validity, is
  the deciding rule.

### 5.2 Deterministic final `module_context.json` resync

#### Files and reused seams

- Add a shared final projection utility, preferably `utils/module_context_projection.py`.
- Refactor/reuse `core/generators/story_first/compatibility.py:214-384`
  (`expected_context_projection` and `validate_reconciled_context`).
- Change `core/generators/module_builder.py:_reconcile_and_validate_context`
  (1926-1999) and `validate_module` (2000 onward).
- Reuse `utils/module_context.py:28-304` for the serialized format, not as the final incremental
  source of truth.
- Reuse `safe_write_json`, `path_transaction_lock`, `module_refresh_lock`, and T088 recovery already
  present around module-builder lines 1943-1969.
- Extend `core/validation/validate_module_files.py` context validation to compare all projected
  fields, not only connection membership.

#### Projection contract

After coordinate/route repair and NPC reconciliation, load the final active area files and final
`module_plot.json` from disk and construct a fresh `ModuleContext`:

- `areas`: exact final name/type, sorted location IDs, actual NPC names, and all owned plot points;
- `locations`: exact name, containing area, NPC list, local plus cross-area connection IDs;
- `npcs`: canonical identity/aliases/role/faction/description from the reconciled identity result,
  but appearances are always re-derived from final location rosters;
- `plot_scopes`: every plot point exactly once;
- `references`: retain only references that resolve to a final canonical entity and regenerate
  their artifact locations where deterministically available;
- `validation_issues`: recompute from the newly projected context;
- `module_name` and `module_id`: use final build identity.

Plot-scope resolution must support both existing contracts:

- if `plotPoints[].location` resolves to a location ID, map it to its containing area
  (story-first);
- if it resolves directly to an area ID, use it as an area scope (classic T028);
- unknown or ambiguous values fail generation.

Incremental `self.context.add_*` calls may continue to supply prompt-time context, but their result
is never published as final truth.

This directly replaces four stale legacy seams: area names captured while generating areas
(`module_builder.py:857-883`), locations captured before cross-area linking (1102-1136), plot scopes
captured before final T028 (1243-1249), and later cross-link mutations written only to area files
(2174-2197).

#### Atomic publication and validation

Within the existing refresh/path lock:

1. recover any pending T088 transaction before reading artifacts;
2. build and atomically publish a pre-reconciliation projection from current final areas/plot;
3. run name/continuity reconciliation against that exact snapshot;
4. reload every reconciled area and plot artifact;
5. rebuild the deterministic projection, preserving only reconciler-approved identity/alias facts;
6. validate it against those same artifacts (story-first can generalize
   `compatibility.py:296-384` rather than adding a second validator);
7. atomically replace `module_context.json` and generate `validation_report.json` from that exact
   image;
8. create `_BU` backups only after resync succeeds.

Never overwrite a pending T088 target before recovery. A crash leaves either the previous coherent
context or the complete new context, never a partial index. `generated_at` may reflect publication
time but is excluded from semantic equality; all gameplay-bearing content is idempotent.

#### Edge cases

- Duplicate location IDs or area IDs fail before projection.
- Cross-area connections appear in both endpoint location records.
- An NPC with aliases is one identity with all actual appearances, not one entry per spelling.
- An NPC mentioned only in prose is not invented into an appearance by the projection.
- A plot point cannot be silently omitted; count and ID sets must match `module_plot.json`.
- Stale `.bak`, timestamp backup, and `_BU` files are not projection inputs.
- `world_registry.json` is untouched; it remains the separate cross-module registry.

## 6. Item 7 - cross-area NPC role and attitude coherence

### 6.1 Files and call order

- Extend `core/generators/story_first/stages/npc_repair.py` (currently 36-173), or split its
  structured continuity logic into `core/generators/story_first/stages/npc_coherence.py` while
  retaining `npc_repair` as the pipeline stage name.
- Change `core/generators/story_first/pipeline.py` at the `npc_repair` stage restore/apply boundary
  (roughly 753-819).
- Extend `utils/npc_reconciler.py` after canonical name/alias resolution in
  `_stage_reconciliation_from_snapshot` (507-539), using the existing staged T088 transaction.
- Reuse the structured stage executor and bounded retry/evidence machinery used by existing
  story-first stages. Register one batched callsite for continuity if no existing callsite contract
  can safely be extended.
- Feed accepted outline/plot evidence and all final NPC appearances into the stage; do not ask one
  call per NPC.

### 6.2 Agentic decision, coded reconciliation

Do not reuse the semantic candidate rules in `ModuleContext.add_npc` or the current T088 prefilter:
`utils/module_context.py:72-90` includes a hard-coded identity special case, while
`utils/npc_reconciler.py:375-378` only asks the model when one label is a substring of another. Both
miss ordinary aliases and violate the agentic-first rule. Reuse T088's immutable snapshot, staged
writes, recovery marker, and atomic commit machinery, but replace candidate identity semantics with
one structured model decision over the complete occurrence set.

Name/alias reconciliation runs first. Code then groups final appearances by the returned canonical
identity. A single structured model call receives, for every repeated cross-area identity:

- canonical name and aliases;
- each area/location ID and name;
- exact NPC object (`name`, `description`, `attitude`);
- local `dmInstructions` and the accepted plot/outline beats that involve the identity;
- the rule that public IDs/structure may not change.

The model decides the semantic facts that code cannot derive from shape: whether appearances are
the same mobile person, projection/disguise/spirit manifestations, a deliberate attitude change,
or an accidental duplicate that should have one primary placement. It returns a strict patch
contract containing:

- canonical role/faction/identity summary;
- continuity mode and concise accepted-story reason;
- retained/removed appearance IDs;
- per-appearance replacement `description` and `attitude` when needed;
- a DM-facing arrival/departure/projection instruction for legitimate recurrence.

Code never scans prose for role keywords. It validates and applies the answer:

- identity and target location IDs must already exist;
- no new NPC, area, location, plot, or private story ID may appear;
- only `npcs[].name/description/attitude` and the containing location's `dmInstructions` may change;
- the canonical identity set is preserved;
- a recurring NPC must have one primary static roster plus explicit continuity mode and guidance
  for any secondary scene; a genuinely non-simultaneous manifestation may remain represented in a
  secondary roster only when the accepted-story contract explicitly requires it;
- a primary-only decision removes only the listed duplicate appearances;
- all affected areas and context commit atomically through T088;
- one bounded correction may repair a contract-invalid answer; repeat failure aborts the candidate.

Do not automatically erase a recurring antagonist, merchant, guide, ghost, or changing ally. The
model can retain the story recurrence by choosing a primary physical placement and adding explicit
mobility/projection/schedule guidance to the secondary scene. This preserves agentic story design
while preventing unexplained simultaneous static copies.

### 6.3 Classic and story-first behavior

Use the same occurrence packet and patch validator for both generation paths:

- Story-first includes the accepted outline and beat anchors, then runs before candidate hardening.
- Classic includes T028 plus the per-area plot fragments, then runs from
  `_reconcile_and_validate_context` after T088 name identity merge and before final context resync.

If there are no repeated cross-area identities, make no call. One-location NPCs pass through
unchanged. Identity ambiguity remains fail-closed; code must not merge two distinct people merely
because their labels resemble each other.

### 6.4 Edge cases

- Deliberate attitude evolution is valid when tied to accepted story state.
- Collective labels such as a guard patrol are classified agentically as groups, not forced into a
  person record.
- A living person and a spirit/projection may be one identity with manifestations or distinct
  identities; the model must state which and code preserves the declared canonical grouping.
- Same-name distinct people remain separate when identity reconciliation cannot prove equivalence.
- A party member must never be added to an NPC roster.
- An NPC/monster same-name collision stays subject to existing candidate checks.
- Weak-model incoherence after the bounded correction aborts publication rather than publishing
  contradictory roles.

## 7. Qwen iterative testing loop

Endpoint: `http://192.168.1.254:1234` (OpenAI-compatible LM Studio). Use the exact model ID returned
by `/v1/models`; do not assume its display name. Store credentials/settings only in local ignored
configuration. The loop is zero-paid-call local validation.

### 7.1 Preflight and evidence rules

1. Confirm the endpoint and loaded model with `GET /v1/models`.
2. Use a disposable game directory and a unique output module name per run. Never overwrite the two
   audited modules or a player's game.
3. Give the local model enough time to finish; no timeout shorter than the observed 30 tokens/second
   worst case plus generation overhead.
4. Save sanitized request metadata, stage evidence, retry/correction counts, and final artifacts.
   Do not save keys or raw configuration.
5. A failed bounded attempt is a real failure. Do not hand-edit output, silently rerun the same seed,
   or loop until a lucky pass. Change a specific prompt/code hypothesis before another trial.

### 7.2 Isolated T026 calibration

Run the real `LocationGenerator.generate_location_batch` callsite against fixed trusted stubs, not a
mock, across ten cases:

- three 2-location simple areas;
- three 4-location mixed exploration/social/combat areas;
- two 6-location areas with cross-area exits and recurring NPC context;
- two deliberately dense areas with doors, traps, creature briefs, and side-thread hooks.

For each result record:

- generation-schema acceptance on first/full-retry/surgical path;
- raw non-empty encounter attempts and fresh-state corrections;
- trusted-field drift, especially coordinates and connection arrays;
- creative floors and fields surgically regenerated;
- final runtime-schema validity.

Pass threshold: 10/10 final runtime-valid, 10/10 fresh-state clean, zero published coordinate drift,
zero lost trusted IDs/edges, no unbounded attempt. The desired quality signal is zero raw encounter
authorship; a nonzero safety-strip count is tolerated but must be reported.

### 7.3 Deterministic development probes

Before full builds, exercise route and context utilities with artifact-shaped inputs for:

- linear A-B-C; backward A-C plus B-A; skipped middle area; disconnected area;
- legitimate branch/rejoin; explicit revisit; two equally valid gateways;
- classic area-ID plot and story-first location-ID plot;
- stale context names/connections/scopes; aliased recurring NPCs;
- map/location coordinate drift and duplicate layout cells.

These prove algorithm behavior during development only. They do not replace the live gates below.

### 7.4 Real module-build matrix

Run the matrix through both generation paths because the audited failures came from dial-down:

- Qwen story-first enabled on two fixed concepts: one linear three-area seed and one
  branch/optional-terminal seed;
- Qwen deliberately forced through the approved story-first failure/dial-down path on those same
  two concepts;
- one Gemma control build for each path;
- after those four path checks, expand Qwen to the six-concept quality matrix below.

Run complete builds through the real CLI, each once per implementation revision:

```text
python run_headless.py build-module --name <unique-name> \
  --narrative-file <concept-file> --areas <n> \
  --locations-per-area <n> --game-dir <disposable-game-dir> --debug
```

Expanded concept matrix:

1. two-area linear rescue;
2. three-area investigation with a clear A-B-C escalation;
3. three-area branched mystery that rejoins before the climax;
4. recurring mobile merchant/guide whose attitude changes after a beat;
5. antagonist appearing by projection before the physical finale;
6. four-area complex module with side threads, locks, hazards, and creature briefs.

If the four path checks already include the linear Gemma control, only one additional recurring-NPC
Gemma control is needed. This is not a model contest; it checks that enforcement works independent
of model and fallback path.

For every build run the production strict validator and an independent artifact audit that asserts:

- all active JSON files conform to their actual schemas;
- every fresh location has empty runtime history;
- room, area, coordinate, and connection projections match;
- a valid canonical route follows the accepted plot/beat prerequisites;
- context equals a projection freshly recomputed from active areas and plot;
- every repeated NPC has coherent, explicit continuity or one justified primary placement;
- retry/correction/floor counts remain within ceilings.

### 7.5 Real headless play gate

Load every successful generated module through the actual game. For each, create or reuse a real
headless character and issue natural player commands through `core/headless/client.py`. Judge success
from files after each turn, not narration.

- Start all six Qwen modules and confirm the party begins at the intended entry beat/location.
- Cross at least one area boundary in every module.
- Fully traverse the canonical ordered route in the linear, branched, and four-area modules.
- Backtrack once, then resume forward progression, proving optional travel was not removed.
- Interact with every repeated NPC in the two continuity-focused modules and verify the correct
  location object/attitude is presented at each story state.
- Trigger one real runtime encounter and verify only that event creates dated encounter history from
  the party clock; untouched locations remain empty.

Record before/after `party_tracker.json`, affected area files, `module_context.json`, and plot state.
Stop immediately on data loss, stale context, impossible required route, false encounter history, or
an unexplained duplicate actor.

### 7.6 Quality and convergence

After structural gates pass, perform a blind content read of at least three Qwen modules and both
Gemma controls. Score cohesion, originality, actionable DM guidance, plot/location agreement, NPC
continuity, and absence of template floors. Compare creative fields with the pre-change modules to
ensure deterministic rails did not flatten story content.

Convergence rule: no more than one rerun of a failed case after a specific fix. A new failure is
classified, added to evidence, and either fixed within items 1/2/3/7 or explicitly deferred. The
release gate is six independent Qwen builds structurally green, both Gemma controls green, and all
required headless routes/play checks green. Passing schema alone is never sufficient.

## 8. Implementation checkpoints

### Checkpoint A - T026 ownership

- Generation schema added; runtime schema unchanged.
- All T026 call/retry/repair paths use the generation schema.
- Final output validates against runtime schema.
- Ten isolated Qwen T026 calls meet the fresh-state/trusted-field gates.

### Checkpoint B - coordinates and routes

- Map is the sole coordinate authority.
- Both classic and story-first adapters pass final map/location checks.
- Canonical ordered routes exist without eliminating optional travel.
- Three early real Qwen builds prove linear, branched, and backward-edge cases before continuing.

### Checkpoint C - context and NPC coherence

- Context is projected after all final edits and validates exactly against active artifacts.
- Repeated NPCs are processed in one bounded agentic batch and applied transactionally.
- No stale names, connections, appearances, plot scopes, or false validation report remains.

### Checkpoint D - final live gate

- Full six-Qwen/two-Gemma build matrix completed.
- Real headless startup, transitions, backtracking, NPC interactions, and runtime encounter stamping
  pass on disk.
- Evidence includes failures and retry counts, not only successful final output.

Only after Checkpoint D should implementation be considered ready for a merge decision.
