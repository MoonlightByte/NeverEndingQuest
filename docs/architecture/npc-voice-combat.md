# NPC Voice in Combat

Purpose: Build one actor-isolated advisory voice batch for the current typed combat
window and carry it unchanged through T096, commit, and T097.

- Revision: `integration/npc-voice-episodic` at `fa1b27fe681e2f25c2da41876f74726e01519e14`
- Verified: 2026-09-01
- Doctrine: [GitHub issue #193 v2.3](https://github.com/MoonlightByte/NeverEndingQuest/issues/193)
- Visual companion: [NPC Voice Flow Map](../npc-voice-flow-map.html)

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Outer-turn liveness | Exact active `LiveTurnScope` object | Current and unsuperseded at admission/merge |
| Voice beat | `combat:<encounter>:r<round>:v<revision>:<actorIds>` | Child advisory scopes register as one complete batch |
| Actor voice | T105 result admitted under the matching child scope and NPC ID | Batch collection admits only current terminal results |
| Tactical choice | T096 intent over encounter, actor IDs, sheets, capabilities, resources | Voice map is advisory input, never mechanics authority |
| Mechanical result | Resolver plus combat transaction | Staged/apply receipts and committed event ledger |
| Narration | T097 over committed events and authoritative facts | Persisted advice may characterize only compatible behavior |
| Relationship memory | Accepted T105 batch | Sidecar write occurs only after the combat turn returns |

The admission tuple is the active parent scope object, its unsuperseded state, and each
child scope's `beat_id == batch_id`. `operation_id` names the parent operation, but exact
object identity is the current-authority check.

## Flow

### Dispatch and collection

1. After accepted non-empty player input, typed combat computes the exact actor window.
2. Automatic initiative steps and windows without eligible companions produce no T105 call.
3. Packet construction derives one beat ID from encounter, round, revision, and ordered actors.
4. `dispatch_batch` validates packets, registers the complete child-scope set, and starts one
   independent daemon monitor/thread per uncached actor.
5. T105 calls run in parallel.
6. `collect_to_completion` waits until every actor future is terminal, emits progress, and
   continuously rechecks authority. Its one-second wait is a heartbeat poll, not an elapsed
   abandonment limit.
7. Collection seals pending work and returns an actor-ID map as `MappingProxyType`.

### T096, transaction, and T097

1. The manager wraps the immutable map as `npc-voice-intents/v1` with `sourceBeatId`.
2. `execute_agentic_turn` normalizes and freezes the envelope once.
3. Every T096 correction attempt receives the same advisory map, filtered to exact pending
   actor IDs; say/do/want/thought cannot grant capabilities or change actor order.
4. Deterministic resolution owns legality and mechanics.
5. The first durable player request persists the envelope under
   `combatState.pendingTurn.npcVoiceIntents`, before any attack, damage, save, or choice pause.
6. `stage_events` preserves that same immutable envelope rather than replacing it.
7. Apply copies it into `pendingDelivery.npcVoiceIntents` with the committed turn.
8. T097 rebuilds its dossier from `pendingDelivery`. Its current combatant projection omits
   action-capability prose, and `authoritativeFacts` from the committed delivery slice is its
   sole action-history input.
9. `combatState.narrationActivity.recentFacts` remains complete T105 continuity input; it is
   not copied into T097's scene dossier.
10. After the turn returns, the accepted batch updates relationship working state idempotently.

### Failure terminals

1. Missing parent authority records `missing_authority`, makes zero physical calls, and leaves
   mechanics playable with an empty batch.
2. Supersession records `stale_rejected` and raises `LiveProviderSuperseded`; stale output
   cannot merge.
3. Invalid packets are omitted before dispatch.
4. Provider or contract failure records `provider_failure` or `invalid_contract`; after the
   two T105 contract attempts the actor becomes `degraded_this_beat` and other actors remain.
5. The pinned code has no `completed_invalid` disposition; contract-invalid completed output
   follows `invalid_contract -> degraded_this_beat`.
6. A malformed envelope at coordinator, stage, commit, or delivery is loudly omitted and never
   invalidates committed mechanics.

## State and atomicity

- Process memory: parent/child scopes, futures, cache, and immutable request map.
- Encounter JSON: the envelope first persists with the pending player request, remains unchanged
  through event staging, and moves `pendingTurn` -> `pendingDelivery` in the same committed turn.
- Relationship sidecar: `data/companion_memories/npc_agent_state.json`.
- Encounter persistence uses transaction `safe_write_json` and the existing staged/apply replay.
- Sidecar writes take the path lock, reread/copy/validate, increment revision, and
  `safe_json_dump`; corrupt or unsupported input latches read-only.
- Telemetry is observational and failure-isolated.

## Load-bearing seams

1. `utils/capture/live_provider_call.py` `LiveTurnScope` (anchors moved by #284) - parent scope and supersession.
2. `utils/capture/live_provider_call.py:173-226` - child scopes and complete-set registration.
3. `core/npc/voice_context.py:1257-1266` - exact combat beat ID.
4. `core/npc/voice_service.py:720-727` - batch dispatch entry.
5. `core/npc/voice_service.py:849-917` - parallel per-actor threads.
6. `core/npc/voice_service.py:1000-1047` - authority recheck before merge.
7. `core/npc/voice_service.py:1084-1128` - completion-bounded collection and progress.
8. `core/npc/voice_context.py:35-107` - actor map and immutable projection.
9. `core/managers/combat_manager.py:4588-4703` - dispatch, collect, envelope, T096 handoff.
10. `core/managers/combat_orchestrator.py:101-149` - copy-once immutable envelope.
11. `core/ai/combat_agent.py:371-426` - exact pending-actor T096 projection.
12. `core/managers/combat_transaction.py:811-940` - pending-turn persistence.
13. `core/managers/combat_state.py:953-975` - pending-turn to pending-delivery copy.
14. `core/managers/combat_orchestrator.py:706-755` - T097 dossier delivery path.
15. `core/npc/voice_context.py:1510-1615` - accepted sidecar commit.

## Invariants

- #193 Part 1 B2(vi).
- #193 Part 2, Combat.
- #193 Part 2, NPC systems.
- #193 Part 2, Provider routing and startup.
- #193 Part 2, Acceptance.
- #193 Part 5, Fork-3; No-Limits; Single-Path.

## Open items

- #254 - combat T105 liveness and empty-stage degradation.
- #255 - stale voice development tests after combat/transition integration.
- #259 - T105 say/do/want loss before T096/narration.
- #262 - No-Limits retirement outside the voice wave.
- #269 - accepted T105 sidecar batch lost at combat roll pause.
