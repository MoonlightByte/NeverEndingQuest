## Context

TABLETOP MODE Multi-PC combat currently combines two orthogonal systems:
- Phase control (`PC_PHASE` vs `ENEMY_PHASE`) driven by Python state (`pc_phase_complete`, initiative start conditions, `/end` forcing).
- Initiative/rendering context built from encounter creatures and tracker payloads.

Recent `dmGroup` start behavior allows enemy-first opening, but the runtime can fail to transition cleanly back to PC control after the opening enemy batch. Separately, encounter creation can seed only the initiating player instead of all party members, which causes UI/LLM roster divergence.

Constraints:
- Preserve upstream merge-safe patterns and keep host edits minimal (`# TABLETOP MODE:`).
- Preserve existing single-player behavior.
- Keep Python state authoritative; prompt/UI must reflect that state.
- Use additive, backward-compatible state handling.

## Goals / Non-Goals

**Goals:**
- Define deterministic `dmGroup` opening-phase transitions that cannot remain stuck in enemy-only loop.
- Ensure encounter/runtime/UI all share one coherent player roster in Multi-PC combat.
- Provide safe recovery when persisted encounter files are partial or stale.
- Add targeted regression tests for phase transitions and roster recovery.

**Non-Goals:**
- Rebuilding combat engine architecture or replacing initiative model.
- Changing spell/action command grammar.
- Broad prompt rewrites unrelated to phase/roster coherence.

## Decisions

1) Explicit opening-phase state marker
- **MUST:** Add an additive encounter/runtime marker (for example `opening_enemy_batch_pending`) when `initiativeWinner=dmGroup` starts combat.
- **MUST:** Consume/clear this marker once the first enemy batch completes, then force `PC_PHASE` readiness (`pc_phase_complete=False`) unless no player can act.
- **SHOULD:** Emit structured debug logs when marker is set/cleared to simplify postmortem analysis.

Rationale: This prevents phase ambiguity and ensures enemy-first is one bounded transition, not a persistent lock.
Alternative considered: infer transition purely from round counters. Rejected because partial logs/retries make inference fragile.

2) Encounter roster normalization at two checkpoints
- **MUST:** During encounter generation in Multi-PC mode, include all `partyMembers` as `type:"player"` combatants.
- **MUST:** During combat start/resume, normalize encounter roster by backfilling missing player combatants from character files + `party_tracker.json`.
- **MUST:** Keep existing enemy/NPC data unchanged when applying backfill.
- **SHOULD:** Preserve existing initiatives; only assign defaults to newly injected players.

Rationale: Build-time + runtime normalization protects both fresh and legacy encounters.
Alternative considered: runtime-only backfill. Rejected because new encounters should be correct at source.

3) Initiative payload inclusion rules
- **MUST:** While combat is active, initiative payload includes player combatants even if unconscious/incapacitated, with status reflected accurately.
- **SHOULD:** Maintain current ordering and visual behavior for alive combatants to avoid UI churn.

Rationale: UI must not hide party members and create false "missing PC" diagnostics.
Alternative considered: keep alive-only filter and add a side channel. Rejected as it keeps two divergent truths.

4) Compatibility and guardrails
- **MUST:** Changes are runtime-gated to Multi-PC path; single-player path remains behaviorally compatible.
- **MUST:** All host modifications are marked `# TABLETOP MODE:`.
- **SHOULD:** New fields are additive and safely ignored if absent.

## Risks / Trade-offs

- [Phase transition over-correction] -> Mitigation: transition marker consumed once; regression tests for dm-first and pc-first paths.
- [Roster backfill duplicates combatants] -> Mitigation: normalize by canonical case-insensitive name and skip existing matches.
- [UI regression from expanded initiative list] -> Mitigation: preserve sort and type fields; only adjust inclusion criteria for player statuses.
- [Legacy encounter assumptions] -> Mitigation: fail-open normalization (log + continue) when character file missing; do not crash combat loop.

## Migration Plan

1. Implement additive state marker + phase flip logic in combat manager flow.
2. Implement encounter generation full-party player seeding in Multi-PC path.
3. Implement combat-start roster backfill normalization before turn queue initialization.
4. Update initiative payload filtering to include non-dead players even when unconscious/incapacitated.
5. Add targeted regression tests.
6. Validate with compile + focused combat smoke scenarios (`dmGroup` start and `pcGroup` start).

Rollback strategy:
- Remove/ignore additive marker and revert to existing phase logic.
- Disable runtime backfill path while retaining logging.
- Revert payload filter to previous behavior if UI issues are found.

## Open Questions

- Should incapacitated players always remain visible in initiative UI, or only when at least one enemy remains alive?
- Should `opening_enemy_batch_pending` be persisted to encounter file or only maintained in-memory during a simulation run?
