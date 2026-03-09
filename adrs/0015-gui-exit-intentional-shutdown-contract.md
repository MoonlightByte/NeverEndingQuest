# ADR-0015: GUI Exit Intentional Shutdown Contract (Return Code 91)

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Operators needed deterministic GUI-based shutdown without terminal dependency or unintended launcher restart.

## Decision
Use explicit intentional-exit code `91`:
- GUI emits `user_exit` and shows shutdown overlay.
- Server exits with code `91` for intentional stop.
- Launcher treats `91` as no-restart shutdown; restart-on-`0` flows stay intact.

## Consequences
- Cleaner operator workflow during tabletop sessions.
- No accidental relaunch on intentional exit.
- Requires preserving return-code semantics in launcher logic.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`
