# LLM Wants To Be Free - Narrative Sovereignty Within Python Mechanics

Status: Archived planning record - Lane 1 complete (G1-G4 archived); Lane 2 handed off to version-2 continuation
Owner: OpenCode planning pass
Target: `plans/archive/llm-wants-to-be-free.md`
Scope: Reframe narrator/runtime architecture so the Narrator LLM remains a sovereign DM for world and story discovery, while Python remains the constitutional authority for 5e mechanics, persistence, and hard legality. Runtime should auto-commit narrator-declared world changes when they are compatible with Python truth instead of rejecting turns over brittle state-sync wording mismatches.

## Immediate release context

This plan is intentionally larger than the current gametest need.

## Implementation status update (2026-03-16)

The minimum gametest slice defined in this document is now complete:

- G1 `narrative-sovereignty-state-packet-foundation` archived
- G2 `travel-reconcile-first-autocommit` archived
- G3 `npc-scene-presence-reconcile-first` archived
- G4 `validator-authority-deconfliction` archived

That means Lane 1 is no longer an active implementation plan. It is now a completed stabilization record.

The remaining work in this document belongs to Lane 2 and should be treated as post-gametest version-2 architecture.

Active continuation path:

- `plans/version-2/narrative-sovereignty-post-gametest.md`

Sequencing decision:

- complete the post-gametest narrative-sovereignty continuation on the stable OpenAI runtime baseline first,
- then proceed to the OpenRouter router re-architecture.

Why this order:

- it isolates runtime authority/prompt-contract work from provider-routing variance,
- it keeps event-ledger and prompt-reset validation on the known-good gametest runtime,
- it reduces the chance of debugging architecture and provider migration at the same time.

The immediate priority is NOT to complete the full architecture rebuild before inviting testers to the GitHub fork. The immediate priority is to stabilize the current gametest build by removing Python/runtime bugs that repeatedly interrupt immersive gameplay, especially bugs that trap the Narrator LLM in retry loops, state-sync dead ends, or brittle validator conflicts.

Important framing:

- the minimum gametest slice is NOT a rollback to original upstream looseness,
- it is a rebalance toward narrator freedom with stronger runtime reconciliation than upstream,
- it keeps a harder Python mechanical constitution than upstream while reducing current reject-first prose policing.

For the gametest release track, this plan should be read as a two-lane strategy:

### Lane 1 - Minimum viable gametest fix

Deliver the smallest safe runtime changes that restore immersive play without reducing narrator freedom.

Gametest goals:

- stop hard-fail/retry-loop behavior in common travel and NPC scene-presence turns,
- preserve Narrator LLM freedom as DM/world-author,
- keep Python as the hard authority only for 5e mechanics, topology legality, persistence safety, and irreversible state truth,
- preserve the existing JSON/action schema surface where practical so the gametest fix is evolutionary, not a full protocol break,
- prefer reconcile-first runtime behavior over reject-first validator behavior,
- restore the best upstream quality -- narrator breathing room -- without returning to upstream's weaker runtime reconciliation model,
- avoid broad risky rewrites before external testing begins.

Gametest non-goals:

- full planner/narrator split,
- full Titans/EGO runtime integration,
- complete prompt-stack redesign,
- large-scale replacement of all existing validation systems in one pass.

Recommended gametest target slice:

1. establish a narrow authoritative runtime packet where needed,
2. convert travel handling to reconcile-first with in-transit/progress support,
3. convert the worst NPC arrival/presence failure loops into reconcile-first behavior,
4. reduce validator authority in these domains only where it is causing immersive-play failures.

This lane should optimize for:

- maximum UX recovery,
- minimum architecture risk,
- fast transcript-based regression coverage,
- compatibility with the already-prepared tester build,
- no accidental regression into either extreme: current over-constrained validator loops or old upstream action-plumbing fragility.

### Lane 2 - Post-gametest architecture program

The remaining sections of this document describe the broader architecture direction:

- authoritative state packet as canonical truth surface,
- world delta reconciler,
- event ledger,
- validator deconfliction,
- prompt contract reset,
- Titans/EGO-ready world evolution substrate.

