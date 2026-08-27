# Single-Turn Travel Authority Amendment

Status: owner-approved design correction, 2026-08-23. This amendment supersedes
the broad post-travel sibling execution in the reviewed travel-coherence plan.
It does not authorize unrelated combat, module creation, provider, or schema work.

## Player contract

One model response resolves one immediate player turn. Travel ends after the
requested movement, travel-owned mechanical consequences, truthful arrival
narration, and an invitation for the player's next action.

A compound future plan such as “travel to X, then buy Y, then end the session”
does not authorize purchase or exit in the travel transaction. Those clauses
remain deferred player intent. They may be acknowledged at arrival, but the
game asks what the player wants to do next and waits.

## Authority

- T067 interprets the player's nearest actionable intent and returns structured
  actions for that one turn.
- T065 validates that the response ends at the same immediate semantic beat.
  It returns scoped correction facts when a response executes downstream plans.
- Code reconciles canonical identities and permits only travel-owned structured
  mechanics. It never classifies prose with keywords, regexes, or verb lists.
- Within-module travel may commit `transitionLocation`, elapsed `updateTime`,
  and an `updatePlot` that records the immediate travel outcome. No character,
  roster, storage, hub, save-management, exit, or later-module action executes
  after arrival in the same response.
- Direct cross-module travel remains the canonical two-action transaction:
  `updatePartyTracker` followed by `updateTime`.
- Standalone actions outside a travel response retain their existing contracts.

## Cross-module reconciliation

The model chooses the canonical module and may request an explicit represented
destination. Code resolves the module's canonical starting projection. A
supplied area/location mismatch, missing canonical object, or stale target is a
pre-mutation correction—not a crash and not permission for code to invent a
different destination. The corrected response is revalidated before staging.

## Required three-call narration lifecycle

One travel turn retains all three existing narration agents after mechanics and
summary state commit:

1. T013 creates the first transition/departure layer from the code-filtered,
   committed location context. That context includes the location record after
   its encounter/history update; it is not merely a static location heading.
   The projection includes the player-disclosed `adventureSummary` for
   continuity while excluding DM-only instructions, undisclosed encounters,
   traps, and actors.
2. T063 creates the destination arrival layer using the first narration and the
   exact committed target/roster projection.
3. T064 rewrites the two layers into one seamless player-facing narration and
   invites the player to choose the next immediate action without taking it.

These are three internal agent transactions in one player turn. The one-turn
rule does not authorize skipping, merging, or replacing them with a static
description. Advisory failure may use the existing truthful deterministic
fallback for that layer, but successful operation runs the complete chain.

## Compatibility disposition

Preserve travel routing, elapsed time, accepted immediate plot effects,
summaries, memories, narration, recovery, module publication, lifecycle
receipts, Save/Load/Reset responsiveness, and the next prompt. Retire only the
newly implemented execution of independent post-arrival sibling goals.

The earlier real hub, save, list, delete, and exit compound runs prove those
mechanisms could execute; they are not acceptance evidence for the corrected
player contract. Their standalone behavior remains unchanged.

## Acceptance

Use the unmodified headless client and real OpenAI calls. Judge authoritative
files and complete player-visible output.

1. “Travel to X” moves once, applies elapsed time once, narrates the committed
   destination, asks for the next action, closes recovery state, and reaches the
   next prompt.
2. “Travel to X, then buy Y, then exit” moves only to X. No purchase, inventory,
   storage, Save, exit, hub, or later action mutates. Arrival acknowledges the
   deferred plan and asks the player what to do next.
3. A direct cross-module request produces only `updatePartyTracker` then
   `updateTime`, transfers authority through the existing random-ID receipt,
   and reaches the target prompt.
4. A real model response containing a mismatched cross-module area/location is
   rejected before mutation, receives canonical scoped correction facts, and a
   corrected real response completes without engine exit.
5. Immediate travel-driven `updatePlot` remains ordered, receipt-backed, and
   crash-convergent. A plot change describing a future arrival activity is
   rejected semantically.
6. Standalone hub, save/list/delete, exit, character, roster, storage, and module
   workflows A/B unchanged.
7. Rejected candidates and correction notes never enter durable history. The
   final narration ends the travel beat and visibly returns agency to the
   player.
