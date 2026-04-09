## 1. Publication Blocker Contract

- [x] 1.1 Define deterministic blocker classes for unresolved destination phrases, ambiguous destination phrases, missing NPC authority, and dangerous player-facing phrase collisions.
- [x] 1.2 Keep blocker policy bounded to authored or player-facing semantics so weak substrate hygiene warnings do not become noisy publication failures.
- [x] 1.3 Add focused contract coverage or source-contract tests for blocking vs warning boundaries.

## 2. Semantic Audit Upgrade

- [x] 2.1 Upgrade `scripts/module_semantic_authority_audit.py` so the standalone audit fails on publication-unsafe semantic contradictions.
- [x] 2.2 Preserve explicit structured output with deterministic `blocking_errors`, `warnings`, and summary counts suitable for later CI/readiness integration.
- [x] 2.3 Add any minimal additive payload fields needed by the audit to classify phrase collisions or observed player-facing phrases deterministically.

## 3. Regression Coverage

- [x] 3.1 Add regression tests proving unresolved authored destination phrases fail the semantic publication audit.
- [x] 3.2 Add regression tests proving missing NPC scene authority for authored visible or revealable NPCs fails the audit.
- [x] 3.3 Add regression tests proving weaker non-player-facing or incomplete substrate issues remain degraded warnings rather than blockers.

## 4. Verification

- [x] 4.1 Run targeted compile checks and semantic-authority audit regression suites.
- [x] 4.2 Run the upgraded audit against at least one real module with known semantic publication gaps and capture blocker output.
- [x] 4.3 Update `plans/module-publication.md` only if real findings change the later probe or publishable-gate sequence.
