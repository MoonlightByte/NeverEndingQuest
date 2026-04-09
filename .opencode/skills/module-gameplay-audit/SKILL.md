# Module Gameplay Audit Skill (Strict Validator)

## Purpose

Validate full NEQ module readiness with a single strict pass contract.

This skill now runs a consolidated validator that requires all gates to pass:
1. Gameplay parity gate (monster references and media parity)
2. Ingest sidecar gate (sidecar exists and passes require-success contract)
3. Continuity gate (continuity contract passes strict required-key checks)
4. Schema gate (module validator passes with `jsonschema` available)

The module only passes when all enabled gates are green.

## Trigger Phrases

- "audit module gameplay"
- "validate module gameplay"
- "validate module readiness"
- "full module gate"
- "module validator"
- "spatial backfill"
- "remediate module spatial"
- "module spatial contract"

## Default Command (Strict)

```bash
python3 scripts/audit_module_readiness.py --module <module_slug>
```

JSON output:

```bash
python3 scripts/audit_module_readiness.py --module <module_slug> --json
```

## Gate Contract

### 1) Gameplay Gate

Runs strict gameplay audit:

```bash
python3 scripts/audit_module_gameplay.py --module <module_slug> --json --strict-instructions
```

Pass criteria:
- Exit code is 0
- `blocking_errors` is empty

### 2) Sidecar Gate

Runs ingest sidecar audit:

```bash
python3 scripts/homebrew_sidecar_audit.py --slug <module_slug> --require-success --json
```

Pass criteria:
- Exit code is 0
- `valid=true`
- `sidecar_found=true`

### 3) Schema Gate

Runs module schema validator:

```bash
python3 core/validation/validate_module_files.py --module <module_slug> --json
```

Pass criteria:
- Exit code is 0
- Validator summary has no failures

Hard fail rule:
- Missing dependency (for example `jsonschema is not installed`) is a fail, not a degraded pass.

## Exit Codes

- **0**: All required gates pass
- **1**: One or more required gates fail

## Output Contract

`audit_module_readiness.py --json` returns:

- `module`
- `overall_status` (`pass` or `fail`)
- `gates.gameplay|sidecar|continuity|schema` (each with `status`, `reason`, `exit_code`)
- `blocking_errors`
- `fix_list`
- `strict_contract`

## Development-Only Overrides

These are available for local debugging only and should not be used for release validation:

```bash
# Skip sidecar gate
python3 scripts/audit_module_readiness.py --module <slug> --no-sidecar-gate

# Skip continuity gate
python3 scripts/audit_module_readiness.py --module <slug> --no-continuity-gate

# Continuity warn-first mode
python3 scripts/audit_module_readiness.py --module <slug> --continuity-warn-mode

# Skip schema gate
python3 scripts/audit_module_readiness.py --module <slug> --no-schema-gate

# Disable strict gameplay heuristics
python3 scripts/audit_module_readiness.py --module <slug> --gameplay-dev-mode
```

## Legacy Continuity Remediation

For existing modules created before continuity v1 enforcement, run remediation first:

```bash
python3 scripts/remediate_module_continuity.py --all --apply
```

Then enrich narrative cross-module refs:

```bash
python3 scripts/enrich_module_cross_refs.py --all --apply
```

Then re-run strict readiness validation:

```bash
python3 scripts/audit_module_readiness.py --module <module_slug>
```

## Legacy Spatial Remediation

For existing modules created before spatial contract enforcement, remediate spatial fields before strict schema validation:

### Safe Rollout Order

1. Analyze current area/map structure first.
2. Dry-run remediation for one module.
3. Verify area location IDs align with map room IDs.
4. Apply remediation only after checking that authored topology/layout is preserved.
5. Re-run schema validation immediately.

### Commands

Dry-run one module:

```bash
python3 scripts/remediate_module_coordinates.py --module <module_slug> --dry-run
```

Analyze parity and predicted remediation impact before apply:

```bash
python3 scripts/analyze_module_spatial_parity.py --module <module_slug>
```

JSON output:

```bash
python3 scripts/analyze_module_spatial_parity.py --module <module_slug> --json
```

Apply one module:

```bash
python3 scripts/remediate_module_coordinates.py --module <module_slug> --apply
```

Bulk dry-run:

```bash
python3 scripts/remediate_module_coordinates.py --dry-run
```

Validate after apply:

```bash
python3 core/validation/validate_module_files.py --module <module_slug>
```

### Expected Remediation Effects

- Add `aliases` per location
- Add 9-cell `tactical_grid` per location
- Add/normalize `coordinates` to align area locations with map rooms
- Add cardinal `directions` in map rooms
- Add `spatialContractVersion: 1` to remediated area/map files

### Safety Contract

- Preserve authored `connectivity`
- Preserve authored map `layout` when present
- Preserve existing map room metadata fields during backfill
- Treat map/location parity failure after remediation as a blocker

### Suggested Audit Pattern

Run this sequence when spatial remediation is in scope:

```bash
python3 scripts/analyze_module_spatial_parity.py --module <module_slug>
python3 scripts/remediate_module_coordinates.py --module <module_slug> --dry-run
python3 core/validation/validate_module_files.py --module <module_slug>
python3 scripts/remediate_module_coordinates.py --module <module_slug> --apply
python3 core/validation/validate_module_files.py --module <module_slug>
python3 scripts/audit_module_readiness.py --module <module_slug>
```

## Legacy Compatibility

`scripts/audit_module_gameplay.py` remains available for focused monster parity analysis, but this skill treats `scripts/audit_module_readiness.py` as the canonical validator entrypoint.

## Continuity Gate Contract

Readiness now includes continuity contract checks:

```bash
python3 scripts/module_continuity_audit.py --module <module_slug> --json --strict
```

Pass criteria:
- Exit code is 0
- `blocking_errors` is empty

Advisory quality signal:
- Empty `cross_module_refs` emits continuity warning with enrichment fix guidance.

Warn-first behavior:
- Alias ambiguity and unknown target modules are warnings (degraded), not blockers
- Missing required continuity keys become blockers only when strict mode is enabled
