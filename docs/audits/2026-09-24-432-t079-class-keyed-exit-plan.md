# #432 T079 character writer: class-keyed exit, confirmed no-change answers, supersession

Status: PLAN r2 (2026-09-24), after Part 3 round 1 (nine seats; resolution ledger in section 11). Nothing implemented. Execution needs convergence and the owner's approval (NEQ-REVIEW-13).

## 0. Provenance (captured dynamically; evidence, never authority)

| Item | Value |
|---|---|
| Branch | `fix/432-433-count-keyed-giveups`, created from `origin/main`; r1 commit 6639a6f9 |
| Base revision | `origin/main` = 7b20bc7d. Ancestor check: `git merge-base --is-ancestor HEAD origin/main` at plan time. |
| #193 epoch | v3.1, `updatedAt` 2026-09-18T18:20:12Z. Re-checked before implementation (NEQ-OPS-03). |
| Provider / model | `openai`. T079, T078 and T051 resolve to `gpt-5.6-luna`, `reasoning_effort: none` (`model_registry.py:390-397`, `:460-477`; verified with `model_config.resolve_callsite_config("T079","openai",0)`). Never the legacy GPT-4.1 provider. |
| Platform | WSL2 headless first; native Windows row owner-run |
| Owner assignment | 2026-09-21: "pick a new issue worthy of your brain that doesn't require the LM model". #432 was filed with owner authorization on 2026-09-18. |

Line numbers below are at 7b20bc7d. They are re-verified at implementation time.

## 1. Scope

**In scope.** The T079 retry loop in `updates/update_character_info.py::_update_character_info_unlocked` (1444-2571), including its exception handlers, and the empty-delta check `_is_meaningful_character_delta` (1141-1148).

**Not in scope.** Each item is already tracked, or has a drafted issue waiting for owner authorization (section 10).
- **#433.** The quoted terminal has been dormant since b7f7a863. Forensics and a re-scope were posted on 2026-09-24, and a separate plan follows.
- **#357 residual.** O3's class belongs to #357's T051 pre-repair (`:1519-1549`). See section 2, O3, and row A2a.
- **#324.** The T051/T052/T054 bounds and description caps stay there. #432 takes over only the T079 default-loop part of #324's "Bounded failure exits". Task 1 routes confirmed no-change answers through the post-commit validators, which carry #324's caps; the caps themselves are unchanged (NL-3).
- **#431.** The T079 `history[-10:]` window at 1910 (NL-2).
- **#367.** The turn loop's `PROVIDER_MAX_FAILURES`.
- **#375.** The storage processor's count.
- **Level-up.** `level_up_manager.py:620` calls `prepare_character_delta` with typed input and never calls T079. It is untouched.

## 2. Observed failures (NEQ-EVIDENCE-01; artifacts under `agent-room-fleet-kit/local-data/`)

### O1: false failure after a correct "no change" answer (2026-09-18, `242-down-scene/marsh-raw-1`, openai gpt-5.6-luna)

- The accepted DM response had one action (`242-down-scene/game-marsh-raw-1/modules/conversation_history/conversation_history.json` index 46): `updateCharacterInfo(eirik_hearthwise, "Escaped the quicksand with a successful Athletics check. Remains at 1 hit point; soaked and on unstable floating moss near the deep central water.")`.
- The pre-update sheet was already at 1/54 HP with status alive. The product's own backup confirms it: `characters/eirik_hearthwise.backup_update_20260918_235325.json`. So the request had no mechanical effect.
- T079 answered `{}` on all three attempts (`242-down-scene/game-marsh-raw-1/debug/character_updates_log.json`; the per-call capture is in `242-down-scene/capture-marsh-raw-1/T079.json`).
- Each answer raised `ValueError: T079 returned an empty or unrecognized character delta` (`game_errors.log:1-15`; the traceback line matches the raise at 7b20bc7d:2071).
- The code then logged `Failed to update character eirik_hearthwise after 3 attempts`, and the action handler returned `status=error` (`core/ai/action_handler.py:3845-3853`).
- What the player saw:
  - At seq 606 in `marsh-raw-1.ndjson`, the correct escape narration.
  - For 10.8 s after that (seq 611 to 702), "Updating character info...".
  - At seq 702: `That action could not be completed safely. No further actions from that response were applied.` (`web/shared_state.py:20`, printed at `main.py:9691-9704`).
- That run used a parity clone with `COMPRESSION_ENABLED = False`. That setting is disclosed; it does not touch this path.

### O2: the same error class at combat end (2026-09-07, `issue116`)

- `issue116/legacy-server.log:3920-3950`: `Following the turn's events: Completes her required turn after all hostile creatures are dead..` for scout_elen. The request has no mechanical effect.
- The same `ValueError` was raised three times, then `Final consolidated update failed for scout_elen`.
- The raw answer was not retained, so that the answer was `{}` is inferred, not proven.
- The combat-end caller only logs the failure (`core/managers/combat_manager.py:5734-5741`). This is the legacy combat entrant, reached by encounters that default to legacy (`combat_state:621-625`).

### O3: pre-#357 armor poisoning (2026-09-07, `issue116`). Superseded on main; not acted on here.

