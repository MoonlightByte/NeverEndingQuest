# Combat #215/#216 Implementation and Acceptance Handoff (2026-08-26)

Operational evidence record only. Live GitHub issue #193 remains the sole design and review
authority.

## Revision and execution pins

- Branch: `design/agentic-combat` (shared branch; no branch migration).
- Production rollback commits:
  - `5acf60e617a6b941f3a6887db3ea4161c3cc3f65` - `fix(combat): project canonical narration names`
  - `acd731e4c511045bf052b8f59a34f07410ded0cd` - `fix(combat): restore rebuilt T067 histories`
- At final verification, local HEAD and `origin/design/agentic-combat` both equal `acd731e4...`;
  `origin/main` `691b5a2f...` remains an ancestor.
- Live #193: OPEN, protocol v1.7, updated `2026-08-24T05:39:19Z`, body SHA-256
  `CEA7074B6D6F9F442E1AD300F87A62BF77E984AC978BD9F497DA624FF6E37EB2`.
- Platform/provider: native Windows PowerShell and the configured real OpenAI provider. Captured
  gameplay/narration calls used `gpt-5.6-luna`; combat-validation calls used `gpt-5.6-terra`.
  Gemma/LM Studio was not used and is not an acceptance gate under the owner's current ruling.
- Live browser port: `8368`, separate from the other agent's `8358` service.
- No merge, PR, deploy, config, schema migration, tracked test, or unrelated UI change was made.

## #215 implementation

The typed scene manifest now carries a canonical `displayName` captured before duplicate combatants
receive mechanical suffixes. Player-facing narration inputs resolve presentation names by exact
`combatantId`; mechanical creature names, IDs, controller authority, initiative, events, persisted
combat state, T096 intent/capability matching, spell context, and preroll cache remain mechanical.

Covered production surfaces include typed T044 encounter/dynamic/initiative input, T043 durable
resume history, T097 dossier/facts/order/event presentation, synthesized automatic-window history,
and skipped-human display/history. Typed no-action T044 omits the provider preroll block; preroll
generation, cache bytes, parser, restart reuse, and legacy/pre-typed request behavior are preserved.
The superseded request-local `runtimeInstanceLabels` workaround was removed so `displayName` is the
single presentation mechanism. Perspective still comes only from `combatState.controllers`.

## #216 implementation

`main.py` now uses one detached, request-local helper to apply the existing canonical main-system
prompt and message ordering to rebuilt histories before T067. It is wired at exactly four live
consumers:

1. transition failure `needs_response`;
2. deferred `needs_post_combat_narration` or `needs_response`;
3. ordinary post-combat narration;
4. completed active-combat startup resume.

The transition seam remains unwired for `needs_post_combat_narration`, which is code-proven
unreachable there. Ordinary/deferred callers preserve `run_outside_response_fence`; resumed startup
preserves its direct call outside response/state authority. Reward, XP, history-record writers,
status routing, persistence formats, retries, and provider routing are unchanged. Structured
`STATE_CHANGE` diagnostics now carry the existing `DEBUG:` marker and duplicate direct prints were
removed, preventing the existing headless/web classifiers from treating the diagnostic as DM prose.

## Deterministic verification

Final commands and results:

- `python -m pytest .superpowers/local-tests/combat -q` -> `72 passed in 1.94s`.
- `node .superpowers/local-tests/combat/test_displayed_narration_adjudication.mjs` -> `2 passed`.
- `python -m py_compile core/ai/combat_agent.py core/ai/combat_narration.py core/generators/combat_builder.py core/managers/combat_manager.py core/managers/combat_state.py main.py` -> exit 0.
- `git diff --check` -> exit 0 (only the pre-existing user-owned React test remains modified).
- Final process check used `Get-NetTCPConnection -LocalPort 8368` and an explicit
  `Get-CimInstance Win32_Process | Where-Object` predicate over all eight named parent/direct child
  acceptance launchers, including `run_headless.py` and direct terminal `main.py`.
  The retained artifact includes the complete literal executable command and structured result:
  `validation_evidence/agentic_combat/slice1/acceptance-215216-final-cleanup.json` -> empty
  `listeners` and `processes`; the required room watcher remained live as PID 15160.

The ignored tests cover exact-ID typed/pre-typed/legacy polarity, canonical names that themselves end
in `_2`, duplicate monsters and NPCs, real caller-owned T044/T096/T097 construction, mechanical vs
presentation delivery splitting, four T067 caller bindings and ordering, and exact-label
case-insensitive adjudication without a generic suffix regex.

## Real OpenAI acceptance and transcripts

All evidence below is local, ignored, and intentionally unstaged under
`validation_evidence/agentic_combat/slice1/`. Raw calls/captures remain local because they can contain
provider or campaign data. The Markdown transcripts record the complete captured player input and
displayed DM output for owner review.

### #215 PASS evidence

- Full headless combat: `acceptance-215216-headless-r1/combat-transcript.md` (exit 0, combat reached
  and completed, clean T044 input and canonical scene names).
- Primary exact event: `acceptance-215-primary-r2/transcript.md` (T096 retains mechanical
  `Snow Rat_2`; T097/display uses `Snow Rat`, second-person human perspective, no bookkeeping).
- Legacy 20-turn voice sample: `acceptance-215-legacy-voice-r1/combat-transcript.md` plus
  `voice-adjudication.json` (20/20 new human-controlled deliveries; globally unique event/delivery
  IDs; every new block correlated and clean).
