# GUI Builder Gameplay Readiness Payload Normalization

## Builder Review Draft

Purpose: define the bounded deterministic slice that fixes gameplay-to-readiness payload shape handling so structured monster-media debt is reported accurately.

This is a builder-facing review artifact for the small reporting bug only.

## Intent

The next slice SHALL fix a deterministic payload-shape mismatch:

1. `scripts/audit_module_gameplay.py` emits JSON under `target`
2. `scripts/audit_module_readiness.py` currently reads gameplay fields as if they are top-level
3. result: gameplay still fails by exit code, but structured `monster_media_findings` are lost and `toolkit_media_policy.structural_media_debt_count` can incorrectly report `0`

This slice SHALL normalize the payload handling without changing the core gameplay audit contract unnecessarily.

## Evidence Baseline

- In `scripts/audit_module_readiness.py`:
  - `evaluate_gameplay_gate(...)` reads `payload.get("blocking_errors")` and `payload.get("warnings")`
  - `_build_fix_list(...)` reads `gameplay_json.get("monster_media_findings")`
  - toolkit media policy assembly also reads gameplay data from the raw JSON as if it were top-level
- User-provided `Murder_at_the_Drowning_Lass` payload proved the contradiction:
  - gameplay listed 14 structural missing-media findings with `outcome: provider_disabled_missing`
  - but `toolkit_media_policy.structural_media_debt_count` came back `0` and slugs were empty

## MUST Contract

- The builder SHALL keep scope limited to deterministic payload normalization between gameplay audit output and readiness/publishability consumers.
- The builder SHALL preserve the gameplay audit’s structural media findings and existing exit-code semantics.
- The builder SHALL make readiness and publishability reflect structured monster-media debt accurately.
- The builder SHALL preserve source-aware toolkit remediation guidance.
- The builder SHALL NOT use LLM classification or heuristic widening in this slice.
- The builder SHALL NOT change unrelated finisher UI behavior.

## SHOULD Guidance

- Prefer a small normalization helper instead of ad hoc repeated `target` access in multiple places.
- Prefer compatibility-safe reads that tolerate both current and legacy payload shapes if easy to do.
- Keep the fix readable and testable.

## Proposed Step Sequence

### Step 1 - Normalize gameplay payload access

Introduce a bounded normalization path so readiness code reads gameplay findings from the correct shape.

### Step 2 - Propagate corrected structured debt reporting

Ensure `_build_fix_list(...)`, toolkit media policy summary fields, and publishability consumers all receive accurate structural media debt data.

### Step 3 - Add targeted regression coverage

Add tests that prove:

- gameplay findings nested under `target` are consumed correctly
- `toolkit_media_policy.structural_media_debt_count` and slugs are correct
- publishability receives accurate toolkit media debt metadata

### Step 4 - Verify against the known contradiction case

Confirm the `Murder_at_the_Drowning_Lass`-style contradiction is eliminated.

Acceptance target:

- no more `count=0` when gameplay lists structural missing-media findings
- readiness and publishability expose accurate debt summaries
- no unrelated semantics change

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-gameplay-readiness-payload-normalization` Step 1-4 only.

Goal: fix the small deterministic payload mismatch so gameplay audit findings under `target` are consumed correctly by readiness and publishability reporting.

Allowed files:

- `scripts/audit_module_readiness.py`
- `scripts/audit_module_publishability.py`
- targeted tests for readiness/publishability payload handling

Forbidden:

- broad gameplay audit redesign unless absolutely necessary
- finisher outcome semantics work
- toolkit UI ordering work
- LLM-assisted ambiguity handling

Required:

- normalize gameplay payload access
- ensure structured monster-media debt counts/slugs propagate correctly
- preserve existing exit-code and remediation behavior
- add focused regression coverage

Edit Strategy: Apply one anchored patch at a time, then re-run `py_compile` before the next patch.

Verification:

- `python3 -m py_compile scripts/audit_module_readiness.py scripts/audit_module_publishability.py`
- run targeted readiness/publishability tests
- provide one concrete before/after example showing corrected debt count/slug propagation

Output:

- normalization approach used
- files changed
- test/compile outcomes
- example corrected toolkit media policy payload

## Review Questions

1. Do you want this slice to support both top-level and nested `target` gameplay payload shapes for compatibility, or should it normalize only the current nested shape?
2. Should the normalization helper live in `audit_module_readiness.py` only, or be extracted for reuse if publishability also benefits directly?
3. Is a small textual/report artifact update desirable here, or should this stay strictly code-and-tests only?
