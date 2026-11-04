# Headless CLI Mode

Drive the full NeverEndingQuest engine -- startup, main loop, combat,
level-up, saves -- without the HTML interface. Built for agentic automation
and testing: an AI coding agent, a pytest harness, or a shell script speaks
newline-delimited JSON (NDJSON) with the game over stdio.

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
python run_headless.py saves delete --save-folder save_20260806_120000

# Generate an adventure module (toolkit policy) with NDJSON progress events.
python run_headless.py build-module --name "Forest of Beasts" \
    --narrative-file concept.txt --areas 1 --locations-per-area 3
# Events: module_progress (stage/percentage/message) ... then
# build_complete {module_name} or build_error {error}.
```

`saves create --save-mode` takes `essential` (the default) or `full`, which
also keeps `combat_logs/` and two extra conversation histories.
`build-module --narrative TEXT` gives the concept inline, in place of
`--narrative-file`.

## Python client

`core/headless/client.py` wraps `serve` for harnesses:

```python
from core.headless.client import HeadlessClient

with HeadlessClient(module="The_Thornwood_Watch", character="/tmp/pc.json",
                    game_dir="/tmp/neq-test") as game:
    print(game.opening.narration)        # a new game's opening scene
    turn = game.play("I look around")    # blocks until the next prompt
    print(turn.text, turn.state["player"])
    game.save("checkpoint")
    print(game.list_saves())
```

`play()` returns a `TurnResult` (`narration`, `text`, `state`, `prompt`,
`events`, `ended`, `recovery_required`). `narration` is the DM's words only;
`text` is all the player read, in order, with roll results and damage cards.
`start()` waits for a new game's opening scene, so `opening` holds it; a
relaunch's welcome back is not waited for. The old `core/ai/dm_wrapper.py` / `enhanced_dm_wrapper.py`
subprocess scrapers are deprecated in favor of this client.

Exit codes: `0` clean end (player exit or post-restore restart), `2` engine
error, `4` bootstrap/usage error, `5` the game stopped (`engine_stop`). A run
that ends `5` did not finish: read it as a stop, not as a played session.

## Script mode

`script FILE` answers each `prompt` with the file's next line, and quits at the
next prompt once the lines run out, whatever kind of prompt that is.

- One input per line. Blank lines and `#` lines are skipped.
- A line holding only `<enter>` sends an empty line.
- `--max-turns N` (default 50) sends at most N lines.
- `--timeout-per-turn SECONDS` (default 300) sets how long the engine can stay
  silent before a `status` notice. It never ends a run.
- A stopped turn or a recovery ends the run with exit code `5`.

## How it works

