## Overview

This change is a narrow follow-on to readiness convergence hardening. The previous slice added convergence classification and residual blocker reporting; this slice closes the concrete residual gaps the Numillian canary exposed.

The design principle is simple:

- MUST consume the validator's actual residual outputs.
- MUST repair only when the transformation is deterministic and source-backed.
- MUST classify and stop when safe repair cannot be proven.
- SHOULD preserve the current convergence reporting surfaces so progress remains measurable.

## Problem Frame

Current Numillian canary outcome:

- `convergence_outcome=repair_budget_exhausted`
- residual classes:
  - `monster_reference_closure_gap`
  - `monster_schema_completion_gap`
  - `plot_prerequisite_gap`
  - `spatial_adjacency_convergence_gap`

This means the repair engine is no longer blind. It is now incomplete in four specific places.

## Design Goals

1. Close unresolved monster references using validator-derived expected paths, not only authored monster candidate lists.
2. Repair schema-incomplete monster files from authoritative source data when available.
3. Match actual `module_plot.json` shapes used by current toolkit output when inserting finale prerequisite gates.
4. Either converge repeated spatial contradictions or classify them explicitly as author-facing debt.
5. Keep Numillian as the primary residual-closure canary.

## Architecture

### 1. Validator-Driven Monster Reference Closure

The readiness gate currently sees `reference_integrity` failures but closure is still mostly driven by authored monster hydration candidates.

This slice adds a deterministic bridge:

- parse validator error payloads for expected monster file paths,
- normalize back to canonical monster identities,
- invoke shared monster materialization or file reuse against that derived set,
- revalidate and classify any unresolved remainder.

MUST rules:

- use validator-derived missing refs as the authoritative closure target,
- preserve fail-closed behavior for unresolved or ambiguous names,
- never fabricate monster files without authoritative source support.

### 2. Authoritative Monster Schema Completion

Existing monster files may be present but incomplete (`salt_wraith.json`). Materialization alone will skip them as `existing`, so closure requires a second deterministic repair path.

Repair strategy:

- load current monster JSON,
- load compendium lookup or other authoritative source records,
- backfill only safe required fields such as `size`, `alignment`, `armorClass`,
- write atomically,
- classify as unresolved when authoritative source data is unavailable.

MUST rules:

- repair only from authoritative source data,
- never invent required schema values,
- emit explicit unresolved file list when completion cannot be performed safely.

### 3. Live-Shape Plot Prerequisite Repair

The current repair attempted prerequisite insertion but skipped with `plot_points_missing`, which indicates a mismatch with the actual `module_plot.json` structure.

This slice should:

- inspect and support the real live plot payload shape used by toolkit output,
- find final/conclusion beats and uniquely provable immediate predecessors,
- add explicit prerequisite gates only when uniquely derivable,
- preserve ambiguity as classified debt rather than guessing.

### 4. Stronger Spatial Escalation

Spatial remediation is already shared, but Numillian produced unchanged contradictions with `changed=0`.

This slice should:

- reuse shared spatial planning/remediation first,
- compare pre/post contradiction sets,
- if contradictions remain unchanged, classify as author-required structural debt,
- keep report surfaces explicit about non-convergence.

This does not require over-expanding the repair budget. It requires stronger closure or cleaner escalation.

## Reporting

Reporting SHOULD continue using the existing convergence artifact shape, but MUST clearly show:

- whether residual closure advanced the canary,
- which residual classes remain,
- whether failures are still repair-engine gaps or now author/content debt.

Suggested artifact interpretation:

- previous slice proved classification,
- this slice must prove closure progress.

## Risks And Fallbacks

### Risk: Over-aggressive repair mutates authored content incorrectly

Mitigation:

- MUST restrict repairs to deterministic, source-backed transforms.
- MUST preserve fail-closed ambiguity handling.

### Risk: Spatial contradictions remain inherently ambiguous

Mitigation:

- classify as author-facing structural debt instead of retrying.

### Risk: Live plot shapes vary across modules

Mitigation:

- support current toolkit-emitted shape first,
- degrade to explicit ambiguity classification when shape inference is not safe.

## Validation Strategy

- Add focused regression tests for validator-driven monster reference closure.
- Add tests for schema completion using authoritative monster source data.
- Add tests for actual `module_plot.json` prerequisite repair shape.
- Add tests proving unchanged spatial contradiction sets are escalated as structural debt.
- Re-run Numillian canary and persist updated artifact showing whether it advanced beyond the previous residual set.
