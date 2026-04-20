# GUI Builder Mixed Failure Classification

## Why
Real toolkit finisher payloads can contain both structured media debt and true semantic publishability blockers at the same time. `The_Ancients_Lab` proved that success-with-media-handoff is correct for pure media-only debt, but incorrect for mixed cases where unresolved destination aliases or other semantic blockers still exist.

## What Changes
- Define an explicit deterministic classification boundary between media-only debt and mixed failure.
- Ensure finisher and publishability reporting preserve failure semantics for mixed cases.
- Keep media-only handoff semantics limited to truly media-only debt.

## Capabilities
- Toolkit finisher SHALL distinguish pure media-only debt from mixed media-plus-semantic failure.
- Publishability reporting SHALL preserve explicit mixed-failure diagnostics.
- Toolkit finisher SHALL NOT emit success-with-media-handoff when semantic blockers remain.

## Impact
- Affected code: `web/extensions/toolkit_module_finisher.py`, `scripts/audit_module_publishability.py`, and targeted tests.
- Affected workflows: post-build finisher classification and operator-facing failure semantics.
- No UI ordering work or LLM remediation logic in this slice.