That broader work remains the correct long-term direction, but it should be staged after the gametest build is stable enough for live external play.

### Review rule for this document

When evaluating the stages below, always distinguish:

- "needed now to stop immersive gameplay failures for testers"
- from
- "needed later to complete the full narrative-sovereignty architecture"

If a change does not materially improve gametest stability or immersive flow, it should be deferred to the post-gametest lane.

---

## 1) Executive summary

NeverEndingQuest should not evolve toward a fully deterministic state machine that forces the LLM to speak only in pre-approved Python transitions. That would protect correctness at the cost of the thing that makes NEQ exciting: the live, exploratory, black-box DM voice.

This plan adopts the following product rule:

- The Narrator LLM is sovereign over emergent narrative reality.
- Python is the constitutional layer for 5e mechanics, persistence, topology, and irreversible state safety.
- When narrator output implies a world change that is compatible with Python truth, runtime SHOULD auto-commit it.
- Runtime SHOULD only hard-fail turns when narration collides with hard mechanical impossibility, persistence corruption risk, or unresolved ambiguity that would commit false canon.

This is a reconcile-first architecture, not a reject-first architecture.

The immediate aim is to stop persistent UX failures like:

- narrated travel with stale `party_tracker.json` location,
- NPC arrival/state-sync retry loops,
- prompt/validator conflict where deterministic logic and LLM validation disagree,
- loss of narrative freedom caused by increasing prose-policing rules.

The longer-term aim is to make room for Titans/EGO background evolution of world reality while preserving the Narrator LLM as the live DM/god of the world, bounded only by Python mechanics and persistent world safety.

---

## 2) Product philosophy to lock

### 2.1 Prime directive

Python enforces the constitution.
The Narrator LLM explores the world.

That means:

1. Python MUST own mechanical truth:
   - HP, max HP, death state
   - spell slots and class resources
   - inventory/currency accounting
   - combat sequencing and action legality
   - save/check math and structured roll requests
   - canonical location graph/topology
   - persistent party membership and schema-safe writes

2. The Narrator LLM SHOULD own emergent fiction:
   - scene composition
   - dialogue
   - discoveries
   - foreshadowing
   - social beats
   - ambient cause/effect
   - implied travel progress
   - soft world facts compatible with existing canon

3. Runtime SHOULD auto-commit narrator-declared world changes when they are:
   - mechanically possible,
   - topologically/legal-world compatible,
   - identity-resolvable,
   - persistence-safe.

4. Runtime MUST NOT reject a good storytelling turn merely because the narrator did not emit the exact explicit action schema for a soft world-state change.

5. Runtime MUST fail closed only for:
   - hard 5e/mechanical contradiction,
   - impossible topology/module transition,
   - ambiguous identity that would commit wrong canon,
   - malformed or unsafe persistence mutation.

### 2.2 Design slogan

Move from:

- `Narration -> validator rejection -> retry loop`

To:

- `Narration -> world-delta inference -> constitutional check -> auto-commit -> final output`

---

## 3) Problem statement

The current system has accumulated multiple validation and state-sync hardening layers to correct drift, but they now increasingly constrain the LLM in the wrong place.

Observed failure pattern:

1. Narrator emits vivid, plausible world progression.
2. Runtime detects missing explicit action/state sync.
3. Validator retries or hard-fails.
4. Conversation history and world state drift further.
5. More deterministic rules are added to patch the new failure mode.

This creates several bad outcomes:

- The LLM becomes afraid to narrate natural scene progression.
- Runtime spends effort rejecting prose instead of reconciling it.
- Validation layers compete with each other.
- History becomes polluted by failed attempts and contradictory near-canon.
- The UX degrades into persistent loop failures.

The root issue is not merely bad prompts. The root issue is architectural:

- the system asks the LLM to both declare reality and manually encode all state mutation plumbing,
- while Python tries to recover legality afterward through multiple overlapping validators.

---

## 4) Comparison with original MoonlightByte runtime model

This plan does NOT propose reverting NeverEndingQuest to the original upstream runtime model.

