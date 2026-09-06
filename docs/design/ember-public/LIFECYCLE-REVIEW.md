# Disposable public lifecycle verification — 2026-09-05

`web/frontend/e2e/ember_lifecycle_probe.py` exercises actual public Flask-SocketIO
action handlers, SaveGameManager, reset code, JSON files and backups. It exports
tracked HEAD into its own fresh child and creates a separate synthetic campaign.
It borrows only data-construction functions from `tests/react_parity_server.py`;
it does not start that harness or install its canned save-list/action responses.

Both `essential` and `full` modes passed against public source
`66f718ad532d62141ae9ae9f24887c106720470e`:

- Busy non-turn work rejects Save without creating a new save entry.
- Save and list use actual files; character, tracker and mode metadata match.
- Corrupt metadata rejects restore without changing the altered current player.
- Valid restore restores the player/tracker, retains a pre-restore backup and
  requests process exit.
- Socket.IO reconnect still lists the save; delete removes it; a second delete
  returns the expected missing-save error.
- Reset clears synthetic player/storage/cache and resets the tracker. Its backup
  retains the character, and the handler requests process exit.

Only synthetic data was deleted/reset. Restore and reset backups are retained.
The local evidence roots are under `/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/`:
`neq-ember-lifecycle-g_j2yxca` (essential) and `neq-ember-lifecycle-c5r_trkb` (full).
Each contains `lifecycle-probe.json`, `lifecycle-result.json`, exported source and
the synthetic campaign. They contain no copied developer configuration or keys.

## Reproduce

Use the game's Python dependency environment from the public repository root.
The chosen parent must already exist and have space for a tracked export:

```sh
python web/frontend/e2e/ember_lifecycle_probe.py --save-mode essential --temp-parent /path/to/test-volume
python web/frontend/e2e/ember_lifecycle_probe.py --save-mode full --temp-parent /path/to/test-volume
```

The probe always exports committed HEAD, not uncommitted production edits. It
blocks outbound Python networking and writes outside its disposable child;
credential-store access is stubbed before imports. No engine starts. Process exit
and restart sleep are intercepted so post-operation assertions can run. This is
a bounded test guard, not a general security sandbox.

## What this does not prove

No browser Save/Load/Reset clicks, actual process restart, active-turn save queue,
live provider/interview, or recovery *from* the reset backup was tested here.
There is no claim that every file in an archive was exhaustively compared.
The separately passing browser edge-state suite covers full-mode presentation,
selected Load hover styling, deliberate reset confirmation/cancel, failed module
and compression presentation, and long initiative containment using fixtures.
Neither suite alone proves the full live new-game-to-save/restore journey.

An independent architecture reviewer inspected probe isolation and assertion
scope. Its bounded review is clean; full-plan and owner acceptance remain open.
