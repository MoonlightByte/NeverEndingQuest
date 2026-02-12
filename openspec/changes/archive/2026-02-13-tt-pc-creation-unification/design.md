## Context

TABLETOP MODE PC creation currently spans four separate flows that do not share a strict completion contract: startup wizard (campaign initiation), mid-campaign add-existing, Create with DM interview, and DM Quick-Create. The codebase already has strong schema assets (`schemas/char_schema.json`) and multiple creation handlers, but finalization checks are inconsistent and allow partial payloads into character files. This propagates to sheet rendering and PDF export quality.

Constraints:
- Keep upstream merge safety and minimize host-file rewrites.
- Preserve single-player compatibility.
- Keep Python state authoritative and persist with atomic JSON operations.
- Keep creation UX playable in a live tabletop session (fast recovery, clear errors).

Stakeholders:
- Table facilitator (needs fast, repeatable onboarding)
- Players (need complete and accurate sheets)
- Maintainers (need one validation path and low regression risk)

## Goals / Non-Goals

**Goals:**
- Introduce one shared creation validation/audit pipeline used by all PC creation entry points.
- Add startup multi-PC loop support without breaking SP startup flow.
- Make Add Existing list semantics truthful (exclude active party and dedupe).
- Improve Create with DM completion reliability (JSON extraction + schema enforcement).
- Replace DM Quick-Create with Roll Your Own and align form sections to 5e sheet structure.
- Add deterministic acceptance checks for all four scenarios before implementation close.

**Non-Goals:**
- No changes to combat manager behavior.
- No schema-breaking redesign of character JSON.
- No mandatory changes to upstream-only startup UX outside compatibility-safe extensions.
- No LLM provider routing/plumbing changes.

## Decisions

### 1) Centralize Creation Validation Behind One Service Boundary
Decision: Add a shared "creation audit" layer (module-level helpers) that performs normalize -> schema validate -> completeness audit -> optional enrichment for all creation paths.

Rationale:
- Removes duplicated and inconsistent checks across startup wizard, web routes, and main-loop finalizer.
- Ensures all produced characters meet one contract before persistence.

Alternatives considered:
- Patch each path independently: rejected (drift risk and repeated bugs).

### 2) Keep UI/Route/Core Responsibilities Explicit
Decision: Keep form/chat orchestration in UI/routes, and keep validation/completeness logic in shared utility/service code.

Rationale:
- Preserves extension-over-modification architecture.
- Makes behavior testable without web UI dependency.

Alternatives considered:
- Put validation in frontend only: rejected (easy bypass; server must be source of truth).

### 3) Use Bounded Recovery for DM Interview Finalization
Decision: On invalid/partial final JSON, keep creation mode active and emit a corrective prompt listing missing/invalid fields; do not auto-save partial sheets.

Rationale:
- Prevents malformed character persistence.
- Keeps table flow active with actionable recovery.

Alternatives considered:
- Auto-fill all missing with defaults silently: rejected (hides major authoring defects and weakens sheet quality).

### 4) Startup Loop Is Additive, Not Replacing SP Path
Decision: Startup supports iterative "add another player" loop and appends to `partyMembers`; if loop is skipped or fails, existing single-PC completion remains valid.

Rationale:
- Meets tabletop onboarding need while preserving existing startup semantics.

Alternatives considered:
- TT-only new startup path: rejected (higher divergence from upstream behavior).

### 5) Readiness Audit for Downstream Sheet and PDF Consumers
Decision: Add non-breaking readiness checks before sheet/PDF usage; warn or annotate, but do not mutate mechanics unless in explicit creation/fix flow.

Rationale:
- Detects creation regressions early and improves operator confidence.

Alternatives considered:
- Let render/export defaults mask data issues: rejected (defers failures and lowers trust).

## Risks / Trade-offs

- [Shared validator introduces central dependency] -> Mitigation: keep API small and add unit tests around normalize/validate/audit behavior.
- [Startup flow complexity increases] -> Mitigation: additive loop with explicit exit at each iteration and SP fallback.
- [DM interview may require extra correction turn] -> Mitigation: emit concise missing-field list and stay in creation mode.
- [Form expansion increases UI complexity] -> Mitigation: staged sections, defaults, and server-side canonicalization.
- [Potential route behavior change surprises] -> Mitigation: scenario-based acceptance tests and release notes for facilitator UX changes.

## Migration Plan

1. Introduce shared creation audit utility and tests (no behavior change yet).
2. Integrate utility into Create with DM finalization path.
3. Integrate utility into manual creation (Roll Your Own) and rename tab/UI labels.
4. Add Add Existing filtering + dedupe in backend list endpoint.
5. Extend startup wizard with multi-PC loop and append semantics.
6. Add sheet/PDF readiness audit hooks and warnings.
7. Run scenario acceptance checks and regression smoke tests.

Rollback strategy:
- Revert each integration step independently while retaining shared utility code.
- Disable startup loop and revert to single-character commit if onboarding issues appear.
- Keep SP defaults and existing endpoints intact throughout rollout.

## Open Questions

- Should readiness audit warnings be surfaced only to DM UI, or also in logs for batch validation scripts?
- For enrichment, should `backgroundFeature` generation run automatically or require explicit DM toggle?
- Should Add Existing support optional filters in UI (level/class/search) in this change or a follow-up?
