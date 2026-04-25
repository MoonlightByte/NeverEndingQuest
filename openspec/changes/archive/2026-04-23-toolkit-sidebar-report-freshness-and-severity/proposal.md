# Why

The Module Builder sidebar currently trusts any persisted `toolkit_build_report.json` failure payload, even when the report is legacy, stale, or missing the newer freshness contract. This causes false failure banners such as Numillian still showing `Build failed: unresolved destinations` after live audits already pass. It also risks overstating media debt when only non-structural warnings remain.

# What Changes

- Require sidebar failure derivation to honor `report_freshness` / `freshness_state` before surfacing persisted failure signals.
- Fail open for legacy or non-authoritative persisted reports rather than showing stale blocker text.
- Keep sidebar media handoff signals focused on structural media debt, preserving current compact failure text for genuinely current publishability blockers.

# Capability Scope

- Sidebar/backend derivation in `core/generators/module_stitcher.py`
- Regression coverage for stale versus authoritative persisted reports

# Non-Goals

- Running live audits from sidebar rendering
- Reworking toolkit templates beyond existing `brief_failure` / `media_generator_needed` consumption
- Replacing `toolkit_build_report.json` as the sidebar truth source

# Impact

- Removes stale false-negative/false-positive sidebar failures for modules like Numillian.
- Preserves real current failures for modules like Thornwood.

# Risks

- Hiding legacy failures too aggressively if freshness metadata is absent on an actually current report.

# Fallback

- Restrict the change to fail-open suppression only for failed reports lacking explicit freshness authority.
