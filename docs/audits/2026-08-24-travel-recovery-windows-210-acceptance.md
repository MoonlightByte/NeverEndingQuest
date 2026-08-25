# Travel recovery #210 -- native-Windows acceptance

Status: **NOT FULLY ACCEPTED -- mechanics pass; player-stream defects remain; Gemma did not reach gameplay**

Branch under test: `origin/travel-recovery-clean`

Pinned revision: `08e3f3563d51db55c786d474d4cd6502c758b0c2`

Policy source: GitHub issue #193 v1.7, refreshed live at epoch
`2026-08-24T05:39:19Z` before execution.

This is the Codex native-Windows arm requested by the addendum in
`docs/audits/2026-08-24-travel-recovery-CODEX-HANDOFF.md`. All runs used native
Windows Python 3.12 against an official Keep_of_Doom campaign. Complete
protocol streams, provider captures, process logs, campaign copies, and local
drivers remain ignored under `validation_evidence/` or the Windows temporary
directory. No gameplay response or on-disk result was fabricated.

## Native Windows + OpenAI

### Untampered kill/resume -- PASS

- Hard-killed the native process tree after the v2 checkpoint durably reported
  `movement_committed` for E03 -> E01.
- At kill: party E01; time 14:22; journal 125; checkpoint present.
- After restart/recovery: party E01; time 14:27; journal 126; checkpoint absent.
- No discard breadcrumb, recovery notice, error, duplicate movement, duplicate
  time, or duplicate journal entry occurred.
- Arrival narration was delivered once and an ordinary following turn was
  playable at E01.

Local evidence:
`validation_evidence/headless_acceptance/windows_openai_210_resume_08e3f356.json`

### Forced blocked path and Load -- MECHANICS PASS

- Hard-killed after `movement_committed`, then changed the complete authoritative
  party projection to valid E05 / Storage Vaults.
- Restart emitted the exact v2 discard breadcrumb and the recovery notice as a
  headless `narration` event, reached a prompt, reported authoritative E05 state,
  removed the checkpoint, and produced no traceback or engine stop.
- The following real turn stayed at E05 with time and journal unchanged.
- A real restore command returned `ok: true`; the relaunched session reached a
  prompt with nonblank narration and authoritative E03 state/history.

Local evidence:
`validation_evidence/headless_acceptance/windows_openai_210_blocked_rerun_08e3f356.json`

### Real browser/player stream -- ROUTING PASS, EXPERIENCE FAIL

Native `web_interface.py` served the real legacy player and native Microsoft
Edge was driven through Playwright. The #210 notice appeared exactly once in
`#game-output` as `.message.narration`; input became enabled; the UI and disk
both reported E05 / Storage Vaults; the checkpoint was removed without a
Windows file-lock/`WinError` failure.

However, the generated startup narration immediately contradicted that truth:
it told the player they stood in **Torture Chamber (E03)**. The same contradiction
occurred in the independent headless blocked rerun. This is a player-visible
failure even though the following ordinary turn rebuilt correct E05 context.

The headless notice event also included the unrelated text
`[SaveGameManager] INITIALIZATION: Validation prompt loaded for both paths`.
The one-line `Dungeon Master:` notice opens the classifier's narration section;
the next startup diagnostic is consumed before the section is flushed. The
notice therefore reaches the correct channel but is not a clean player message.

Local browser evidence:
`validation_evidence/headless_acceptance/windows_openai_210_web_08e3f356.json`

## Required real-call forensic classification

The live T067 startup capture at `2026-08-24T18:51:30.561631` used
`gpt-5.6-luna`, `reasoning_effort=none`.

- The request did contain the authoritative Current Location system projection
  for Storage Vaults / E05.
- Later in the same request, retained interrupted-turn history contained a stale
  player-context message declaring `Current location: Torture Chamber (E03)`.
- The final startup instruction only said to resume at the current location; it
  did not restate the authoritative E05 projection.
- The model returned E03 prose with no actions.

Verdict: **context plumbing (class c)**. The discarded checkpoint is removed,
but its later stale turn context remains more recent than the authoritative
scene projection used by the startup narrator. This is not a deterministic
travel-gate disagreement and not evidence for a scenario-specific prompt rule.

No production fix is included in this acceptance branch. Any correction must
first follow #193 planning/review and preserve accepted history, Load behavior,
the normal resume path, and the T013 -> T063 -> T064 travel narration chain.

## Gemma / LM Studio

Native Windows reached the owner-provided LM Studio endpoint at
`192.168.1.254:1234` and pinned the loaded model
`google/gemma-4-12b-qat`. No model was downloaded or changed.

Gemma did **not reach the first gameplay prompt**. Startup issued four parallel
historical compression calls; none completed before the real 600-second
transport boundary, after which the SDK immediately reissued them. The exact
native test tree was terminated to prevent a retry spiral. LM Studio reported
the loaded Gemma instance's reasoning default as `on`, while these local
callsites send no reasoning override.

This is a real local-provider startup failure, not a travel pass or fail. The
Gemma travel/#210 matrix remains **NOT REACHED** until the owner disables
reasoning for the loaded instance (or an independently reviewed application
change supplies the provider-supported override).

## Verdict

The native Windows `os.remove`/checkpoint behavior, blocked fail-forward
mechanics, untampered convergence, next-turn playability, and Load control pass.
The complete Windows acceptance does **not** pass because player-visible startup
narration contradicts authoritative location and the headless recovery notice
contains diagnostic text. Gemma acceptance is not reached.
