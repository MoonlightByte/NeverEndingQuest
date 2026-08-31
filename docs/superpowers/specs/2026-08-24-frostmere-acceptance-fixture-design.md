# Frostmere Acceptance Fixture Repair

## Scope

Repair only ignored combat-acceptance fixture data. Do not modify production code,
the source runtime campaign, tracked Frostmere module files, or historical evidence.

## Design

Add one ignored local helper that copies an existing Frostmere acceptance game into
a fresh target, rewrites the copied root `party_tracker.json` to the canonical tuple
`Shadows_of_Frostmere / FV001 / AJ01 / Frostbound Guildhall`, and validates that the
selected area contains exactly one matching location ID and name. The helper must
write atomically and fail before provider or game startup when the source module,
area, location, or name is inconsistent.

Historical evidence directories remain immutable. Future headless and browser runs
use the newly prepared target. A deterministic negative probe against the stale
`A01 / FV001` tuple must fail, and a prepared target must pass the same preflight.

## Acceptance

- Source and historical evidence hashes are unchanged.
- The new target root tracker contains `AJ01 / FV001 / Frostbound Guildhall`.
- The target module tracker and `FV001.json` agree with the root tracker.
- The stale `A01 / FV001` tuple is rejected before startup.
- No tracked production, campaign, prompt, schema, or test file changes.
