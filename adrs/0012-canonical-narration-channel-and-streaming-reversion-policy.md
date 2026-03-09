# ADR-0012: Canonical Narration Channel and Streaming Reversion Policy

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Player-facing streaming drafts introduced instability (JSON leakage, duplicate output, UX regressions).

## Decision
Use one canonical narration path for user-visible output and keep streaming infrastructure dormant unless reintroduced under a hardened contract.

## Consequences
- Stable, predictable narration UX.
- Future streaming work can reuse retained backend scaffolding.
- Real-time draft rendering is intentionally disabled for now.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-02-15-streaming-ux-reversion/`