Upstream MoonlightByte should be understood as:

- prompt-strict,
- validator-driven,
- relatively runtime-loose.

That upstream balance had an important virtue:

- the narrator had more room to breathe than in the current heavily patched build.

But upstream also still depended heavily on the LLM to manually emit the correct action plumbing for world-state changes such as travel, time passage, NPC movement, and party composition. In practice, that meant the system could still drift when narration was good but state mutation instructions were incomplete.

This plan does NOT discard the upstream JSON/action schema as a compatibility surface. Instead, it reduces hard dependence on perfect manual action emission for soft world-state commitment.

The target of this plan is a different balance point:

- narrator-loose,
- reconcile-first,
- mechanically strict.

### 4.1 Upstream model

Operational shape:

1. LLM narrates and emits explicit action JSON.
2. Validator checks whether the action bundle is acceptable.
3. Runtime executes the emitted actions.

Strengths:

- more live DM feel,
- less prose-policing than the current build,
- fewer deterministic intervention layers.

Weaknesses:

- world-state commitment depends too much on perfect action emission,
- soft narration can still drift away from persistence,
- no strong runtime reconciliation layer for compatible narrated world changes,
- limited future support for Titans/EGO-style background world evolution.

### 4.2 Current heavily patched build

Operational shape:

1. LLM narrates and emits action JSON.
2. Multiple deterministic and LLM validation layers inspect prose and action state sync.
3. Runtime frequently rejects or retries when the wording/action coupling is imperfect.

Strengths:

- stronger mechanical protection,
- tighter anti-drift safeguards,
- better hard-fail boundaries for dangerous contradictions.

Weaknesses:

- too many immersive-play failures,
- retry loops for legal/natural story turns,
- validator authority collisions,
- narrator freedom degraded by prose-policing.

### 4.3 Proposed gametest balance

Operational shape:

1. LLM narrates boldly and may still emit explicit action JSON.
2. Runtime infers compatible world deltas from narration plus explicit actions.
3. Python auto-commits legal world changes and only blocks true constitutional impossibility.

Strengths:

- keeps narrator freedom,
- adds stronger reconciliation than upstream,
- keeps harder mechanics than upstream,
- preserves the existing action schema as a preferred but not exclusive expression surface for soft world-state changes,
- reduces current retry-loop UX failures,
- creates a cleaner substrate for Titans/EGO later.

Tradeoff accepted:

- runtime becomes slightly smarter and more interpretive than upstream,
- but this is preferable to either extreme: full manual action-plumbing dependency or over-constrained deterministic prose policing.

### 4.4 Summary distinction

The target is not:

- upstream rollback,
- or deterministic script engine.

The target is:

- upstream's breathing room for the narrator,
- plus a stronger Python reconciler,
- plus the current build's hard mechanical constitution.

This plan should therefore be evaluated as a new balance point, not as a return to the old one.

---

## 5) Target operating model

## 5.1 Three-layer authority stack

### Layer A - Mechanical Constitution (Python, hard authority)

Hard-truth domains:

- character mechanical state,
- combat legality,
- graph-valid movement and module boundaries,
- inventory/resource conservation,
- schema-safe persistence,
- canonical durable party composition.

This layer MUST remain deterministic and fail-closed.

### Layer B - World Reconciler (Python, commit authority)

New runtime layer.

Purpose:

- infer narrator-declared world deltas,
- normalize them into safe state mutations,
- auto-commit compatible changes,
- request clarification only when ambiguity is real,
- reject only when constitution is violated.

Examples of reconciled deltas:

- travel progress,
- scene location commitment,
- NPC scene presence,
- NPC relocation,
- party NPC join/leave if clearly declared and identity-safe,
- time passage implied by travel or scene work,
- scene discoveries that should persist as world events.

### Layer C - Narrative Sovereignty (LLM, expressive authority)

The Narrator LLM remains free to:

- discover the world in motion,
- weave Titans/EGO pressure into scenes,
- improvise dialogue and atmosphere,
- create emergent social or mystery dynamics,
- establish soft canon in play,
- make binding narrative declarations as long as they do not violate Layer A.

