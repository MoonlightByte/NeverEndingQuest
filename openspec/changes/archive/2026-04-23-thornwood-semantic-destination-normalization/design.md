# Context

Thornwood’s semantic authority payload already contains the needed anchor:
- `north tower overlook` -> `RO06` resolved
- `north tower` -> unresolved

The unresolved short-form is sourced from the same authored location name/alias surface as the resolved full phrase. This is exactly the kind of deterministic short-form normalization that should be fixed in authored module semantic data.

# Goals

- Resolve `north tower` to `RO06` without widening ambiguity rules.
- Remove the stale unresolved-destination diagnostic entry.
- Align `Merchant Lira` scene authority with her authored placement at `TW06`.

# Non-Goals

- Generic semantic-authority algorithm changes.
- Changes outside Thornwood module content.

# Decisions

1. `north tower` SHALL be resolved directly to `RO06`.
2. The diagnostics summary SHALL no longer list `north tower` as unresolved.
3. `Merchant Lira` SHALL gain `visible_location_ids: ["TW06"]` because the module already places her there in `npcs.merchant_lira.appears_in`.

# Architecture

- Directly patch `modules/The_Thornwood_Watch/module_context.json`.
- Keep the fix additive and deterministic.

# Risks / Trade-offs

- The semantic payload is generated content, so manual normalization can drift from future regeneration.
- This is acceptable because the issue is current, module-specific, and deterministic.

# Migration Plan

1. Patch Thornwood semantic authority entries.
2. Re-run semantic authority and publishability audits.

# Verification Plan

- `.venv/bin/python scripts/module_semantic_authority_audit.py --module The_Thornwood_Watch --json`
- `.venv/bin/python scripts/audit_module_publishability.py --module The_Thornwood_Watch --json`
