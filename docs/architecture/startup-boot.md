# Startup and Boot

Purpose: create or repair the minimum durable game state, resume durable work, build canonical context, and expose the first player prompt.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Safety worktree delta (2026-09-05; live acceptance pending)

The shared loop wrapper owns genuinely unowned startup/combat work and borrows an
existing scope when present. Its scope extends through recovery and post-combat
handoff, then closes at the input boundary. Nested work never closes its caller's
scope. Module-completion generation likewise owns an unowned entry or borrows the
current/accepted-control context. Typed supersession bypasses startup completion
failure narration. Existing wizard/welcome ownership remains distinct.

No extra startup scanner, autosave or crash manifest is added: existing clean
state and subsystem receipts are the resume authority. Native live startup and
saved-combat cancellation acceptance is still pending.

## Authority table

| Datum | Source of truth | Acceptance or commit point |
|---|---|---|
| Wizard required | `party_tracker.json`, its first party member, and the canonical character file | `startup_required()` checks all three |
| Available adventures | Public module directories and files on disk | Read-only module scan |
| Wizard dialogue | Persisted T092 conversation | Nonempty accepted turn is appended to `startup_conversation.json` |
| Character sheet | Selected module character JSON | Deterministic repair and schema validation precede atomic write |
| Initial location | Exact six-field T093 proposal, or complete deterministic fallback | Whole `party_tracker.json` projection is written |
| Current game context | Tracker, module, location, plot, roster, and history files | Reloaded after recovery and used to rebuild conversation context |
| Welcome identity | `startup_state.json` attempt ID, status, and lease owner | Lock-protected claim/processing/done transition |
| Welcome result | Frozen history/location snapshot plus T067 output | Only the game thread may accept and apply a still-current result |
| Surface readiness | Structured startup markers | `startup_loop_ready`, completed kickoff, or skipped kickoff unlocks input |
| Recovery state | Each subsystem's own durable receipt or checkpoint | Startup invokes those owners; it does not duplicate their authority |

## Flow

1. The terminal wrapper configures the console, checks `config.py`, creates directories, hydrates missing runtime module files, runs calendar migration, optionally runs the wizard, builds the location graph, and enters `main_game_loop`.
2. Web and headless enter `main_game_loop` directly. The shared loop repeats boot-critical hydration and wizard checks.
3. Shared boot creates debug paths, performs missing-only backup hydration, runs the companion-memory startup check, issues a fresh startup attempt ID, and emits `startup_handoff_begin`.
4. A new game runs the startup sequence: initialize the wizard conversation, choose a module, choose or create a character through T092, validate and write the character, ask T093 for an initial location when needed, write the tracker, and archive the wizard conversation.
5. An existing game repairs missing character fields and synchronizes the durable `wizard_complete` state.
6. Before ordinary context, startup drains staged module completion, recovers effects migration, reloads the location graph, resumes pending travel, and resumes an active combat encounter.
7. It then reloads history and party state, reconciles campaign state, loads location/plot/module context, installs the system prompt and fresh context blocks, orders messages, and saves history with compression disabled.
8. On queue-backed web/headless, startup freezes history, registers a detached welcome scope, starts a non-daemon T067 worker, emits an attempted marker, and proceeds to the input loop. The worker generates only; it cannot mutate history or game state.
9. On raw terminal, the same welcome T067 runs synchronously, is lease-checked, applied by the game thread, and marked done before input opens.
10. The loop emits `startup_loop_ready`, refreshes state/effects, loads player statistics, and requests input. Queue-backed input can therefore be reachable while welcome generation is still active.
11. If the player submits first, the game thread supersedes and reaps the welcome, then discards or hands it back before processing player text.
12. T092 owns conversational character authorship only. Final JSON is accepted after explicit confirmation, sanitized, repaired, schema-validated, and written.
13. T093 owns only the proposal. Code accepts exactly `areaId`, `areaName`, `locationId`, `locationName`, `weather`, and `politicalClimate` as nonempty strings; otherwise it uses the complete fallback before the tracker write.
14. Headless installs its shims before starting the engine thread and converts startup markers, output, and prompts into NDJSON events.

## State and atomicity

- Durable stores include `party_tracker.json`, the selected character file, `startup_conversation.json`, canonical conversation history, and `startup_state.json` plus its lock.
- Module, campaign, effects, travel, combat, and companion-memory recovery keep their own stores and receipts.
- Character, wizard-conversation, and tracker writes use the shared safe JSON writer. Startup handoff state uses a sibling temporary file, flush/fsync, and `os.replace`.
- Boot is not one transaction. Each recovery owner converges its own durable work before context is rebuilt.
- T092 and T093 provider scopes fence persistence against supersession. Their output is not state authority before its file commit.
- The detached welcome worker never mutates state. Game-thread acceptance rechecks the lease, frozen history, and current location, then applies exactly once.
- Welcome Save/Load/Reset operations queue through the welcome scope and drain before it becomes quiescent.
- The synchronous companion-memory backfill is still a real pre-prompt gate at this revision; open issue #258 tracks that gap.
- Old-format transition and chronicle repair is deferred until after real input opens a cancellable turn scope. It may gate the first submitted turn, but not the prompt construction shown above.

## Load-bearing seams

1. `main.py:9172-9295` - terminal wrapper and shared-loop handoff.
2. `main.py:7007-7057` - shared hydration, memory check, and startup attempt.
3. `utils/startup_wizard.py:172-246` - wizard orchestration and need predicate.
4. `utils/startup_wizard.py:682-758` - character interview and final JSON acceptance.
5. `utils/startup_wizard.py:1680-1804` - T092 request, persistence, and supersession.
6. `utils/startup_wizard.py:1517-1606` - party projection, T093 call, and commit fence.
7. `utils/startup_wizard.py:1823-1913` - T093 validator, provider call, and fallback.
8. `utils/startup_handoff_state.py:112-159` - handoff-state loading and wizard status.
9. `utils/startup_handoff_state.py:212-350` - welcome claim and completion lifecycle.
10. `main.py:7135-7294` - module, effects, and travel recovery before context.
11. `main.py:7305-7370` - active-combat startup branch.
12. `main.py:7481-7584` - authoritative context build and no-compression save.
13. `main.py:298-378` - detached welcome lifecycle and generation-only worker.
14. `main.py:420-750` - game-thread welcome acceptance and receipts.
15. `main.py:7586-7758` - surface split, readiness marker, and first input.

## Invariants

- See #193 Part 1 for B1/B2, AP-1 through AP-7, leanness, evidence, and lineage.
- See #193 Part 2 pages 2, 8, 9, 10, 11, 12, and 13 for disk truth, compression, controls, threading, providers, compatibility, and real acceptance.
- See #193 Part 5 for structural liveness, No-Limits, and the ruling that legacy combat migration is lazy-on-use rather than a startup sweep.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- First-prompt and recovery gates: #202, #204, #211, #213, #217, and #258.
- Wizard and new-game behavior: #114, #115, #170, #232, #234, #235, and #257.
- Welcome and UI handoff: #214, #221, and #248.
- Legacy/startup reconciliation: #158, #199, and #238.
