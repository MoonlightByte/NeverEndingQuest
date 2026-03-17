## Context

The live narrator currently consumes a prompt payload that is good at preserving long-form continuity but weak at separating current-scene truth from historical narrative material. Recent transcript evidence showed the outbound payload still contained multiple prior location summaries and chronicles, a full module world atlas with remote NPC placement, and verbose completed-plot prose while the current turn was happening on Bandit Trail.

The validator already enforces deterministic NPC scene-presence rules correctly. The larger issue is that narrator generation receives too much mixed historical material, then fails closed when it re-materializes an off-scene NPC. The current fail-closed UX is also too opaque in web play: the user sees an apparent dead turn instead of a helpful retry message.

Constraints:

- MUST preserve fail-closed validation semantics.
- MUST not rewrite canonical conversation history for the conservative slice.
- MUST preserve current mechanical truth surfaces and recent raw turns.
- MUST remain merge-safe and backward compatible with single-player mode.
- SHOULD keep implementation local to `main.py` for the first pass.

## Goals / Non-Goals

**Goals:**

- Reduce off-location bleed by making narrator outbound payloads scene-first.
- Preserve current-scene truth, active plot pressure, recent raw turns, and companion memory context.
- Improve user-facing fail-closed behavior when retries exhaust.
- Add dedicated rejected-turn logging for diagnosis.

**Non-Goals:**

- No redesign of compression history generation or archive semantics.
- No live integration of `data/memory.db` or world-narrative DB retrieval.
- No validator architecture changes beyond preserving current behavior.
- No module-specific allowlist/denylist hacks.

## Decisions

### Decision 1: Apply narrator payload hygiene only at outbound assembly time

The runtime will sanitize `messages_to_send` inside `get_ai_response()` immediately before the live narrator LLM call.

- MUST: this sanitation path affects narrator generation only.
- MUST: canonical conversation history, compressed archives, and validator-local assembly remain unchanged.
- SHOULD: implement as small helper functions in `main.py` for the first slice.

Why this over rewriting stored history?

- Stored history changes are higher risk and harder to roll back.
- A narrator-only wrapper fixes the immediate signal-to-noise problem without destroying long-term evidence.

### Decision 2: Filter historical scene-rich content, not all continuity content

The sanitizer will remove or replace only the most contamination-prone surfaces:

- assistant `=== LOCATION SUMMARY ===`
- assistant `=== LOCATION CHRONICLE ===`
- system `=== COMPLETE MODULE WORLD ATLAS ===`
- verbose completed-plot prose in `=== ADVENTURE PLOT STATUS ===`

The sanitizer will preserve:

- canonical main system prompt
- current location packet
- current DM note / mechanical truth
- recent raw user and assistant turns
- companion memory packet
- active and upcoming plot pressure

Why this over fully rebuilding the narrator prompt from scratch?

- A full prompt-packet rewrite is a larger architecture change and harder to verify in one pass.
- Selective filtering is conservative and keeps the current flow recognizable.

### Decision 3: Compact completed plot history rather than remove all plot context

Active and upcoming plot pressure still matters to narration. The runtime will therefore rewrite plot status into a narrator-safe compact form instead of dropping the plot packet entirely.

- MUST: active and upcoming objectives remain visible.
- MUST: verbose completed-beat prose is omitted from the live narrator packet.
- SHOULD: the compacted text remain deterministic and easy to inspect in exported payloads.

### Decision 4: Fail-closed UX will split player copy from debug detail

Retry exhaustion remains fail-closed, but the user-facing system message should be non-technical and action-oriented.

- MUST: the live UI receive an immediate visible `[SYSTEM]` message when retries exhaust.
- MUST: detailed deterministic reasons remain in logs.
- SHOULD: player-facing copy avoid domain-specific validator jargon.

Why this over surfacing the raw validation reason?

- Raw deterministic reasons are useful for developers but confusing during play.
- Clear but generic player guidance keeps the UX stable while preserving diagnostics elsewhere.

### Decision 5: Rejected-turn logging is separate and fail-open

Rejected turns will be written to a dedicated JSONL file under `debug/quality_control/`.

- MUST: logs include timestamp, user input, rejection reason, raw response payload, and basic turn context.
- MUST: logging failures do not block gameplay or alter fail-closed control flow.
- SHOULD: use append-only JSONL for easy grep/manual review.

## Risks / Trade-offs

- [Payload too lean] -> Preserve recent raw turns, companion memories, current location, and active/upcoming plot context so the narrator still has continuity anchors.
- [Hidden dependence on atlas/history] -> Keep the change local and verify exported narrator payload plus live Bandit Trail-style transcript behavior before expanding scope.
- [Debugging becomes harder for non-developers] -> Split player-facing copy from detailed rejected-turn logs.
- [Future retrieval pressure returns] -> Treat DB-backed long-term retrieval as a separate OpenSpec change once this narrower hygiene slice is verified.

## Migration Plan

1. Add narrator-safe outbound helper(s) in `main.py`.
2. Apply helper(s) only in the main narrator generation path.
3. Add retry-exhaustion output and rejected-turn logging.
4. Add source-contract and behavior tests.
5. Verify exported narrator payload and transcript behavior.

Rollback strategy:

- Revert the narrator-only sanitizer and logging hook in `main.py`.
- Because the change does not rewrite canonical history or DB state, rollback is code-only.

## Open Questions

- Should a future change scope companion-memory packets by scene type or current module to reduce cross-module bleed further?
- Should future narrator packets use bounded `memory.db` retrieval via `get_context_memories(...)` once the scene-first baseline is stable?
