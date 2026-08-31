# Complete Agentic Combat Design

Consolidated review draft v8 — complete replacement for v7 and every earlier fragmented combat design screen.

> **Design stage only.** This document is not an implementation plan and authorizes no production-code change, implementation planning, merge, rollout, or activation. It preserves all accepted v7 content while resolving the atomic acceptance-claim, gameplay-mutation staging, Load/Reset supersession, completion/controller, post-roll dependency, and correction-output contradictions found in the v7 review. Planning remains blocked until the owner approves this complete document and later separately approves a converged implementation plan.

## Future planning and implementation method

Design horizontally for lifecycle completeness; implement vertically for integrated truth.

Every workflow lane must first be mapped horizontally across its complete lifecycle:

```text
authoritative inputs → disclosure-safe projection → proposal → reconciliation
→ acceptance → freeze → persistence → execution → commit → publication
→ restart/recovery → next-cycle feedback
```

This horizontal analysis ensures that no lane is treated as complete merely because its prompt returns valid output. Each lane must define its authority, consumers, persistence boundary, correction loop, interruption behavior, and contribution to the next combat cycle.

Implementation must then proceed through narrow, playable vertical slices. Each slice crosses every required semantic, mechanical, persistence, recovery, narration, and player-interaction boundary needed for one real scenario. Do not implement all agents first, all mechanics second, or all persistence last and attempt integration afterward.

Representative vertical slices include:

1. Encounter activation → accepted participants/controllers → initiative → one non-player attack → commit → narration → restart.
2. Human action → player-owned roll → resolution atoms → state commit → next actor.
3. Companion perspective → independent tactic → mechanics → voice → published narration → attributed memory → next turn.
4. Multiattack → target defeated after one atom → same controller chooses remaining action → turn finalization.
5. Shield or another reaction → durable trigger and roll → player response → crash/restart → exact continuation.
6. Nested Counterspell → child-frame unwind → costs and effects committed once → replayable delivery.
7. Surrender, escape, defeat, or victory → accepted completion → consequences/rewards → narration → archive → main-DM handoff.

A swimlane is complete only when a real vertical slice consumes it through the unmodified game, its authoritative files prove the correct mutation, interruption and restart preserve the workflow, player-visible output is truthful, and the committed result feeds the next cycle.

The future implementation plan must therefore maintain a two-dimensional coverage matrix:

| Swimlane | Complete horizontal lifecycle | First vertical slice using it | Failure/restart proof | Next-cycle consumer |
|---|---|---|---|---|
| Each approved lane | Inputs through recovery and feedback | Named playable scenario | Named crash/restart boundary | Exact downstream lane or next turn |

Transaction-level prompt evaluation remains preparatory evidence only. No horizontal lane or vertical slice passes final acceptance without real provider-backed headless/browser play and authoritative persisted-file inspection.

Planning, implementation, schema changes, and production edits remain blocked until the complete design is approved and the owner separately authorizes a converged implementation plan.

## Contents

