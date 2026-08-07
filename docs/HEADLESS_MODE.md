# Headless CLI Mode

Drive the full NeverEndingQuest engine -- startup, main loop, combat,
level-up, saves -- without the HTML interface. Built for agentic automation
and testing: an AI coding agent, a pytest harness, or a shell script speaks
newline-delimited JSON (NDJSON) with the game over stdio.

Design background: `docs/plans/2026-08-06-headless-cli-mode-plan.md`.

## Quick start

```bash
# One-time: bootstrap config (or set OPENAI_API_KEY in the environment and
# let serve/script create config.py from the template automatically).
cp config_template.py config.py   # then add your API key

# Interactive agent session. Seeding a character skips the startup wizard.
python run_headless.py serve --module The_Thornwood_Watch --character my_pc.json

# Scripted smoke run: feed 5 turns from a file, then exit.
python run_headless.py script turns.txt --module The_Thornwood_Watch \
    --character my_pc.json --timeout-per-turn 300

# Read game state without starting the engine.
python run_headless.py state

# Save management without starting the engine.
python run_headless.py saves list
python run_headless.py saves create --description "before the cave"
python run_headless.py saves restore --save-folder save_20260806_120000

# Generate an adventure module (toolkit policy) with NDJSON progress events.
python run_headless.py build-module --name "Forest of Beasts" \
    --narrative-file concept.txt --areas 1 --locations-per-area 3
# Events: module_progress (stage/percentage/message) ... then
# build_complete {module_name} or build_error {error}.
```

## Python client

`core/headless/client.py` wraps `serve` for harnesses:

```python
from core.headless.client import HeadlessClient

with HeadlessClient(module="The_Thornwood_Watch", character="pc.json",
                    game_dir="/tmp/neq-test") as game:
    print(game.opening.narration)        # startup kickoff narration
    turn = game.play("I look around")    # blocks until the next prompt
    print(turn.narration, turn.state["player"])
    game.save("checkpoint")
    print(game.list_saves())
```

`play()` returns a `TurnResult` (`narration`, `state`, `prompt`, `events`,
`ended`). The old `core/ai/dm_wrapper.py` / `enhanced_dm_wrapper.py`
subprocess scrapers are deprecated in favor of this client.

Exit codes: `0` clean end (player exit, engine stop, or post-restore
restart), `2` engine error, `3` per-turn silence timeout (script mode),
`4` bootstrap/usage error.

## How it works

