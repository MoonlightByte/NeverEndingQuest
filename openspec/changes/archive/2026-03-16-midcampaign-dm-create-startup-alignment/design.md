## Context

The repository currently has two DM-driven PC creation stacks.

- Startup path:
  - `utils/startup_wizard.py:create_new_character()`
  - `utils/startup_wizard.py:ai_character_interview()`
  - startup-specific save and onboarding lifecycle
- Mid-campaign GUI path:
  - `web/routes/tabletop_party_routes.py:create_party_player()`
  - `utils/pc_manager.py:get_character_creation_prompt()`
  - `main.py:handle_character_creation_response()`
  - optional route-based finalizer in `web/routes/tabletop_party_routes.py:finalize_character_creation()`

The startup path is stable and upstream-aligned, while the GUI path has accumulated separate prompt-building, corrective retry, and persistence logic. This is the architectural drift we want to remove.

## Goals / Non-Goals

**Goals:**
- Make startup behavior the canonical baseline for DM-driven PC creation.
- Reuse one shared prompt/context and finalization core across startup and GUI DM creation.
- Keep startup and GUI adapters distinct where runtime semantics truly differ.
- Remove duplicate finalization ownership so fixes land once.

**Non-Goals:**
- Rebuild startup as a web-first wizard.
- Replace web creation-mode pause/resume with terminal-style interaction.
- Merge Roll Your Own or Add Existing into the DM creation refactor.

## Decisions

### 1) Shared creation core SHALL separate contract from transport

Decision: introduce a neutral shared service layer for DM creation that owns:
- prompt/context assembly
- final JSON extraction/sanitization
- audit/corrective-note generation
- persistence/finalization helper contracts

Startup and GUI remain adapters over that shared core.

Rationale:
- Startup and GUI differ in transport (`input()`/`print()` vs web queue + main loop), not in the underlying character-creation contract.
- A shared service collapses drift while preserving adapter-specific runtime semantics.

Alternatives considered:
- Reuse `startup_wizard.ai_character_interview()` directly from the GUI: rejected because it is terminal-coupled and would force the web flow into the wrong I/O model.
- Keep two paths and manually align prompts: rejected because this is the drift pattern that already failed.

### 2) Startup semantics SHALL be the behavioral baseline

Decision: startup interview behavior and validation expectations remain the reference behavior, while the shared core becomes the reusable implementation of that contract.

Rationale:
- Startup creation is already proven and efficient.
- Refactoring around the known-good path reduces risk compared with promoting the GUI path to canonical status.

### 3) Prompt/context assembly SHALL support startup and mid-campaign modes

Decision: prompt generation will move to a shared builder with an explicit mode contract:
- `startup`
- `mid_campaign`

Both modes share the same field/output contract, but mode-specific context is injected deterministically.

Mode differences:
- `startup`: level 1 onboarding, no conversation backup/restore, startup bootstrap framing
- `mid_campaign`: target level, current party/location context, ongoing-campaign join framing

### 4) Finalization SHALL have one owner contract

Decision: extract one finalization service used by:
- startup wizard after interview completion
- `main.py:handle_character_creation_response()`
- any retained route-based finalizer

Shared finalizer responsibilities:
- identify candidate JSON
- sanitize/extract fenced/raw JSON
- run `audit_character_creation(...)`
- produce deterministic corrective guidance on failure
- persist through one canonical save helper
- return structured results to caller adapters

Rationale:
- The current duplicated finalizers are a direct source of drift.
- A structured result contract allows startup and GUI to respond differently without duplicating the validation logic.

### 5) Persistence SHALL be standardized through one helper

Decision: centralize character persistence for DM-created PCs behind one helper/service instead of mixing module-aware startup saves with direct `characters/` writes.

Rationale:
- Save-path drift is already present.
- A shared helper makes future portability and lifecycle work safer.

## Architecture Boundaries

### Shared core responsibilities (MUST)
- Build canonical DM-creation prompt/context payloads.
- Normalize candidate final JSON.
- Run audit/correction logic.
- Return structured finalization outcomes.
- Own canonical persistence helper contract.

### Startup adapter responsibilities (MUST)
- Keep terminal interview loop behavior.
- Keep iterative onboarding and `startup_incomplete` lifecycle handling.
- Keep startup save/party bootstrap flow semantics intact.

### GUI adapter responsibilities (MUST)
- Keep `backup_conversation_history()` / `restore_conversation_history()` semantics.
- Keep creation marker lifecycle.
- Keep web queue submission and main-loop interception.
- Keep current target-level and mid-campaign context behavior.

## Risks / Trade-offs

- [Risk] A shared finalizer bug could affect both startup and GUI creation.
  - [Mitigation] Land the refactor behind targeted regression coverage for both adapters before broader changes.
- [Risk] Persistence unification could accidentally change startup save semantics.
  - [Mitigation] Extract helper first, then route startup through it with behavior-preserving tests.
- [Risk] The existing route-based finalizer may drift further if left partially wired.
  - [Mitigation] Either route it through the shared finalizer or explicitly reduce it to a thin wrapper.

## Migration Plan

1. Extract shared prompt/context builder with explicit startup vs mid-campaign mode support.
2. Route startup prompt construction through the shared builder without changing startup interview loop semantics.
3. Extract shared finalization/persistence service with structured result objects.
4. Route `main.py:handle_character_creation_response()` through the shared finalizer.
5. Route or collapse `/api/party/finalize_creation` to the same finalizer.
6. Add targeted regression coverage for startup parity and mid-campaign web creation behavior.

Rollback:
- Revert adapter wiring in reverse order while keeping new tests as documentation of intended parity.
- Preserve startup behavior first if any shared-core regression appears.

## Open Questions

- The exact helper/module names are implementation details, but the shared-core vs adapter boundary is mandatory.
- The final persistence helper may live in `utils/character_creator.py` or a new adjacent utility module; either is acceptable if the boundary remains clear.
