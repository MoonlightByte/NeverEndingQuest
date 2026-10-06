# Shared desktop polish port

Base: public main `f18f4128d8539371884c01d422c4cc1d08420623`.

## Included

- Requested checks expose one server-owned prompt token. Quick d20s, manual faces and automatic rolls submit through the same single-use boundary. The engine still owns bonuses and advantage/disadvantage; free rolls never fabricate a modifier. Typed numeric dice remain supported by the legacy browser.
- Free dice insert a player-written sentence into the existing draft. Individual d20s remain separate; only damage dice receive a combined total. Desktop Insert roll sits at the right beneath Clear.
- Check results remain in the rules/DM context without a second mechanical Dungeon Master message.
- Player replies align right, narration uses the available story width, and the approved gold dragon identifies the Dungeon Master.
- New narration starts at its beginning, preserves older reading, and offers an unread-response button. Reduced motion remains respected.
- Generated scenes open in a focus-managed preview with image-only zoom/pan/pinch and keyboard close.
- Progress appears above the input, preserving the draft and placeholder. Configuration, billing, retry and recovery instructions remain explicit.
- Reconnect history replaces stale browser history while preserving messages received during hydration. Connection notices are temporary rather than campaign entries.
- Browser startup restores its status callback before starting the worker and publishes launching before ready. A completed welcome handback reopens a parked input boundary only after synchronous work and lifecycle checks finish.

## Deliberately excluded

Account/seat capacity, sponsored keys and quotas, hosted catalog/entitlements, hosted Quick Start and onboarding, moderation policy, hosted image model/reference prompting, deployment configuration, and the separate hosted mobile layout. Public provider settings, local startup and save/load/exit controls remain in place. No NQL binary or rule calculation was changed.

## Validation

- TypeScript compilation and production Vite build.
- Complete frontend unit suite: 389 passing tests, including dice combinations, stale/disconnected submission, history replacement, image preview and reading position.
- 26 backend tests pass across input readiness, rolls, companion grounding and provider settings. Real Flask-SocketIO tests for manual/automatic/legacy dice, reconnect, invalid/stale/duplicate requests and paused-game rejection.
- Input boundary tests reproduce welcome handback busy state and verify subsequent command acceptance; restore/supersession never unlock. Fast startup verifies callback and event ordering.
- Browser workflow checks at 1280/1440, plus existing map, save, settings, reconnect, combat and responsive-shell checks. These use deterministic Socket.IO fixtures, not paid model calls or a full adventure playthrough.

### Existing validation limitations

The unchanged launcher suite has seven failures on both this candidate and untouched public base: old tests still expect legacy defaults/fallback and incomplete fake bundles to be accepted. The old visual suite also has obsolete fixed geometry and absent Windows screenshot baselines. These were not relabeled as passing. Feature browser checks use layout/behavior assertions and captured screenshots instead. The populated legacy phone header has an overlapping party arrow/dice control; this port retains that separate public layout rather than importing the hosted phone UI.