Headless mode mirrors the web interface's proven embedding trick: it swaps
`sys.stdin` / `sys.stdout` / `sys.stderr` for shims around an unmodified
`main.main_game_loop()`. All engine input -- the main turn prompt, combat,
level-up, and the startup wizard -- funnels through bare `input()` calls,
so one stdin shim covers everything. Output is recovered by a line
classifier (`core/headless/classifier.py`, a transport-neutral copy of the
web layer's stdout heuristics) plus the engine's structured seams
(status_manager callbacks, the player-output sink, `STARTUP_MARKER` lines).

Everything the engine prints is also mirrored raw to
`modules/logs/headless_raw.log` for debugging.

## The protocol

One JSON object per line. Every server event has `type`, `seq` (monotonic),
and `ts` (unix seconds).

### Server -> agent events

| type | fields | meaning |
|---|---|---|
| `hello` | `protocol`, `game_dir`, `pid` | session started |
| `startup` | `phase`, ... | startup readiness marker; `startup_kickoff_done` (or `startup_kickoff_skipped` with `result: "already_done"`) means the game is live |
| `narration` | `channel` (`main`/`combat`/`levelup`/`system`), `content`, `source` (`sink` or `stdout_scrape`) | DM output for the player. `source: "sink"` is the structured path all engine narration uses; `stdout_scrape` marks a fallback recovery from raw stdout and normally never appears |
| `status` | `message`, `is_processing` | engine busy/idle heartbeat |
| `prompt` | `kind` (`main`/`combat`/`levelup`/`wizard`/`unknown`), `raw_prompt`, `stats` (`hp`, `max_hp`, `xp`, `next_level_xp`, `time`, `time_context` when available) | **the engine is waiting for input; the turn boundary** |
| `state` | see below | snapshot taken right after `prompt` |
| `system` | `content` | structured system messages (module transitions, safe-action failures, bootstrap notes) |
| `debug` | `content`, `is_error` | raw engine chatter; only emitted with `--debug`, except engine-crash tracebacks, which are always emitted |
| `compression` | `event`, ... | history-compression progress |
| `module_progress` | build progress fields | in-game module creation progress |
| `result` | `id`, `ok`, `data`/`error` | reply to a `command` |
| `exit` | `reason` (`player_exit`/`engine_stop`/`restart`/`error`), `detail?` | session over |

### Agent -> server lines

```json
{"type": "input", "content": "I search the room"}
{"type": "command", "id": "c1", "name": "state"}
{"type": "command", "id": "c2", "name": "save", "args": {"description": "checkpoint"}}
{"type": "command", "id": "c3", "name": "list_saves"}
{"type": "command", "id": "c4", "name": "restore", "args": {"save_folder": "..."}}
{"type": "command", "id": "c5", "name": "delete_save", "args": {"save_folder": "..."}}
{"type": "command", "id": "c6", "name": "quit"}
```

Rules:

- Send one `input` per `prompt` event. Inputs sent early are buffered FIFO.
- `save`, `restore`, `delete_save` are only accepted while a prompt is
  pending (the engine is idle); otherwise the `result` is `ok: false`.
- `restore` replies with `result`, then emits `exit {reason: "restart"}` and
  ends the process (exit code 0) because in-memory engine state is stale
  after a restore. Relaunch the session to continue from the restored save.
- Wizard turns work over the same channel: if no character is seeded, the
  startup wizard's questions surface as `prompt {kind: "wizard"}` events and
  free-text answers drive the AI character-creation interview.
- NPC-initiative combat turns can produce narration with no intervening
  `prompt` -- do not assume strict prompt/narration alternation.

### The `state` snapshot

Built only from the on-disk state files (never from narration text), taken
when the engine is idle at a prompt, i.e. after its post-turn saves:

```json
{
  "party_tracker": {"module": "...", "partyMembers": ["..."], "partyNPCs": [],
                     "time": "09:00:00", "day": 1, "month": "Springmonth", "year": 1492},
  "player": {"name": "...", "class": "...", "level": 1, "hp": 10, "max_hp": 10,
              "xp": 0, "next_level_xp": 300, "armor_class": 14, "status": "alive",
              "condition": "none", "currency": {"gold": 10}},
  "location": {"id": "RO01", "name": "...", "area_id": "RO001", "area_name": "..."},
  "plot": [{"id": "PP001", "title": "...", "status": "not started"}],
  "combat": null,
  "files": {"party_tracker": 1754500000.0, "character": 1754500000.0}
}
```

`combat` becomes `{"active": true, "encounter_id": "...", "round": N}` while
an encounter is live.

## Character seeding (skipping the wizard)

`--character FILE --module NAME` (on `serve`, `script`, or the standalone
`new-game` subcommand) installs a pre-made character sheet and points
`party_tracker.json` at it, which makes the engine's `startup_required()`
check pass and skips the interactive wizard entirely. The file must satisfy
`schemas/char_schema.json`; it is run through the wizard's own repair +
validation chain first, so a bad seed fails fast with a clear error. Any
existing valid player character file (e.g. from `characters/` in a live
game) works as a template.

## Isolated game directories

`--game-dir DIR` runs the session inside an isolated directory: the static
content the engine needs (`schemas/`, `prompts/`, `data/`, and the chosen
`modules/<module>/`) is copied in on first use, and all state files
(`party_tracker.json`, `characters/`, conversation history, saves) live
there. Test runs never touch the real campaign in the repo root, and
parallel agents can each use their own directory. `config.py` always stays
at the repo root (it is imported, not read from the game dir).

## Driving it from an agent (example)

```bash
python run_headless.py serve --game-dir /tmp/neq-test \
    --module The_Thornwood_Watch --character pc.json
```

Then, per turn: wait for `{"type": "prompt"}`, read the `state` event that
follows it, decide, and write `{"type": "input", "content": "..."}` to the
process's stdin. A provider call in flight shows up as `status` events with
`is_processing: true`; prolonged total silence means a hung provider call --
script mode enforces `--timeout-per-turn` for exactly that case.

## Limitations

- One session per game directory. There is no lock yet -- do not point two
  sessions at the same directory.
- `new-game` prints engine chatter before its final JSON line; parse the
  last line only.