- The request was: `Uses one arrow to attack Skeleton_2, dealing 8 piercing damage.` (`:3840`, `:3890`).
- Thane was at 50/50 HP before the merge (`:3895`).
- The T079 answers were ammunition -1 on attempts 1 and 3. On attempt 2 the answer also carried `hitPoints: 42` (`:3906`), which misread the damage Thane *dealt* as damage taken.
- All three answers were rejected with `99 is greater than the maximum of 10 at path: equipment.2.dex_limit`. The requested arrow was lost; no HP change was requested. Kira shows the same class (`:3865-3887`).
- The `99` came from an older T051 correction in the same run (`:3304`, `:3380`, `:3469`).
- #357 (948ff048, 2026-09-11, an ancestor of main) since added two fixes:
  - prevention: T051 checks its proposals against the schema (`core/validation/character_validator.py:2613-2621`);
  - recovery: before T079 runs, T051 repairs out-of-schema armor in memory, and the repair shares the update's one atomic write (`update_character_info.py:1519-1549`; D-357-1..4).
- #357's own live acceptance observed 99 -> null with HP 8 -> 12 committed in one write (`docs/audits/2026-09-11-issue-357-armor-schema-contract-acceptance.md`).
- O3 predates #357, so this plan adds no mechanism for it. Row A2a re-derives it on today's main as forensics. If it reproduces (T051 exhausts, then T079 is refused), the result goes to the owner under #357 (two-strikes) and not into this plan.
- **Failed approach (NEQ-OPS-04):** r1's Task 2 (commit around pre-existing violations with a WARN) was withdrawn. It duplicated #357's single path. #357's plan had already rejected that exact option ("O2 ... leaves invalid data forever", `docs/audits/2026-09-11-issue-357-armor-schema-contract-plan.md:482-484`). Its index-free key would also have passed a violation introduced by the delta (GL-2).

### Real-data scan (row A0, run read-only by the Acceptance seat)

- No `"dex_limit": 99` in the owner's `modules/`, `data/` or `characters/`.
- Schema check of 39 live sheets: violations only in four `test_integration_hero` backups.

## 3. Root cause (NEQ-OPS-02)

**O1/O2 are class (d): a deterministic-vs-agentic disagreement that breaks the coherence rule.**
- The T079 prompt says "Do not include unchanged fields" and "Only include top-level keys ... if a value within them has changed" (`:1610`, `:1627`). For a change with no mechanical effect, the contract-correct answer is `{}`.
- The gate rejects exactly that answer (`:1141-1148`, `:2068-2073`), so the loop cannot be won:
  - On the ordinary path it gives up after 3 attempts and reports a false failure.
  - On the staged travel-sibling path (`effects_runtime.py:253`, `structural_reissue=True`), the generic handler adds no correction note (`:2505-2556`). The same request reissues forever. This is CODE-PROVEN.
- **Origin of the empty rejection:** 36bd7ed0 (2026-07-14, "fix(multi-model): harden callsite contracts and state recovery"; no issue), reaching main through 715732d5. Its goal traces to 12ddb548 (HIGH-6: "the update silently no-ops"): never report success when a real change produced nothing.

