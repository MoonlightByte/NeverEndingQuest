# Travel-Recovery Clean Branch -- Handoff to Codex (Windows + Gemma arm)

Branch: **`origin/travel-recovery-clean`** @ `6625cca4` (off `origin/main` 691b5a2f; NO voice/
episodic code). Nothing merged. This is the clean, voice-free travel-recovery line extracted from
the `0bbb5f19` mega-commit on `fix/travel-contract-coherence`.

> **Tip moved since first handoff.** `d42ebdf8` = extraction; `04644183` = this handoff doc;
> **`6625cca4` = the #210 startup-fail-forward fix** (see the new section at the bottom:
> "ADDENDUM 2026-08-24 -- #210 acceptance"). `git pull` before starting.

## What this branch is
The recoverable within-module transition work (crash-convergent checkpoint machine + single-turn
travel contract + cancellable pre-mutation transport seam), extracted onto clean `origin/main` with
the NPC voice/episodic line fully removed. Voice reconciliation is DEFERRED and tracked in **#209**
-- do NOT re-add voice here; that happens on the separate voice branch.

## What Claude already verified (OpenAI-on-WSL arm) -- PASSED
Real headless play on **Keep_of_Doom** (official, consistent save), driven via `run_headless.py`:
- **G1** builds standalone: compiles; `import main` + action_handler + live_provider_call +
  campaign_manager + location_manager + save_game_manager import with NO `core.npc.*` /
  `npc_voice_batch` hard dep; boots + enters the interactive loop (A/B identical to `0bbb5f19`).
- **G2** FS-1/AP-4: every `live_provider_call.py` bound traced -> B2-iii liveness (unbounded
  reissue; 600s watchdog reaps child + reissues; 4xx backoff + reissues; supersede only on
  player Save/Quit); real consumers confirmed.
- **G3** immediate travel: E02->E01 moved exactly once (one move / one time step / one journal
  entry / prose arrival), control returned.
- **G3** recovery kill-test: hard `kill -9` of the whole process group at `movement_committed` ->
  party at destination exactly once -> relaunch -> deterministic turn-loop resume drives the
  checkpoint to `completed` (~2 player turns): journal +1 (NOT +2), arrival narration once,
  checkpoint cleaned, NO duplicate movement/time/journal/narration, playable throughout.
- **G3** deferred clause ("travel then buy then exit" -> travel only, buy/exit deferred, control
  returned); semantic non-travel (mentioning a location does not move the party); Save/Quit
  responsive mid-provider (save ack 0.0s + safe-boundary complete; quit exit 0.2s).
- **G3** blocked_conflict: detected, no corruption/double-move; startup fail-closes cleanly ->
  tracked as **#210** (pre-existing design question, not a defect of this branch).

