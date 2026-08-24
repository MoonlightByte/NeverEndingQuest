# Travel-Recovery Clean Branch -- Handoff to Codex (Windows + Gemma arm)

Branch: **`origin/travel-recovery-clean`** @ `d42ebdf8` (off `origin/main` 691b5a2f; 7 commits;
32 travel-only files; NO voice/episodic code). Nothing merged. This is the clean, voice-free
travel-recovery line extracted from the `0bbb5f19` mega-commit on `fix/travel-contract-coherence`.

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
