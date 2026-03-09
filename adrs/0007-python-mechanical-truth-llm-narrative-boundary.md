# ADR-0007: Python Mechanical Truth and LLM Narrative Boundary

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Narrative memory occasionally contradicted actual mechanical state (for example exhaustion/HP drift at session boundaries).

## Decision
Enforce this authority boundary:
- Python state is ground truth for mechanics (HP, conditions, slots, saves).
- LLM retains narrative freedom but must not contradict mechanical truth.
- DM Note state and `@STATE_SYNC` rules override stale narrative memory.

## Consequences
- Higher player trust in mechanical consistency.
- Better narrative coherence from explicit state visibility.
- Slight prompt/token cost increase for stronger state synchronization.

## Sources
- `AGENTS.md`
- `memory-bank/ONCNotes.md`
- `plans/version-2/v2-narrative-track.md`
