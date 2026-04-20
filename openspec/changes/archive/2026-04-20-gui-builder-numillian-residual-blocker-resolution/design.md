## Overview

This slice is a narrow follow-on to residual convergence closure. It does not add another general repair framework. It closes or cleanly classifies the four live Numillian blocker families that still survive the repaired readiness gate:

1. validator-targeted monster reference closure,
2. authoritative monster schema completion,
3. live prerequisite repair for `PP018 <- PP017`,
4. unchanged spatial contradictions split into repair-engine gap vs authored debt.

The canary for success remains `The_Hidden_City_of_Numillian`.

## Goals

### MUST

- Reduce or explicitly classify the remaining live Numillian validator failures.
- Use the validator's own expected-path output as the source of truth for residual monster closure.
- Repair only when the target change is uniquely provable from authoritative data already present in repo/module state.
- Persist a blocker-resolution canary artifact that compares previous and current live validator state.

### SHOULD

- Reuse the existing readiness-gate repair/reporting structure instead of introducing a second remediation path.
- Keep new logic concentrated in builder/readiness helpers, not in gameplay runtime code.

## Workstreams

### 1. Validator-Targeted Monster Closure

The current residual flow extracts missing monster slugs from validator errors, but Numillian still fails on `expected monsters/echoes_of_the_party.json`. This workstream should trace why the closure path does not land a validator-clearing file and then make the closure result explicit:

- if the expected file can be created/reused from authoritative source data, do so;
- if not, emit a residual classification that identifies the target slug/path as unresolved.

The output should distinguish:
- closure attempted and landed,
- closure attempted but unresolved,
- closure skipped because no authoritative source exists.

### 2. Authoritative Monster Schema Completion

`salt_wraith.json` still lacks `size`, `alignment`, and `armorClass` in the live canary. The existing schema-repair path should be tightened so it can backfill those fields when authoritative compendium/module source data exists. If no authoritative source exists, the result must remain fail-closed and classify the file as irreducible schema debt rather than pretending the repair succeeded.

### 3. Live Plot Prerequisite Resolution

The readiness gate now supports list-shaped `plotPoints`, but the real canary still reports `PP018` as missing an explicit prerequisite from `PP017`. This workstream should validate the live write path end-to-end:

- detect the exact plot structure in `module_plot.json`,
- apply the prerequisite where uniquely provable,
- confirm post-repair validator output actually clears the failure.

If a live repair does not clear the validator, the report must say whether the issue is:
- repair not applied,
- repair applied but validator still sees stale/other shape,
- ambiguous authoring that requires manual resolution.

### 4. Spatial Residual Split

The current residual flow correctly adds `spatial_structural_debt`, but the canary still keeps both `spatial_adjacency_convergence_gap` and `spatial_structural_debt`. This slice should make the split more explicit:

- unchanged contradiction set after deterministic repair => authored structural debt,
- contradiction set changed but still failing => repair-engine gap remains,
- contradiction set removed => closure advanced.

The goal is not necessarily to auto-fix all Numillian spatial contradictions; it is to stop blurring repair-engine limits with authored map debt.

### 5. Canary Advancement Reporting

The next canary artifact should make advancement measurable with fields such as:

- previous vs current total failure count,
- removed/added residual classes,
- whether live validator output improved,
- whether remaining failures are repair-engine gaps or author/content debt.

## Risks And Fallbacks

### MUST

- Do not fabricate monster schema values without authoritative source support.
- Do not inject plot prerequisites when the upstream dependency chain is ambiguous.
- Do not rewrite spatial connectivity or coordinates destructively just to reduce validator counts.

### SHOULD

- If a direct fix cannot be proven safe, classify the blocker and preserve the failure for human review.

## Verification Strategy

### MUST

- Add targeted regression tests for the exact residual blocker flows.
- Re-run the Numillian canary and persist a new blocker-resolution report artifact.
- Validate the OpenSpec change after drafting/implementation alignment.

### SHOULD

- Reuse existing readiness-gate tests where possible instead of introducing duplicate harnesses.
