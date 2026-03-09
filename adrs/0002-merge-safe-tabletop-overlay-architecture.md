# ADR-0002: Merge-Safe Tabletop Overlay Architecture

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
This repository extends upstream NeverEndingQuest for in-person tabletop multiplayer while still tracking upstream updates.

## Decision
Implement tabletop functionality as a merge-safe overlay:
- Keep core host edits minimal and clearly marked with `# TABLETOP MODE:`.
- Prefer extension files for new behavior.
- Preserve single-player behavior by default.

## Consequences
- Upstream merges remain practical.
- Tabletop features stay isolated and easier to test.
- Architectural boundaries are explicit for future extraction into TT-only forks.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
