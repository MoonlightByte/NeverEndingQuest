# Module Gameplay Audit Skill (Strict Validator)

## Purpose

Validate full NEQ module readiness with a single strict pass contract.

This skill now runs a consolidated validator that requires all gates to pass:
1. Gameplay parity gate (monster references and media parity)
2. Ingest sidecar gate (sidecar exists and passes require-success contract)
3. Schema gate (module validator passes with `jsonschema` available)

The module only passes when all enabled gates are green.

## Trigger Phrases

- "audit module gameplay"
- "validate module gameplay"
- "validate module readiness"
- "full module gate"
- "module validator"

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
- `gates.gameplay|sidecar|schema` (each with `status`, `reason`, `exit_code`)
- `blocking_errors`
- `fix_list`
- `strict_contract`

## Development-Only Overrides

These are available for local debugging only and should not be used for release validation:

```bash
# Skip sidecar gate
python3 scripts/audit_module_readiness.py --module <slug> --no-sidecar-gate

# Skip schema gate
python3 scripts/audit_module_readiness.py --module <slug> --no-schema-gate

# Disable strict gameplay heuristics
python3 scripts/audit_module_readiness.py --module <slug> --gameplay-dev-mode
```

## Legacy Compatibility

`scripts/audit_module_gameplay.py` remains available for focused monster parity analysis, but this skill treats `scripts/audit_module_readiness.py` as the canonical validator entrypoint.
