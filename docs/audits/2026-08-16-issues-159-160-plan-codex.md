# Independent implementation plan for issues #159 and #160

Date: 2026-08-16

Scope: planning only. This document does not change production code. It was
written from the issue reports and an independent trace of the current
`main-merge` code after commits A-F.

## Executive decisions

1. Issue #159 must not be fixed by globally replacing cross-area connections
   with empty arrays. `LocationGenerator` is shared by the classic and
   story-first builders. Classic location stubs intentionally begin with empty
   cross-area arrays, while story-first stubs already contain exact compiled
   links. The safe shared rule is: after the ordered location-ID preflight,
   restore the exact `areaConnectivity` and `areaConnectivityId` values from
   each trusted stub.
2. The classic finalizer must become the sole author of classic cross-area
   links. It should clear the staged classic cross-area arrays once, rebuild
   the complete expected set from the final plot route, validate the result,
   and then publish it. It must not merely append to model-authored arrays.
3. Issue #160 requires an agentic semantic decision followed by deterministic
   code validation. Role, mobility, projection, and an intentional attitude
   change live in prose and cannot be inferred with names, substrings, or
   attitude equality.
4. Version 1 of #160 should apply to the classic/legacy builder only and remain
   disabled by default. Story-first already performs T101 before publication;
   adding a second post-publication authority there would create competing
   ownership and invalidate its expected-context snapshot.
5. Neither issue should modify a published module in place. These changes act
   while a disposable module candidate is being built. A failed enabled pass
   aborts that candidate and preserves the last accepted module.

---

## Issue #159: model-authored cross-area connection pollution

### Reproduced failure and root cause

A real Qwen candidate contained both a bogus and a valid destination in one
location:

- `areaConnectivity`: `The Weeping Woods`, `The Weeping Wilds`
- `areaConnectivityId`: `WW001`, `B01`

`WW001` is an area ID in a field consumed as a destination **location** ID.
`B01` was the valid destination location appended later by code. Both survived.

There are three cooperating causes:

1. The T026 contract actively asks the model to author these fields.
   `LocationPromptGuide.areaConnectivity` and `areaConnectivityId` describe
   cross-area names and IDs at
   `core/generators/location_generator.py:914-945`. The final checklist at
   `core/generators/location_generator.py:1248-1253` explicitly tells the
   model to supply other *area IDs*. The generation and runtime schema
   descriptions repeat that stale meaning.
2. `_canonicalize_t026_stub_owned_fields` performs an ordered-ID preflight and
   restores code-owned IDs and coordinates, but currently does not restore the
   two cross-area arrays (`core/generators/location_generator.py:92-186`).
   Listing them in `_T026_STRUCTURAL_STUB_FIELDS` at lines 959-962 only helps a
   surgical schema repair; it does not stop a schema-valid, semantically wrong
   model value.
3. The classic finalizer appends deterministic links without first removing
   model-authored links. A valid code-owned link therefore coexists with the
   bad one instead of replacing it. The relevant seams are
   `_create_bidirectional_connection`, `_plot_ordered_area_transitions`, and
   `finalize_locations_and_connections` in
   `core/generators/module_builder.py:2214-2360`.

At runtime, `areaConnectivityId` is resolved as a location destination, so the
wrong area ID is not harmless metadata. It can break a transition or create a
route inconsistent with the displayed map.

### Ownership contract

The contract after this fix is:

- `connectivity`: local, same-area map connectivity; produced upstream and
  preserved exactly. This issue does not change it.
- `areaConnectivity`: names of destination areas for code-owned cross-area
  gateways.
- `areaConnectivityId`: destination **location IDs**, parallel by index with
  `areaConnectivity`.
- Classic path: T026 receives empty cross-area arrays. The final classic route
  compiler owns the complete final arrays.
- Story-first path: `compile_area_binding` owns the complete arrays before
  T026 and T026 must copy them unchanged.

### Cross-path safety proof

The same T026 generator serves both paths, so a blanket clear is unsafe:

- Classic stubs from `core/generators/area_generator.py:594-642` initialize
  both cross-area arrays as empty.
- Story-first stubs from
  `core/generators/story_first/compilers.py:239-353` initialize them empty and
  then add exact destination area names and destination location IDs from
  `crossAreaLinks` at lines 325-347.
- Story-first marks both fields as trusted at
  `core/generators/story_first/validators.py:844-853`, and
  `validate_story_first_location_result` compares the result to the stubs at
  lines 1095-1111.