This is where NEQ remains alive.

---

## 6) Chosen policy for narrated travel

User decision locked:

- If narration clearly indicates movement but not a precise canonical destination, runtime should preserve an in-transit/progress state rather than forcing a fake exact destination or failing the turn.

Operational contract:

1. If the narrator clearly commits arrival at a known reachable node, runtime SHOULD commit the location.
2. If the narrator clearly commits travel progress toward a known destination but not arrival, runtime SHOULD persist a soft in-transit/progress state.
3. If the narrator describes progress but the destination is not uniquely inferable, runtime SHOULD preserve current node, record travel-progress scene state, and ask for clarification only when needed.
4. If the narrator attempts impossible movement through disconnected topology, runtime MUST fail or reframe before commit.

This avoids both brittle hard-fail loops and fake precision.

---

## 7) Architectural components to introduce

### 7.1 Authoritative State Packet

Add a single canonical runtime packet assembled from Python state before each turn.

Suggested module:

- `utils/authoritative_state_packet.py`

Responsibilities:

- current module/area/location truth,
- connected reachable exits,
- current party roster,
- current party NPC roster,
- currently visible/nearby NPC presence,
- combat truth if active,
- active blockers and resolved hostile flags,
- current plot/side-quest gates,
- world clock and environmental facts,
- optional soft transit/progress metadata.

Rules:

- This packet MUST become the canonical machine-readable truth used by validators, reconcilers, and DM Note rendering.
- DM Note SHOULD become a human-readable rendering of this packet, not an independent truth assembly path.

### 7.2 World Delta Reconciler

Add a new reconcile-first runtime layer.

Suggested module:

- `utils/world_delta_reconciler.py`

Inputs:

- player input,
- assistant JSON,
- authoritative state packet,
- location graph and module data.

Outputs:

- inferred world deltas,
- normalized explicit actions,
- constitutional conflicts,
- ambiguity flags,
- advisory notes for narration/telemetry.

Delta classes should include at least:

- `travel_progress`
- `location_commit`
- `time_passage`
- `npc_scene_presence_add`
- `npc_scene_presence_remove`
- `npc_party_membership_add`
- `npc_party_membership_remove`
- `scene_fact`
- `plot_progress_hint`

### 7.3 Turn Event Ledger

Add a committed event layer for durable world/narrative facts.

Suggested module:

- `utils/turn_event_ledger.py`

Purpose:

- capture committed world events after reconciliation,
- provide a durable source for Titans/EGO background pressure,
- reduce dependence on freeform history as pseudo-state,
- support future memory and world-evolution systems.

Possible event types:

- `party_traveled`
- `travel_progressed`
- `npc_entered_scene`
- `npc_left_scene`
- `npc_joined_party`
- `npc_left_party`
- `scene_discovery`
- `threat_revealed`
- `foreshadowing_established`
- `combat_started`

### 7.4 Narrative Render Contract

Narration shown to the player should ultimately reflect:

- committed world deltas,
- post-commit authoritative state,
- live LLM expressive prose.

Long term, the best end-state is:

1. Narrator proposes reality.
2. Reconciler commits legal truth.
3. Final visible narration is guaranteed compatible with committed truth.

This does not necessarily require a second LLM call in the first implementation slice. It does require runtime ownership of final compatibility.

---

## 8) What stays hard-fail vs what becomes soft-reconcile

### 8.1 Hard-fail domains (MUST remain constitutional)

- HP/slot/condition contradictions
- impossible combat sequencing
- illegal actor/target/mechanics states
- inventory/resource underflow
- impossible graph jump or illegal module transition
- malformed persistence payloads
- unresolved NPC/character identity ambiguity that would commit wrong canon
- schema or file integrity risk

### 8.2 Soft-reconcile domains (SHOULD stop causing retry loops)

- narrated travel progress
- narrated approach to destination
- soft scene relocation and traversal framing
- NPC off-screen movement compatible with current world graph/context
- NPC scene presence if canon-compatible
- ambient discoveries and scene facts
- foreshadowing and world-emergent hints
- implied time passage from legal scene activity