- Reversed controller, React: `acceptance-215-reversed-react-r4/transcript.md`.
- Reversed controller, legacy: `acceptance-215-reversed-legacy-r1/transcript.md`.
  In both, Snow Rat is human and Eirik is actor-agent; narration addresses the rat as `you` and
  Eirik in third person, with no raw instance suffix or mechanical bookkeeping.
- Skipped-human presentation:
  - React: `acceptance-215-skipped-react-r1/transcript.md`
  - legacy: `acceptance-215-skipped-legacy-r1/transcript.md`
  - headless: `acceptance-215-skipped-headless-r1/transcript.md`
  - terminal raw transcript: `acceptance-215-skipped-terminal-r3/terminal.stdout.log`
  Each reached the canonical notice for Eirik while mechanical T096 identity remained unchanged.
- Full React combat through closed completion and post-combat receipt:
  `acceptance-215216-react-full-r3/combat-transcript.md`.
- Full legacy combat through closed completion and post-combat receipt:
  `acceptance-215216-legacy-full-r1/combat-transcript.md`.

The React and legacy full runs include real human input, persisted completion receipts, screenshots,
server streams, and trace archives. Every newly displayed correlated combat narration block was
checked against exact authoritative internal labels case-insensitively, without suffix heuristics.

### #216 split verdict

- Ordinary post-combat T067: REACHED/PASS in the full headless, React, and legacy runs above. Raw
  requests contain one canonical JSON-bearing system prompt first; calls returned valid OpenAI
  responses and the completion receipts closed.
- Active-combat resume: REACHED/PASS at
  `acceptance-216-active-resume-r1/transcript.md`. T043 re-engaged the persisted encounter; the
  player killed the final enemy; completion closed; XP increased exactly once by 37; exactly one
  new resumed `[COMBAT CONCLUDED]` compatibility record preceded a successful T067 request. The
  pre-existing action-handler `[COMBAT CONCLUDED - HISTORICAL RECORD]` record remained unchanged.
- Typed T043 initial resume: REACHED/PASS in the reversed React and legacy captures. The persisted
  automatic-window history presents `Scout Kira, Snow Rat, Snow Rat`, contains no `_2`/`_3`, has a
  canonical prompt, and reached real OpenAI.
- T043 malformed-first live retry: NOT REACHED. The available evaluation override changes only the
  model profile; it cannot honestly induce malformed output. Deterministic retry/caller wiring is
  covered, but no synthetic or model-shopped provider result is claimed.
- Lawful deferred immediate-travel-outcome path: T065 REACHED, execution/post-combat T067 NOT
  REACHED. In `acceptance-216-deferred-game-r1`, real OpenAI produced ordered
  `transitionLocation`, `updateTime`, `createEncounter`; after one correction T065 accepted it as the
  immediate travel outcome. Travel committed, but the operation stalled before `createEncounter`
  committed and exceeded the harness observation bound. Exact game processes were terminated and
  port 8368 was freed. No success is claimed for the deferred T067 seam.
- Transition-failure `needs_response`: NOT REACHED. No safe production failure could be induced
  without corrupting authoritative campaign state. Deterministic caller wiring passes; the real
  acceptance remains open.

Accordingly, #215's scoped naming/perspective repair is accepted on the configured OpenAI/native
Windows matrix. #216 is implemented and its ordinary/resume seams are accepted, but the issue must
remain open until the deferred execution and transition-failure real entrants are reached or the
owner explicitly revises their acceptance disposition.

## Disclosed unrelated or pre-existing failures

- Existing campaign-chronicle compression emitted repeated errors distinct from T042:
  21 lines in the full headless streams, 12 in full React, 12 in full legacy, 24 in active resume,
  and 24 in the deferred probe. They name the existing Thornwood Watch, Keep of Doom, and Shadows of
  Kharos chronicle files. These errors can affect context/token behavior, so none of those runs is
  claimed globally error-free; the scoped name/perspective and T067 request/result evidence remains
  bounded to the correlated combat records described above.
- T042 round-summary compression emitted 25 failures during the legacy 20-turn run and one during
  the full React run. Combat/T097 deliveries still persisted, so this does not negate the narrow
  #215 result, but those runs are not globally error-free.
- Frostmere has known missing-media 404s, especially on legacy. These are visible in the retained
  browser/server evidence and are not hidden.
- Direct terminal startup has a pre-existing debug-interceptor/UTF-8 wrapper incompatibility. The
  terminal presentation probe used a narrow launcher that uninstalled the interceptor before
  `main.main()`, reached the required skipped-human output, then deliberate EOF exposed another
  pre-existing `run_combat_simulation`-returns-None unpacking error. The terminal slice is therefore
  reached for presentation but FAILED as a complete clean run.
- The lawful deferred probe exceeded its 600-second observation bound after travel. It is recorded
  as NOT REACHED, not a product pass or an invented provider failure.

## Repository hygiene and next gate

- Production changes are committed and pushed as two rollback points above.
- Ignored local tests, fixtures, captures, traces, screenshots, and evidence were not staged.
- `config.py` and secrets were not staged.
- The unrelated user-owned modification
  `web/frontend/src/components/party/party.test.tsx` was not edited or staged.
- No merge, PR, deployment, or issue closure was performed.
- Next gate: independent review of this evidence record, then a separate documentation-only commit
  and push. The final room handoff is sent only after that commit, per owner instruction.