Therefore the shared canonicalizer must copy the exact arrays from the trusted
stub, not set them to a universal value. Empty classic values stay empty and
non-empty story-first values survive unchanged.

### Implementation slices

#### 159-A: make the trusted stub authoritative at the T026 boundary

Files:

- `core/generators/location_generator.py`
- `tests/` for development-only unit coverage; these tests are not acceptance
  evidence

Changes:

1. Add a small validator for each stub's two cross-area fields:
   both values must be lists of strings, lengths must match, and blank IDs or
   names are invalid. Do not infer or repair pairings.
2. In `_canonicalize_t026_stub_owned_fields`, after the existing full-batch
   location-ID preflight succeeds, deep-copy both fields from the corresponding
   trusted stub into the returned location on every attempt.
3. Emit one bounded advisory count when model values differed. Do not log
   model prose or raw responses.
4. Keep the existing behavior that returns the untouched model response if a
   present ID conflicts or ordering is suspect. Positional ownership is only
   safe after identity/order is proven.
5. Do not alter `connectivity`, content fields, danger variation, or any other
   story field.

Why here: all full generation, retry, and targeted complete-location repair
responses pass through `_canonicalize_t026_response_fields` before acceptance.
The correction therefore covers every T026 recovery route without a new model
call.

Edge cases:

- A reordered or duplicate returned location batch must still fail and retry;
  no partial overlay.
- A story-first hub location may have several cross-area pairs; preserve order
  and multiplicity exactly from the stub.
- A classic one-area module remains empty.
- Malformed upstream stubs are a code-contract failure, not a reason to trust
  model output.

#### 159-B: correct prompt and schema semantics

Files:

- `core/generators/location_generator.py`
- `schemas/loca_generation_schema.json`
- `schemas/loca_schema.json` description only

Changes:

1. Replace the `LocationPromptGuide` guidance with: both cross-area arrays are
   code-owned; copy the exact values from the supplied stub; never add, remove,
   rename, reorder, or reinterpret them.
2. Replace the T026 checklist's instruction to provide other area IDs with the
   precise rule that `areaConnectivityId` contains destination location IDs.
3. Correct descriptions in both schemas. Do not change runtime field shapes or
   required fields.
4. Retain both fields in the strict generation schema because strict OpenAI
   schemas require the complete object shape. The prompt and code overlay are
   still necessary because local models may ignore schema descriptions.

#### 159-C: rebuild classic links from clean staged arrays

Files:

- `core/generators/module_builder.py`
- the current route validator in
  `core/generators/story_first/validators.py`, if a shared final invariant is
  appropriate

Changes:

1. In `finalize_locations_and_connections`, deep-copy all classic area
   payloads before mutation.
2. Clear `areaConnectivity` and `areaConnectivityId` on every staged classic
   location exactly once.
3. Derive the complete ordered transition set from the final T028 plot via
   `_plot_ordered_area_transitions`. Preserve branch, hub, and revisit edges;
   do not impose an alphabetical chain when a valid plot route exists.
4. Add every expected bidirectional gateway to the staged copies using the
   existing deterministic last-source-location to first-destination-location
   rule. Accumulate all links before validation; do not clear per edge.
5. Validate before writes:
   - parallel arrays have equal lengths;
   - each pair is unique;
   - every target ID resolves to exactly one location in another area;
   - the paired name equals that target area's name;
   - the exact reciprocal ID/name pair exists at the expected endpoint;
   - the link set equals the expected plot-derived set, with no model extras;
   - all local `connectivity` values are unchanged.
6. If any invariant fails, abort the candidate before publishing/backups. Do
   not guess an endpoint or keep a partially rebuilt graph.
7. Save only after every staged area passes. Keep managed candidate cleanup and
   last-accepted-module preservation as the outer recovery behavior.

This second defense is important even after 159-A: it makes the finalizer
idempotent and prevents stale links from an interrupted/resumed classic
candidate from surviving.

### Real acceptance plan for #159

Synthetic fixtures may aid development but do not establish acceptance.

1. Query the local provider at `http://192.168.1.254:1234/v1/models` and pin
   the returned Qwen model ID for the run record.
2. Run a real isolated T026 request through `LocationGenerator` with classic
   stubs whose cross arrays are empty. Inspect the accepted response object:
   both arrays must be empty regardless of raw model authorship.
3. Run the same real T026 path with story-first stubs containing two valid
   compiled links. Inspect the accepted result: both pairs must exactly match
   the stubs in order.
4. Build one real three-area classic Qwen module through the normal managed
   module-creation path. Inspect every active `areas/*.json` file and prove all
   validation rules in 159-C from disk. There must be no area ID in a
   destination-location-ID slot and no unexplained link.