### 8.3 Clarification-only domains

Runtime SHOULD ask for clarification instead of hard-failing when:

- multiple valid travel destinations fit the narration equally,
- NPC identity resolution is ambiguous among canon entities,
- the scene implies a commitment that could validly map to several world states,
- narrator prose is too soft to commit durable canon safely.

---

## 9) Existing systems to refactor, not expand

The goal is to reduce bandaids, not add more.

### 9.1 `main.py`

Current role is over-centralized.

Future role should become:

1. build authoritative packet,
2. get assistant output,
3. run world delta reconciler,
4. run constitutional checks,
5. commit normalized actions/deltas,
6. emit final output and append event ledger.

The following current behaviors should be narrowed or retired:

- reject-first travel sync loops,
- reject-first NPC arrival loops,
- LLM validator re-litigating deterministic state-sync domains,
- override battles between deterministic and LLM validation.

### 9.2 `utils/travel_state_sync_guard.py`

Refactor from hard rejection into travel reconciliation logic.

New purpose:

- infer location commit vs in-transit progress,
- enforce topology only at constitutional boundary,
- ask for clarification only when exact destination cannot be safely inferred.

### 9.3 `utils/npc_arrival_validator.py`

Refactor from arrival-policing into NPC presence reconciliation.

It should distinguish:

- foreshadowed NPC,
- scene-present NPC,
- relocated background NPC,
- joined-party NPC,
- ambiguous identity requiring clarification.

### 9.4 `utils/multi_pc_dm_note.py`

Refactor so DM Note is derived from authoritative packet rather than acting as a second state reconstruction system.

### 9.5 `core/ai/action_handler.py`

Refactor to accept normalized/inferred deltas from reconciler as first-class inputs.

Explicit LLM actions remain useful, but they should no longer be the only legal path for soft world-state commitment.

---

## 10) Titans / EGO compatibility

This plan is intentionally designed to support Titans/EGO.

### 10.1 Desired future role

Titans/EGO should be able to:

- evolve background world pressure,
- activate factions/NPC agendas,
- introduce omens and narrative drift,
- project long-running world consequences,
- produce candidate world deltas or event pressure.

### 10.2 Required boundary

Titans/EGO MUST NOT force runtime into a brittle deterministic content engine.

Instead:

- Titans/EGO can propose background world movement,
- the Narrator can discover or invoke that movement in live play,
- Python can reconcile/commit compatible deltas,
- mechanics remain constitutionally enforced.

### 10.3 Why this architecture fits Titans

The event ledger and world reconciler create a clean handoff:

- Titans/EGO create background pressure,
- Narrator expresses or discovers it,
- Python commits safe outcomes.

That is a much better fit than adding more validator language to one giant monolithic narrator prompt.

---

## 11) Staged implementation strategy

This work should be split into staged OpenSpec changes rather than one giant build.

Recommended order:

### Stage A - Runtime packet foundation

Goal:

- create the authoritative state packet,
- centralize truth sources,
- make existing DM Note and validators consume the same packet.

Expected impact:

- reduces truth duplication,
- gives later builder stages a stable contract.

### Stage B - Travel reconcile-first conversion

Goal:

- replace reject-first travel validation with inference + constitutional enforcement,
- add in-transit/progress state support,
- stop narrated travel from failing when mechanically legal.

Expected impact:

- fixes the most visible gameplay UX failures quickly.

### Stage C - NPC presence reconcile-first conversion

Goal:

- convert arrival-sync policing into scene-presence reconciliation,
- distinguish foreshadowing, scene presence, and durable party membership.

Expected impact:

- removes recurring arrival-state retry loops,
- restores freedom for world-facing narration.

### Stage D - Validator deconfliction

Goal:

- narrow LLM validator authority,
- stop re-litigating domains already reconciled by Python,
- simplify retry loop behavior.

Expected impact:

- fewer contradictory reject/override paths,
- cleaner authority boundaries.

### Stage E - Event ledger and Titans readiness

Goal:

