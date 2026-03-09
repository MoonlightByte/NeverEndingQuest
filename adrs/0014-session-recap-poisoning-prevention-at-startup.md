# ADR-0014: Session Recap Poisoning Prevention at Startup

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Repeated startup recap constraints accumulated in history and blocked normal gameplay action generation.

## Decision
Run deterministic stale-recap cleanup at startup across both chat and conversation histories using a shared utility and script parity.

## Consequences
- Prevents context poisoning from stale recap directives.
- Improves reliability after repeated restarts.
- Requires maintaining known marker rules and cleanup tests.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
- `openspec/changes/archive/2026-03-02-startup-stale-recap-autocleanup/`