5. Build one real branching or hub story-first Qwen module. Prove the compiled
   non-empty links survive T026 and publication unchanged and that no valid hub
   edge was removed.
6. Use unmodified `core/headless/client.py` against disposable copies of both
   completed modules. Start a game, cross every boundary in both directions,
   revisit one prior area, and inspect `party_tracker.json` and active area
   files after each transition. Narration alone is not evidence.
7. Run one Gemma classic control to distinguish a contract fix from a
   Qwen-specific prompt coincidence.
8. Bound iteration: at most three contract revisions. If the same failure
   repeats twice, stop and trace the contract rather than adding prose patches.

Acceptance requires all on-disk invariants to pass. A build that merely avoids
crashing is not sufficient.

### Open questions for #159

1. Should a multi-area classic module whose final plot names fewer than two
   areas be allowed? Recommendation: no implicit alphabetical chain. Require an
   explicit structural designation for optional plot-free areas; otherwise
   fail the candidate for correction.
2. Should the current report-only route check become a gate in this slice?
   Recommendation: promote only the pollution-specific parallel-array,
   resolution, reciprocal, and exact-code-owned-link invariants after real
   linear/hub/branch/revisit builds pass. Keep broader story-route quality
   findings report-only until separately proven.
3. Should existing modules be migrated? Recommendation: no automatic rewrite.
   Offer a read-only diagnostic first; generated candidates use the new
   ownership contract going forward.

---

## Issue #160: agentic cross-area NPC role and attitude coherence

### Current state and root cause

The shipped Step 4.57 advisory at
`core/generators/module_builder.py:548-571` reports exact same-name recurrence
and attitude divergence. It intentionally does not decide whether recurrence
is a mobile person, a projection, an intentional relationship change, an
accidental duplicate, or two distinct people with the same label. That was the
correct boundary: role is semantic and lives in prose.

The remaining gap has two parts:

1. Classic T088 is an identity/name reconciler, not a role reconciler. Its model
   prompt receives only two labels (`utils/npc_reconciler.py:184-200`), its
   candidate prefilter uses substring matching at lines 356-378, and its staged
   area update changes names only at lines 411-428. It cannot establish
   cross-area continuity.
2. Story-first T101 handles exact casefold duplicate placements before
   publication (`core/generators/story_first/stages/npc_repair.py:36-173`), but
   it does not cover aliases which T088 may later canonicalize into the same
   identity. It also should not be followed by an independent late writer that
   invalidates its expected-context projection.

Neither exact name equality nor attitude equality answers the semantic
question. Existing `duplicate_npc_placements` at
`core/generators/story_first/validators.py:1205-1223` is useful for grouping
already-canonical occurrences, not for deciding identity or intent.

### Version-1 scope and ownership

Version 1 should be:

- classic/legacy module creation only;
- behind `ENABLE_NPC_COHERENCE_REPAIR = False` in `config_template.py`;
- one structured model call over all repeated canonical identities in the
  candidate, not one call per NPC;
- one correction attempt at most;
- applied to T088's in-memory staged snapshot and committed in the same durable
  transaction as context/name reconciliation;
- fail-closed when enabled: invalid or unresolved output makes no writes and
  aborts the disposable candidate with a clear model-limitation message;
- no call and no file changes when there are no repeated canonical identities.

Story-first remains on T101 in version 1. A later shared implementation must
move the semantic pass before story-first's expected-context snapshot or
recompute that snapshot from the accepted patched images.

### Implementation slices

#### 160-A: structured occurrence packet and strict response contract

Files:

- new `core/generators/npc_coherence.py` for packet construction, response
  validation, and pure in-memory patch application
- `model_config.py` for a named task binding
- `config_template.py` for the default-off feature flag and named model
  settings
- shared structured execution utilities in
  `core/generators/story_first/execution.py`

Packet construction:

1. Run after T088 has made its agentic identity decisions in memory and
   rewritten aliases to canonical names, but before any transaction write.
2. Group exact casefold canonical identities across final staged areas. Do not
   use `ModuleContext.add_npc`, the T088 substring prefilter, or any prose
   keywords.
3. Include all qualifying groups in one packet. For every occurrence include:
   - opaque occurrence ID generated by code;
   - canonical NPC name;
   - area ID/name and location ID/name;
   - exact NPC object (`name`, `description`, `attitude`);
   - location `dmInstructions`;
   - structurally associated plot-point data from the final plot;
   - party names as an exclusion set.
