# GUI Builder Gameplay Readiness Payload Normalization

## Why
Gameplay audit JSON currently emits detailed findings under `target`, but readiness code reads parts of that payload as if they were top-level fields. This causes structured monster-media debt details to be dropped even when gameplay correctly reports them. The result is contradictory reporting such as non-zero gameplay findings paired with `toolkit_media_policy.structural_media_debt_count = 0`.

## What Changes
- Normalize gameplay payload access in readiness.
- Ensure readiness and publishability receive accurate structured monster-media debt details.
- Preserve gameplay audit exit-code semantics and current remediation behavior.

## Capabilities
- Readiness SHALL consume gameplay findings from the correct payload shape.
- Readiness SHALL compute correct structural media debt counts and slugs.
- Publishability SHALL receive accurate toolkit media policy metadata from readiness.

## Impact
- Affected code: `scripts/audit_module_readiness.py`, `scripts/audit_module_publishability.py`, and targeted tests.
- Affected workflows: toolkit/reporting accuracy only.
- No finisher semantics, UI ordering, or LLM logic changes in this slice.