- persist committed world/narrative events,
- provide a substrate for Titans/EGO world evolution.

Expected impact:

- better long-term memory and background world evolution support.

### Stage F - Prompt contract simplification

Goal:

- update prompt and validation language to reflect reconcile-first runtime,
- remove brittle exact-action wording for soft world-state changes,
- keep hard-action requirements for mechanical domains.

Expected impact:

- prompt stack becomes simpler and more aligned with runtime reality.

### 11.1 Minimum gametest slice (OpenSpec-to-builder)

This is the recommended builder-facing execution subset for the GitHub-fork gametest release.

The goal is NOT to implement the entire architecture program before testers arrive.
The goal is to recover immersive gameplay quickly while preserving the intended long-term direction.

#### Gametest execution rule

Builder should implement the minimum slice as a staged OpenSpec program with mandatory pause-and-review gates after each change.

#### Change sequence for the minimum slice

##### Change G1: `narrative-sovereignty-state-packet-foundation`

Builder target:

- introduce the thinnest useful `AuthoritativeStatePacket` foundation,
- wire current validation and DM Note assembly to the same truth surface where practical,
- avoid any broad rewrite of all validation domains.

MUST scope:

- create a minimal packet builder for current location/module/party/NPC/topology truth,
- expose packet data to travel and NPC reconciliation paths,
- preserve current action schema and current gameplay flow,
- avoid Titans/event-ledger scope.

SHOULD guidance:

- keep the packet intentionally narrow for gametest,
- prefer additive helpers over moving large blocks in `main.py` on the first pass,
- preserve existing APIs where possible.

Expected files:

- new `utils/authoritative_state_packet.py`
- `main.py`
- `utils/multi_pc_dm_note.py`

Verification gate:

- packet builds from current runtime state without breaking current turns,
- DM Note still renders correctly,
- no behavior regression in non-travel/non-NPC turns.

##### Change G2: `travel-reconcile-first-autocommit`

Builder target:

- replace reject-first travel sync behavior with reconcile-first travel commit logic,
- support the chosen in-transit/progress state when destination is not yet exact,
- preserve hard fail-closed behavior for impossible topology.

MUST scope:

- legal narrated movement may auto-commit location or in-transit progress,
- impossible travel remains blocked,
- ambiguous travel may clarify but SHOULD NOT enter brittle retry loops,
- retain backward compatibility for explicit `transitionLocation` action flow.

SHOULD guidance:

- reuse existing transition graph/path infrastructure,
- prefer additive normalization and reconciliation over deleting old paths immediately,
- keep transcript-driven regression tests close to the failure transcripts that motivated the change.

Expected files:

- `main.py`
- `utils/travel_state_sync_guard.py`
- `core/managers/location_manager.py`
- `core/ai/action_handler.py`

Verification gate:

- narrated legal travel from current gametest transcripts no longer hard-fails,
- in-transit/progress state is persisted when arrival is not exact,
- same-location and impossible-jump protections remain intact.

##### Change G3: `npc-scene-presence-reconcile-first` (completed in gametest slice)

Builder target:

- this change was initially conditional,
- it was implemented before tester invite because post-G2 review still justified it.

MUST scope:

- convert the worst arrival/presence loops into reconcile-first behavior,
- preserve identity safety and ambiguity clarifiers,
- do not broaden into full Titans-ready event semantics yet.

Expected files:

- `main.py`
- `utils/npc_arrival_validator.py`
- `core/ai/action_handler.py`

Verification gate:

- foreshadowing stays legal,
- compatible scene presence no longer hard-fails,
- ambiguous NPC identity still does not silently commit wrong canon.

#### Explicit deferrals for the gametest slice

The following SHOULD be deferred until after testers are playing unless a blocking bug forces earlier work:

- full event ledger,
- Titans/EGO runtime integration,
- broad prompt reset,
- planner/narrator split,
- non-essential combat architecture changes.

Deferred items now belong to the version-2 continuation plan at `plans/version-2/narrative-sovereignty-post-gametest.md`.

#### Builder stop points

Builder should stop after each of the following and wait for review:

