## Context

The publication plan is now past the substrate phase. The repository has:

- continuity/readiness groundwork
- toolkit finishing parity
- spatial authoring groundwork
- semantic-authority payload generation
- a standalone semantic-authority audit surface

What it still lacks is the policy layer that turns semantic-authority findings into explicit publication blocker classes. Right now a module can have unresolved destination phrases or missing NPC authority and still only produce degraded diagnostics. The next slice should make those failure classes explicit and stable without yet widening into synthetic gameplay probes or the final `publishable` gate.

## Goals / Non-Goals

**Goals:**
- Define deterministic blocker classes for semantic publication contradictions.
- Upgrade the semantic-authority audit so it can fail on publication-unsafe destination and NPC authority gaps.
- Keep audit output structured and stable enough for future CI/readiness/release integration.
- Keep this phase standalone from the later `publishable` gate.

**Non-Goals:**
- Implementing synthetic travel/escort/hidden-NPC gameplay probes.
- Wiring `ready` vs `publishable` into repo policy.
- Reworking runtime travel/NPC validators to consume the new audit output.
- Broadening into spatial publication probes or release UI changes.

## Decisions

### Decision: Semantic publication blocker classes MUST be explicit and deterministic
- Rationale: the publication audit must be auditable by developers and stable across modules.
- Blocking classes should include:
  - unresolved destination phrase with authored provenance
  - ambiguous destination phrase that cannot resolve uniquely
  - missing NPC scene authority for authored visible/revealable NPCs
  - phrase collisions where a likely player-facing phrase would route to the wrong valid location
- Alternative considered: keep generic degraded warnings until the final `publishable` gate.
- Rejected because later gating needs settled blocker semantics first.

### Decision: The audit SHOULD remain standalone in this phase
- Rationale: the next slice should harden the policy and result shape before it is wired into broader readiness/release workflows.
- Approach: keep `scripts/module_semantic_authority_audit.py` as the canonical surface, with structured JSON and deterministic text output.
- Alternative considered: immediately add the semantic audit as a hard dependency of `audit_module_readiness.py`.
- Rejected because that would combine blocker-policy definition and repo-gate rollout in one step.

### Decision: Phrase-collision blocking MUST focus on likely player-facing phrases, not every alias overlap
- Rationale: not all alias duplication is equally dangerous. The audit should block the collisions that would realistically misroute natural-language play.
- Approach: treat destination phrases observed in authored prose and canonical player-facing aliases as higher-confidence blocker inputs than obscure internal labels.
- Alternative considered: block every duplicate alias regardless of observed/player-facing relevance.
- Rejected because it would create noisy failures disconnected from real gameplay semantics.

### Decision: Report surfaces MUST clearly distinguish blocker findings from non-blocking diagnostics
- Rationale: later CI and release gates need a stable contract now.
- Approach: return explicit `blocking_errors`, `warnings`, and summary counts; preserve provenance for each finding.
- Alternative considered: infer blocking state only from aggregate counts.
- Rejected because the operator needs exact failure reasons for remediation.

## Proposed Blocking Policy

This phase should enforce:

- **Block** when a destination phrase appears in authored content and remains `unresolved`.
- **Block** when a destination phrase appears in authored content and remains `ambiguous`.
- **Block** when an authored NPC is visible or revealable in module semantics but has no deterministic scene-authority path.
- **Block** when a player-facing phrase collides across valid destinations strongly enough that natural-language routing would drift.
- **Warn** for weaker substrate hygiene issues such as missing optional provenance details or empty sections that do not yet correspond to authored semantics.

## Risks / Trade-offs

- [Too many blockers from weak imported prose] -> Mitigation: restrict blocking to authored/observed player-facing phrases and concrete NPC authority gaps, not every low-confidence substrate warning.
- [Audit policy drifts from later release gating] -> Mitigation: keep JSON output stable and explicit so the later `publishable` gate can consume it unchanged.
- [Need for substrate tweaks discovered mid-audit] -> Mitigation: allow narrow additive payload changes in the same slice only if required to support deterministic blocker classification.

## Migration Plan

1. Define blocker classes and expected pass/degraded/fail outcomes in specs and tasks.
2. Upgrade `scripts/module_semantic_authority_audit.py` to emit blocking findings for destination/NPC contradictions.
3. Add focused regression tests for blocking and warning boundaries.
4. Validate on at least one real module with known semantic publication gaps.
5. Optionally add small report-surface notes, but stop short of wiring repo-wide publishable gating.

## Open Questions

- Should player-facing phrase collision severity be inferred only from observed authored phrases, or also from canonical location aliases never mentioned in prose?
- Should the audit expose a machine-readable `blocker_classes` array in addition to `blocking_errors` strings?
- Is there a narrow, non-gating summary field that ingest/toolkit should mirror in this phase, or should stronger reporting wait for the final `publishable` gate slice?
