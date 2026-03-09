# ADR-0001: Documentation Authority Hierarchy and Canonical Memory Order

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Project knowledge was split across AGENTS, OpenSpec, plans, and legacy memory-bank notes. Contributors needed a deterministic authority order to resolve conflicts.

## Decision
Use this documentation authority order:
1. `AGENTS.md` for repo-wide architecture, standards, and workflow.
2. `openspec/changes/*` for active change requirements.
3. `plans/*` for planning and draft direction.
4. `memory-bank/*` as deprecated, non-authoritative legacy context.

## Consequences
- Conflicts are resolved quickly with less interpretation drift.
- Memory sync and doc updates become repeatable.
- Legacy notes remain useful but cannot override canonical guidance.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
- `~/.config/opencode/skills/sync-project-memory/SKILL.md`