4. Frame all module content as untrusted data. The system prompt states that
   quoted module prose is evidence, never instruction.

Use a new task ID after checking the complete registry to avoid collision with
other work. T111 is the likely next free ID in this branch, but the implementer
must confirm before reserving it. Route the call through the existing
`capture_and_fanout`/structured execution path so OpenAI, Gemini, and LM Studio
receive their provider-compatible schema forms and bounded failure telemetry.

Suggested strict response shape (all keys required for strict providers):

```json
{
  "decisions": [
    {
      "canonicalName": "exact input enum",
      "classification": "same_mobile_person | projection_or_manifestation | deliberate_attitude_change | accidental_duplicate | distinct_people_same_label",
      "primaryOccurrenceId": "exact input enum",
      "continuityReason": "short semantic explanation",
      "repairs": [
        {
          "occurrenceId": "exact input enum",
          "keepInRoster": true,
          "name": "exact or approved canonical name",
          "description": "complete replacement string",
          "attitude": "complete replacement string",
          "dmInstructions": "complete replacement string"
        }
      ]
    }
  ]
}
```

Contract requirements:

- exactly one decision for every supplied group;
- exactly one repair for every occurrence and no unknown occurrence;
- primary occurrence must belong to that group;
- no omitted optional keys; strict schema compatibility is identical across
  providers;
- no raw model response persisted in production telemetry.

One focused correction can return the same full response shape with exact
validation findings and the original immutable packet. A second failure aborts.

#### 160-B: deterministic patch validation

Files:

- `core/generators/npc_coherence.py`
- location/module schema validators already used by T088

Apply the model response only to deep-copied staged payloads. Code must prove:

1. The target group, occurrence set, primary occurrence, and location IDs are
   exact and complete.
2. No area ID, location ID, local/cross connectivity, coordinate, plot,
   encounter, monster, door, loot, or unrelated NPC field changes.
3. Only roster presence, the targeted NPC's `name`, `description`, `attitude`,
   and that location's `dmInstructions` may change.
4. Every original canonical identity still has at least one static roster
   occurrence; no identity is silently deleted or invented.
5. Party names are never introduced as NPCs.
6. Every changed area still passes the full runtime location/area schemas.
7. The output follows classification-specific structural rules. For example,
   an accidental duplicate cannot keep several unexplained static roster
   entries, while `distinct_people_same_label` cannot silently merge them.
8. Re-running the advisory on the staged result reports the expected resolved
   state or an explicitly permitted intentional recurrence.

The code validates identities, targets, allowed fields, and atomicity. It does
not decide role by rereading descriptions.

Recommended version-1 handling by classification:

- `same_mobile_person`: retain one primary static roster; remove secondary
  static entries and preserve appearances as explicit mobility/schedule
  guidance in the secondary locations' `dmInstructions`.
- `projection_or_manifestation`: retain one physical primary. Represent other
  appearances in location instructions unless the owner explicitly authorizes
  multiple simultaneous roster entries.
- `deliberate_attitude_change`: retain one physical primary and put the
  location-specific state/attitude transition in instructions. Do not flatten
  intentional character development into one attitude string.
- `accidental_duplicate`: retain the selected primary, remove the other static
  entries, and preserve any useful unique prose as continuity guidance.
- `distinct_people_same_label`: no mutation in version 1, plus an advisory.
  Renaming would invent identity and require coordinated plot/context rewrites.

#### 160-C: integrate with T088 staging and durable commit

Files:

- `utils/npc_reconciler.py`
- `utils/module_context.py`
- `core/generators/module_builder.py`

Changes:

1. Extend `_stage_reconciliation_from_snapshot`
   (`utils/npc_reconciler.py:507-539`) so the ordering is:
   agentic identity reconciliation -> canonical-name area staging -> build all
   canonical occurrence groups -> optional one T111 call -> validate/apply the
   returned patch to staged copies -> build the final context from those staged
   copies.
2. Do not call the model while holding only the context-path lock. Preserve the
   established module-refresh then context-path lock order and source snapshot
   revalidation.
3. Generalize `ModuleContext.from_artifacts`
   (`utils/module_context.py:310-376`) with a projector that can consume staged
   area payloads and final plot payload directly. Reading current disk here
   would rebuild context from the old, unpatched images.
4. Carry existing NPC aliases/references only when they resolve through the
   canonical identity map. Do not use `ModuleContext.add_npc` during
   projection.
5. Put every changed area and `module_context.json` in the same existing T088
   durable transaction (`utils/npc_reconciler.py:805-866`). Reuse the pending
   transaction record, source revalidation, commit verification, rollback, and
   recovery mechanisms.
