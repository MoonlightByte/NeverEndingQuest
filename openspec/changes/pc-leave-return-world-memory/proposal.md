## Why

PC retirement currently removes party membership but does not provide a first-class leave/return lifecycle that preserves narrative continuity through long-term world memory. We need this now to prevent memory loss-style behavior during live tabletop rotation and to establish the first gameplay-critical hook where `memory.db` is the long-term authority.

## What Changes

- Add a PC leave/return lifecycle flow where retirement and rejoin are explicit world events, not just party list mutations.
- Extend retirement API to accept optional departure text and queue graceful departure narration; if absent, narration defaults to mysterious disappearance.
- Add return narration that is memory-aware and references prior NPC/party relationships.
- Persist retirement/return as high-priority `role_transition` memory events linked to departing/returning PC and relevant witnesses.
- Update canonical entity state to reflect retired/active status and role timeline transitions without changing character identity.
- Maintain merge-safe behavior: route-level hooks and extension services only; preserve upstream-compatible single-player behavior.

Mandatory constraints:

- Retirement and return lifecycle persistence MUST be written to `data/memory.db` using canonical entity identity (no duplicate entity creation).
- Retirement flow MUST NOT purge NPC/world memory rows or remove prior memory links.
- Leave/return narration hooks MUST fail open for gameplay (party operations continue if memory writes fail).
- Host-file modifications MUST stay minimal and be marked with `# TABLETOP MODE:` comments.

Preferences:

- Journal JSON SHOULD receive concise mirror milestone entries for operator visibility.
- Retrieval context SHOULD prioritize identity/relationship continuity events for return narration.

Non-goals:

- Replacing the entire legacy companion memory subsystem in this change.
- Rebuilding full NPC emotional model generation from DB history.
- Altering upstream single-player core flow beyond compatibility-safe hooks.

## Capabilities

### New Capabilities
- `tt-pc-leave-return-lifecycle`: Retire/rejoin PC lifecycle with optional farewell input, graceful narration hooks, and party-safe runtime guardrails.

### Modified Capabilities
- `memory-role-transition-continuity`: Expand role-transition continuity from retrieval foundation to gameplay write hooks and entity retirement/reactivation state management.

## Impact

- Affected routes: `web/routes/tabletop_party_routes.py` (`/api/party/remove_character`, `/api/party/add_character`).
- Affected UI: `web/static/js/tabletop_mode.js` retirement flow payload.
- New memory service: `core/memory/party_transition_memory.py` for transition writes and retrieval-pack assembly.
- Prompt assets: new tabletop leave/return narration templates.
- Character file lifecycle metadata: append `_tabletop_role_history` events for retire/return transitions.
- Risk profile:
  - Memory DB unavailable/failed writes -> fallback path keeps party mutation + generic narration (degraded mode).
  - Duplicate/rapid retire clicks -> require idempotent event generation and route guards.
  - Active combat state -> retirement blocked by guardrail.
- SP/MP compatibility:
  - TABLETOP route hooks apply to multiplayer UI paths.
  - Single-player behavior remains unchanged unless the same endpoints are used.

## Execution Strategy

This change MUST be implemented via phased approval gates per the openspec-plan-to-builder skill:

- MUST execute ONE step at a time with verification gate before next step
- MUST stop after each phase for explicit user approval
- Default verbosity: **lite** (6-line capsule) unless user requests standard/full
- Each step MUST include verification gate checks before declaring complete
- Scaffolded tasks.md includes explicit PHASE GATE checkpoints

**Workflow:**
```
Plan emits step prompt → Builder executes one step → Plan verifies → Plan emits next step prompt
```
