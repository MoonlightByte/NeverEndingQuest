## Context

Recent gametest regressions show that the runtime currently has no single authority for movement or tracked item possession.

Observed failure chain:

1. The narrator emits same-module movement or possession narration.
2. Python transition or inventory execution may fail, partially apply, or never run.
3. The special transition branch in `main.py` can still generate arrival/stitching narration after a failed transition action.
4. Conversation history is then rewritten to match the narrated outcome rather than the committed runtime outcome.
5. Later turns read a different mix of truth surfaces:
   - cached global location graph during transition validation,
   - fresh topology during some execution paths,
   - raw character files in the UI and DM surfaces,
   - selective validator truth packs,
   - narration-only skip routing that can bypass contradiction handling.

This split-brain architecture makes each narrow recovery patch less reliable over time. The design goal is to restore one authoritative Python-controlled contract for same-module transitions and tracked item possession, then explicitly mark the LLM seamless transition layer as dormant until it can be safely removed or revalidated.

Hard constraints:

- MUST preserve backward compatibility with single-player and tabletop flows.
- MUST preserve explicit action precedence when the LLM emits valid state actions.
- MUST keep Python as mechanical ground truth.
- MUST keep host-file changes narrow and marked with `# TABLETOP MODE:` comments where required.
- MUST keep user-facing Python logs/messages ASCII-only.
- SHOULD minimize prompt-surface churn while authority is being reset.

Stakeholders:

- Live facilitators who need reliable movement and inventory state during gametests.
- Future builders/agents who need an explicit record that the seamless transition post-processor is disabled, not silently abandoned.

## Goals / Non-Goals

**Goals:**

- Ensure same-module movement is validated and executed against one authoritative fresh topology snapshot.
- Ensure failed `transitionLocation` actions stop the turn cleanly and never produce synthetic arrival narration or false history.
- Ensure tracked item possession and party-to-party transfers are Python-owned and transactional.
- Ensure possession contradiction turns such as "Do I still have the relic?" cannot bypass authoritative checks as `narration_only`.
- Ensure multi-PC inventory grounding uses the active character, not an implicit first-party fallback.
- Explicitly document the seamless transition post-processor as disabled/dormant so it does not linger as accidental dead-weight architecture.

**Non-Goals:**

- No replacement of the entire narrator response pipeline.
- No broad event-sourcing or database migration.
- No new provider/router abstraction work.
- No attempt to improve or expand the disabled transition post-processor.
- No speculative generic parser for all narrated inventory situations.

## Decisions

### Decision 1: Same-module transition validation SHALL use a fresh authoritative topology snapshot

Same-module `transitionLocation` validation SHALL read fresh topology from current module area data at execution time instead of relying on a long-lived cached global graph.

Rationale:

- The live bug shows `NIG04 -> NIG05` can fail in runtime despite valid module connectivity.
- A fresh same-module snapshot removes stale-graph drift from the most common local transition path.

Alternative considered:

- Keep the global graph and just reload it more often.
- Rejected because it preserves split authority and makes correctness depend on cache timing rather than direct current topology.

### Decision 2: Transition commit and transition narration SHALL be separated by a hard success gate

Runtime SHALL treat movement state commit as the gate for any arrival narration, stitching, or history replacement.

Rationale:

- The current transition branch saves the assistant turn and generates cinematic arrival prose even after action failure.
- That behavior turns execution failure into accepted story fact, which then poisons later validation and scene state.

Alternative considered:

- Keep the current narration helper and only tweak its prompts.
- Rejected because the problem is post-failure invocation, not prose quality.

### Decision 3: The seamless transition post-processor SHALL be treated as dormant runtime code

The helper pair in `main.py` that generates and stitches arrival narration SHALL be considered disabled/dormant for active runtime use until a future change explicitly re-enables or removes it.

Rationale:

- The helper is an optional narrative beautifier, not a state authority.
- Leaving it silently present without documented status encourages accidental reactivation and future dead-weight code bloat.

Alternative considered:

- Delete it immediately in the same change.
- Rejected because documenting and disabling first gives a safer migration path and makes review easier.

### Decision 4: Tracked item possession SHALL be Python-owned and queryable without narrator interpretation

Tracked item possession, especially named story-critical items, SHALL be answered from committed character state. Narrator-only inference SHALL NOT be authoritative for possession queries.

Rationale:

