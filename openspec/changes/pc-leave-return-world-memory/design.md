## Context

Current retirement behavior in TABLETOP MODE removes a PC from `party_tracker.json` but does not treat leave/return as durable world events. This causes weak continuity when a retired PC returns later, because relationship recall and lifecycle milestones are not consistently written into long-term memory.

The repository already has the long-term memory foundation (`entities`, `entity_roles`, `memory_events`, `memory_links`, deterministic retrieval) and a merge-safe route architecture. This change uses those existing primitives to make PC leave/return the first gameplay-critical long-term memory hook.

Hard constraints:

- The long-term lifecycle record MUST be written to `data/memory.db` and tied to canonical entity identity.
- Party operations MUST remain available when memory writes fail (degraded but playable path).
- Core host edits MUST remain minimal and marked `# TABLETOP MODE:`.
- Single-player compatibility MUST be preserved.

Implementation preferences:

- Route layer SHOULD orchestrate narration + memory writes because it has `user_input_queue` and request context.
- Memory logic SHOULD live in a dedicated extension module to preserve merge safety.

## Goals / Non-Goals

**Goals:**

- Implement retirement and return lifecycle events as first-class `role_transition` memory events.
- Support optional player-authored departure text and fallback mysterious departure behavior.
- Queue graceful leave/return narration that can include NPC reactions informed by memory retrieval.
- Preserve canonical character identity and role timeline continuity across retire/rejoin cycles.
- Prevent accidental memory loss by forbidding purge semantics during retirement.

**Non-Goals:**

- Replacing legacy companion-memory generation/compression in this change.
- Introducing new global config flags for activation (reuse existing runtime patterns).
- Redesigning Manage Party UI beyond a minimal farewell input extension.

## Decisions

### Decision 1: Add `core/memory/party_transition_memory.py` service as the single lifecycle write/read hook

Decision:

- Introduce a focused service with:
  - `record_pc_retirement(...)`
  - `record_pc_return(...)`
  - `build_return_memory_pack(...)`

Rationale:

- Keeps memory lifecycle logic out of route handlers.
- Reuses existing memory DB APIs (`create_memory_event`, `create_memory_link`) and retrieval queries.
- Keeps extension boundaries clear for upstream merges.

Alternatives considered:

- Inline SQL in route handlers: rejected (high coupling, lower testability, harder merge maintenance).
- Put logic in `pc_manager.py`: rejected because `pc_manager.py` should remain state mutation utility, not narration/memory orchestrator.

### Decision 2: Use route-layer orchestration for retire/rejoin narrative hooks

Decision:

- `web/routes/tabletop_party_routes.py` will:
  - validate guards,
  - call lifecycle memory service,
  - mutate party membership,
  - enqueue leave/return narration prompts.

Rationale:

- Route already controls request payload and `user_input_queue`.
- Preserves existing flow patterns used by Add Existing and character entrance.

Alternatives considered:

- Queue narration in frontend only: rejected (server must produce authoritative narrative context and memory retrieval package).

### Decision 3: Dual-write lifecycle metadata (DB authority + character history mirror)

Decision:

- `memory.db` is authority for leave/return lifecycle retrieval.
- Character file `_tabletop_role_history` receives mirrored retire/return event for local inspection continuity.

Rationale:

- Supports forward migration to DB authority while preserving file-level auditability.
- Maintains consistency with existing promotion lifecycle metadata pattern.

Alternatives considered:

- DB-only with no file mirror: rejected for operator visibility and continuity with current lifecycle trace patterns.

### Decision 4: Retirement safety guards and fail-open behavior

Decision:

- Block retirement during active combat and when retiring the final party member.
- If memory writes fail, proceed with party mutation and queue fallback narration.

Rationale:

- Protects combat state integrity and prevents invalid table state.
- Keeps sessions playable even when memory subsystem is degraded.

Alternatives considered:

- Hard-fail retirement on DB write error: rejected due poor live-session resilience.

### Decision 5: Prompt templates for leave/return narrative shape

Decision:

- Add:
  - `prompts/tabletop/retirement_narration.txt`
  - `prompts/tabletop/return_narration.txt`

Rationale:

- Keeps style/prompt logic out of route code.
- Mirrors existing entrance narration pattern and supports faster tuning.

## Risks / Trade-offs

- [Risk] Duplicate leave/return events from double-clicks or repeated calls -> Mitigation: deterministic idempotency key and route-side duplicate suppression.
- [Risk] DB unavailability in live session -> Mitigation: fail-open route path with warning logs and generic narration fallback.
- [Risk] Inconsistent witness linking if party context mutates mid-request -> Mitigation: snapshot party context before mutation and use snapshot for memory links.
- [Risk] Overly noisy narration prompts from large memory packs -> Mitigation: bounded retrieval limits and concise summary formatting.
- [Trade-off] Dual-write complexity (DB + file mirror) -> Accepted to balance migration safety and operator visibility.

## Migration Plan

1. Add transition-memory service and tests (no route wiring yet).
2. Wire retirement endpoint with guards, optional farewell input, and narration queue.
3. Wire return endpoint with retrieval-backed narration queue.
4. Add character lifecycle mirror events for retire/return.
5. Run targeted lifecycle tests + memory regression suite.

Rollback strategy:

- Disable route calls into transition-memory service while keeping existing `add/remove` behavior.
- Keep prompt templates inert if narration hook disabled.
- Do not delete existing DB rows (non-destructive rollback).

## Open Questions

- Should retirement set canonical role to `retired_player` or close role without a dedicated active role row? (Recommendation: explicit `retired_player` for query simplicity.)
- Should return narration include both NPC and remaining-PC witness reactions by default, or only NPCs? (Recommendation: include both, cap output length in prompt.)
- Should journal mirror be mandatory for MVP or best-effort optional? (Recommendation: best-effort optional.)

## Builder Phase Contract

This design assumes phased execution per openspec-plan-to-builder:

### Step Isolation
- Each step (1.1, 1.2, etc.) edits ONLY the files scoped for that step
- No cross-phase work before approval gate
- Builder MUST stop after each PHASE GATE task (1.4, 2.5, 3.4, 4.4, 5.5) and wait for approval

### Verification Gates (Required per Step)
1. **Compile/Syntax**: `python3 -m py_compile [files]`
2. **Behavior Smoke**: expected functionality works
3. **Compatibility**: no breaking changes to existing callers
4. **Scope Compliance**: only allowed files modified

### Verdict Flow
- **PASS** → proceed to next step
- **FAIL** → retry step with corrections
- **NEEDS_FIX** → specific fix instruction

### Fail-Open Constraints (Route Phases 2-3)
- Party mutations MUST succeed even if memory persistence fails
- Narration MUST queue even if memory context unavailable
- Logs MUST emit degraded-mode warnings when fallback triggers
