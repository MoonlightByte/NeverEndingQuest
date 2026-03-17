## Why

The current web runtime keeps re-entering the main loop while no player input exists because `WebInput.readline()` eventually returns a synthetic blank line instead of blocking for real input. That churn repeatedly re-runs idle housekeeping, emits noisy debug lines, and makes the server feel as if it is "ticking away" despite no player action.

Separately, world time currently advances mostly when the model emits `updateTime` or when travel fallback injects it. This creates a UX mismatch where real player discussion time passes, but the world clock can remain frozen at the same morning timestamp across multiple turns or scene transitions.

## Objective

Implement a turn-synced wall-clock bridge that keeps world time feeling believable without introducing a continuous background timer.

## Non-Goals

- Do NOT add live background ticking while the game waits for input.
- Do NOT replace or weaken existing explicit `updateTime` action semantics.
- Do NOT introduce unbounded AFK time skips.
- Do NOT redesign the broader travel/action contract beyond the narrow time-sync surfaces required for this slice.

## What Changes

- Runtime MUST stop generating synthetic empty-input turns in the web path; no-input periods SHALL block until real user input arrives.
- Runtime MUST persist a per-session wall-clock marker and, on each accepted non-empty player turn, advance world time by elapsed whole real minutes since the previous accepted turn.
- Runtime MUST clamp turn-synced wall-clock advancement to a bounded maximum per turn so long AFK gaps do not fast-forward the campaign excessively.
- Runtime MUST fail open on malformed or missing wall-clock metadata by resetting the marker and preserving gameplay.
- Reconcile-first narrated-arrival commits MUST keep time synchronized with the committed location state, not just the location fields.
- Existing explicit `updateTime` behavior MUST remain authoritative and unchanged.
- SHOULD keep the implementation additive, merge-safe, and localized to helper/runtime surfaces instead of broad prompt rewrites.

## Capabilities

### New Capabilities
- `tt-web-input-idle-blocking`: web input handling blocks on real user input and SHALL not synthesize blank turns during idle waits.
- `tt-turn-input-wall-clock-sync`: accepted non-empty player turns SHALL advance world time by bounded elapsed real minutes.

### Modified Capabilities
- `tt-transition-time-sync`: inferred narrated-arrival travel commits SHALL include deterministic time advancement in the same effective commit cycle.

## Impact

- Affected code: `web/web_interface.py`, `main.py`, a new narrow helper under `utils/`, `utils/travel_state_sync_guard.py`, and targeted regression tests under `scripts/`.
- Affected systems: web input lifecycle, turn acceptance flow, party-tracker world clock persistence, travel reconcile-first time synchronization, and gameplay observability logs.
- Merge-safety impact: moderate; host-file edits MUST remain small and marked with `# TABLETOP MODE:` comments where applicable.
- SP/MP compatibility impact: MUST preserve single-player behavior and SHALL keep multiplayer semantics compatible; the turn-sync rule applies equally to accepted turns in both modes.
- Risk: medium; touching input blocking and time advancement can create hangs or double-advance if scoped loosely.
- Fallback: if wall-clock sync proves unsafe, runtime SHALL preserve existing explicit `updateTime` behavior and degrade to timestamp reset / no-op rather than inventing extra time changes.
