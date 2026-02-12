## Context

NPC and PC state is persisted in character JSON files and party role membership is tracked in `party_tracker.json` via `partyNPCs` and `partyMembers`. Promotion can therefore be done by role transition and party-list movement, without file cloning. To preserve continuity across future transitions (including retirement), identity/lifecycle metadata should be explicit.

## Goals / Non-Goals

**Goals:**
- Add explicit, confirmable NPC -> PC promotion flow in GUI.
- Preserve one canonical character file and identity.
- Add durable lifecycle metadata (`character_id`, `_tabletop_role_history`).
- Keep current active PC unchanged after promotion.
- Run post-promotion audit/readiness checks and surface warnings.

**Non-Goals:**
- Implement PC -> NPC retirement UX.
- Modify combat runtime behavior.

## Decisions

### 1) Canonical identity continuity
Decision: Promotion updates role fields in-place in the existing character file.

Rationale:
- Preserves memory continuity and historical context.
- Prevents divergence from duplicate files.

### 2) Internal lifecycle history field
Decision: Use internal append-only `_tabletop_role_history` for transition events.

Event shape (proposed):
```json
{
  "timestamp": "2026-02-12T18:10:00Z",
  "action": "promoted_to_pc",
  "from_role": "npc",
  "to_role": "player",
  "source": "manage_party_add_existing",
  "actor": "dm"
}
```

Rationale:
- Keeps operational metadata out of core gameplay schema.
- Enables future retirement/restore traceability.

### 3) Stable character identifier
Decision: Ensure `character_id` exists on promotion; generate once if missing.

Rationale:
- Name changes/format shifts should not break identity continuity.

### 4) Confirmed promotion flow
Decision: Add preview + confirm UI for NPC promotion.

Rationale:
- Prevents accidental role changes in live sessions.

### 5) Add without auto-switch
Decision: Promotion adds to `partyMembers` and removes from `partyNPCs` but does not alter `active_character`.

Rationale:
- Matches facilitator preference and avoids surprise context switching.

## Risks / Trade-offs

- [Promotion of non-playable NPC state] -> Mitigation: post-promotion audit/readiness warnings; do not block unless critical schema failure.
- [Inconsistent role fields] -> Mitigation: centralized helper updates all role markers (`type`, `character_type`, `character_role`).
- [Future retirement mismatch] -> Mitigation: append lifecycle events now, with reversible semantics.

## Migration Plan

1. Add identity/lifecycle helper utilities.
2. Add backend list filtering metadata for NPC candidates.
3. Add promotion preview/apply endpoints with confirm requirement.
4. Add UI source toggle and Promote action.
5. Run audits and regression checks.

## Open Questions

- Should promotion be limited to current `partyNPCs` by default (recommended) or include all NPC files via optional filter?