Headless mode mirrors the web interface's proven embedding trick: it swaps
`sys.stdin` / `sys.stdout` / `sys.stderr` for shims around an unmodified
`main.main_game_loop()`. All engine input -- the main turn prompt, combat,
level-up, and the startup wizard -- funnels through bare `input()` calls,
so one stdin shim covers everything. The player's output comes through the
engine's player-output sink, and status through status_manager callbacks. A
line classifier (`core/headless/classifier.py`, a transport-neutral copy of
the web layer's stdout heuristics) reads what is still printed: prompts,
`STARTUP_MARKER` lines, and any print the sink does not cover yet, which
arrives as `narration` with `source: "stdout_scrape"`.

Everything the engine prints is also mirrored raw to
`modules/logs/headless_raw.log` for debugging.

## The protocol

One JSON object per line. Every server event has `type`, `seq` (monotonic),
and `ts` (unix seconds).

### Server -> agent events

| type | fields | meaning |
|---|---|---|
| `hello` | `protocol`, `game_dir`, `pid` | session started. With `--character`, `startup` and `system` events can come first |
| `startup` | `phase`, and when the engine has them `source`, `result`, `timestamp`, `lease_owner`, `startup_attempt_id`, `attempt_count`, `state_version` | startup readiness marker; `startup_kickoff_done` (or `startup_kickoff_skipped` with `result: "already_done"`) means the game is live |
| `narration` | `channel` (`main`/`combat`/`levelup`/`system`), `content`, `message_id` (can be null), `source` (`sink` or `stdout_scrape`) | DM output for the player. `source: "sink"` is the structured path all engine narration uses; `stdout_scrape` marks a fallback recovery from raw stdout and normally never appears |
| `status` | `message`, `is_processing`, `recovery_required`, `source?` (`script_wait` on a script's silence notice) | engine busy/idle heartbeat. While `recovery_required` is true, an idle status reads "Gameplay is paused. Choose a save to Load, Reset, or Quit.", no `prompt` follows, and only list-saves, Load, Reset or Quit are accepted |
| `welcome_progress` | `message`, `kind?` (`opening_scene`/`resume`) | background progress of a new game's opening scene (`opening_scene`, e.g. "The DM is setting the opening scene...") or a resumed game's welcome (`resume`, "The DM is recalling your journey..."). Presentational only: it is not a `status` event and never locks input. An empty `message` clears it |
| `prompt` | `kind` (`main`/`combat`/`levelup`/`roll`/`wizard`/`resume`/`unknown`), `raw_prompt`, `stats` (`date`, `time`, `time_context`, `hp`, `max_hp`, `xp`, `next_level_xp` when the prompt shows them; `{}` at a `roll` prompt), `roll` (only when the next line answers a roll; see "The `roll` object"), `pendingRoll` (the same roll as `{kind: "check" | "hitDie", label, dice: [{count, sides}]}`, only for a check or a short rest's hit dice this line answers; a waiting check comes first) | **the engine is waiting for input; the turn boundary** |
| `state` | see below | snapshot taken right after `prompt` |
| `system` | `content`; from the sink also `channel`, `message_id`, `source` | structured system messages: roll results, damage cards, receipts, notices, module transitions, safe-action failures, bootstrap notes. `channel: "input_suggestion"` holds a declared action the game offers to send as it stands |
| `debug` | `content`, `is_error` | raw engine chatter; only emitted with `--debug`, except engine-crash tracebacks, which are always emitted |
| `compression` | `event`, ... | history-compression progress |
| `module_progress` | build progress fields | in-game module creation progress |
| `operation` | `name`, `status`, `id?`, `operation_id?`, `message?`, `waiting_for_current_operation?` | a transport receipt or deferral for a command or input, e.g. `status: "accepted_deferred"` with "Your action is queued for after travel recovery.". Never proof of execution; wait for the correlated `result` |
| `result` | `id`, `ok`, `data`/`error` | reply to a `command`. `id` is null for a line that could not be parsed |
| `exit` | `reason` (`player_exit`/`engine_stop`/`restart`/`error`), `detail?` | session over. `engine_stop` means the game stopped with no player exit (exit code `5`): a start with nothing to play, a read-only save, or a Quit from a stopped game, whose `detail` says what stopped |

### Agent -> server lines

```json
{"type": "input", "content": "I search the room"}
{"type": "command", "id": "c1", "name": "state"}
{"type": "command", "id": "c2", "name": "save", "args": {"description": "checkpoint"}}
{"type": "command", "id": "c3", "name": "list_saves"}
{"type": "command", "id": "c4", "name": "restore", "args": {"save_folder": "..."}}
{"type": "command", "id": "c5", "name": "delete_save", "args": {"save_folder": "..."}}
{"type": "command", "id": "c6", "name": "quit"}
{"type": "command", "id": "c7", "name": "reset", "args": {"confirmed": true}}
```

Rules (live-accepted on 2026-10-24 by the L12 headless save, load and resume runs):

- Send one `input` per `prompt` event; do not batch future gameplay turns.
- Save can queue at a live/welcome safe boundary. Load and confirmed Reset
  coordinate supersession/quiescence; delete-save still requires idle state.
- Restore results include `restore_outcome` and `can_resume`. A verified clean
  result emits `exit {reason: "restart"}`; relaunch to use the clean state.
  `recovery_required` does not start gameplay or advertise a normal prompt:
  command intake remains for list-saves, Load, Reset or Quit.
- `recovery_required` is also how a stopped fight reads: the party has fallen,
  a fight is paused on disk (`state.combat.recovery` says so, with its
  `reason`), or a resumed fight stopped again. A line sent then is refused.
- `prompt {kind: "resume"}` means a turn stopped and the fight did not go on.
  The next line re-enters the fight and is **not played**: any line will do,
  and your real action goes to the combat prompt that follows. A Quit here ends
  `engine_stop`. In script mode the run ends there, exit code `5`, since the
  next script line would be spent.
- A resume can be costly: the engine stops a turn at 24 provider calls, so one
  bad resume can cost 24 calls.
- `operation {status: "received"}` acknowledges command transport only. The
  existing runner executes commands FIFO; wait for the correlated `result`.
  Receipt alone never proves execution or success. Input retains its existing
  prompt/narration/state contract, not command-style receipts.
- Quit can cancel Load's outer read-only preflight before any restore claim.
  That result says `status: "cancelled"`, identifies the Quit operation, and
  means this Load changed no state. Earlier accepted Saves still drain normally.
  Cancellation does not extend to applying/rolling-back Load; that priority is
  still owner-open. Native control acceptance remains in the execution ledger.
- Restart ends this process's ephemeral queue. A command known to be undispatched
  must be resubmitted; a missing result alone is not proof it never executed.
  Never blindly resend gameplay input merely because it had no command result.
- A `prompt` with a `roll` field means the next line answers that roll,
  whatever its `kind`: send the numbers as `input`, or the word `roll` to let
  the game roll. A question or a change of mind is an ordinary line. With no
  `roll` field, the line is not read as a roll, even if a check is waiting:
  a check held during a fight stays held until a prompt carries it.
- Reset requires `args.confirmed: true` (otherwise the result is
  `reset requires args.confirmed=true`). Its result's `data.backup_dir` names
  the backup. Like a clean restore, it ends with `exit {reason: "restart"}`;
  relaunch to play the reset campaign.
- A new game's first `prompt` can come before its opening scene. To read the
  scene first, wait for the `welcome_progress {kind: "opening_scene"}` with an
  empty `message`.
- A new game's opening scene (`welcome_progress {kind: "opening_scene"}`) is
  never discarded by early input. An `input` sent before the scene's
  `narration` arrives is held and answered after the scene: expect the
  scene's `narration`, then the answer's.
- Wizard turns work over the same channel: if no character is seeded, the
  startup wizard's questions surface as `prompt {kind: "wizard"}` events and
  free-text answers drive the AI character-creation interview. The wizard
  also sends fixed `narration` lines: a welcome line before the adventure
  menu, a start line before the interview, and the model's finalize
  narration after approval. Its `status` heartbeat names the purpose:
  "Still preparing your adventure choices (N seconds elapsed)..." while the
  menu is written, "Still working on character setup (N seconds
  elapsed)..." during the interview.
- NPC-initiative combat turns can produce narration with no intervening
  `prompt` -- do not assume strict prompt/narration alternation.

### The `roll` object

Built from the game's typed records, never from `raw_prompt` or narration. It
is on the prompt only while that line is being read:

```json
{"kind": "phase", "label": "Dagger (Dexterity)", "phase": "damage", "target": "Trader Sila",
 "dice": [{"count": 1, "sides": 4}, {"count": 1, "sides": 6, "name": "Hex"}], "eachDie": true}
```

| field | meaning |
|---|---|
| `kind` | `check`, `hitDie`, `phase` (the game's own combat roll; `prompt.kind` is `roll`), or `ask` (the DM asked for this roll in combat; `prompt.kind` is `combat`) |
| `label` | what the roll is for: "Dexterity check for Mira Willowmere", a weapon or spell as the sheet names it, or the phase of a DM's ask |
| `dice` | what the player rolls, main dice first; a die added by a spell such as Hex has a `name` |
| `eachDie` | `true`: one number for each die, in `dice` order. `false`: one total |
| `phase` | combat only: `attack`, `damage`, or the DM's typed phase |
| `target` | a `phase` roll's target |
| `mode` | `normal`, `advantage` or `disadvantage`, where the game holds it. With two d20s, send both: the game keeps the right one |
| `reason`, `dc` | why the roll is asked, and its DC, when set |
| `addedDice` | `[{name, count, sides}]`: dice the game adds to a check itself (Guidance, Bless). Do not roll these |

A blank line also lets the game roll at a `check`, `hitDie` or `phase` roll. At
an `ask` it does nothing, and the prompt comes back.

### The `state` snapshot

Built only from the on-disk state files (never from narration text), taken
when the engine is idle at a prompt, i.e. after its post-turn saves:

```json
{
  "party_tracker": {"module": "...", "partyMembers": ["..."], "partyNPCs": [],
                     "time": "09:00:00", "day": 1, "month": "Springmonth", "year": 1492},
  "player": {"name": "...", "race": "...", "class": "...", "level": 1, "hp": 10, "max_hp": 10,
              "xp": 0, "next_level_xp": 300, "armor_class": 14, "status": "alive",
              "condition": "none", "currency": {"gold": 10}},
  "location": {"id": "RO01", "name": "...", "area_id": "RO001", "area_name": "..."},
  "plot": [{"id": "PP001", "title": "...", "status": "not started"}],
  "combat": null,
  "files": {"party_tracker": 1754500000.0, "character": 1754500000.0,
            "module_plot": 1754500000.0}
}
```

`combat` becomes `{"active": true, "encounter_id": "...", "round": N}` while
an encounter is live. A fight that needs Load or Reset adds
`"recovery": {"required": true, "message": "...", "actions": ["load", "reset"]}`,
with `reason` (for example `party_defeated`) when the fight is paused on disk.

## Character seeding (skipping the wizard)

`--character FILE --module NAME` (on `serve`, `script`, or the standalone
`new-game` subcommand) installs a pre-made character sheet and points
`party_tracker.json` at it, which makes the engine's `startup_required()`
check pass and skips the interactive wizard entirely. The file must satisfy
`schemas/char_schema.json`; it is run through the wizard's own repair +
validation chain first, so a bad seed fails fast with a clear error. Any
existing valid player character file (e.g. from `characters/` in a live
game) works as a template.

With `--game-dir`, give `--character` as an absolute path: the session enters
the game directory before it reads the file, so a relative path is looked up
there.

Relaunching `serve` or `script` with the same flags is safe: when the folder's
party already holds that hero in that module, the saved sheet stands and the
file is not applied, and a `system` line says so. `new-game` still refuses a
sheet that differs from the saved one.

## Isolated game directories

`--game-dir DIR` runs the session inside an isolated directory: the static
content the engine needs (`schemas/`, `prompts/`, `data/`, and the chosen
`modules/<module>/`) is copied in on first use, and all state files
(`party_tracker.json`, `characters/`, conversation history, saves) live
there. Test runs never touch the real campaign in the repo root, and
parallel agents can each use their own directory. `config.py` always stays
at the repo root (it is imported, not read from the game dir).

Each later launch refreshes `schemas/`, `prompts/` and `data/` file by file
from the repo, and keeps the files the game writes. `modules/<module>/` is not
refreshed: a kept directory plays the module content it was given, even when
the launch notice says the folder was updated. Use a fresh directory to test
the module as it stands in the repo.

## Driving it from an agent (example)

```bash
python run_headless.py serve --game-dir /tmp/neq-test \
    --module The_Thornwood_Watch --character /tmp/pc.json
```

Then, per turn: wait for `{"type": "prompt"}`, read the `state` event that
follows it, decide, and write `{"type": "input", "content": "..."}` to the
process's stdin. A provider call in flight shows up as `status` events with
`is_processing: true` whose message names the transport phase the provider
child has actually reported, e.g. "Attempt 1, 12 s: request delivered to
OpenAI; waiting for it to acknowledge (11 s)... Your turn is safe." or
"OpenAI is working on it (last activity 3 s ago)...". The phases are
connecting, connected, secured, sent, acknowledged, working, receiving, done,
failed (shown as "connecting to", "connected to ...; sending your request",
"request delivered to ...", "... is working on it", "answer arriving from",
"answer received from ...; finishing", "... connection failed; reconnecting"); every provider row in `debug/api_captures/api_calls_master.jsonl`
carries them under `metadata.phases` with `lastPhase`, so a stalled call can
be attributed to its stage after the fact. Silence alone does not identify the
cause: inspect the same live process/children and protocol before diagnosing
provider versus local blocking. Observation timeout is not permission to
abandon gameplay work. `python utils/provider_health.py` runs one real tiny
call through the same transport and prints its phase timeline.

## Limitations

- One session per game directory. There is no lock yet -- do not point two
  sessions at the same directory.
- The no-engine commands share stdout with engine chatter, so read them with
  care. `new-game` and `saves create` end on a JSON line: parse the last line
  only. `saves list` prints one JSON object over several lines, after chatter.
  `state` is one JSON object over several lines, and can follow a chatter line.
  `saves restore` joins its JSON to the end of a longer last line. To parse
  these results, use `serve`: the `state` event and the `list_saves` and
  `restore` commands are clean.
- Saves are named to the second. A second `saves create` in the same second
  writes nothing, yet reports `ok: true` with "Save game already exists".