1. G1 complete and verified
2. G2 complete and verified
3. Reassess live gametest transcripts
4. Only then decide whether G3 is still required before tester invite

#### Success bar for the minimum slice

The minimum slice is successful if:

- immersive travel play resumes without repeated Python interruption,
- soft world-state narration no longer constantly collapses into retry loops,
- mechanics remain trustworthy,
- the runtime balance is visibly closer to "narrator breathing room plus stronger reconciliation" than either upstream fragility or current over-constraint.

### 11.2 OpenSpec-to-builder handoff rules for this plan

For this specific plan, builder prompting should follow these rules:

1. Treat Lane 1 as the active build lane and Lane 2 as deferred architecture.
2. Never combine G1, G2, and G3 into one mega-change.
3. Every change MUST include transcript-based regression coverage for the motivating bug family.
4. Every change MUST include compile verification for touched Python files.
5. Every change MUST preserve the current JSON/action schema surface unless there is a narrowly justified compatibility-safe extension.
6. Every change MUST preserve hard constitutional mechanics while relaxing only soft world-state rejection behavior.
7. Builder should prefer additive runtime reconciliation over prompt-only fixes.

---

## 12) Recommended OpenSpec change breakdown

These are suggested staged changes suitable for builder execution.

### Change 1: `narrative-sovereignty-state-packet-foundation`

Purpose:

- introduce canonical authoritative state packet,
- make DM Note and validators consume it.

Primary files likely affected:

- `main.py`
- `utils/multi_pc_dm_note.py`
- new `utils/authoritative_state_packet.py`

Key verification:

- packet accurately reflects current world state,
- DM Note parity preserved,
- existing gameplay does not regress.

### Change 2: `travel-reconcile-first-autocommit`

Purpose:

- convert travel from reject-first to reconcile-first,
- add in-transit/progress state.

Primary files likely affected:

- `main.py`
- `utils/travel_state_sync_guard.py`
- `core/managers/location_manager.py`
- `core/ai/action_handler.py`

Key verification:

- legal narrated travel auto-commits,
- ambiguous travel asks clarifier,
- impossible travel still fails closed.

### Change 3: `npc-scene-presence-reconcile-first`

Purpose:

- convert NPC arrival validation into presence reconciliation.

Primary files likely affected:

- `main.py`
- `utils/npc_arrival_validator.py`
- `core/ai/action_handler.py`

Key verification:

- foreshadowing does not force movement,
- scene-compatible NPC presence can auto-commit,
- ambiguous NPC identity remains safe.

### Change 4: `validator-authority-deconfliction`

Purpose:

- stop LLM validator from vetoing already-reconciled state domains,
- simplify retry logic.

Primary files likely affected:

- `main.py`
- validation prompts
- `utils/validation_routing.py`

Key verification:

- no deterministic-vs-LLM override battles remain for reconciled domains,
- retry loops are reduced.

Current status note:

- runtime foundation is now in place: domain-scoped deterministic handoff, generic deconfliction, telemetry fields for suppressed vs remaining domains, and prompt/retry closeout.
- Change 4 is complete for the gametest lane and archived; future follow-on work should build on the archived G4 contract rather than reopening this slice.

### Change 5: `turn-event-ledger-titans-ready`

Purpose:

- introduce committed event ledger for world and narrative facts.

Primary files likely affected:

- new `utils/turn_event_ledger.py`
- `main.py`
- selected action/commit paths

Key verification:

- committed events are durable,
- event stream is suitable for future Titans/EGO consumption.

Current status note:

- deferred from the gametest lane,
- promoted to the version-2 continuation plan at `plans/version-2/narrative-sovereignty-post-gametest.md`,
- intended to execute before OpenRouter router re-architecture.

### Change 6: `prompt-contract-reconcile-first-reset`

Purpose:

- align prompts with new runtime philosophy.

Primary files likely affected:

- `prompts/system_prompt_compressed.txt`
- `prompts/system_prompt.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`

Key verification:

- prompt language no longer over-requires explicit action plumbing for soft world changes,
- hard mechanics contract remains strict.

Current status note:

