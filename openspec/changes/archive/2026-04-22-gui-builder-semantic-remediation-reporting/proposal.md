# GUI Builder Semantic Remediation Reporting

## Why
Toolkit publishability already distinguishes media-only debt from true semantic blockers, but the builder workflow still surfaces semantic failures mostly as raw JSON payloads or generic `not_publishable` messaging. That makes authoring defects harder to resolve and obscures the intended next step for any module that is structurally built but still blocked by semantic publication findings.

## What Changes
- Add a generalized builder-facing semantic remediation lane for toolkit builds that fail publishability because of semantic blockers.
- Surface semantic blocker detail from structured audit fields instead of relying on raw JSON dumps.
- Preserve the existing distinction between pure media handoff, semantic remediation, and mixed media-plus-semantic failure.
- Keep all semantic remediation review-only; no automatic repair or LLM autonomy is added in this slice.

## Capabilities
- Toolkit UI SHALL render a distinct semantic remediation section when semantic publishability blockers are present.
- Toolkit reporting SHALL expose structured semantic blocker detail for any module, not just specific canaries.
- Toolkit reporting SHALL preserve mixed-failure semantics when media debt and semantic blockers coexist.

## Impact
- Affected code: toolkit finisher result consumption, toolkit upload/build UI rendering, and targeted reporting tests.
- Affected workflows: toolkit post-build operator guidance and semantic blocker follow-up.
- No change to semantic authority extraction rules, media generation policy, or final Python publishability authority.