- The reliquary drift shows that a later roleplay question can cause the narrator to contradict committed or intended inventory state.
- Players need the same answer from DM note, UI, and narration.

Alternative considered:

- Continue using narration-time recovery for possession questions.
- Rejected because this lets contradiction handling depend on prose shape rather than committed state.

### Decision 5: Party-to-party transfer handling SHALL be transactional at the runtime boundary

Explicit transfers of tracked items between characters SHALL commit atomically: either both sides persist or neither side persists.

Rationale:

- The current two-action model can partially fail, especially if giver ownership is stale in JSON.
- Atomicity prevents receiver-only or giver-only truth divergence.

Alternative considered:

- Keep two independent `updateCharacterInfo` mutations and add more reconciliation heuristics.
- Rejected because it increases patchwork behavior and hides partial failures.

### Decision 6: Validation routing SHALL reserve `narration_only` for genuinely non-authoritative turns

Turns that include explicit possession contradictions, tracked item checks, or other authoritative runtime questions SHALL NOT finalize through the low-risk `narration_only` skip path before Python-owned checks have run.

Rationale:

- Current skip routing is one of the main escape hatches that lets drift survive.
- The skip path should remain for pure flavor and umpire narration, not for contested mechanical truth.

Alternative considered:

- Disable `narration_only` entirely.
- Rejected because that would overcorrect and remove useful low-risk routing.

### Decision 7: Multi-PC inventory context SHALL resolve from active-character identity

When building inventory-aware DM context in multiplayer mode, runtime SHALL prefer the active character identity from `party_tracker.json` over `partyMembers[0]` fallback behavior.

Rationale:

- The current fallback can ground the wrong PC's inventory in multi-PC flows.
- This is a direct contributor to possession confusion during handoffs and pack checks.

Alternative considered:

- Pass richer inventory context for all PCs on every turn.
- Rejected for now because the simpler active-PC correction addresses the current failure with lower risk.

## Risks / Trade-offs

- [Risk] Tightening fail-closed movement behavior could surface more rejected turns during gametest. -> Mitigation: add focused regressions and keep same-module validation logic simple and explicit.
- [Risk] Transactional transfers may reject historical turns that previously half-worked. -> Mitigation: use explicit tracked-item scope first and keep informative error logging.
- [Risk] Disabling the seamless transition layer may temporarily reduce prose polish on successful movement turns. -> Mitigation: prefer correctness first and allow future re-enable only after state commit is trustworthy.
- [Risk] Changing skip routing may increase validation cost on a subset of inventory-question turns. -> Mitigation: narrowly target possession contradiction patterns rather than broadening all narration-only turns.
- [Risk] Fresh topology loading at transition time could add small overhead. -> Mitigation: scope the fresh read to same-module local movement, which is low-cost compared to LLM calls.

## Migration Plan

1. Add artifact/spec/test locks for same-module transition authority, transition failure history hygiene, inventory possession authority, and dormant transition post-processor documentation.
2. Implement authoritative same-module transition validation and route local moves through it.
3. Update transition processing flow so failed movement exits before arrival/stitching/history rewrite.
4. Disable or bypass seamless transition post-processor in the active runtime path, while documenting dormant status.
5. Implement transactional tracked-item transfer/possession authority and possession-query handling.
6. Fix multi-PC inventory context grounding to use active-character identity.
7. Update validator skip routing so authoritative possession checks run before `narration_only` skip.
8. Run targeted compile/tests/OpenSpec validation.
9. After successful gametest verification, decide whether dormant transition post-processor should be removed in a follow-up cleanup change.

Rollback strategy:

- If same-module transition reset is too disruptive, keep the fresh validator behind a narrow runtime switch while retaining the old graph path for comparison during debugging.
- If transactional transfer handling rejects too many legacy turns, narrow initial scope to tagged/tracked key items before widening.
- If documentation or dormant-layer marking lands before code changes, it remains safe and reviewable on its own.

## Open Questions

- Should transactional transfer be implemented as a new dedicated runtime helper while still accepting the existing two-action narrator contract as input, or should the narrator contract itself be narrowed in a later change?
- Should dormant seamless transition helpers remain in `main.py` with explicit disabled comments, or be moved into a quarantine helper module before eventual deletion?
- Should possession-query detection initially target named tracked items only, or all inventory checks that mention a concrete item label?
- Should the same-module fresh topology validator fully replace global-graph validation for local moves immediately, or run in parallel during one gametest cycle for comparison telemetry?