1. [Provenance and purpose](#1-provenance-and-purpose)
2. [Player experience and non-negotiable behavior](#2-player-experience-and-non-negotiable-behavior)
3. [C4 architecture](#3-c4-architecture)
4. [Authority partitions](#4-authority-partitions)
5. [Fresh Actor-State Assembly](#5-fresh-actor-state-assembly)
6. [Complete workflow lanes](#6-complete-workflow-lanes)
7. [Mechanical and SRD boundary](#7-mechanical-and-srd-boundary)
8. [Reaction and resumable-continuation workflow](#8-reaction-and-resumable-continuation-workflow)
9. [Transaction, commit, completion, and narration](#9-transaction-commit-completion-and-narration)
10. [Existing persistence and recovery](#10-existing-persistence-and-recovery)
11. [Current-stage and crash-boundary map](#11-current-stage-and-crash-boundary-map)
12. [Failure, correction, retry, and liveness semantics](#12-failure-correction-retry-and-liveness-semantics)
13. [Schema, legacy, and rollout safeguards](#13-schema-legacy-and-rollout-safeguards)
14. [Prompt and provider development](#14-prompt-and-provider-development)
15. [Real acceptance matrix](#15-real-acceptance-matrix)
16. [Owner gates](#16-owner-gates)
17. [Non-goals and stop conditions](#17-non-goals-and-stop-conditions)
18. [Review gate](#18-review-gate)

## 1. Provenance and purpose

Compatibility authority comes only from approved mainline behavior. NPC personality, attributed memory, and voice continuity are explicit owner-mandated target capabilities. Unmerged branch implementations may be inspected as prototypes but do not define required behavior.

Only ancestors of the live `origin/main` tracking ref define shipped behavior. Aborted, parked, unmerged, non-ancestral, worktree-only, or locally documented combat work is archaeology. It may reveal ideas or failure modes, but it cannot establish a compatibility promise or silently supply a missing requirement.

The design goal is to recover the elegant original turn-based player experience while retaining valuable mainline additions: canonical combatant IDs, deterministic initiative bookkeeping, typed intents and events, code-owned arithmetic, state revisions, staged recovery, replay-safe narration delivery, effects, XP receipts, archive behavior, and combat-to-main-DM handoff.

The missing seam is semantic. Models must establish scene facts, actor perspectives, tactical intent, contextual rulings, and completion meaning in structured form. Code must reconcile those proposals against fresh canonical state and own the paper tracker, exact arithmetic, resource conservation, ordering, persistence, and recovery. Code must not answer semantic questions from entity `type`, faction defaults, names, prose, regexes, or scenario-specific conditions.

## 2. Player experience and non-negotiable behavior

### Human player authority

- The human chooses the player character’s actions. The game never replaces the player’s stated goal with a mechanically preferred action.
- Improvised actions, dialogue, movement, surrender, object interaction, and environmental actions are valid intents alongside named attacks, spells, items, and features.
- The player rolls their own attacks, damage, checks, saving throws, and other player-owned dice after the game asks for one exact roll.
- **Initiative is not included in that promise in this draft.** Approved mainline currently generates player initiative automatically. Player-rolled initiative is an explicit owner gate with its own encounter-opening, persistence, duplicate-answer, and restart design if approved.
- Quick Roll displays dice only. It does not submit a result into the game. The player must provide the result through the normal player-input path.
- The game asks one focused question only when missing information prevents truthful resolution.
- Out-of-turn player intent is acknowledged and deferred, not discarded or executed in the wrong turn window.

### Non-player actor authority

- Companions, NPCs, monsters, summons, and other DM-controlled actors choose their own actions through their isolated agentic lanes.
- Companions preserve personality, voice, memory, resources, abilities, spells, tactics, and XP eligibility.
- A companion may ask the player for guidance in character. The player is never required to play the companion.
- Code supplies exact initiative order. It never chooses a non-player action, target, surrender, recruitment response, allegiance, or fallback tactic.

### Turn-based presentation

- Combat opens as a scene, not a mechanics dump.
- Higher-initiative non-player turns resolve in order and may be narrated together as one cinematic exchange.
- The initiative window stops exactly at a human-controlled actor.
- Reactions, saves, rolls, and choices pause at the actual decision point and resume the exact continuation.
- A completed player action closes the appropriate remaining actor window without repeated “keep going” prompts.
- The player is addressed in second person.
- Party defeat is an explicit non-victory state with named recovery options. A dead or unconscious player character is never asked for another ordinary combat command.

### Outcome integrity

- Victory, defeat, surrender, escape, negotiation, unresolved departure, phase change, and continuing combat are distinct outcomes.
- Completion consumes accepted objectives, relations, participation, and committed survival state. It never derives victory from source kind, `type`, or faction defaults.
- Defeat, surrender, escape, and unresolved departure never use the victory finalizer or receive victory rewards unless the accepted outcome explicitly makes a reward eligible.
- Committed mechanics, rewards, world consequences, and relationship transitions do not depend on successful browser observation.

## 3. C4 architecture

### Level 1 — System context

```text
Human player
  -> Browser / terminal / headless client
  -> NeverEndingQuest combat runtime
  <-> Configured OpenAI-compatible provider or Gemma through LM Studio
  <-> Authoritative campaign files
  -> Ordered replayable player-visible feed
  -> Main DM continuation
```

The model provider supplies semantic proposals and narration. The runtime constructs every disclosure-safe prompt projection, validates the proposal’s encounter/turn/revision identity, owns mechanics, and persists committed state. Campaign files—not narration, memory, UI state, or stale prompts—are authoritative.

### Level 2 — Containers

| Container | Responsibility | Explicit non-responsibility |
|---|---|---|
| Agentic orchestration | Invokes small scene, perspective, tactic, ruling, completion, narration, and memory transactions | Agents never invoke other agents, advance workflow stages, mutate files, or publish output |
| Fresh Actor-State Assembly | Reloads canonical and encounter-instance sources and derives revision-bound effective actor projections | Does not infer relationships, intentions, or unrepresented geometry |
| Disclosure firewall | Builds the minimum code-approved projection for each model call | Does not send full state and ask the model to ignore secrets |
| Mechanical kernel | Initiative bookkeeping, roll ownership, exact values, arithmetic, resources, effects, legality where represented, typed events | Does not choose tactics, relationships, objectives, contextual rulings, or unsupported geometry |
| Existing `combatState` coordinator | Owns the only authorized next transition, pending interaction, staged/committed identity, narration publication, completion receipts, and recovery state | Is not a new store, WAL, generic workflow engine, or global startup gate |
| Existing persistence | Encounter JSON, canonical character/world files, full active conversation, player-visible archive, party tracker | Narration and memory never reconstruct mechanics |
| Delivery and UI | Publishes stable output through a replayable ordered feed and displays authoritative state | “Player observed this” is generally unknowable and is not state authority |

### Level 3 — Component flow

```text
Fresh Actor-State Assembly
  -> Scene foundation proposals
  -> Canonical reconciliation
  -> Accepted scene facts + disclosure grants committed with activation
  -> Stable initiative ledger / exact actor window
  -> Per-actor perspective and tactical proposal
  -> Contextual ruling and represented-legality reconciliation
  -> Accepted resolution input frozen before randomness/reservation
  -> Parent turn advances through one or more resolution atoms
  -> Durable trigger/roll and resumable roll/reaction/choice frames when required
  -> Complete owned mutation atom staged
  -> Crash-convergent atom application
  -> Atom receipt written last; turn cursor advances only after every atom closes
  -> Completion proposal only from fully settled committed state
  -> Completion/rewards/consequences committed exactly once
  -> Narration retained
  -> Narration published to replayable player feed
  -> Archive, attributed memory, cleanup, and main-DM handoff
```

### Level 4 — Intended ownership

| Mainline area | Target ownership |
|---|---|
| Adventure DM / encounter commitment | Semantically proposes encounter scene and participant references |
| Encounter builder / reconciler | Materializes reconciled canonical identities; never classifies allegiance from list/type |
| `combat_state.py` | Existing operational coordinator: revision, phase, stable initiative ledger, turn/window, pending interaction, accepted resolution input, staged/applied IDs, narration publication, completion |
| `combat_orchestrator.py` / manager | Invokes transactions in the only authorized order; validates returned encounter/turn/revision/window; no prose-derived roll topology or tactical fallback |
| T096-equivalent intent lanes | Actor-specific semantic intent and contextual requests |
| Ruling/referee lanes | Contextual SRD interpretation, scene coherence, player-agency checks, semantic transition support |
| Pipeline/resolver/rolls/events | Represented legality, exact values, roll ownership, arithmetic, resources, effects, typed events |
| Transaction layer | Stage, value-level before/after reconciliation, atomic individual writes, receipt/cursor last, crash convergence |
| T097-equivalent narrator | Narrates only committed facts and accepted outcome |
| Conversation/archive/memory | Published player history and attributed continuity, never mechanics |

## 4. Authority partitions

There is no undifferentiated scene packet. Every transaction receives only the projection it needs.

### 4.1 Authoritative State

Canonical files, canonical source references, stable combatant IDs, character sheets, monster source sheets, encounter-instance state, equipment, form, HP, resources, conditions, effects, initiative, action economy, revisions, and committed typed events.

### 4.2 Workflow Execution State

This is a code-owned partition inside the existing encounter JSON’s `combatState`. It is the operational coordinator, not a new persistence family.

It owns:

- Encounter revision and phase.
- Stable initiative ledger, current window, and turn identity.
- Accepted current controller for every participant, including the controller revision and any temporary expiry.
- The only authorized next transition.
- Pending player roll, reaction, save, choice, answer owner, and continuation.
- Accepted resolution input once it must be frozen.
- Parent-turn state, resolution-atom cursor, nested interaction frames, staged events, reservations, and roll consumption.
- Applied atom, turn, and event identities.
- Retained narration and publication state.
- Completion, reward, summary, archive, and closure state.

Agents return untrusted proposals. They never call another agent, select the next stage, write files, advance initiative, reserve resources, apply events, or publish output. Every response must match the active encounter, expected revision, exact turn, actor window, authorized logical invocation, and mechanics-affecting dependency projection before acceptance. A stale, late, duplicate, or superseded response cannot mutate state.

The nonoptional acceptance invariant is: **at most one provider response may be accepted for one logical invocation, and no pre-Load/Reset response may commit afterward.** The execution structure is owner-selectable:

- **Serialized structure:** no replacement begins until the earlier attempt has genuinely completed or been cancelled. Encounter/turn/revision checks are sufficient only while overlap is structurally impossible.
- **Overlapping/off-thread structure:** every attempt has a unique invocation generation or equivalent authority. Only the currently authorized generation may be accepted. Load/Reset invalidates every pre-restore generation even when restored state recreates the same encounter/turn/revision tuple. Revalidation occurs immediately before freezing or staging.

Immediately before acceptance, code acquires the campaign-scoped mutation authority and atomically verifies the active encounter, turn, window, revision, invocation authority, mechanics-dependency values, and authorized next transition. It then claims that transition and freezes the accepted result before releasing the authority. A second response cannot pass the same claim. The concrete lock, cancellation, or invocation-generation mechanism remains owner-gated; the atomic claim does not.

This design does not choose the concrete cancellation or invocation-generation mechanism. It does not automatically add fencing tokens, hashes, worker leases, or a global epoch; those remain under D-1/D-8 and owner approval.

This design does **not** automatically add projection hashes, complete read-set hashes, prompt-version authority, worker leases, fencing tokens, generic timeout/failure state machines, or another marker family. Exact additional `combatState` fields remain owner-gated.

### 4.3 Accepted Scene Facts

Revision-bound presence, participation, controller grants, relationships, sides, disposition, objectives, observable positioning, entry/removal proposals, and disclosure grants reconciled to canonical IDs. Initial accepted facts commit into the encounter with activation before initiative consumes them. Mid-combat changes commit as typed semantic-transition atoms before targeting, initiative, disclosure, or completion uses the changed fact. Recovery reloads them from encounter state, never narration.

The accepted current controller is operational authority inside Workflow Execution State. Its initial value comes from explicit canonical ownership or an accepted encounter control grant, never entity type. Relationship, faction, charm, betrayal, surrender, or recruitment never changes controller implicitly. A controller transition is its own accepted semantic atom with actor ID, before/after controller, cause, scope, expiry when temporary, expected revision, and required player consent. Temporary expiry checks the current controller revision, and completion consequences cannot bypass this lane.

### 4.4 Actor Perspectives

One actor’s beliefs, memories, personality, goals, private knowledge, and current perceptions. Perspectives are attributed and isolated. They may be mistaken. They are never world truth or mechanics.

### 4.5 Player-Control State

Exact player input, deferred intent, pending roll/reaction/save/choice, answer ownership, duplicate/conflicting answers, and the exact unresolved continuation.

### 4.6 Narration states

- **Retained:** stable narration stored for replay but not yet part of player history.
- **Published:** durably appended to the ordered replayable player-visible feed.
- **Observed:** whether the player actually saw it. This is usually unknowable and is never state authority.

Only published narration enters narrative history, the player-visible transcript, and actor-memory extraction. Retained-but-unpublished narration may be replayed but must not be remembered as publicly spoken or seen.

### 4.7 Disclosure firewall

Code constructs every model projection from three separate inputs:

1. Canonical facts the lane is authorized to use.
2. Accepted observation/disclosure grants for the receiving actor or lane.
3. That actor’s attributed beliefs and memories.

The perception lane receives only minimum candidate facts and secrecy metadata. It proposes what an actor can observe; its output is not actor-visible until code validates the referenced disclosure grants. Code then constructs the actor-specific projection. Beliefs may be wrong; disclosure grants control which canonical facts the actor can access. Models never receive the full state with a prose instruction to ignore secrets.

Every committed event that may alter visibility—including movement, entry, doors, light, invisibility, revelation, effects, or reactions—invalidates affected grants. Before the next tactic, reaction, correction, or narration call, code rebuilds or minimally revalidates the affected projections. Revision-stale grants are unusable. Shared `combat_conversation_history.json` contains only appropriate shared prompt/interaction continuity; it must not leak private actor perspectives, internal rulings, or correction prompts. Lane-internal context is isolated, filtered, or stateless, and published shared dialogue remains distinct from private lane history.

## 5. Fresh Actor-State Assembly

Fresh Actor-State Assembly runs before Scene Foundation, before every turn, after every commit, and on recovery before accepting new semantic work.

### Inputs

- Fresh player and canonical NPC character files.
- Canonical monster source sheets.
- Committed per-monster encounter-instance state.
- Equipment, current form, conditions, and effects.
- Current encounter revision.

### Source rules

| Actor category | Persistent/base authority | Encounter-instance authority |
|---|---|---|
| Player | Canonical character file | Combatant ID, initiative/turn cursor, encounter-only status required by the active fight |
| Canonical NPC | Canonical NPC character file | Combatant ID, initiative/turn cursor, encounter-only status required by the active fight |
| Monster | Canonical monster source sheet | Instance HP, status, effects, initiative, acted state, and encounter-local resources represented there |
| Summon/hazard/other | Owner-approved canonical or encounter source | Instance state exactly as represented by the accepted encounter contract |

### Effective-state derivation

```text
canonical base source
+ committed equipment
+ current form
+ committed conditions and effects
+ represented rules facts
= revision-bound effective combat state
```

Code derives authoritative AC, modifiers, represented resources, restrictions, resistances, and available represented capabilities from those sources. This addresses the observed AC/effect regression without expanding into a comprehensive hardcoded 5e rules engine.

Stale prompt copies, narration, archives, summaries, and memory cannot supply mechanics. Every projection records the encounter revision it was assembled against. After any commit, the next transaction reloads sources rather than carrying forward a prompt-era copy.

## 6. Complete workflow lanes

Every semantic lane follows:

```text
PROPOSED -> RECONCILED -> ACCEPTED
                    -> FROZEN before randomness/reservation when mechanics-affecting
                    -> STAGED as a complete owned resolution or semantic-transition atom
                    -> APPLIED when owned values converge
                    -> COMMITTED when the atom receipt converges
                    -> RETAINED / PUBLISHED for player-visible narration
```

Initial scene facts do not remain prompt context. Presence, participation, relationships, initial controller grants, objectives, and disclosure grants commit with encounter activation before initiative reads them. Later entry, departure, betrayal, charm, surrender, recruitment, controller, objective, and visibility changes use typed semantic-transition atoms. Each transition carries canonical IDs, expected revision, and owned before/after facts, and commits before downstream targeting, initiative, disclosure, or completion consumes it. Beliefs, motives, and private thoughts remain attributed perspectives rather than semantic world state.

### A. Fresh state and scene foundation

| Lane | Inputs | Agent responsibility | Code responsibility | Output/correction |
|---|---|---|---|---|
| Fresh Actor-State Assembly | Fresh canonical and instance sources plus revision | None | Produce disclosure-safe, revision-bound effective projections | Feeds Scene Foundation and repeats before every turn |
| Identity and persistence | Canonical sources plus proposed participant reference | Identify intended display identity and scene role | Resolve source reference, source kind, stable combatant ID, and persistence destination | Source, display, participation, controller, relationship, and persistence remain separate facts |
| Physical presence | Location/world state, reconciled identities, explicit scene input | Propose who is physically present, entering, or leaving | Verify canonical IDs and revision | Presence never implies initiative participation |
| Participation and perception | Presence, relations, objectives, physical circumstances | Propose active, observing, hidden, unaware, entering/leaving, initiative eligibility, and observable facts | Reconcile IDs and represented visibility/position facts; establish disclosure grants | Revision-bound eligible set and per-actor disclosure grants |
| Relationships and sides | Participants, accepted history, current dialogue, objectives | Propose ally/hostile/neutral relations, disposition, recruitment, betrayal, charm, surrender, and side changes | Verify referenced IDs/revision; never infer from type/faction/name | Accepted relationship graph; no implicit controller change |
| Controller transition | Accepted actor/relationship facts, authoritative current controller, and explicit proposed control change | Propose a control transfer when semantically intended | Require actor ID, before controller, after controller, cause, scope, expiry if temporary, expected controller revision, and required player consent; commit it as a distinct semantic-transition atom | Current controller changes only through this transition; relationship/faction/charm/betrayal/recruitment never changes it implicitly |
| Objectives and phase | Participants, relations, plot stakes, actor-visible facts | Propose defend/capture/escape/negotiate/surrender/defeat/other objectives and phase | Verify references and revision only | Accepted objectives feed tactics and completion |
| Environment and positioning | Observable terrain, represented positions, hazards, doors, obstacles, objects | Propose semantic movement, range/reach, cover, and interaction where exact geometry is absent | Verify represented geometry and references; never invent a grid | Actor-specific environment projection |

### B. Initiative and actor decision

| Lane | Inputs | Agent responsibility | Code responsibility | Output/correction |
|---|---|---|---|---|
| Initiative ledger | Committed initiative-eligible IDs, authoritative controllers, committed entry/removal events, current ledger | None | Reconcile eligible IDs; own initiative values, stable order, round, cursor, entry timing, and acted state | Exact actor window; no participation inference from presence/type/faction and no consumption of uncommitted semantic changes |
| Stable ordering | Exact ledger and committed entry/removal events | Each actor proposes only for its assigned position | Supply exact combatant order; never let a composer reorder actors | A composer may assemble the batch without reordering combatants; actors order only components inside their own action where legal |
| Human intent | Exact player input, player-control state, observable scene, effective owned sheet | Preserve the player’s semantic goal; identify named capability only when invoked; support improvised action | Verify turn ownership and referenced canonical/represented facts | Focused clarification only when required; no preferred-action substitution |
| Actor perspective | Only that actor’s disclosure grants, beliefs, memories, personality, objective, and effective capability projection | Produce current desire, fear, belief, voice, and goal | Enforce attribution, isolation, canonical identity, and disclosure firewall | Feeds only that actor’s tactical proposal and permitted narration |
| Tactical proposal | Exact actor position, isolated perspective, committed objectives, environment, effective state, current controller | Actor chooses action, capability/mode, semantic targets, desired outcome, speech, retreat, surrender, or other tactic | Verify actor/window/controller identity and represented action/resource availability | Stale/impossible proposal returns fresh actor/action-scoped facts; code never retargets or emits Defend |
| Contextual ruling | Proposed intent, relevant SRD context, represented capability facts, disclosure-safe scene facts | Interpret attack/save/check/choice topology where canonical structured data is incomplete; assess player agency and semantic coherence | Use authoritative structured facts where they exist; never derive roll purpose from narration/prose | Accepted mechanics-affecting ruling proceeds to freeze; raw critique remains non-canonical correction context |

### C. Represented legality and action resolution

Code owns target/action legality only where authoritative representation exists:

- Canonical target identity.
- Accepted relationship.
- Target type/count defined by the represented capability.
- Represented range, reach, position, line of sight/effect, and cover.
- Duplicate-target restrictions.
- Represented area-of-effect membership.
- Action/resource availability.
- Represented movement triggers.

Where exact geometry or a structured rule fact is absent, the ruling remains agentic. The design does not invent a grid, pathfinder, occupancy model, or unsupported distance engine.

| Lane | Agent responsibility | Code responsibility |
|---|---|---|
| Weapon attack | Choose attack, mode, semantic target, and desired action | Resolve canonical attack row, roll ownership, exact modifiers, hit/critical, damage, multiattack state, ammunition, typed events |
| Spell/ability | Choose capability, mode, semantic targets, desired effect, and concentration intent; ruling agent interprets incomplete contextual SRD topology | Own represented slots/uses, exact DC/modifier, roll ownership, arithmetic, durations/effect operations, conservation, and mutation |
| Improvised/environmental action | Express semantic attempt and desired effect | Verify represented objects/positions/resources and apply accepted contextual ruling through typed events |
| Effects/survival | Propose declarative semantic effect or meaningful reaction/save framing | Own effective values, HP, conditions, duration/expiry, concentration uniqueness, death state, and committed mutation |

### D. Completion, narration, archive, and memory

| Lane | Inputs | Agent responsibility | Code responsibility | Output |
|---|---|---|---|---|
| Completion proposal | Fully settled committed state, accepted objectives/relations/participation, survival, surrender/escape/negotiation/control events | Propose continue, phase change, victory, defeat, surrender, escape, negotiation, or unresolved departure and cite supporting accepted facts | Reject completion while any continuation remains open; reconcile references/revision; never infer from source kind/type | Accepted completion outcome distinct from rewards and narration |
| Completion commit | Accepted outcome plus authoritative participants/state | Propose semantic relationship/world consequences within the outcome; request controller-consequence evaluation through the controller-transition lane when needed | Commit outcome, eligible rewards, accepted relationship transitions, effect-clock exit, and represented world consequences exactly once; reference only controller transitions already accepted through their lane and never originate or directly commit a controller change | Durable committed outcome independent of browser observation |
| Narration generation | Committed turn/outcome, disclosure-safe observable facts, permitted actor voices | Narrate committed facts without invention or private leakage | Check committed-event coverage without making prose mechanical authority | Retained stable narration |
| Publication | Retained narration and stable delivery ID | None | Append once to ordered replayable player-visible feed | Published narration eligible for archive and memory |
| Archive/handoff | Published narration and committed outcome | None | Preserve required archive/summary-before-active-cleanup guarantees; clear active encounter and hand off without duplicating completion | Player-visible transcript and main-DM continuation |
| Attributed memory | Published narration, committed typed events, actor involvement/disclosure | Extract grounded episodes, beliefs, and relationship observations | Enforce attribution and canonical identity | Perspective context only; never mechanics |

## 7. Mechanical and SRD boundary

The design does not move all native rule meaning into code.

### Agents own

- Intent, capability, mode, semantic targets, and desired outcome.
- Contextual interpretation of SRD requirements when canonical structured data is incomplete.
- Semantic participation, relationships, objectives, positioning where geometry is absent, tactical behavior, surrender, retreat, recruitment, and completion meaning.
- Per-actor perspective and voice.

### Code owns

- Fresh canonical/effective values where authoritative structured facts exist.
- Stable initiative ledger and exact actor window.
- Canonical target identity and represented target/action legality.
- Exact AC, DC, modifiers, roll ownership, arithmetic, resource consumption, HP, effects, durations, conservation, ordering, revisions, and mutation.
- Stable request/turn/event/delivery identity and recovery.

### Code does not own

- Semantic roll requirements inferred from prompt wording or narration.
- Unsupported geometric conclusions.
- A comprehensive deterministic 5e rules engine.
- Tactical fallback, alternate target, allegiance, recruitment consent, controller transfer, or victory meaning.

### Resolution ladder

The runtime chooses the narrowest truthful resolution level supported by authoritative data. It never infers rules from prose and never expands into a comprehensive hardcoded rules engine.

1. **Supported structured capability.** Code owns represented attack/save/check topology, target structure, exact values, concentration, and represented outcome branches. The actor still chooses intent, capability, mode, and semantic targets.
2. **Generic represented primitives.** The actor/ruling lanes select semantic intent and approved operations; code validates and executes the represented plan with exact values, ownership, conservation, and mutation.
3. **Improvised or contextual ruling.** The ruling agent proposes a typed plan containing semantic purpose, an approved difficulty band, targets, costs, success/failure meaning, and represented effect primitives. Code maps approved bands to exact values, freezes the accepted plan before randomness, and executes it.
4. **Unrepresentable ambiguity.** Ask one focused next question or return a non-consuming correction. Do not guess, fabricate a capability, or silently substitute another action.

Whether models may adjudicate incomplete native spells or features beyond represented primitives is an explicit owner authority decision. This document does not treat that authority as settled.

## 8. Reaction and resumable-continuation workflow

Reactions and interrupts are not a single “effect” step. They are resumable child frames beneath a resolution atom, coordinated by the existing `pendingTurn`. Every frame logically identifies its parent and child, trigger phase (`pre-roll`, `post-roll/pre-result`, `post-result`, or `before dependent mutation`), eligible controllers and ordering, pass/decline state, stable roll, pending versus consumed cost, parent invalidation conditions, partially completed movement/action state, atom cursor, and parent-turn cursor. Exact field names remain owner-gated.

### Minimum flow

```text
freeze accepted declaration
  -> persist trigger and any known roll
  -> persist interaction/reaction frame and exact continuation
  -> publish player request
  -> release filesystem locks and wait
  -> consume one answer exactly once
  -> resume exact continuation
  -> reserve/consume cost only at the accepted mechanical point
  -> calculate dependent result
  -> stage/apply the dependent resolution atom
  -> unwind child-to-parent deterministically
```

Nothing player-visible is requested before the trigger, answer owner, and continuation are durable. No filesystem lock is held while waiting for a human or provider. Passing/declining advances the reaction window in its accepted controller order; exhaustion resumes the parent without inventing a response. A pending reservation is not a canonical resource deduction.

### Required continuation cases

- **Shield:** make the triggering attack roll durable before publishing the reaction request; the answer resumes hit resolution without rerolling.
- **Counterspell:** pause spell resolution, preserve spell/caster/target/slot context, and resume after the reaction. Counterspell costs remain pending until their accepted consumption point.
- **Counterspell-on-Counterspell:** nest child frames and unwind child-to-parent deterministically without losing or duplicating the original spell, earlier reaction, costs, atom cursor, or initiative cursor.
- **Opportunity attack:** preserve the represented movement trigger and exact movement interruption point; resolve the reaction before dependent movement completion where represented rules require it, then resume from that point.
- **Player saving throw:** persist exact save purpose, actor, DC/modifier source, answer owner, and continuation; never infer purpose from the displayed prompt.
- **Multiattack interruption:** after each applied atom, refresh target state. If a target is defeated, reconsider only remaining legally orderable sub-actions through the same controller: the human for a player character, or that isolated actor agent for a non-player actor. Code never retargets.
- **Death-state decision:** pause at the real player/agent choice, preserve non-victory semantics, and never route through victory completion.

### Duplicate and conflicting answers

The pending interaction identifies the exact answer owner, publication identity, and continuation. One accepted answer consumes it. A duplicate equivalent answer is acknowledged without reapplying mechanics. A conflicting late answer cannot overwrite the consumed continuation and is treated as stale/superseded input. A reaction frame closes only after every eligible controller has answered/passed or the represented window has otherwise exhausted.

Exact persisted fields for reaction/continuation representation remain owner-gated.

## 9. Transaction, commit, completion, and narration

### 9.1 Freeze mechanics-affecting semantics before randomness

A semantic proposal may remain unpersisted only while no random result, resource reservation, or irreversible resolution step exists.

Before the first roll or reservation, freeze in the existing pending turn:

- Actor.
- Action/capability.
- Targets.
- Mechanics-affecting accepted ruling.
- Roll topology and ownership.
- Exact continuation.
- Expected encounter revision and actor window.

A raw referee critique is not canonical. The accepted resolution input is transaction evidence. Recovery may regenerate an uncommitted proposal only when no roll, reservation, or irreversible resolution has occurred.

### 9.2 Resolution atoms beneath the parent turn

A parent turn is not complete merely because one attack, movement component, reaction, spell branch, or other sub-action has committed.

```text
TURN OPEN
  -> RESOLUTION ATOM FROZEN
  -> TRIGGER/ROLL PERSISTED
  -> INTERACTION PERSISTED, when required
  -> REQUEST PUBLISHED
  -> WAITING FOR CONTROLLER
  -> ANSWER CONSUMED ONCE
  -> ATOM STAGED
  -> ATOM APPLIED ONCE
  -> NEXT ATOM or TURN FINALIZED
  -> CURSOR ADVANCED ONCE
```

Every atom belongs to one parent turn. Applying an atom does not finalize that turn. The initiative cursor advances only after every atom, reaction, roll, choice, and continuation has closed. Restart resumes the pending atom or next unresolved component without replaying any applied atom. A pending reservation records intent and continuation but is not itself a canonical resource deduction.

Shield’s triggering roll is durable before request publication. Nested Counterspells unwind child-to-parent. Opportunity movement resumes from its exact interruption point. Multiattack reconsideration returns to the same authoritative controller rather than code. Exact persisted field names remain owner-gated.

### 9.3 Mechanics-dependency freshness

Encounter revision alone cannot prove that canonical mechanics remained unchanged during a provider call. Immediately before freezing or staging, code rereads the exact mechanics-affecting value projections used by the proposal, including applicable AC/effective defenses, equipment and attack row, resources/slots, conditions/effects, resistances/immunities, controller, participation, represented position, and target legality. This is value-level dependency evidence, never a full-file or content hash.

If a dependency changed:

- **Before randomness or reservation:** reconsider only the affected uncommitted proposal using fresh state.
- **After a roll or atom was frozen, exact arithmetic only changed:** when the frozen action remains legal, preserve the action and roll and recompute only the dependent arithmetic from fresh authoritative values.
- **After a roll or atom was frozen, a declaration-defining dependency changed:** when controller, target legality, roll topology, or another fact defining the declaration changed, do not apply, retarget, reroll, or reinterpret automatically. Enter scoped recovery/reconciliation with the frozen action and roll preserved.
- **Always:** patch only owned values and never overwrite unrelated concurrent changes.

### 9.4 Initiative stability

Code supplies the exact combatant order. Each actor supplies its proposal for its assigned position. A composer may assemble the batch without reordering combatants. An actor may choose only the legally orderable components of its own action.

Participation changes do not reroll or globally sort the encounter. Code applies explicit entry/removal events to the stable initiative ledger, then derives the remaining uncommitted window without rerolling, resorting, duplicating, or omitting existing turns.

### 9.5 Invalid proposal versus failed action

| Class | Result |
|---|---|
| Hallucinated model capability | Actor/action-scoped correction; no mutation and no action cost |
| Invalid player reference | Player-visible correction/no-op; no mutation and no action cost; tagged as correction output and excluded from world-event memory, relationship history, and chronicle authority |
| Stale state | Reload fresh state and reconsider only the uncommitted action |
| Malformed structured response | Correction at the originating lane; no fictional action and no mutation |
| Mechanically legal in-world attempt that misses or fails | Consume proper action/resource economy and commit the truthful failed-attempt event |
| Nonexistent or unowned thing | Player-visible natural correction/no-op; no mutation; never silently invent/retarget and never promote correction phrasing into a world event |

Model hallucinations are internal actor-scoped corrections and are not published. A valid in-world action that fails or receives an in-world refusal is a typed committed outcome, consumes its proper economy, and may enter narration and memory. Narrative phrasing alone never promotes correction output into a mechanical or historical event.

### 9.6 Complete owned mutation atoms and crash-convergent application

The combat commit is not one physically atomic multi-file write. It is a staged, crash-convergent sequence:

1. Before the first mutation of any canonical or encounter-instance gameplay value, persist the complete owned mutation atom in the encounter coordinator: parent turn and atom/event identity; target record/file; owned field path; before value; after value; required dependency values; and safe application order. Earlier encounter-coordinator writes may freeze the proposal, roll, reaction frame, or mutation plan; those staging writes are distinct from the gameplay mutations they authorize.
2. While holding the relevant mutation authority, reread the latest target file and, for every owned field:
   - Current equals `before`: apply `after`.
   - Current equals `after` and the staged atom owns it: treat it as already applied.
   - Current equals neither: preserve the current value and enter recovery reconciliation; never overwrite blindly.
3. Use value-level before/after evidence, not hashes as authority.
4. Patch only owned fields and preserve unrelated fields.
5. Preserve same-directory temporary write, flush, and atomic replacement for each authoritative file.
6. Write canonical owned values in the staged safe order.
7. Record the encounter atom receipt last. Finalize the parent turn and advance its cursor only after every atom closes.

This is not a generic write-set framework or a new store. Each resolution/semantic atom and each existing completion subtransaction retains only its minimal staged record and receipt. Existing completion steps may keep separate idempotent receipts when they protect distinct external writes.

### 9.7 Recovery-pending conflict

If a partially applied operation finds a current value that matches neither its staged `before` nor `after` value:

- Preserve the frozen operation, accepted semantics, rolls, applied subset, and remaining mutations.
- Do not rerun intent, ruling, randomness, or already applied mechanics.
- Keep the parent-turn cursor unadvanced.
- Mark only the active encounter as recovery-pending conflict.
- Do not present the mixed snapshot as coherent gameplay.
- Permit Load, Reset, and the owner-approved deterministic repair/fail-forward route.
- Show honest player-visible recovery progress.

Load and Reset use the same campaign-scoped mutation authority. Before changing campaign state, they explicitly supersede every uncommitted invocation, interaction, staged atom, and recovery continuation. Superseded operations remain diagnostic evidence but can never resume or apply another mutation after restoration. This reuses existing encounter coordination and does not require another ledger or store.

There is no startup-wide recovery scan and unrelated read-only UI remains available. The active combat entry/mutation path reconciles its own pending operation before producing another gameplay projection. The final player-facing route remains an owner decision under D-4.

### 9.8 Completion precondition and order

Completion cannot be proposed, accepted, or committed while any resolution atom, reaction frame, roll, save, choice, multiattack continuation, reinforcement/entry semantic transition, or uncommitted resolution step remains open.

Required order:

1. Turn mechanics converge and commit.
2. Fully settled committed state is reloaded.
3. Completion/transition proposal consumes committed facts.
4. Completion is reconciled and accepted.
5. Completion state, eligible rewards, accepted relationship transitions, and world consequences converge exactly once. Completion may reference a controller transition already accepted through the controller-transition lane or request that a proposed controller consequence be evaluated there; it never originates or directly commits a controller change.
6. Final narration is generated from the committed turn and committed completion outcome.
7. Narration is retained for replay.
8. Narration is published to the ordered player-visible feed.
9. Published transcript is archived and attributed memory may be extracted.
10. Active-combat cleanup and main-DM handoff finish using existing recovery receipts.

Browser observation never gates steps 1–5.

### 9.9 Narration integrity

Narration is generated only from committed facts and disclosure-safe context. Correction may not roll back mechanics, rerun the turn, revoke completion, duplicate rewards, or silently freeze. Retained narration is replayable; only published narration becomes player-visible history or actor memory.

Whether deterministic committed-fact narration is allowed after model narration failure is an explicit owner decision. This design does not preserve or reject the current fallback by fiat.

## 10. Existing persistence and recovery

No new store, journal, WAL, database, coordinator file, generic workflow framework, or startup-wide recovery gate is introduced.

### Existing authority families

| Record | Authority |
|---|---|
| `modules/encounters/encounter_<ID>.json` | Operational coordinator and mechanical truth: roster/IDs, committed scene facts and semantic transitions, authoritative controllers, encounter-instance state, `combatState`, stable initiative ledger, parent turn/atom cursor, staged/applied atoms, pending interaction, retained narration, completion receipts |
| Canonical player/NPC character files | Persistent player/NPC facts, equipment, form, represented resources/effects, HP/XP as currently owned |
| Canonical monster sources | Monster base capabilities |
| `modules/conversation_history/combat_conversation_history.json` | Full active prompt and interaction continuity, including system messages; reused only when newest encounter marker matches |
| `combat_logs/<ID>/combat_chat_*.json` | Published player-visible history; system messages intentionally excluded |
| `party_tracker.json` | Active encounter selection and completed-encounter handoff |
| Existing NPC personality/memory/voice stores | Owner-mandated attributed perspective continuity, never mechanics |

Restart constructs new projections from these records. It never interprets narration to recreate mechanics.

### Recovery invariants

1. Encounter JSON remains the operational coordinator.
2. Provider calls occur outside file locks.
3. Immediately before acceptance, campaign-scoped mutation authority atomically verifies the active encounter, expected turn, revision, actor window, authorized next transition, authorized logical invocation, and fresh mechanics dependencies; it claims the transition and freezes the accepted result before release, so a second response cannot pass the same claim.
4. At most one response is accepted per logical invocation. Under that same mutation authority, Load/Reset supersedes every uncommitted invocation, interaction, staged atom, and recovery continuation before changing campaign state, even if restored state recreates the earlier encounter/turn/revision tuple. Superseded work remains diagnostic-only and cannot resume or mutate.
5. Every owned value uses current/before/after reconciliation; conflicting current data is preserved and enters encounter-scoped recovery-pending reconciliation.
6. Value evidence—not projection hashes, read-set hashes, or content digests—proves state transitions.
7. Individual authoritative writes retain same-directory temporary write, flush, and atomic replacement.
8. A complete minimal atom is staged in the encounter coordinator before mutating any canonical or encounter-instance gameplay value; earlier coordinator writes may freeze proposals, rolls, and interactions. The atom receipt is written last, and the parent-turn cursor advances only after all atoms close.
9. Combat entry and mutation paths inspect and resume their own pending encounter state. Read-only UI access never triggers a global startup recovery gate or bricks startup.
10. Initial accepted scene facts/controllers/initiative and the full-conversation marker become durable before conditional activation of `party_tracker.activeCombatEncounter`; combat is not enterable before every prerequisite exists.
11. Clearing `activeCombatEncounter` is conditional on it still matching the expected encounter ID. Delayed cleanup for E1 cannot clear active E2, and `lastCompletedEncounter` is set consistently to the expected completed ID.
12. Preserve archive/summary prerequisites and archive/summary-before-active-cleanup unless observed crash evidence proves another order necessary.
13. Do not reverse the current party-tracker/encounter closure order on theory. Map and kill-test both crash sides first; if tracker-first leaves only diagnostic encounter status stale, prove restart/handoff still works.
14. Separate idempotent completion receipts may remain where they protect distinct external writes.

## 11. Current-stage and crash-boundary map

### Encounter activation boundary

Combat activation is a conditional sequence, not the mere existence of an encounter file:

1. Accepted encounter identity and initial scene facts are frozen.
2. Encounter JSON is written.
3. Initial controller grants are written.
4. Initial stable initiative state is written.
5. The full-conversation encounter marker is written.
6. `party_tracker.activeCombatEncounter` is set only if the tracker still satisfies the expected before-state and is set to the expected encounter ID.
7. Combat becomes enterable.

Kill-test before and after every write. An orphan inactive encounter is not authority. An active tracker cannot point to an unusable partial encounter without an honest recoverable state.

### Mandatory closure invariants

The exact closure order remains empirically owner-gated, but every acceptable order must:

- Clear `activeCombatEncounter` only when it still equals the expected encounter ID.
- Prevent delayed cleanup for E1 from clearing newly active E2.
- Set `lastCompletedEncounter` consistently to the expected completed ID.
- Preserve archive and summary prerequisites.
- Survive real-process interruption on both sides of every tracker/encounter write.
- Prove restart and handoff remain correct if a tracker-first order can leave only diagnostic encounter status stale.

### Status labels

- **PRESENT:** current mainline has durable evidence for the boundary and the target preserves it.
- **PARTIAL:** current machinery exists, but authority, semantics, or recovery behavior does not yet satisfy the target.
- **UNCOMMITTED GAP:** no durable receipt exists and rerun is allowed only because randomness/reservation/mutation has not begun.
- **OWNER-GATED GAP:** the target needs a persisted representation that current main lacks; exact fields require owner approval.
- **CONFLICT:** current mainline behavior directly contradicts the target and must be resolved in the future reviewed plan.

No `CONNECTED` status is used.

| # | Boundary | Current proof | Restart behavior | Status and target correction |
|---:|---|---|---|---|
| 1 | Encounter activation | Builder writes encounter JSON and then sets `party_tracker.activeCombatEncounter`; full conversation marker is established later by combat entry | An encounter file may exist before activation; tracker selects the active file | **PARTIAL + CONFLICT.** Target activation requires accepted identity/scene facts, encounter JSON, controller grants, stable initiative, and full-conversation marker before conditional expected-ID tracker activation; kill-test each write |
| 2 | Scene facts and semantic transitions committed | Encounter creature/scene fields exist, but controller/relations/participation/objectives/disclosure are not a revision-bound committed authority partition | Reloads encounter plus matching conversation | **PARTIAL / OWNER-GATED GAP.** Initial facts commit with activation; every later semantic change uses a typed minimal transition atom before consumers read it |
| 3 | Initiative window established | `combatState.initiativeOrder`, `round`, `turnCursor`, `actedThisRound`; claimed window in `pendingTurn.actorIds` | Continues from durable ledger/cursor or pending claim | **PARTIAL.** Ordering exists, but participation/player stop still use creature/type logic; entry/removal must update a stable ledger without reroll/resort |
| 4 | Parent turn opened | `pendingTurn` claims actor IDs and revision | Pending claim can be recovered | **PARTIAL.** Current shape does not distinguish parent-turn completion from applied sub-actions or bind current controller as operational authority |
| 5 | Resolution atom frozen | No complete accepted actor/action/targets/ruling/topology/continuation atom is durably frozen before every random result | Some pre-resolution model work regenerates | **OWNER-GATED GAP.** Freeze minimum accepted atom and exact mechanics dependencies before randomness/reservation; only truly pre-random work may be reconsidered |
| 6 | Trigger/roll persisted | `playerExchanges`, `requestedDie`, and roll-related state preserve parts of an exchange | Some unresolved exchanges survive | **PARTIAL + CONFLICT.** Current roll purpose can be inferred from prose/regex; Shield-class triggers are not proven durable before request publication; target uses accepted semantic purpose and stable roll identity |
| 7 | Interaction persisted/request published | `playerExchanges[].dmRequest`, `requestedDie`, `playerInput` provide a durable request/answer chain | Preserves some unresolved exchanges | **PARTIAL.** Target persists frame identity, controller order, publication identity, exact continuation, and pass/decline state before requesting anything player-visible |
| 8 | Provider response accepted | Encounter/turn/revision checks exist around current work | A stale response may be rejected against changed state | **PARTIAL + CONFLICT.** Current tuple checks do not prove one accepted response per logical invocation or an atomic transition claim, and do not fence pre-Load/Reset provider/staged work when restored state recreates the same tuple; target atomically revalidates, claims, and freezes under campaign mutation authority |
| 9 | Mechanics/atom staged | `pendingTurn.stage="events_staged"`, typed events, character preconditions, delivery context, and roll consumption exist | Replays staged turn events after checks | **PARTIAL.** Current staging is turn-oriented and uses SHA fingerprints; target persists complete value-level owned atom mutations and dependencies in the encounter coordinator before mutating canonical or encounter-instance gameplay values |
| 10 | Resolution atom applied | Canonical files receive after-values and encounter tracks applied event/turn IDs | Absolute after-values and receipts provide useful crash convergence | **PARTIAL + CONFLICT.** Current SHA fingerprints and five-second busy/refusal lease deadlines do not satisfy value-authority/B2 targets; use value-level owned fields, preserve unrelated values, receipt last, and record lock-timeout debt under D-6 |
| 11 | Parent turn finalized/cursor advanced | Current `commit_turn` advances turn state after staged events | Current turn-level receipt can avoid some replay | **PARTIAL.** Target advances once only after all atoms, nested reactions, rolls, choices, and continuations close; applying one atom never finalizes the parent turn |
| 12 | Completion accepted | `combatState.completion` exists, but current completion begins from `all_hostiles_resolved` inferred through type/faction | Can retry completion steps but lacks accepted semantic outcome | **OWNER-GATED GAP.** Persist minimum accepted outcome only after all atoms/interactions settle; completion consumes committed objectives/relations/participation/controller state |
| 13 | Rewards/outcome committed | `pendingRewards`, `rewardsApplied`, canonical XP, effect-clock and summary receipts | Absolute values/receipts prevent duplicate XP/summary | **PARTIAL.** XP recovery is valuable; non-victory eligibility, semantic transitions, and world consequences need accepted outcome authority |
| 14 | Narration retained | `pendingDelivery.narration`, attempts, committed events; completion summary | Reuses retained narration without rerunning mechanics | **PARTIAL + CONFLICT.** Current bounded T096/T097 attempts, code-authored NPC Defend fallback, and deterministic narration fallback conflict with unsettled D-4/D-8 policy and target no-tactical-fallback behavior |
| 15 | Narration published | Stable delivery ID in full conversation and encounter delivered IDs; pending delivery clears after publication/delivery path | Replays retained output and deduplicates publication | **PRESENT.** Publication means durable ordered feed append; observation is not authority; only published text enters shared history/memory |
| 16 | Transcript archived | `combat_logs/<ID>/combat_chat_*.json`, `archiveFile`, `transcriptArchived`; system messages excluded | Deterministic archive filename safely overwrites on retry | **PRESENT.** Preserve archive prerequisites, published-only input, and private-lane isolation |
| 17 | Encounter closed/handoff | Party tracker clears active encounter/sets last completed; encounter completion status/summary/archive receipts remain | Current party-tracker-first side can leave only diagnostic encounter status stale | **PRESENT, ORDER REQUIRES EMPIRICAL MAPPING.** Expected-ID conditional clear and delayed-E1-versus-E2 safety are mandatory; crash-test both orders before any change |

Current-main evidence for this table was re-read from the live mainline versions of `core/generators/combat_builder.py` (automatic initiative and persisted mode), `core/managers/combat_state.py` (revision/window/staging/delivery/completion), `core/managers/combat_transaction.py` (requests, value application, reward receipts), `core/managers/combat_orchestrator.py` (prose-derived roll inference, bounded intent/narration attempts, NPC Defend fallback), and `core/managers/combat_manager.py` (history marker, publication, archive, and closure). These paths are evidence snapshots, not embedded revision authority; every future plan must re-read them from then-current `origin/main`.

## 12. Failure, correction, retry, and liveness semantics

### Correction classes

- **Stale state:** reload fresh sources and reconsider only the uncommitted action. A late/superseded response cannot mutate.
- **Correctable structured error:** return minimum actor/action-scoped facts to the originating agent.
- **Genuine player ambiguity:** persist one focused request and continuation.
- **Hallucinated model capability:** internal actor-scoped correction, not published, no cost, no mutation, and no memory/history entry.
- **Player typo, nonexistent reference, or unowned capability:** player-visible natural correction/no-op, no cost and no mechanical event; explicitly excluded from world-event memory, relationship history, and chronicle authority.
- **Mechanically legal failed attempt or in-world refusal:** consume proper economy, commit a typed truthful outcome, and permit narration/memory.
- **Already committed work:** continue delivery/completion only; never rerun mechanics.
- **Conflicting current values after partial application:** preserve the frozen atom, roll, semantics, applied subset, and current data; keep the parent turn unadvanced and enter encounter-scoped recovery-pending conflict.

### Retry and liveness invariants

- No abandoned player workflow or accepted work. A provider attempt may be genuinely cancelled, superseded, or lost with process failure, but it may not continue as an untracked worker capable of later mutation.
- No invisible infinite loop.
- Visible progress during correction, retry, or recovery.
- No code-selected tactical fallback.
- Committed mechanics and completion remain safe.
- At most one response is accepted for a logical invocation; pre-Load/Reset invocations, interactions, staged atoms, and recovery continuations cannot resume or commit later.
- Stale responses are superseded by the selected serialized or invocation-generation authority plus encounter/turn/revision/transition/dependency revalidation.
- Deterministically unhealable handling requires an owner-ratified failure class.
- Provider calls run outside file locks.
- Busy cannot become a player-facing refusal.

The workflow may occupy these nonterminal logical states without choosing retry counts: **running/waiting**, **retry scheduled**, **superseded and genuinely cancelled**, **recovery pending**, **blocked but retryable**, **deterministically unhealable under an owner-ratified class**, and **resumed or manually recovered**. There is no universal terminal `FAILED` gameplay state.

This design rejects a universal “bounded attempts then FAILED” rule. It also does not invent universal unbounded retry mechanics. Exact retry counts, cancellation mechanics, backoff, cost controls, concurrent/off-thread scope, stale-response authority, and deterministically unhealable behavior remain governed by owner decisions D-1, D-4, and D-8 in issue #193. Current five-second busy/refusal lease behavior is explicit D-6 doctrine debt, not accepted target behavior.

Whether a deterministic committed-fact narration may be published after model narration failure remains an owner decision. It is not silently settled here.

## 13. Schema, legacy, and rollout safeguards

- Persisted play-path schemas and player-data contracts remain frozen until the owner approves each additive field.
- Exact field names and shapes for resolution atoms, semantic-transition atoms, current controller, interaction frames, disclosure grants, invocation authority, recovery-pending conflict, activation, and closure remain owner-gated. Their logical guarantees are mandatory and cannot be omitted by leaving the schema undecided.
- Prompt wording and ephemeral structured contracts may iterate; persisted field changes do not ride along implicitly.
- Existing saves keep loading. State writers preserve existing non-empty values unless they own a genuinely new value.
- Acceptance diffs persisted state and flags every non-empty-to-empty transition.
- Working mainline mechanics and legacy player experience are expanded, not casually deleted. Any replacement later runs the full behavioral-contract and consumer mapping required by issue #193.
- Existing encounters marked/stamped legacy remain legacy. They are not rewritten or reinterpreted mid-combat.
- New encounters become unconditionally agentic only after the typed committed participant/relationship/controller/objective/disclosure boundary, resolution-atom and recovery design, real acceptance, review convergence, and owner approval land together.
- No hidden kill switch, default-off rollout, environment opt-in, provider bypass, or player-selected combat architecture may silently defeat approved production functionality.
- Intentional player settings and genuine diagnostic/cost safeguards remain, but cannot act as hidden rollout controls.
- NPC personality, attributed memory, and voice continuity are owner-mandated target behavior; unmerged implementations do not define the contract.
- Persistent/recruited monster destination is not inferred from source kind or temporary relationship. It is an owner-gated schema/persistence decision.

## 14. Prompt and provider development

The existing tuned prompt system is preserved and extended carefully. Prompts are not frozen prose; persisted gameplay contracts are frozen.

Each lane is evaluated independently before gameplay wiring:

1. Assemble real, read-only, revision-bound scene snapshots from approved mainline data.
2. Construct the minimum disclosure-safe lane projection.
3. Combine existing tuned rules with one narrow semantic task.
4. Call real OpenAI and Gemma providers. Do not use Qwen unless the owner explicitly instructs it.
5. Validate exact ephemeral structured output and semantic authority boundaries.
6. Vary allies, hostile canonical NPCs, friendly monsters, neutrals, hidden facts, reinforcements, improvised actions, surrender, defeat, reactions, and recovery state.
7. Correct only the failing transaction with actor/action-scoped facts.
8. Reload fresh sources after every committed test transition.

Provider evaluations may run independently when they do not share mutable game state. Final stateful acceptance is sequential, one operation at a time.

A prompt snapshot proves only that the transaction can return usable structured output for that input. It does not prove player experience, persistence, restart, publication, or legacy compatibility.

## 15. Real acceptance matrix

All player-facing acceptance uses the unmodified native-Windows game through real headless commands or live Playwright/browser interaction, a real configured provider, real files, complete player-visible output, and authoritative on-disk inspection. Tests do not simulate player-facing content. Crash probes kill the real process only after the required durable boundary is observed. No monkeypatches or test-only gameplay hooks.

### 15.1 Recovered experience and semantic scenarios from epic #191

| Scenario | Required proof |
|---|---|
| Standard party versus monsters, legacy/new A/B | Scene opening, initiative cadence, player-owned non-initiative rolls, NPC voice, cinematic batching, save/resume, XP, archive, and main-DM handoff remain compatible |
| Missing Quick Roll input | Exact missing roll is requested; Quick Roll does not submit it; no actor replay, skipped player action, or mutation |
| Existing hostile canonical NPC | Canonical character identity remains intact; accepted relationship drives targeting/completion rather than NPC type |
| Friendly monster | Monster source remains allied and is never counted hostile from source kind |
| Neutral witness/creature | Presence persists without forced initiative, targeting, or completion blocking |
| Three-sided party/cult/demon fight | Explicit relations permit non-player sides to oppose each other without a binary shortcut |
| Same species/name on opposing sides | Distinct canonical references and IDs; no display-name merge or retarget |
| Party NPC refuses involvement | Party persistence remains intact while encounter participation/control follows accepted facts |
| Recruit hostile NPC during combat | Typed relationship transition occurs once; controller changes only through a distinct accepted controller transition; encounter/party remain consistent |
| Recruit monster | Temporary versus permanent relation is explicit; source kind remains monster; persistence follows owner-approved destination |
| Failed/nonexistent recruitment | Narrated refusal/no-op; zero guessed identity or mutation |
| Betrayal/surrender/charm expiration | Exactly one structured relationship transition; no implicit controller change, stale legality, or premature completion |
| Reinforcement | Canonical source verified; explicit entry event updates stable initiative ledger without reroll/resort/duplication after restart |
| Terminal party defeat | Clean named recovery choices; encounter preserved; no victory finalizer, XP, auto-load, or dead-character command prompt |
| AC/effect regression | Protection fighter effective AC comes from canonical/equipment/form/effects; no transient invented Defense bonus on disk or in encounter |
| Sole-player narration | Player addressed in second person through combat and handoff |
| Identity round trip | Display name, canonical ID, and source reference remain consistent without fuzzy/five-attempt no-op loops |
| Malformed or hallucinated model output | Internal actor/action-scoped correction only; not published, no mutation/cost, and no memory/history event |
| Genuine player ambiguity | One focused player question persists with its exact answer owner and continuation; no mechanics begin before the answer |
| Invalid player reference | Natural player-visible correction/no-op, no mutation/cost, tagged as a non-event and excluded from world-event memory, relationship history, and chronicle authority |
| Phrasing adversary | Diverse natural phrasing yields equivalent structured facts without gameplay keyword/regex gates |
| Legacy save | Legacy-provenance encounter loads and behaves unchanged; no faction/controller rewrite |
| Browser reconnect | Retained/published output replays with stable ID without rerunning mechanics or narration |
| Provider stall during combat/build | Tracked under the cross-cutting liveness design; combat semantic acceptance cannot hide a stalled provider |

### 15.2 Reaction, continuation, disclosure, and concurrency

| Scenario | Required proof |
|---|---|
| Shield across restart | Same triggering attack roll and accepted declaration survive; no reroll or duplicate cost |
| Counterspell | Original spell continuation and reaction cost resolve once |
| Counterspell-on-Counterspell | Nested continuation returns to the original spell without duplicate/lost costs or cursor drift |
| Opportunity attack | Represented movement trigger and continuation resume in correct order |
| Player save | Semantic save purpose, DC/modifier source, owner, and continuation persist without prose inference |
| Human-controlled multiattack interruption | Earlier target defeat pauses/reloads; the same human controller reconsiders remaining sub-actions; code does not retarget/Defend or advance the parent turn |
| Non-player multiattack interruption | The same isolated actor agent reconsiders remaining sub-actions with fresh dependencies; code does not retarget/Defend |
| Death-state decision | Non-victory decision resumes correctly and cannot enter victory completion |
| Duplicate player answer | Equivalent duplicate does not reapply mechanics |
| Conflicting player answer | Late conflict cannot replace consumed/superseded continuation |
| Completion with open continuation | Completion is rejected before mutation while any reaction/roll/save/choice/multiattack/entry step remains |
| Explicit controller transfer | Before/after/cause/scope/expiry/revision/consent are honored; relationship alone never changes control |
| Hidden-information canary | Actor receives granted observable facts only; secret canonical fact never leaks through prompt, correction, narration, or memory |
| Stable roll reuse | Crash/restart retains accepted roll and topology; no reroll |
| Invalid model capability vs invalid player input | Model hallucination receives scoped correction; invalid player reference receives focused correction/no-op; neither consumes action cost |
| Reverse-order same-state provider responses | If overlap is allowed, only the currently authorized invocation can atomically claim/freeze the transition; if overlap is prohibited, prove the second attempt cannot begin or be accepted; in either structure two responses cannot pass the same claim |
| Load restores the same encounter revision while an old response lives | Under campaign mutation authority, Load supersedes old invocation/interaction authority before restoration; the response remains diagnostic-only even when encounter/turn/revision values repeat and cannot freeze, stage, or commit |
| Load/Reset with a staged or partially applied atom | Before restoration, the same campaign mutation authority supersedes every uncommitted staged atom and recovery continuation; later recovery cannot resume or write into restored state, while diagnostic evidence remains available |
| In-flight mechanics dependency change | Change AC, resistance, equipment, resource, effect, controller, participation, or represented position during provider work; fresh value projection forces scoped reconsideration/reconciliation without overwriting unrelated values |
| Late provider response after retry or Load/Reset | Serialized cancellation or invocation-generation authority rejects it immediately before freeze/stage; tuple equality alone is not accepted evidence |
| Two simultaneous mutation attempts | Only the authorized transition commits; conflicting current values are preserved and reconciled |
| At-least-once browser replay | Stable delivery ID deduplicates publication while permitting reconnect replay |
| Nested reaction unwind | Child Counterspell/reaction frames unwind in deterministic child-to-parent order with stable rolls, costs, atom cursor, and parent-turn cursor |
| Visibility changes mid-round | Movement/revelation/effect invalidates affected grants; next actor/correction/narration projection refreshes without cross-actor leakage |
| Cross-turn/post-revelation secrecy canary | Private actor facts and internal correction/ruling history remain absent until a committed disclosure grant permits them |
| Secret leakage through saved context | Full conversation and every saved lane context contain no private perspective, internal ruling, or correction material in shared player/model history |
| Completion with open atom | Completion is blocked before mutation while any atom, child frame, answer, or entry transition remains unresolved |
| Permanent provider/schema failure | After D-4 defines the legal route, the player sees a recoverable nonterminal state and can use the approved recovery path; no silent loop, tactical fallback, or universal terminal failure |
| Crash during encounter activation | Kill before/after every activation write; orphan inactive encounter is not authority and tracker never selects an unusable partial encounter without recoverable status |
| Delayed E1 cleanup after E2 becomes active | Expected-ID conditional cleanup leaves E2 selected and sets no incorrect completion identity for either encounter |

### 15.3 Crash and authoritative-write matrix

For each applicable scenario, observe and kill the real process before and after every individual authoritative write:

- Accepted encounter identity/initial scene-fact freeze.
- Encounter JSON creation.
- Initial scene-fact and controller-grant commit.
- Initial stable initiative write.
- Full conversation encounter-marker write.
- Conditional expected-ID `party_tracker.activeCombatEncounter` activation.
- Stable initiative entry/removal event.
- Resolution-atom freeze.
- Trigger/roll persistence before request publication.
- Pending player request.
- Reaction/choice persistence.
- Player-request publication.
- Answer consumption.
- Complete owned mutation-atom staging.
- Each canonical character/NPC write.
- Encounter-instance write.
- Atom receipt write.
- Parent-turn finalization/cursor advance.
- Relationship transition.
- Controller transition.
- Completion acceptance.
- Reward/consequence write and receipt.
- Narration retention.
- Player-feed publication.
- Transcript archive.
- Party-tracker active/last-completed write.
- Encounter closure receipt.

Also kill after a partial atom application, then externally create a value matching neither staged `before` nor `after`; prove the mixed snapshot is not presented as coherent gameplay, the frozen semantics/roll/applied subset remain preserved, Load/Reset remains available, and the turn cursor does not advance. Kill during activation to prove an orphan inactive encounter never becomes authority and an active tracker never points to an unusable partial encounter without recoverable status. Delay E1 cleanup until E2 is active and prove E1 cannot clear E2.

After restart, prove no duplicate roll, atom, turn, event, resource spend, relationship/controller change, recruit, reward, publication, archive, memory extraction, or XP; prove no lost player request; and prove no narration-derived mechanics. Publication and memory extraction deduplicate by stable encounter/event/delivery source identities.

### 15.4 Platform, provider, and performance

- Run real OpenAI paid-path acceptance independently of local-model availability.
- Run Gemma through the owner-provided LM Studio endpoint when reachable, without downloads, swaps, or configuration changes.
- Do not run Qwen unless the owner explicitly requests it.
- Confirm progress is visible for waits over the product’s accepted UX threshold without adding a gameplay-abort deadline.
- Judge UI assertions through live Playwright/browser output and on-disk state.
- Judge headless compatibility through the unmodified NDJSON protocol.
- Confirm no material per-turn token/cost regression on the default provider.
- Run one mutation operation at a time during crash probes; overlapping acceptance probes are invalid evidence.
- Dedicated overlap/concurrency scenarios above are the explicit exception: isolate each one, record both invocation identities and arrival order, and do not overlap unrelated acceptance operations.
- Required OpenAI or Gemma evidence that cannot run is reported **BLOCKED** or **NOT REACHED**, never inferred or silently passed.

Deterministic backend tests remain local and untracked. Expected values come from independent contracts rather than implementation output. They may support arithmetic, parsing, serialization, and I/O verification but never substitute for native provider-backed gameplay acceptance.

## 16. Owner gates

No implementation plan may assume answers to these owner-gated choices:

1. **Exact persisted field names and schemas:** minimum accepted-resolution, resolution-atom, semantic-transition, current-controller, reaction/continuation, disclosure-grant, invocation-authority, recovery-conflict, activation, completion, and closure representations are reviewed field-by-field.
2. **Concrete lock/cancellation/invocation implementation:** serialized versus overlapping/off-thread structure, cancellation primitive, authorized invocation generation/equivalent, and mutation authority—without automatically adding hashes, leases, fencing tokens, or a global epoch.
3. **Player-rolled initiative:** keep mainline automatic initiative, or approve a behavior change with encounter-opening request, persistence, duplicate-answer, and restart semantics.
4. **Persistent/recruited-monster destination:** encounter-only, canonical companion representation, or another owner-approved existing persistence family.
5. **Actor call topology:** one call per actor or safely isolated batch, decided by real OpenAI/Gemma quality, privacy, latency, and cost evidence.
6. **Numerical retry/backoff/cost thresholds:** only after D-1/D-8 settle the legal structural behavior and ratified deterministic classes.
7. **Narration fallback policy:** whether deterministic committed-fact narration may be retained/published after model narration failure.
8. **Exact closure order:** preserve current archive/summary and recovery guarantees; choose only after native crashes on both sides show the safe order.
9. **Incomplete native spell/feature authority:** whether the ruling model may adjudicate beyond supported capability topology and generic represented primitives.
10. **Off-thread liveness scope (D-1):** combat/build provider work structure, player responsiveness claims, and safe interaction with single-slot LM Studio.
11. **Combat correction/failure semantics (D-4):** player-facing route for recovery-pending conflict and deterministically unhealable semantic/provider states.
12. **Retry, cancellation, and stale-response policy (D-8):** cancellation, backoff, jitter, concurrency, cost visibility, invocation identity, idempotence, and deterministically unhealable classes.
13. **Doctrine timeout debt (D-6):** replace or explicitly waive current five-second busy/refusal leases and other listed timeout debt; this design does not ratify them.

The following guarantees are not optional owner gates:

- At most one accepted response per logical invocation.
- Atomic revalidate → claim authorized transition → freeze accepted result under campaign mutation authority; a second response cannot pass the same claim.
- No pre-Load/Reset invocation, interaction, staged atom, or recovery continuation may resume or commit afterward.
- Fresh value-level mechanics dependencies immediately before freeze/stage.
- Parent-turn resolution atoms and deterministic nested-reaction semantics.
- Accepted current controller as operational authority.
- Complete minimal owned mutation atom persisted in the encounter coordinator before mutating any canonical or encounter-instance gameplay value.
- Encounter-scoped recovery-pending conflict that preserves frozen work and leaves Load/Reset available.
- Disclosure-grant lifecycle, private-history isolation, and projection refresh.
- Expected-ID activation and closure, including delayed-E1-versus-E2 safety.
- Idempotent publication and memory extraction from stable encounter/event/delivery source identities.

Every persisted-field gate is reviewed field-by-field: name, type, authority source, writer, readers/consumers, revision behavior, migration, legacy behavior, and acceptance proof.

## 17. Non-goals and stop conditions

### Non-goals

- No comprehensive hardcoded 5e rules engine.
- No invented grid, pathfinder, occupancy, or distance engine.
- No new store, WAL, database, generic workflow framework, startup recovery pass, marker family, or hash authority.
- No prose/regex/faction/type/name heuristic as gameplay authority.
- No code-authored tactic, retarget, Defend fallback, relationship, controller change, recruitment result, or completion meaning.
- No redesign of unrelated providers, save systems, travel, module generation, or UI.
- No deletion of the legacy adapter before new-path acceptance and existing-save parity.
- No prompt-version or git-revision authority embedded in gameplay state.
- No comprehensive generic write-set/transaction framework: only minimal atom-local staged values and existing completion receipts inside the existing encounter coordinator.

### Stop and return to design/owner review if

- A persisted field or schema delta lacks explicit owner approval.
- A solution adds a scenario-specific semantic condition.
- A model response can mutate without matching encounter/turn/revision/window/transition, authorized logical invocation, and fresh mechanics dependencies.
- Two responses can be accepted for one logical invocation, or a pre-Load/Reset response can later commit.
- Revalidation and transition claim can race because they are not atomic under campaign mutation authority.
- A continuation cannot survive restart without rerolling or replaying earlier actors.
- Applying one atom finalizes a parent turn while another atom/reaction/choice remains open.
- A provider call or human wait holds a filesystem lock.
- Load/Reset cannot supersede in-flight work.
- Load/Reset can restore state without first superseding uncommitted interactions, staged atoms, and recovery continuations under the same campaign mutation authority.
- Narration, memory, or UI state is used to reconstruct mechanics.
- A failure path abandons the player workflow/accepted work, leaves an untracked worker able to mutate later, invisibly loops, refuses a busy play path, or invents a tactical fallback.
- Shared conversation or saved lane history leaks private actor perspectives, internal rulings, or correction prompts.
- A partial conflict is shown as coherent gameplay or overwrites a current value matching neither staged before nor after.
- Activation or closure writes an unconditional tracker ID that can select/clear the wrong encounter.
- A current mainline consumer or recovered player behavior is unmapped.
- A non-main branch is cited as compatibility authority.
- Acceptance requires monkeypatches, test-only gameplay hooks, fabricated player/model content, or overlapping mutation probes.

## 18. Review gate

This complete v8 draft supersedes v7. It preserves the accepted agent/code authority split, architecture, workflow lanes, existing persistence families, typed events, player control, outcome distinctions, delivery replay, archive behavior, prompt-development discipline, legacy safeguards, fresh state assembly, existing-`combatState` execution authority, parent-turn resolution atoms, committed semantic transitions, authoritative current controllers, value-level dependency freshness, recovery-pending conflicts, nested reactions, resolution ladder, disclosure lifecycle, activation/closure invariants, and native acceptance. It resolves only the six v7 contradictions: atomic response acceptance, pre-gameplay-mutation atom staging, Load/Reset supersession of all uncommitted work, controller-lane-only transitions, scoped post-roll dependency handling, and non-published model-error correction.

The active design branch intentionally contains the NPC prototype lineage and is therefore **not** documentation-only. That lineage may be inspected as a prototype but remains non-authoritative until it is approved on main; the specification’s compatibility authority remains approved `origin/main` only.

### Specification-only commit safeguards after owner approval

Owner approval of this v8 document authorizes only a later specification commit, not an implementation plan or production change. Before any such commit:

- Work from the correct native-Windows `design/agentic-combat-integration` worktree.
- Stage only `docs/design/agentic-combat-design.md`; never use `git add -A`.
- Do not commit `.superpowers/**`.
- Eliminate wholesale CRLF/status noise or prove the staged diff contains exactly this design document.
- Confirm the final staged diff is exactly one file before committing.
- Do not plan implementation, modify production code, merge, roll out, or activate combat.

> **Owner review option B — revise the complete document again**
>
> Return corrections against this whole file. The next revision must again present the complete consolidated document, not fragments.

> **Owner review option A — approve the complete design**
>
> Approval permits only the specification-only commit safeguards above. It does not authorize an implementation plan, production code, merge, rollout, or activation. A future implementation plan must separately run issue #193’s review protocol to convergence and return to the owner for explicit execution approval.
