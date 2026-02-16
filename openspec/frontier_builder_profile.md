# Frontier Builder Profile

Purpose: keep OpenSpec artifacts reliable across model tiers (Kimi/Opus-class and GPT-5.3+ class) by separating hard contract from flexible execution guidance.

## Two-Layer Contract

- Contract Layer (MUST)
  - Normative, testable, enforceable statements.
  - Uses SHALL/MUST language for requirements and failure semantics.
  - Defines invariants, compatibility boundaries, and verification expectations.

- Guidance Layer (SHOULD)
  - Preferred implementation sequence, hints, and style guidance.
  - Non-normative notes for performance, readability, or maintainability.
  - Never overrides a MUST contract.

Conflict resolution:

- If SHOULD conflicts with MUST, follow MUST.

## Artifact Rules

- proposal.md
  - MUST: problem, objective, non-goals, risks, fallback.
  - SHOULD: rollout recommendations and sequencing hints.

- design.md
  - MUST: architecture boundaries, key decisions, trade-offs, migration and rollback.
  - SHOULD: implementation options and optimization notes.

- specs/*/spec.md
  - MUST: requirements and scenarios with explicit acceptance outcomes.
  - SHOULD: non-normative implementation guidance in separate guidance text.

- tasks.md
  - MUST: checkbox steps that are verifiable and dependency-ordered.
  - SHOULD: optional execution tips outside checklist items.

## Style Targets

- Keep MUST statements specific and unambiguous.
- Keep SHOULD guidance concise so stronger models can optimize without drifting from contract.
- Prefer additive compatibility language over rewrite language for merge-safe evolution.
