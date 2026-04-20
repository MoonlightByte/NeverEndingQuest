## Overview

This change closes the gap between the live Numillian module and the deterministic remediation paths that are supposed to clear it. The target is not a new generalized framework. The target is exact reconciliation of four mismatches that the current canary proves are still alive.

The implementation remains fail-closed:

- MUST reconcile only from deterministic, validator-visible, module-authored evidence.
- MUST NOT loosen validator behavior just to make the canary green.
- SHOULD classify unresolved cases explicitly as author/content debt when deterministic repair cannot be proven.

## Problem Breakdown

### 1. Monster authority vs validator mismatch

`Echoes of the Party` is authored as a structured monster reference in `TMS001.json`, so the validator expects `monsters/echoes_of_the_party.json`. But `module_context.json` also catalogs `echoes_of_the_party` under `npcs`, and `build_module_monster_authority(...)` excludes known NPC slugs from the authorized monster roster. That makes deterministic closure report `unauthorized_monster_reference` for a validator-visible monster.

Design requirement:

- validator-visible structured monster references MUST be reconcilable with the authorization roster when their authored usage is unambiguously monster-shaped.
- NPC filtering SHOULD remain intact for true NPC identities, but MUST NOT hide a structured monster reference from deterministic closure.

### 2. Canonical schema recovery gap

`salt_wraith.json` lacks required schema fields, but authoritative source data exists under a near-match compendium identity (`salt_wraiths`). The current schema repairer only attempts exact slug lookup.

Design requirement:

- schema repair MUST try safe canonical recovery layers before declaring irreducible failure.
- safe layers SHOULD be bounded to deterministic variants such as singular/plural normalization or source-backed canonical aliases, not fuzzy open-ended search.

### 3. Plot repair targets the wrong node

The validator flags `PP018 <- PP017`, but the current repairer chooses the numerically terminal node (`PP019`). That is a repair-targeting bug, not a missing framework.

Design requirement:

- plot prerequisite repair MUST derive the target from the validator-failing plot edge when available.
- fallback to terminal-node inference SHOULD only happen when the validator does not identify the failing node precisely.

### 4. Spatial parity drift

The active area files were repaired to cardinal adjacency, but `map_GLQ001.json` and `map_TUS001.json` still contain the old coordinates. This is not just abstract spatial debt; it is live area/map parity drift.

Design requirement:

- spatial remediation MUST synchronize paired `map_*.json` coordinates/directions from repaired area truth when the mapping is unambiguous.
- only after parity sync attempt fails or leaves unchanged contradictions SHOULD the residual classify as author/content debt.

## Technical Approach

### Monster reference reconciliation

Add a validator-derived override path that uses the actual unresolved validator target slug and the authored area content to decide whether the identity is legitimately monster-scoped. If a slug appears in `locations[].monsters[]`, that evidence MUST take precedence over broad NPC filtering for deterministic closure of that slug.

Likely implementation surface:

- `utils/module_monster_authority.py`
  - augment authority construction/resolution with structured-monster evidence precedence
  - or add a narrow helper used only by readiness repair for validator-derived slugs

### Monster schema canonical recovery

Extend `_deterministic_repair_monster_schema(...)` to attempt bounded alternate slug resolution before giving up:

- exact slug
- singular/plural variant
- deterministic alias recovered from authoritative source if available

Recovered fields must still come from authoritative compendium data, not guessed defaults.

### Validator-edge plot repair

Parse the failing plot progression error text to extract the target node and upstream dependency. Repair should write the explicit `prerequisites` edge into the live `module_plot.json` shape that produced the error.

### Area/map parity synchronization

Use the repaired area room coordinates as the canonical source for paired map room coordinates when room ids match uniquely. Directions should then be recomputed or normalized from the synchronized coordinate graph if safe.

## Reporting

Canary/report outputs should answer one question clearly: did reconciliation materially advance the live validator result?

Reporting MUST include:

- whether reference reconciliation advanced,
- whether schema reconciliation advanced,
- whether plot-edge repair advanced,
- whether area/map parity sync advanced,
- which remaining blockers are still repair-engine gaps vs author/content debt.

## Risks And Fallbacks

### Risk: false monster authorization

If reconciliation overrules NPC filtering too broadly, NPC-only identities could be treated as combatants.

Mitigation:

- MUST scope override to identities explicitly present in structured `locations[].monsters[]` evidence.

### Risk: over-broad schema recovery

If slug recovery is too fuzzy, the wrong compendium entry could backfill a monster file.

Mitigation:

- MUST restrict recovery to deterministic bounded variants only.

### Risk: map sync mutates authored special layouts incorrectly

Mitigation:

- SHOULD sync only when room-id parity is direct and unambiguous.
- MUST classify instead of forcing a rewrite when parity cannot be proven safely.