**The cancel signal is swallowed (FF-1, CODE-PROVEN; pre-existing and found in round 1).**
- `:2506` re-raises `LiveProviderSuperseded` only when `commit_guard is not None`.
- That condition came from 2e6ad1f8 (2026-09-13, the #323 baseline). No production caller passes `commit_guard` (grep of every caller: `effects_runtime.py:98/130/253`, `combat_manager.py:5734`, `process_effect_expirations.py:54/101`, `update_character_effects.py:740`).
- On the ordinary path, a superseded T079 therefore spends two more immediate attempts and returns `False`.
- On the staged path the loop never ends:
  - `_check_live_authority` raises again on every reissue (`live_provider_call.py:1166-1168`) and the handler swallows it each time.
  - A web Load waits on `quiescent.wait()` (`web_interface.py:3187-3188`) forever. B1 says Load is never refused.

**B2-vii: the count keys on every failure class.**
- The one bound counts all of these:
  - completed-invalid answers;
  - deterministic provider refusals (`LiveProviderCompletedError`, the #240 rule in its docstring). These are retried twice on the ordinary path and forever on the staged path.
  - swallowed supersession;
  - non-live provider errors.
- Non-live errors arrive only when T079 runs outside a live turn scope. Inside one, T079 is a required live task, and the transport already reissues transient and empty failures (`live_provider_call.py:46`, `:1691-1698`).
- The one verified entrant outside a scope is effect-reversal expiry for unmigrated campaigns: `main.py:8810`, inside the main `while True` at `:8742`, before the per-turn scope at `:9414`. That caller re-queues a failed reversal as `pending` (`update_character_effects.py:524-528`) and resumes on the next iteration, so the resume already lives at the caller.

## 4. Spec-pin (NEQ-REVIEW-04)

**Identities.**
- The character file comes from `get_character_path(name, role)`.
- The ordinary path holds the per-character update lock and the `.effects.lock` lease (`update_character_info.py:1403-1422`, `effects_runtime.py:107-115`).
- The staged preparation (`effects_runtime.py:238-262`) holds neither. It locks only at apply (`:283-298`).
- The callsite is `T079` (`update_character_info.py:111`). Lock order is unchanged.

**Source of truth.** The character sheet JSON on disk. A T079 answer is a proposal (NEQ-CORE-06).

**Commit points (unchanged).**
- Ordinary path: `commit_character_sheet` (`:2327`).
- Staged path: `apply_staged_character_update` (`effects_runtime.py:283-298`). It returns `already_committed` when the file equals `after`, `blocked_conflict` when the file differs from `before`, and `committed` otherwise.

**Failure classes.** Only exceptions raised by the provider-call statement (`:1978-1983`) are provider-classified; everything else is `completed_invalid`.

| Class | What produces it | Policy |
|---|---|---|
| `superseded` | `LiveProviderSuperseded` from anywhere in the pre-commit loop | Re-raised on every path |
| `provider_deterministic` | `LiveProviderCompletedError` (live scope) | The transport has already decided no reissue can heal it: 4xx, quota, or a schema rejection |
| `provider_handback` | `ProviderCallError` from a non-live call (`core/ai/api_client.py:22`; includes `ProviderEmptyResponse`, which `_fire_primary_with_retry` has already retried) | Returned to the caller at once, never counted. Transport recovery is not this loop's job; the transport or the caller owns it |
| `completed_invalid` | JSON decode error; a non-empty delta with no recognized field; an incomplete delta (`:2093`); critical-field loss (`:2224`); schema-invalid merged sheet (`:2267`); any other exception from the loop body or the call statement (capture or config errors) | Counted |

**No-change confirmation.**
- A first `{}` answer is not a failure. The loop appends one confirmation note and asks again (Task 1).
- A second consecutive `{}` is accepted as "no mechanical change".

**End states.** Each has a player-visible terminal.

| # | End state | Result | What the player sees |
|---|---|---|---|
| 1 | Success with a change | Sheet committed; returns `True` or a receipt | Narration, and the sheet matches it |
| 2 | Confirmed no change (`{}` twice) | The unchanged sheet flows through the existing preparation and normalization and commits. On the ordinary path the post-commit validators run as for any update. On the staged path the receipt's `after` is the prepared sheet, which may differ from `before` only by normalization. | Narration, with no failure line |
| 3 | `completed_invalid` at the D-432-1 bound (ordinary path only) | Returns `False` | Ordinary action: `SAFE_ACTION_FAILURE_MESSAGE` after the narration, and the narrated change is absent from the sheet. Combat end: log only; the narrated change is absent with no player line (pre-existing, issue I-1 drafted). Effect reversal: re-queued as pending; resumes. |
| 4 | `provider_deterministic` | Returns `False` at once on both paths | Ordinary path: as in state 3. Staged path: `prepare_character_update` raises `EffectsRuntimeError` (`effects_runtime.py:261-262`) inside `prepare_current_transition_actions` (`action_handler.py:3579`), after the `planned` checkpoint was written at `:3573`. `main.py:6655-6668` shows the safe failure; the `planned` checkpoint is discarded on the next iteration (`action_handler.py:1668-1674`), and the party does not move. Today this state is an endless reissue. |
| 5 | `provider_handback` | Returns `False` at once, uncounted | Effect reversal: pending, resumes next iteration. Any other non-live entrant: its caller's existing handling (table in Task 3 step 0). |
| 6 | `superseded` | Raises | Staged path: `superseded_invocation` (`main.py:6655-6659`). Ordinary path: the action handler's existing generic handler (`action_handler.py:3854-3863`) while the superseding Load/Reset/Quit proceeds. |

**Part 2 pages cited.**
- p5 NEQ-EFFECTS-01: the staged caller is the effects runtime.
- p8 NEQ-WORLD-04: the sheet is player data.
- p9 NEQ-SAVE-01: Load is never refused.
- p11 NEQ-PROVIDER-01: `create_completion` stays a thin router and is untouched.
- p12 NEQ-SCHEMA-01/02: schema authority is unchanged.
- p13 NEQ-ACCEPT-01..03.

**README promise.** "an intelligent AI that remembers every decision" (README.md:22) and "Character Sheets" (README.md:233): what narration says happened must be on the sheet. This plan advances the promise and must not degrade it.

## 5. Tasks

**Task 0. Rollback point.** The plan-only commits (r1 6639a6f9, then this r2) precede any code change.

**Task 1. `{}` is a typed "no change" answer, confirmed once (fixes O1/O2; D-432-2; GL-3).**
- `_is_meaningful_character_delta` (`:1141-1148`) returns `True` for an empty dict. It still returns `False` for a non-dict, and for a non-empty dict with no recognized schema field. Its docstring's word "meaningful" becomes "recognized".
- In the loop, straight after the parse (`:2067`):
  - A `{}` answer that does not directly follow the confirmation note appends one confirmation note to the request. Wording: "Your previous answer was {} (no character-sheet field changes). If the described change alters any field on this sheet (hit points, spell slots, equipment, ammunition, currency, experience, conditions or any other field), return those fields now. If it changes nothing on the sheet, return {} again." The loop then reissues. This is not a `completed_invalid` outcome and does not count.
  - A `{}` answer immediately after the confirmation note is accepted. The loop logs `info("T079 confirmed no mechanical change for <name>")` and continues through the existing completeness check, preparation and commit, unchanged.
  - The note is appended exactly as the existing correction notes are (`messages[-1]["content"] += ...`), with no count or length bound.
- **Coverage (disclosed in D-432-2).** After confirmation, T079 is the authority on "no mechanical change". The existing completeness regex (`:1151-1251`, AP-7, issue I-2 drafted) is not presented as a safeguard; it returns an empty set for most observed change strings.
- **Interaction with the completeness regex (disclosed).** A confirmed `{}` still passes through the completeness check. If the regex infers a required field, that is a regex-vs-model disagreement: it counts as `completed_invalid`, exactly as a partial non-empty answer does today. On the staged path that disagreement can repeat without end, which is the same pre-existing exposure a partial answer has there (issues I-2 and I-4). No new handling is added for it here.
- **The `declarative_effects and managed_effect_operation` clause at `:2068-2070` (SP-5).** It already lets an empty delta through when an engine-owned effect operation exists, and it is unchanged. That case needs no confirmation because the effect operation is the change.

**Task 2. Withdrawn in r2** (section 2, O3; resolution ledger rows SP-2, CUST-1, LEAN-1, GL-1, GL-2, ACC-1). The number is kept so ledger references stay stable.

**Task 3. Class-keyed exit (B2-vii; D-432-1).**
- **Step 0 (audit, before code).** Produce the entrant table: caller, file:line, live scope present?, terminal on `False`. Cover the seven entrants in section 3, plus the startup combat resume (`main.py:8419` then `combat_manager.py:5734`), which LEAN-3 hypothesized runs without a round scope. Record the result in this plan. Any entrant whose terminal silently loses a narrated change goes to issue I-1, not into this plan.
- **Step 1.** Wrap the provider-call statement (`:1978-1983`) in its own `try`:
  - `LiveProviderSuperseded`: re-raise.
  - `LiveProviderCompletedError`: `provider_deterministic`. Log `FAILURE: T079 provider refused <name> (deterministic, <http_status>)` and return `False`.
  - Any other `ProviderCallError`: `provider_handback`. Log `T079 provider call for <name> returned to caller (<class>)` and return `False`.
  - Anything else: re-raise into the existing handlers, where it counts as `completed_invalid`.
  - The live transport already classified the error, so no second classifier is imported (SP-1, SP-4, LEAN-4).
- **Step 2.** In the loop-level generic handler (`:2505-2507`), re-raise `LiveProviderSuperseded` unconditionally. Drop the `commit_guard is not None and` condition.
  - The post-commit validator handlers at `:2451` and `:2469` keep their condition. They run after the primary commit; raising there would report a committed update as failed.
- **Step 3.** Replace the per-iteration `attempt <= max_attempts` exits (`:2115`, `:2242`, `:2269`, `:2552`) with one total count of `completed_invalid` outcomes (`completed_invalid_count`, never reset: LEAN-6).
  - The ordinary path ends at the D-432-1 bound.
  - The staged path (`structural_reissue=True`) keeps its unbounded correction loop for this class. That is unchanged behavior, and the pre-existing split is issue I-4 drafted.
- **Step 4.** The debug field `attempt` (`:2001`, `:2015`) stays: it is the call ordinal for each T079 answer. The terminal line at `:2569` becomes `FAILURE: T079 answers stayed invalid for <name> (<n> completed-invalid answers)`.

**Task 4. Documentation.**
- `docs/architecture/provider-routing.md`, the T079 paragraph at `:54`: the class-keyed exit and the confirmed `{}` no-change contract.
- `docs/architecture/travel-transitions.md`, step 6 (`:48`) and the crash/restart steps (`:67-71`): the staged-sibling `provider_deterministic` terminal (end state 4) and supersession propagation (end state 6) (CUST-2).
- `docs/audits/2026-09-11-issue-357-armor-schema-contract-plan.md`: no change. This plan cites it and adds no competing mechanism.
- #193 Part 5: append D-432-1 and D-432-2 once the owner rules (NEQ-LEDGER-01).
- Issue comments after landing:
  - #432 and #324: landed scope.
  - #431: after Task 1 a confirmed `{}` commits, so a `{}` caused by context lost beyond the 10-message window would now be accepted (NL-2).
  - #357: the A2a result.

**Task 5. Acceptance (section 8).** Rows run serially, one operation at a time.

## 6. GL-1 Behavioral Contract

| Changed element | Origin | Goals | Disposition |
|---|---|---|---|
| `{}` rejection (`:1143-1144`, raise `:2068-2073`) | 36bd7ed0 (2026-07-14, no issue) via 715732d5; goal from 12ddb548 (HIGH-6); engine-effect exemption 3525150b | (a) never report success when a real change produced nothing; (b) reject dicts with only unknown keys; (c) do not silently no-op on Gemini narration | (a) PRESERVED in part: a `{}` gets one typed confirmation (Task 1). A second `{}` makes T079 the authority, which D-432-2 discloses. (b) PRESERVED (`:1146-1148`). (c) PRESERVED: narration fails `json.loads`, or yields unknown keys, under schema forcing. |
| Single `attempt <= max_attempts` budget (`:1921-1922`, `:2115`, `:2242`, `:2269`, `:2552-2556`) | f5e84dd5 (2025-05-31, "Implement unified character system") | Every update ends and returns; the effect-reversal caller relies on that return (`main.py:8810-8816`) | PRESERVED for `completed_invalid` (D-432-1). `provider_deterministic`: the retries are REMOVED, and the call stops at once (D-432-1). `provider_handback`: the retries are REMOVED, and the error is returned to the caller at once. `superseded`: re-raised. |
| `structural_reissue` bypass (`:1971`, `:2115`, `:2242`, `:2269`, `:2552`) | b7f7a863 (2026-08-24, "fix(travel): make agentic transitions recoverable"); `commit_guard` wiring at `:1428/:1437` from 2e6ad1f8 (#323), which has zero production callers | A required staged sibling is fixed before movement and never fails the travel turn by count | PRESERVED for `completed_invalid`. `provider_deterministic` now ends the staged preparation (end state 4). |
| Supersession re-raise condition (`:2506`) | 2e6ad1f8 (2026-09-13, #323 baseline) | Re-raise for the #323 guarded caller | Widened to every path (FF-1). The goal is kept, and the endless staged loop and wasted ordinary attempts are removed. |
| #357 pre-gate armor recovery (`:1519-1549`) | 948ff048 (#357; D-357-1..4) | Recover damaged armor through T051 in the same atomic write; never loosen the schema | UNCHANGED. Listed because it sits in the changed function. |
| Schema-invalid branch and its correction notes (`:2267-2288`) | f5e84dd5 (the gate); 31f5e8db (2025-06-28, the notes: "learn from validation failures", item_subtype values) | Never commit an invalid sheet; give the model actionable feedback | UNCHANGED, apart from counting as `completed_invalid` |
| Completeness regex (`:1151-1259`) | 36bd7ed0 via 715732d5 | Stop partial application of mechanically coupled changes | UNCHANGED in code. No longer described as a `{}` safeguard. AP-7 issue I-2 drafted. |
| Success consumers of a confirmed no-change: `effects_runtime.py:137-147` (rest lifecycle, keyed on prose; pre-existing) and `:101-104` | 3525150b lineage | Run the effect lifecycle after a successful update | PRESERVED: they run on every success, as today |

**Not true in r1, and corrected:** "No deletion of an except, retry ... pattern". Task 3 removes the retries for `provider_deterministic` and `provider_handback`. Both are listed above.

## 7. FS-1

| Hit | Exhaustion terminal | Class |
|---|---|---|
| `completed_invalid_count` bound (ordinary path) | End state 3 | TERMINATES for the `completed_invalid` class only. Legal only with the D-432-1 ratification (B2-iv; B2-vii scoped to a deterministic class). |
| `provider_deterministic` stop (N=1) | End state 4 | TERMINATES. Legal only with the D-432-1 ratification. #240 is a code docstring, not a ledger entry. |
| `provider_handback` (N=1) | End state 5 | CONTINUES at the caller for the verified non-live entrant (reversal re-queued as pending, `update_character_effects.py:524-528`). The Step 0 table must show a CONTINUES terminal for every other non-live entrant, or the entrant is issue I-1. |
| `time.sleep(1)` before a reissue (`:2554`) | A reissue | CONTINUES |
| Staged-path unbounded `completed_invalid` | A reissue with a correction note | CONTINUES. Pre-existing; the split is issue I-4. |
| `_fire_primary_with_retry(max_attempts=3)` for non-live empties (`multi_model_capture.py:350-377`) | `ProviderEmptyResponse`, which becomes `provider_handback` | Inherited; flagged, not added |
| `.effects.lock` 30 s (`update_character_info.py:1412-1422`; `effects_runtime.py:109-115`, `:283-287`) | Busy turned into a refusal | Inherited B2-ii. Flagged, not added: #324 (2026-09-10 comment) covers `update_character_info.py`; issue I-3 drafted for `effects_runtime.py`. |

## 8. Acceptance (NEQ-ACCEPT-01..03; evidence block NEQ-EVIDENCE-04 on every row)

**Common conditions for every row.**
- Headless, real OpenAI, current bindings.
- Driver: `run_headless.py serve --game-dir` plus the kit's `242-down-scene/build_combat.py` / `drive_combat.py` pattern. The harness named in #193 p13 does not exist on main (ACC-6).
- Every fixture is built fresh, with `prompts/` and `schemas/` refreshed from the checkout, and every prompt file's hash is recorded (NEQ-REVIEW-16, 2026-09-04).
- `COMPRESSION_ENABLED` stays at its default (True). The difference from O1 is disclosed.
- T079 raw answers come from the capture directory, not the trimmed `debug/character_updates_log.json`.
- Every row lists every T079, T078 and T051 call with: response.model; latency from the player input; capture line; T079 history length compared with the 10-message window (NL-2); and whether each post-commit validator hit its cache or made a model call (NL-3).
- Every row prints each T079 answer next to its change string and the narration. Any `{}`, confirmed or not, next to a change string with a mechanical effect is FAILED.
- The Player-Experience seat reviews every row's transcript. Five narration claims are spot-checked against disk (PX-6).
- Runs are serial.

**Rows.**
- **A0. Real-save scan.** Done read-only in round 1 (section 2): the owner's live sheets are clean. It is re-run with the literal command at implementation time over `modules/`, `data/`, root `characters/` and every kit fixture.
- **A1. No-change answer at the play layer (O1).**
  - Setup: branch; the Boggard Marsh fixture; the marsh-raw-1 command sequence up to the quicksand escape.
  - PASSED when all of these hold:
    - the DM emits an `updateCharacterInfo` with no mechanical effect;
    - T079 answers `{}`, the confirmation follows, and `{}` again;
    - the log shows `T079 confirmed no mechanical change`;
    - the mechanical fields are byte-equal before and after;
    - the transcript has no `could not be completed safely` line.
  - NOT-REACHED if the DM emits no such action, or if T079 answers non-empty.
- **A1b. Updater-layer diagnostic (O1 input verbatim). Never cited as PASSED.**
  - Setup: a fresh fixture directory whose Eirik pre-state is the product backup `eirik_hearthwise.backup_update_20260918_235325.json` (1/54, disclosed).
  - Call the production `update_character_with_effects("eirik_hearthwise", <O1 change string>, party, action_context=<O1 captured action_context>)`.
  - Record the parsed T079 requests next to the O1 capture, both answers, the return value, and the sheet diff (no non-empty -> empty transition, NEQ-SCHEMA-02).
  - Evidence class: OBSERVED at the updater layer, outside a live scope. It is diagnostic only.
- **A2a. O3 forensics on today's main, before any code (ACC-1).**
  - Setup: main 7b20bc7d; `issue116/clean-reset-fixture/saved_games/save_20260907_125556` restored into a fresh game directory with refreshed prompts and schemas.
  - One ordinary-path command changes Kira's sheet (29/40 HP; three armor pieces with `dex_limit` 99), for example "Kira takes a short rest and binds her wounds".
  - Record the T051 pre-check calls, T051's answers, T079's answers and the outcome.
  - If the change commits with `dex_limit` repaired, O3 is not reproduced on main: record the result on #357 and do nothing here.
  - If T051 exhausts and T079 is refused, escalate:@owner under #357 (two-strikes; D-357-2/4).
- **A3. Gate polarity (NEQ-ACCEPT-02).** Each item is PASSED if reached in A1, A2a or a pinned run, and otherwise stated NOT-REACHED. No synthetic probe is added.
  - (a) `provider_deterministic` stop, end state 4.
  - (b) The completeness INCOMPLETE correction still fires.
  - (c) A staged travel sibling (`updateCharacterInfo` alongside `transitionLocation`) commits. Pinned run: travel with a sibling that changes the sheet.
  - (d) Combat-end entrant: the O2 path. Record the terminal.
  - (e) Supersession: a headless Load issued while a T079 call is in flight completes, with no hang and no orphan provider child.
    - Control arm on main for (e) on the staged path: expected hang (FF-1). The attempt is bounded by the operator stopping it and is reported with its artifacts.
    - (e) is attempted on the ordinary path first. It is PASSED when Load completes and the transcript shows the restore.
  - (f) `completed_invalid` at the bound.
- **A4. Parity.** For every T079 call in A1, A2a and A3, the change string and sheet diff are shown side by side and judged by Claude.
  - Zero `{}` answers are accepted on a change string with a mechanical effect.
  - Zero non-empty -> empty transitions.
  - Changes the narration did not claim are listed (PX-2).
- **Hygiene.**
  - ASCII-only touched Python.
  - `pyflakes` undefined-name check on changed files (NEQ-OPS-05).
  - No-Limits and Single-Path sentinel greps over the diff, pasted raw.

## 9. Owner decisions (execution blocked until ruled, NEQ-REVIEW-09)

**D-432-1. T079 class-keyed exit (B2-iv/B2-vii; a new ledger class like D-VR-15/D-VS-12).** Ratify all four of:
- (i) On the ordinary path, 3 completed-invalid T079 answers in total end the update with `False`. The terminals are exactly end state 3:
  - Ordinary action: the safe-failure line after the narration, with the narrated change absent from the sheet.
  - Combat end: log only (issue I-1).
  - Reversal: resumes.
- (ii) `LiveProviderCompletedError` (4xx, quota, schema rejection, as the transport already classifies it) ends the update at once on both paths. The staged terminal is end state 4.
- (iii) Non-live provider errors are returned to the caller at once and never counted.
- (iv) Supersession always propagates.
- Recommendation: ratify. The alternative, unbounded correction on the ordinary path, risks an unwinnable loop (the #194 scar).

**D-432-2. Accept `{}` as T079's typed "no change" answer after one confirmation.**
- Disclosed: after the confirmation, T079 alone decides that a change has no mechanical effect. A lazy second `{}` to a real change such as "takes 8 damage" would commit as no change.
- No observed case exists: across 7 debug logs and 65 T079 answers, the only `{}` answers were O1's correct ones.
- For an effect reversal, a confirmed `{}` completes the durable reversal claim (`update_character_effects.py:563-568`) instead of releasing it for retry, so a wrong confirmed `{}` there loses that reversal (COMPAT-3).
- Cost: one extra T079 call per no-change request.
- Recommendation: yes.

**Issue authorizations** (new public issues need the owner, per the standing rule; bodies drafted by the finding seats, R9). File each: yes/no.
- **I-1** (PX-1/FF-3): the combat-end consolidated update failure is log-only, so narrated XP/HP/ammunition is silently absent (`combat_manager.py:5731-5741`). Evidence: `issue116/legacy-server.log:3889/3918/4035/4138`, and an owner-checkout quota 429 at combat end (`modules/logs/game_errors.log:3330-3452`).
- **I-2** (CUST-3/GL-7): the T079 completeness check infers required fields from DM prose by regex (AP-7) (`update_character_info.py:1151-1251`).
- **I-3** (FF-6): the `.effects.lock` 30 s deadlines in `effects_runtime.py:109-115/283-287` turn busy into a refusal (B2-ii).
- **I-4** (SP-3): T079 termination forks on `structural_reissue`, and the `commit_guard` mode is dormant (NEQ-LEDGER-09, NEQ-CORE-08). Its twin is #375.
- **I-5** (SP-4): provider errors are classified twice with divergent verdicts: typed `_error_disposition` versus prose-matching `classify_provider_error`.
- **I-6** (FF-7, mechanism CODE-PROVEN, reachability HYPOTHESIS): staged siblings for the same character are prepared from one starting sheet, so the later one returns `blocked_conflict`.

## 10. Tracked follow-ups

- #433: separate plan.
- #357: A2a result.
- #324: validator bounds and caps.
- #431: history window (plus the NL-2 comment).
- #367: turn-loop provider count.
- I-1..I-6: `escalate:@owner` until filed.

## 11. Resolution ledger

Round 1 dispatched nine seats on r1 (6639a6f9). Verdicts:
- BLOCKING: Custodian, Fail-Forward, Acceptance, Legacy-Contract, Player-Experience, Leanness, Single-Path, Consumer/Compat.
- PASS: No-Limits.

The Consumer/Compat real-save scan (read-only Draft7Validator) found:
- 137 owner sheets: 3 raw root `additionalProperties` (`inventory` holding only empty currency, purged on every update today). The pre-merge view is clean.
- 3,645 kit sheets: 18 invalid, all armor `dex_limit` 99 (issue116 and 332-acceptance snapshots). Zero non-armor violations, zero container-level violations.
- Every sheet that the withdrawn Task 2 would have touched is in #357's T051 class.

| Round | Seat | Finding | Reconciliation (NEQ-REVIEW-14) | Resolution |
|---|---|---|---|---|
| 1 | Single-Path | SP-1: transient branch is a second transport-reissue path | GENUINE_FIX | task-3 (branch removed; `provider_handback`) |
| 1 | Single-Path | SP-2: Task 2 duplicates #357's single path | GENUINE_FIX | task-2 withdrawn; A2a |
| 1 | Single-Path | SP-3: `structural_reissue` termination split, dormant `commit_guard` | PRE_EXISTING_OUT | escalate:@owner (I-4) |
| 1 | Single-Path | SP-4: two classifiers; "one classifier exists" false | PRE_EXISTING_OUT + wording | fixed-inline; escalate:@owner (I-5) |
| 1 | Single-Path | SP-5: Task 1's relation to the `:2068-2070` exemption | plan-polish | fixed-inline (Task 1) |
| 1 | Custodian | CUST-1: Task 2 rests on pre-#357 evidence | GENUINE_FIX | task-2 withdrawn; A2a |
| 1 | Custodian | CUST-2: travel schematic, p5 cite, #357 relation | GENUINE_FIX | task-4; fixed-inline (section 4) |
| 1 | Custodian | CUST-3: regex presented as the `{}` safeguard (AP-7) | GENUINE_FIX + PRE_EXISTING_OUT | task-1 (confirmation), D-432-2 disclosure; escalate:@owner (I-2) |
| 1 | Custodian | CUST-4: classifier boundary undefined | GENUINE_FIX | task-3 step 1 |
| 1 | Fail-Forward | FF-1: supersession swallowed; staged loop blocks Load | GENUINE_FIX | task-3 step 2; A3(e) |
| 1 | Fail-Forward | FF-2: transient branch freezes the main loop | GENUINE_FIX | task-3 (branch removed) |
| 1 | Fail-Forward | FF-3: combat-end terminal is silent | PRE_EXISTING_OUT | D-432-1 disclosure; escalate:@owner (I-1) |
| 1 | Fail-Forward | FF-4: classifier input set | GENUINE_FIX | task-3 step 1 |
| 1 | Fail-Forward | FF-5: empty class unnamed | GENUINE_FIX | task-3 (`provider_handback` includes `ProviderEmptyResponse`); D-432-1(iii) |
| 1 | Fail-Forward | FF-6: busy->refuse in effects_runtime untracked | PRE_EXISTING_OUT | escalate:@owner (I-3) |
| 1 | Fail-Forward | FF-7: same-character sibling conflict | PRE_EXISTING_OUT (HYPOTHESIS reachability) | escalate:@owner (I-6) |
| 1 | Fail-Forward | FF-8: spec-pin lock text; caller list | plan-polish | fixed-inline (section 4, section 3) |
| 1 | Leanness | LEAN-1 = SP-2 | GENUINE_FIX | task-2 withdrawn |
| 1 | Leanness | LEAN-2 = FF-2 | GENUINE_FIX | task-3 |
| 1 | Leanness | LEAN-3: entrant list incomplete | GENUINE_FIX | task-3 step 0 |
| 1 | Leanness | LEAN-4 = FF-4 | GENUINE_FIX | task-3 step 1 |
| 1 | Leanness | LEAN-5 = CUST-3 | GENUINE_FIX | task-1; D-432-2 |
| 1 | Leanness | LEAN-6: "consecutive" reset undefined; unread debug field | GENUINE_FIX | task-3 step 3 (total, no reset); Task 2 field gone |
| 1 | Leanness | LEAN-7: artifact root path | plan-polish | fixed-inline |
| 1 | Player-Experience | PX-1 = FF-3 | PRE_EXISTING_OUT | D-432-1 disclosure; escalate:@owner (I-1) |
| 1 | Player-Experience | PX-2: O3 misstated (HP 42 was a misread) | GENUINE_FIX | fixed-inline (O3); task-5 (A4 unclaimed changes) |
| 1 | Player-Experience | PX-3: `{}` vs mechanical change unguarded | GENUINE_FIX | task-1; task-5 (FAILED rule) |
| 1 | Player-Experience | PX-4: staged terminal unstated | plan-polish | fixed-inline (end state 4) |
| 1 | Player-Experience | PX-5: no status during transient reissue | moot | the transient branch was removed (task-3) |
| 1 | Player-Experience | PX-6: transcript review per row | plan-polish | fixed-inline (section 8) |
| 1 | Acceptance | ACC-1: A2 contradicted by #357 | GENUINE_FIX | task-5 (A2a) |
| 1 | Acceptance | ACC-2: A1b input differs from O1 | GENUINE_FIX | task-5 (A1b) |
| 1 | Acceptance | ACC-3: gate polarity incomplete | GENUINE_FIX | task-5 (A3 a-f) |
| 1 | Acceptance | ACC-4: A4/A1 PASS not falsifiable | GENUINE_FIX | task-5 (A1, A4) |
| 1 | Acceptance | ACC-5: evidence-block gaps | GENUINE_FIX | task-5 (common conditions) |
| 1 | Acceptance | ACC-6: harness absent; A0 scope; stale prompts | plan-polish | fixed-inline (section 8) |
| 1 | Legacy-Contract | GL-1 = SP-2 (plus #357 row omitted) | GENUINE_FIX | task-2 withdrawn; GL-1 row added |
| 1 | Legacy-Contract | GL-2: index-free key passes delta-introduced violations | GENUINE_FIX | moot (task-2 withdrawn) |
| 1 | Legacy-Contract | GL-3: HIGH-6 goal (a) unproven | GENUINE_FIX | task-1 (confirmation); D-432-2 |
| 1 | Legacy-Contract | GL-4: origins, "no retry deleted", end state 2, `attempt` field | plan-polish | fixed-inline (sections 4 and 6); task-3 step 4 |
| 1 | Legacy-Contract | GL-5 = FF-4 | GENUINE_FIX | task-3 step 1 |
| 1 | Legacy-Contract | GL-6: deterministic stop needs a ledger cite | GENUINE_FIX | D-432-1(ii) |
| 1 | Legacy-Contract | GL-7: success-path consumers; AP-7 issue | GENUINE_FIX + PRE_EXISTING_OUT | GL-1 row added; escalate:@owner (I-2) |
| 1 | No-Limits | NL-1: uncapped correction text | plan-polish | fixed-inline (Task 1 note unbounded; Task 2 withdrawn) |
| 1 | No-Limits | NL-2: `{}` from context lost past the 10-message window | GENUINE_FIX | task-5 (history length recorded); task-4 (#431 comment) |
| 1 | No-Limits | NL-3: more calls through #324's caps | GENUINE_FIX | section 1 names the dependency; task-5 (cache vs call recorded) |
| 1 | Consumer/Compat | COMPAT-1 = SP-2 (O3 predates #357) | GENUINE_FIX | task-2 withdrawn; A2a |
| 1 | Consumer/Compat | COMPAT-2: container-level errors defeat the error key | moot | task-2 withdrawn |
| 1 | Consumer/Compat | COMPAT-3: a `{}` now completes a durable reversal claim (`update_character_effects.py:563-568`) instead of releasing it | GENUINE_FIX (disclosure) | D-432-2 disclosure; task-5 (A4 records every reversal answer) |
| 1 | Consumer/Compat | COMPAT-4 = end state 4 | plan-polish | fixed-inline (end state 4) |
| 1 | Consumer/Compat | COMPAT-5 = FF-4 | GENUINE_FIX | task-3 step 1 |
| 1 | Consumer/Compat | Polish: end state 2 before/after; GL-1 bypass | plan-polish | fixed-inline (section 4; Task 1 and GL-1 name the `:2068-2070` clause) |
| 1 | Consumer/Compat | FYI: on `{}`, the unmigrated path (`effects_runtime.py:98-104`) now also runs `update_character_effects` (one more model call); the migrated path now runs the rest lifecycle on a no-change rest (fixes a latent skipped rest) | fyi | recorded |
