## Context

The combat stack in `core/managers/combat_manager.py` and `core/managers/multi_pc_combat.py` currently works, but it predates the recent narrator prompt-validator refactor. The current combat path still mixes prompt loading, broad runtime context injection, LLM validation, retry correction storage, and token-heavy duplicated state into one monolithic flow.

The narrator stack has already proven a better pattern in gameplay:

- canonical compressed prompt authority,
- threshold-based validation compression,
- deterministic routing telemetry,
- compact truth-pack validation context,
- validation-local retry correction handling.

This change ports that architecture pattern to combat without yet changing the underlying combat mutation contracts. That scope boundary is important: combat should become smaller, cleaner, and more deterministic before structured enemy-side mechanics or broader contract changes are introduced.

Key constraints:

- Python MUST remain ground truth for initiative, phase control, legality, and accounting.
- Combat narration MUST remain vivid and tactically competent.
- Enemy tactical intent MUST remain flexible within Python-owned legality constraints.
- Single-player compatibility MUST remain unchanged.
- TT host-file edits MUST remain minimal and clearly marked.

Stakeholders:

- facilitator using TT combat live at the table,
- player-facing combat narration quality,
- developer/operator needing smaller payloads and clearer validation logs,
- future builder agents who need a less fragile combat-manager surface.

## Goals / Non-Goals

**Goals:**
- Make compressed combat sim and validation prompts canonical runtime authority.
- Add contract tests so combat prompt/runtime/validator drift is caught early.
- Reduce duplicated runtime combat state packets and lower prompt token load.
- Add combat validation telemetry and threshold-based compression.
- Add compact touched-combatant truth packs for combat validation.
- Keep combat retry correction messages validation-local rather than polluting persistent combat history.

**Non-Goals:**
- No `updateEncounter.ops` support in this change.
- No first-class combat `requestRoll` migration in this change.
- No save/concentration contract redesign in this change.
- No rewrite of combat turn-resolution architecture.
- No change intended to reduce enemy tactical intelligence or narration quality.

## Decisions

### Decision 1: Compressed combat prompts become canonical runtime authority

**Decision:** Live combat simulation and combat validation SHALL load the compressed multi-PC combat prompt variants as the runtime authority.

**Rationale:** This matches the narrator refactor pattern, eliminates live drift between compressed and uncompressed prompt families, and concentrates prompt maintenance on the actual runtime contract.

**Alternatives considered:**
- Keep the current `USE_COMPRESSED_COMBAT` split for live behavior.
  - Rejected because it preserves drift risk in exactly the part of the system being hardened.
- Delete uncompressed prompts entirely.
  - Rejected because mirrored artifacts are still useful for docs/debugging and should be retired separately if desired.

### Decision 2: First-wave efficiency work focuses on packet reduction, not contract expansion

**Decision:** This change SHALL reduce overlapping combat runtime packets before changing action contracts.

**Rationale:** The largest immediate cost is repeated state, not missing rule text. Combat currently injects multiple overlapping sections covering initiative, phase, AC, creature state, encounter details, and formatted character sheets. Trimming duplication is lower risk than changing combat mutation behavior in the same slice.

**Alternatives considered:**
- Introduce structured enemy and PC ops in the same change.
  - Rejected for first wave because it broadens change risk and makes debugging harder.
- Only edit prompts and ignore runtime packet assembly.
  - Rejected because prompt-only slimming would leave large token waste in runtime-generated state blocks.

### Decision 3: Combat validation routing starts with telemetry and thresholded compression, not aggressive skip logic

**Decision:** Combat validation SHALL gain routing telemetry and threshold-based compression in this change, but SHALL remain conservative about validation skipping.

**Rationale:** Combat turns are mechanically denser and riskier than narrator turns. The first safe improvement is better observability and lower unnecessary compression overhead, not a large skip surface.

**Alternatives considered:**
- Add a broad combat validator skip path immediately.
  - Rejected because combat has more state mutation per turn and fewer safe low-risk branches.
- Keep unconditional compression and add telemetry only.
  - Rejected because compression policy is one of the easiest immediate efficiency wins.

### Decision 4: Truth-pack scope is touched combatants only

**Decision:** Combat validation truth packs SHALL cover only PCs/allied NPCs touched by candidate `updateCharacterInfo` actions.

**Rationale:** This aligns with existing structured character data helpers, keeps payloads compact, and targets the area where combat currently still relies heavily on prose accounting. Enemy-side combat mutations remain on the encounter-side prose path in this change, so enemy truth-pack expansion can wait for the deferred second wave.

**Alternatives considered:**
- Build full encounter truth packs for every combatant.
  - Rejected because it largely recreates the current heavy validation payload.
- Omit truth packs until structured combat ops land.
  - Rejected because touched-character truth packs already provide immediate value and mirror the narrator validation improvement.

### Decision 5: Combat retry corrections stay validation-local

**Decision:** Invalid-JSON retry notes and combat validation correction messages SHALL remain validation-local metadata rather than being appended as persistent user turns in combat history.

**Rationale:** This directly ports the retry hygiene lesson from the narrator refactor and reduces long-run combat prompt noise during multi-round encounters.

**Alternatives considered:**
- Preserve current history-appended retry behavior for compatibility.
  - Rejected because that behavior is itself part of the problem being fixed.

## Risks / Trade-offs

- **Risk:** Context trimming removes state the LLM was implicitly relying on.
  - **Mitigation:** Remove duplicate blocks first, preserve authoritative phase/tracker/touched-state packets, and validate against current combat regression suites.

- **Risk:** Compressed prompt authority changes runtime behavior unexpectedly.
  - **Mitigation:** Add source-contract tests before loader changes and keep uncompressed prompt mirrors for reference.

- **Risk:** Combat telemetry/compression helper wiring adds complexity inside `combat_manager.py`.
  - **Mitigation:** Prefer small helper extraction under `utils/` where practical and keep host edits minimal.

- **Risk:** Truth-pack integration improves touched character grounding but leaves enemy-side validation broad.
  - **Mitigation:** Accept this as a deliberate first-wave compromise; enemy-side structuring is explicitly deferred.

- **Trade-off:** This change improves efficiency and hygiene more than it improves mechanics structure.
  - That is intentional. It prepares the combat stack for a later structured-mechanics slice without overloading this first change.

## Migration Plan

### Phase 1 - Prompt authority and contract locks
- Add source-contract tests for compressed combat sim/validator authority.
- Switch live combat loader paths to compressed authority.

### Phase 2 - Runtime packet reduction and prompt slimming
- Add packet/prompt hygiene tests.
- Trim duplicated runtime packets and reorder/slim compressed combat prompts.

### Phase 3 - Validation efficiency and telemetry
- Add combat validation telemetry helper(s).
- Add threshold-based combat validation compression.
- Add touched-combatant truth-pack assembly and integration.

### Phase 4 - Retry hygiene
- Add tests proving retry corrections are not persisted into combat history.
- Move retry/correction notes into validation-local flow only.

### Rollback Strategy
- If regressions appear, first revert packet slimming and retry-hygiene wiring while preserving prompt authority tests and telemetry helpers.
- If prompt authority itself proves unstable, revert loader-path changes only after preserving the new contract tests for controlled reapplication.

## Open Questions

- Should combat validation telemetry share the existing narrator helper module or use a combat-specific wrapper around the same schema?
- How aggressively can `format_character_for_combat()` and `format_npc_for_combat()` be trimmed in this first wave without losing tactical usefulness?
- Should low-risk combat validator skipping remain entirely deferred, or should a very narrow query-only skip branch be allowed if tests show it is safe?
