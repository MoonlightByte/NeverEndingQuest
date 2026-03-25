## Context

Multi-PC combat currently derives acting state from multiple partially overlapping sources:
- `party_tracker.json` for selected `active_character`
- `MultiPCCombatManager._state.current_pc_name` for selected PC focus
- `TurnQueueManager.current_turn_index` / `get_current_actor()` for prompt actor
- `encounter.creatures` for living and dead combatant truth
- character JSON files for persistent PC state

The failure mode in current gametest is not a single bad prompt. It is a coherence split across those sources. Mixed-form party identities create duplicate PCs at combat initialization, stale queue ownership leaks the wrong actor into the required-response block, dead enemies remain visible in player-phase turn windows, local `/att` resolution prefers dead enemy matches, and death-save outcomes are routed through a legacy character-update path that purges unsupported fields before persistence.

Constraints:
- Preserve upstream host flow with minimal `# TABLETOP MODE:` hooks.
- Preserve single-player behavior.
- Keep Python mechanics as authoritative truth.
- Use atomic JSON persistence only.
- Keep user-facing Python text ASCII-only.

## Goals / Non-Goals

**Goals:**
- Restore one canonical logical player identity per party member inside multi-PC combat startup and resume.
- Make selected active PC, prompt actor, and command-routing actor converge before each turn prompt.
- Prevent dead or inactive enemies from remaining valid player-facing targets.
- Prevent incapacitated PCs from using normal attack and damage commands.
- Persist death-save outcomes deterministically so crash and resume preserve combat truth.

**Non-Goals:**
- Do not redesign the entire combat prompt or validator architecture.
- Do not replace local combat commands with a different UX.
- Do not broaden scope into non-combat status systems beyond death-save persistence.
- Do not introduce a new database or external dependency.

## Decisions

### Decision 1: Canonical party dedupe MUST happen at combat-state ingestion, not only at party write time
The backend already attempts to dedupe `partyMembers` at write time, but combat cannot trust that all historical state is already clean. Combat startup and resume will perform a second canonical dedupe pass before building `pc_states` or injecting missing players.

Why:
- This protects existing dirty sessions and crash resumes.
- It localizes combat safety to combat runtime instead of assuming all upstream writers are correct.

Alternatives considered:
- Trust `party_tracker.json` because write-time dedupe exists. Rejected because current logs prove legacy or mixed-form data still reaches combat runtime.
- Normalize only in UI payloads. Rejected because the bug exists in backend turn ownership and prompt assembly, not only rendering.

### Decision 2: Selected active PC MUST be the authoritative player-phase actor for prompt generation
During `PC_PHASE`, prompt assembly will use the selected active PC after reconciliation instead of allowing stale `get_current_actor()` queue ownership to drive the required-response actor label.

Why:
- Current behavior mixes queue actor and selected actor, producing contradictory prompt state.
- Multi-PC tabletop mode explicitly supports facilitator-controlled PC switching inside the player phase.

Alternatives considered:
- Make queue index the only source of truth. Rejected because current tabletop UX intentionally allows active-PC switching without strict queue-only play.
- Continue dual-source behavior with extra warnings. Rejected because the current contradiction already contaminates prompts.

### Decision 3: Player target resolution MUST filter inactive enemies before partial-name preference
Local `/att` and `/dmg` resolution will first search for living canonical matches, then reject defeated-only matches instead of preferring the first enemy match regardless of state.

Why:
- Current target selection is biased toward the earliest enemy match, which repeatedly selects dead cultists.
- This bug corrupts both fast-lane encounter state and downstream narration.

Alternatives considered:
- Require explicit exact target IDs from users. Rejected because it worsens tabletop usability.
- Allow dead targets and let LLM correct it later. Rejected because fast-lane commands mutate encounter state before the LLM sees the turn.

### Decision 4: Incapacitated active PCs MUST be gated before fast-lane attack handling
If the active PC is at 0 HP and unconscious, fast-lane command routing will refuse ordinary combat actions and route the turn into death-save request and resolution flow only.

Why:
- Current code allows incapacitated PCs to become active and attack.
- This is a mechanics violation that also poisons turn history and prompt context.

Alternatives considered:
- Let the validator catch it. Rejected because the invalid action already mutates target state in fast-lane handling before validator correction.
- Hide incapacitated PCs from the turn system entirely. Rejected because they still need death-save turns.

### Decision 5: Death-save persistence MUST use explicit schema-supported deterministic fields
Character persistence will add schema support for `deathSaves` and deterministic combat ops support for death-save outcome updates. Supported death-save ops must be applied directly in Python and must not silently degrade into prose fallback or field purge.

Why:
- Current flow logs death-save updates but the schema purges `deathSaves`, so durable state is lost.
- Crash recovery requires committed counters, not narration-derived inference.

Alternatives considered:
- Encode death-save counters only in combat manager memory. Rejected because counters are lost on crash and resume.
- Continue prose-only update strings. Rejected because current purge/validation path has already shown silent data loss.

## Risks / Trade-offs

- [Canonical dedupe false-positive] -> Mitigation: dedupe only by existing normalized identity rules already used in party registration and tab sync.
- [Selected actor vs queue actor divergence] -> Mitigation: reconcile once before prompt assembly and emit targeted regression coverage for manual switch, active tab update, and player-phase prompt actor.
- [Death-save schema change touching legacy validators] -> Mitigation: keep field additive, update deterministic ops path first, and run focused character-validation regressions.
- [Fast-lane command guard breaking tabletop flow] -> Mitigation: guard only incapacitated PCs; conscious-PC `/att` and `/dmg` behavior stays unchanged.
- [Dead-target rejection changing facilitator habits] -> Mitigation: return explicit immediate feedback when only defeated matches remain so the facilitator sees why the command was blocked.

## Migration Plan

1. Add additive schema support and deterministic death-save persistence support.
2. Add combat-runtime canonical dedupe and living-target resolution safeguards.
3. Reconcile player-phase prompt actor selection with selected active PC.
4. Add incapacitated-command guard and death-save-only turn enforcement.
5. Run focused combat and character-validation regressions.
6. Roll back in reverse order if a regression appears, preserving schema additions unless they prove harmful.

Rollback strategy:
- Revert prompt-actor reconciliation independently from roster dedupe if turn-order behavior regresses.
- Revert strict incapacitated command blocking only after preserving death-save request routing, so invalid attacks do not reappear silently.
- Revert deterministic death-save ops only if a legacy-safe persistence fallback is already in place.

## Open Questions

- Should death-save deterministic ops use dedicated op names (`death_save_failure_delta`, `death_save_success_delta`) or a compact nested-set op contract? Recommendation: use explicit dedicated op names for validator clarity.
- Should defeated-only target matches return a hard error or a soft redirect suggestion listing living candidates? Recommendation: hard error with concise guidance to avoid silent retargeting surprises.

## Follow-up Notes

- SHOULD future-clean `core/managers/combat_manager.py` by extracting the long action-processing block into smaller helpers now that deterministic ops and persistence sync are threaded through it.
- SHOULD eventually represent `stable` as a first-class durable character-state concept; current persistence preserves stable death-save progress through `deathSaves` while character sheet `status` remains constrained to `unconscious` or `dead`.
