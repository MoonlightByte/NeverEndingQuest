# ADR-0003: Upstream-First Extend-Do-Not-Replace Policy

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Past merge regressions occurred when local modifications replaced upstream structures rather than extending them.

## Decision
Adopt upstream-first integration rules:
- Preserve upstream UX and structure intact.
- Add narrow hooks only when needed.
- Avoid broad rewrites in host files.

## Consequences
- Lower risk during upstream sync.
- Better behavioral parity with upstream features.
- Slightly more indirection, but substantially safer merges.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`