One real defect was found by live play and FIXED here (commit `d42ebdf8`): the extraction left
`npc_voice_batch` referenced-but-undefined in the turn loop (NameError, built+imported clean, only
crashed at runtime). Now initialized inert (`= None`, #209).

## What Codex needs to do -- AUTHORITATIVE arm
Re-run the SAME acceptance on the platform of record that Claude cannot reach:
1. **Native Windows** (cp1252 console; O_BINARY file semantics) -- the acceptance platform of record.
2. **Gemma / LM Studio** (and any other local-model provider) -- the compressed combat/travel and
   validation prompts are what the local path uses; local models follow prompts differently than
   gpt-5.x, so the single-turn contract, travel-gate honesty, and recovery convergence MUST be
   re-verified there. Also spot-check Legacy/Gemini/Qwen if in scope.

Re-run the G3 matrix above and confirm on Windows+Gemma:
- immediate travel completes exactly once (one move/time/journal, prose arrival, control returned);
- travel-then-<deferred clause> executes travel only and returns control;
- semantic non-travel does not move the party;
- **kill at `movement_committed` -> resume with no duplicate movement/time/journal/narration,
  converges to completed, checkpoint cleaned, game playable** (the headline);
- Save/Quit responsive during provider work;
- blocked_conflict detected without corruption (behavior per #210).

## Env / how to run (mirror of Claude's setup)
- `cp config_template.py config.py` + local keys/provider (gitignored -- never commit).
- Use an OFFICIAL, internally-consistent module: **Keep_of_Doom / Thornwood / Pumpkin King**.
  Do NOT use `Shadows_of_Frostmere` (old, unofficial, borked: inconsistent A01 vs AJ01 location IDs
  make every travel refuse -- false signals; owner ruling).
- Claude used Keep_of_Doom save `save_20250719_072702` (party at E02 "The Gaol", TCD001; E02->E01,
  E01->E03 are valid connected travels). Restore a consistent save, or hand-stage a save snapshot.
- Drive via `python run_headless.py serve` (NDJSON stdin: `{"type":"input","content":"..."}`;
  commands `{"type":"command","name":"save|quit|state"}`) or `run_headless.py script inputs.txt`.
- The kill-test: launch a travel turn, poll
  `modules/conversation_history/pending_location_transition.json` for
  `phase == "movement_committed"`, hard-kill the process group, relaunch, take a turn, verify no
  duplication + convergence. (Claude's driver scripts are LOCAL dev aids, untracked per D-9 -- not
  shipped; re-create as needed.)

## Open items (do NOT do on this branch)
- **#209** voice/episodic re-integration into recoverable transitions -- belongs to the voice branch.
- **#210** blocked_conflict startup-stop vs boot-and-offer-recovery -- owner design decision.

## Division of labor
Claude = OpenAI-on-WSL (done, above) + reviews Codex's diffs. Codex = native Windows + Gemma/local
(this handoff). Report results back; on any diff/fix, Claude re-runs the OpenAI arm.

---

## ADDENDUM 2026-08-24 -- #210 acceptance (NEW WORK on this branch)

Commit **`6625cca4`** `fix(travel): #210 startup fails forward on un-appliable interrupted
transition`. Converged 6/6 under the #193 Part 3 blind panel; Claude ran full OpenAI/WSL acceptance
(ALL PASS). **Codex owns the authoritative native-Windows + Gemma/local-model re-run.** Plan +
Claude's evidence: `docs/audits/2026-08-24-issue-210-startup-fail-forward-plan.md` (see its §13).

### What #210 changed (2 code edits, +63/-4)
- `core/ai/action_handler.py::recover_pending_location_transition`: at its three terminal `blocked`
  returns (v1, v2, v2 cross-module) it now RETIRES the un-appliable checkpoint via the existing
  `_remove_location_transition_checkpoint()` and returns `{"status":"blocked","discarded":True,...}`
  with a per-site forensic `warning` breadcrumb.
- `main.py` startup handler: the old `error()+return` (engine_stop on `blocked`) is REPLACED by a
  player-facing recovery notice emitted **through the DM narration channel** + fall-through to the
  playable loop. No engine_stop. (Register is D-210-2 = narration-now; OOC channel = #212.)

### Why Windows + Gemma must re-run this specifically
1. **Native Windows (cp1252 / O_BINARY):** the fix calls `os.remove` on the checkpoint (via the
   retire helper) during startup. Confirm no `WinError`/lock issue on the real Windows FS (the helper
   only swallows `FileNotFoundError`; a lock-raise would hit the `main.py:6374` exception branch that
   still stops -- tracked as **#211**, out of #210's scope but worth watching on Windows).
2. **Gemma / LM Studio:** the fix's player notice is deterministic code, but the recovery
   convergence around it depends on the travel transaction (T013/T063/T064) driven by the local
   model. Re-verify the notice + convergence hold with local-model traffic and the compressed prompts.

### Re-run this exact matrix on Windows AND Gemma (Keep_of_Doom, NOT Shadows_of_Frostmere)
Use an official consistent module. Claude's repro used Keep_of_Doom: party at E03 (Torture Chamber);
E03->E01 (Dungeon Entrance) is a valid travel; E05 (Storage Vaults) is a valid third location.

**GATE-POLARITY (the headline):**
1. Launch a travel turn (E03 -> E01). Poll
   `modules/conversation_history/pending_location_transition.json` for `phase == "movement_committed"`.
2. Hard-kill the process group (`taskkill /F /T` on Windows). Party is now authoritatively at E01.
3. Tamper `party_tracker.currentLocationId` -> `E05` (matches neither origin E03 nor dest E01).
4. Relaunch. **Assert ALL:**
   - boots into the playable loop (reaches a prompt); NO engine_stop, no traceback;
   - the `blocked` breadcrumb fired -- capture the `warning` line
     `Discarding un-appliable interrupted transition (v2 origin=E03 dest=E01 current=E05): party location matches neither.`
     (proves the firing path executed; run headless with `--debug` to get it as a `debug` event);
   - the recovery notice ("A prior travel action didn't finish cleanly, so you remain where the
     party actually stands - Storage Vaults. ...") reaches the PLAYER surface:
       - **headless:** as a `narration` protocol event (NOT a `debug` event);
       - **web (`run_web.py`):** in the game pane as a `game_output`/`narration` payload (NOT the
         Debug tab / `debug_output`). Pin the exact stream -- this was the round-1 bug.
   - `pending_location_transition.json` is REMOVED after boot;
   - a subsequent ordinary turn completes normally; no duplicate movement/time/journal
     (party stays E05).

**NO-REGRESSION:** same kill@`movement_committed` but NO tamper (party at E01) -> relaunch takes the
`resume` path (NO discard breadcrumb), converges to completed, party at E01 once, arrival narrated
once (journal +1 not +2).

**LOAD control (B1 p9):** from the fail-forward booted state, `restore` an earlier save -> succeeds
and the resumed session shows the player where they are (not a blank screen).

### Coverage note
Claude's live repro exercised the **v2 within-module** `blocked` site only; the v1 and v2
cross-module sites use the identical retire+return contract (accepted by construction). If cheap on
your arm, a cross-module `blocked` probe would close that boundary.

### Do NOT on this branch
- No voice/episodic (#209). Do not implement the #212 OOC channel or the #211 exception-branch fix
  here -- both are separate, owner-mandated work.

Report results back; on any diff/fix, Claude re-runs the OpenAI/WSL arm.