- partially advanced indirectly by G4 validation prompt updates,
- still open as a broader system-prompt/runtime philosophy cleanup,
- promoted to the version-2 continuation plan at `plans/version-2/narrative-sovereignty-post-gametest.md`,
- intended to execute before OpenRouter router re-architecture.

---

## 13) Builder-oriented execution notes

For OpenSpec builder work, each change should follow these execution principles:

1. Prefer narrow, verifiable slices over broad rewrites.
2. Introduce new modules before replacing old logic.
3. Preserve backward compatibility during intermediate stages.
4. Add transcript-based regression tests for each bug family.
5. Treat current reject-first validators as migration targets, not sacred contract.
6. Verify every touched Python file with `python3 -m py_compile`.
7. Mark host-file integration points with `# TABLETOP MODE:` comments.
8. Keep all new Python strings ASCII-only.

Suggested builder workflow per change:

1. scaffold OpenSpec change,
2. define MUST/SHOULD contract,
3. implement one stage,
4. add transcript-based regressions,
5. verify compile and behavior,
6. stop for review before next stage.

---

## 14) Verification strategy

Success should be measured in UX terms, not just validator pass counts.

### 14.1 Core positive tests

- Narrated legal travel without explicit `transitionLocation` can still commit successfully.
- Narrated travel progress without exact arrival persists in-transit/progress state.
- Narrated compatible NPC scene presence no longer causes retry loops.
- Narrator can foreshadow off-location NPCs without false arrival failures.
- DM Note, validator context, and persistent state agree after commit.

### 14.2 Hard safety tests

- Impossible topology still fails closed.
- Illegal HP/slot contradictions still fail closed.
- Ambiguous NPC identity still requires clarification.
- Combat legality remains deterministic.

### 14.3 UX acceptance bar

The player should experience:

- fewer dead-end retries,
- fewer invisible state desyncs,
- more natural DM narration,
- no major loss of trust in mechanical accounting.

---

## 15) Risks and mitigations

### Risk 1: Over-committing soft narration into wrong canon

Mitigation:

- use clarification path for ambiguous identity/destination,
- commit only high-confidence deltas automatically,
- preserve in-transit soft state instead of forcing exact node.

### Risk 2: Reconciler becomes another brittle rule jungle

Mitigation:

- keep reconciler domain-limited,
- use state packet and graph truth directly,
- do not rebuild giant prose regex systems.

### Risk 3: Hidden regression in existing action paths

Mitigation:

- preserve explicit action paths as first-class supported inputs,
- implement additive path first, then narrow old validators later.

### Risk 4: Titans/EGO integration creates second competing authority

Mitigation:

- keep Titans/EGO as background pressure and delta proposal source,
- require narrator + reconciler + constitution to mediate live commitment.

---

## 16) First recommended implementation slice

If only one change starts now, start with:

- `travel-reconcile-first-autocommit`

Reason:

- travel desync is the most visible recurring UX pain,
- it is the clearest proof of the new philosophy,
- it exercises the chosen `in transit / progress toward X` rule,
- it can be built before the full Titans/event-ledger work.

However, if implementation discipline is preferred, then do:

1. `narrative-sovereignty-state-packet-foundation`
2. `travel-reconcile-first-autocommit`

That is the safer sequence.

This first slice should explicitly preserve the intended balance:

- not upstream rollback,
- not deterministic script engine,
- but narrator breathing room plus stronger reconciliation plus hard mechanics.

---

## 17) Review checklist

Before implementation, confirm that this plan preserves the intended product identity:

1. The Narrator LLM remains a true DM and world-explorer.
2. Python remains the mechanical constitution, not the storyteller.
3. Soft world-state narration is reconciled and auto-committed when legal.
4. Hard mechanics remain deterministic and trustworthy.
5. Titans/EGO gains a future-compatible world-evolution lane.
6. NEQ remains exciting because the LLM is still the wildcard, not a clerk.
7. The gametest slice does not merely return to upstream looseness; it surpasses upstream by adding reconcile-first runtime behavior.

If these seven statements remain true, the architecture is moving in the right direction.
