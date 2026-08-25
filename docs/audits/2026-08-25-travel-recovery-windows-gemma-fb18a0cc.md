# Travel recovery #210 player-stream revalidation -- native Windows and Gemma

Status: **OpenAI PASS; Gemma #210 mechanics/player notice PASS, generated-resume delivery NOT
FULLY ACCEPTED because the pre-existing #213 startup boundary is reached**

Branch under test: `origin/travel-recovery-clean`

Pinned revision: `fb18a0ccf34e8494bffad3a8dd38d19571c93e04`

Policy source: GitHub issue #193 v1.7, refreshed live at epoch
`2026-08-24T05:39:19Z` before execution.

This is the native-Windows/Gemma arm requested by the 2026-08-25 addendum in
`docs/audits/2026-08-24-travel-recovery-CODEX-HANDOFF.md`. The tests used native Windows
Python 3.12, native Edge/Playwright, a real Keep_of_Doom campaign, real OpenAI calls, and the
owner-provided LM Studio endpoint at `192.168.1.254:1234` with the already-loaded
`google/gemma-4-12b-qat`. No model was downloaded or changed. No production file was changed.

The documented minimal v2 checkpoint was constructed only to establish the crash boundary. The
unmodified game performed startup recovery, checkpoint deletion, prompt generation, provider
calls, output routing, browser delivery, and authoritative state reporting.

## Native Windows + OpenAI

### Constructed blocked checkpoint -- PASS

- Startup executed the exact `origin=E03`, `destination=E01`, authoritative-current=E05 discard
  path and removed `pending_location_transition.json` without a Windows lock or `WinError`.
- The #210 notice was exactly one headless `narration` event. It contained no
  `[SaveGameManager]` or `INITIALIZATION` diagnostic text.
- The real captured `main_dm` request contained
  `The party is currently at Storage Vaults (E05)`.
- The generated welcome placed the player in Storage Vaults/E05 and did not present Torture
  Chamber/E03 as current.
- A prompt returned, there was no `engine_stop`, and protocol state reported E05.

The first local evidence run correctly exercised the product but its ignored harness initially
looked for captures under the repository instead of the isolated game directory and expected the
state under a nonexistent `data` wrapper. The raw product evidence was re-read from the real
fixture; the harness was corrected without changing game code.

### Native legacy browser -- PASS

Native `web_interface.py` served the actual legacy player and native Microsoft Edge was driven by
Playwright. The game pane showed one clean `.message.narration` #210 notice, the generated welcome
named Storage Vaults, no stale-current E03 claim appeared, the location widget showed Storage
Vaults, and input became enabled. The diagnostic remained on the debug stream.

### Normal resume -- PASS

From the untouched official campaign with no pending checkpoint, the captured request carried the
same authoritative E05 note and the generated welcome opened with `You find yourself in the
Storage Vaults`. It mentioned Torture Chamber only as the route back, which is a truthful adjacent
location, not as the current location. This distinction corrected an over-broad first local oracle
that rejected any mention of the old location.

## Native Windows + Gemma / LM Studio

LM Studio reported two loaded instances of `google/gemma-4-12b-qat`; their
`reasoning_budget_message` was empty. Calls completed normally (roughly 4.5 minutes per startup)
instead of repeating the prior 600-second transport stall.

### Constructed blocked checkpoint and player notice -- PASS

- Checkpoint deletion, the discard breadcrumb, prompt return, E05 authoritative state, and absence
  of `engine_stop` all passed.
- The #210 notice was one clean headless narration event.
- The real `main_dm` request carried the authoritative Storage Vaults/E05 note.
- The late Gemma response itself narrated Storage Vaults rather than stale E03.

### Native legacy browser -- PASS for the #210 player-stream fix

The actual game pane showed the clean #210 notice once; the location widget showed Storage Vaults;
the diagnostic did not leak into the notice; input became enabled; no stale-current E03 claim was
shown.

### Generated welcome / normal resume -- NOT FULLY ACCEPTED (pre-existing #213 boundary)

The untouched-save normal-resume run reached a playable prompt and E05 state, but delivered no
startup welcome narration. Real debug evidence recorded:

`INITIALIZATION: Startup kickoff did not complete cleanly: {'status': 'failed', 'reason': 'timeout'}`

The first 120-second startup worker expired during the synchronous compression backlog; the forced
second attempt also expired. This is the already-filed #213 startup/compression behavior and was
explicitly excluded from the #210 implementation scope. Waiting longer in the external harness
cannot change the internal 120-second fence.

The late real Gemma response proves the new #210 context plumbing itself worked: it explicitly
placed the party in Storage Vaults and never treated E03 as current. However, Gemma also returned an
unrequested `updatePlot` action despite the resume note saying to provide narrative and prompts.
Because the attempt was fenced out on timeout, that action did not mutate state. This is a genuine
provider-specific narration-only contract failure; it must not be hidden by calling the complete
Gemma resume path accepted, and it must not be patched here with a scenario-specific rule.

Forensic classification under the #193 procedure:

- real request recovered: yes; actual model `google/gemma-4-12b-qat`;
- authoritative E05 note present at the request tail: yes;
- model understood current location: yes (response names Storage Vaults);
- model violated the immediate narration-only action boundary: yes (`updatePlot`);
- deterministic disagreement: no; no validator demanded the action;
- classification: provider/prompt semantic compliance, compounded by the separately tracked #213
  startup liveness fence.

## Evidence and verification

Ignored local evidence:

- `validation_evidence/windows_210/openai_headless.json`
- `validation_evidence/windows_210/openai_web.json`
- `validation_evidence/windows_210/openai_normal_resume.json`
- `validation_evidence/windows_210/gemma_headless.json`
- `validation_evidence/windows_210/gemma_web.json`
- `validation_evidence/windows_210/gemma_normal_resume_rerun.json`
- complete protocol/debug streams and API captures under the named Windows temporary campaign
  copies recorded in those files.

Additional checks:

- `git diff --check` -- PASS
- native `C:\Python312\python.exe -m py_compile main.py core/ai/action_handler.py` -- PASS
- tracked worktree remained clean; local drivers/settings/evidence were ignored.

## Verdict

The two `e18f7248` player-stream defects are corrected on native Windows. OpenAI passes headless,
normal-resume, and real-browser validation. Gemma proves the #210 checkpoint and notice fixes and
the authoritative E05 prompt context, but the complete generated-resume experience remains not
fully accepted because #213's startup timeout suppresses the late response; that late response also
contains a separate narration-only contract violation. No #209 voice work and no #211/#212/#213
implementation was added.