6. If the call, validation, source revalidation, or commit fails, restore the
   in-memory context, write nothing, and retain/recover the last accepted disk
   state.
7. Move or repeat Step 4.57 after accepted T088 staging for final telemetry.
   The pre-T088 advisory can remain useful but is not proof of the final state.

#### 160-D: classic builder gate and story-first exclusion

Files:

- `core/generators/module_builder.py`
- `config_template.py`

Changes:

1. Pass the final classic plot/module context into the T088 staged coherence
   phase when the default-off flag is explicitly true.
2. Treat enabled unresolved coherence as a candidate-generation failure, not a
   warning followed by partial publication.
3. Explicitly skip the new phase on story-first candidates in version 1.
4. Keep T101 and its current story-first contracts unchanged.

### Real acceptance plan for #160

Conflict generation is stochastic, so the test protocol must be declared
before calls and must not retry until a convenient output appears.

1. Prepare three distinct natural module concepts. Each explicitly requests a
   single recurring named NPC who appears across three areas, with one concept
   involving travel, one a projected manifestation, and one a relationship
   change. These are real player concepts, not edited model outputs.
2. Run each concept once through the normal classic Qwen module builder with
   the feature disabled. Record whether the final disk artifacts contain a
   repeated canonical identity. If none do, report the live trigger as blocked;
   do not manufacture a conflict or claim acceptance.
3. For a real conflicting candidate, rerun through the normal builder with the
   feature enabled and a real T111 call. Inspect all active area files and
   `module_context.json` before/after. Prove only permitted paths changed,
   identity is conserved, context matches final areas, and no pending T088
   transaction remains.
4. Run a real no-conflict candidate with the flag enabled. Prove zero T111
   calls and no coherence-related file differences.
5. Exercise one externally induced provider failure, such as an unavailable
   disposable LM Studio endpoint, without monkeypatching. Prove no area or
   context writes, clean candidate abort/recovery, and a truthful model-
   limitation message.
6. Exercise one real malformed/failed local-model response if naturally
   observed. Do not fabricate it as acceptance evidence. Prove one bounded
   correction maximum and then fail closed.
7. Launch the accepted module using unmodified `core/headless/client.py`.
   Visit each affected location, interact with the NPC using natural player
   language, cross areas, backtrack, save, disconnect, resume, and revisit.
   Judge correctness from area files, context, party tracker, and save state,
   not narration.
8. Run one real story-first Qwen build with a recurring NPC to prove the new
   legacy-only phase makes no call and T101/publication behavior is unchanged.
9. Run one Gemma classic control on the same semantic class after Qwen passes.

Record call count, attempt count, classification, correction reason category,
latency, and allowed on-disk field differences. Sanitize provider content and
credentials. A result is not shippable until a genuine conflict reaches the
new phase in a real build.

### Open questions for #160

1. Version-1 path scope: recommend classic only. Story-first should be unified
   later at T101, before expected-context construction, rather than patched by
   a second late authority.
2. Multiple static roster entries for a projection/mobile NPC: recommend one
   physical primary plus location instructions in version 1. Multiple active
   static copies need explicit runtime semantics before they are safe.
3. Distinct people with the same label: recommend preserve unchanged and
   advise. Automatic renaming changes identity and requires a wider plot and
   reference rewrite contract.
4. Model tier: recommend the module's main semantic model initially, not the
   cheapest pairwise T088 mini. After measured real runs demonstrate that a
   smaller model classifies and patches reliably, the binding can be reduced.
5. Enabled unresolved result: recommend abort the disposable candidate after
   one correction. Default-off protects current production behavior until the
   real acceptance battery passes.

---

## Delivery order

1. Implement and validate 159-A and 159-B together: shared ownership boundary
   plus truthful prompt/schema semantics.
2. Implement 159-C and run the complete #159 classic/story-first/headless
   battery before promoting any route invariant to fail-loud.
3. Implement 160-A and 160-B as pure staged transforms and strict contracts.
4. Implement 160-C using T088's existing snapshot, lock order, durable
   transaction, recovery, and final context projection.
5. Add 160-D default-off classic wiring.
6. Run the predeclared real conflict battery. Keep the feature off unless a
   genuine conflict, no-conflict case, provider failure, story-first regression
   case, save/resume, and on-disk atomicity all pass.

The two issues should remain separate commits and review gates. #159 is a
deterministic ownership defect suitable for normal promotion after real path
validation. #160 adds a new semantic authority and should not be enabled merely
because its schema or fixtures pass.
