## 1. Probe Fixture Contract

- [x] 1.1 Define deterministic fixture shapes for travel, escort/handoff, and hidden/revealable NPC discovery probes.
- [x] 1.2 Keep fixtures source-driven and canonical so expected targets and failure classes are reviewable without runtime AI execution.
- [x] 1.3 Add focused contract coverage for fixture parsing and probe-type boundaries.

## 2. Standalone Probe Harness

- [x] 2.1 Add a standalone semantic probe harness script that reads authored module semantics and executes publication probes deterministically.
- [x] 2.2 Reuse existing semantic-authority and semantic-audit outputs where appropriate instead of duplicating resolution logic.
- [x] 2.3 Emit explicit structured pass/degraded/fail output with per-probe results, summary counts, blocking errors, and warnings suitable for later CI/readiness integration.

## 3. Regression Coverage

- [x] 3.1 Add regression tests proving travel probes catch unresolved or misrouted destination semantics.
- [x] 3.2 Add regression tests proving escort/handoff probes catch continuity drift or unsupported expected targets.
- [x] 3.3 Add regression tests proving hidden/revealable NPC probes catch missing discovery authority while weaker fixture gaps remain degraded warnings.

## 4. Verification

- [x] 4.1 Run targeted compile checks and semantic probe regression suites.
- [x] 4.2 Run the probe harness against at least one real module with known publication-semantic gaps and capture structured output.
- [x] 4.3 Update `plans/module-publication.md` only if real findings change the final publishable-gate sequencing.
