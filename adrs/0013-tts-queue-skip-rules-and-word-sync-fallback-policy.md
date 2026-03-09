# ADR-0013: TTS Queue, Skip Rules, and Word-Sync Fallback Policy

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
TTS autoplay created overlap/cacophony and read system/mechanical lines that harmed table pacing.

## Decision
Apply a queue-based narration policy:
- Sequential playback, one active item at a time.
- DM narration focus; mechanical/system lines can be tagged `skipTTS`.
- Browser word-sync when boundary events exist; otherwise reveal full text after watchdog timeout.

## Consequences
- More usable in-session audio behavior.
- Better readability on browsers without robust boundary events.
- Slight implementation complexity in queue and message metadata.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
