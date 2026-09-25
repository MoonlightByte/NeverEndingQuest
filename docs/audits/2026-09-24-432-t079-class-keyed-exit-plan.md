# #432 T079 character writer: class-keyed exit, confirmed no-change answers, supersession

Status: PLAN r6 (2026-09-24), after Part 3 rounds 1-4 (nine seats each; round 3 re-run on r4 after a filesystem interruption; round 4 returned PASS/LGTM from every seat; resolution ledger in section 11). Nothing implemented. Execution needs convergence and the owner's approval (NEQ-REVIEW-13).

## 0. Provenance (captured dynamically; evidence, never authority)

| Item | Value |
|---|---|
| Branch | `fix/432-433-count-keyed-giveups`, created from `origin/main`. r1 6639a6f9, r2 09bfbbed, r3 20679781, r4 e566a175, r5 68a4a35f. Code is unchanged from base; only this plan differs. |
| Base revision | `origin/main` = 7b20bc7d. Ancestor check: `git merge-base --is-ancestor HEAD origin/main` at plan time. |
| #193 epoch | v3.1, `updatedAt` 2026-09-18T18:20:12Z. Re-checked before implementation (NEQ-OPS-03). |
| Provider / model | `openai`. T079, T078 and T051 resolve to `gpt-5.6-luna` with `reasoning_effort: none` (`model_registry.py:390-397`, `:460-477`). Never the legacy GPT-4.1 provider. |
| Platform | WSL2 headless first. The native Windows row is owner-run. |
| Owner assignment | 2026-09-21: "pick a new issue worthy of your brain that doesn't require the LM model". #432 was filed with owner authorization on 2026-09-18. |

Line numbers below are at 7b20bc7d and are re-verified at implementation time.

## 1. Scope

**In scope:** the T079 retry loop in `updates/update_character_info.py::_update_character_info_unlocked` (1444-2571), including its exception handlers, and the empty-delta check `_is_meaningful_character_delta` (1141-1148).

**Not in scope.** Each item is tracked in an issue or in a drafted issue waiting for owner authorization (section 9).

- **#433.** Re-scoped on 2026-09-24; a separate plan will follow.
- **#357 residual.** Covered by row A2a.
- **#241.** The staged travel-sibling preparer passes the removed `structural_reissue` to `classify_effect`. A second-instance comment was posted on 2026-09-24. See section 3.
- **#324.** The T051/T052/T054 bounds and description caps. Confirmed no-change answers now pass through the post-commit validators, which carry those caps; the caps themselves are unchanged (NL-3).
- **#431.** The T079 `history[-10:]` window.
- **#367.** The turn-loop provider count.
- **#375.** The storage processor count.
- **#300.** The legacy effects runtime that owns the effect-reversal entrant.
- **Level-up.** `level_up_manager.py:620` never calls T079.

## 2. Observed failures (NEQ-EVIDENCE-01; artifacts under `agent-room-fleet-kit/local-data/`)

**O1: false failure after a correct "no change" answer.** 2026-09-18, `242-down-scene/marsh-raw-1`, openai gpt-5.6-luna.

- **Pre-state:** Eirik was already at 1/54 HP and alive. The product backup `242-down-scene/game-marsh-raw-1/characters/eirik_hearthwise.backup_update_20260918_235325.json` shows this.
- **Accepted DM action:** the response had exactly one action (`conversation_history.json` index 46):

  ```
  updateCharacterInfo(eirik_hearthwise, "Escaped the quicksand with a successful Athletics check. Remains at 1 hit point; soaked and on unstable floating moss near the deep central water.")
  ```

- **What T079 did:** it answered `{}` three times (`242-down-scene/capture-marsh-raw-1/T079.json`, also `game-marsh-raw-1/debug/character_updates_log.json`).
- **What the code did:** each answer raised `ValueError: T079 returned an empty or unrecognized character delta` (`game_errors.log:1-15`; this is the raise at `:2071`). The loop then logged `Failed to update character eirik_hearthwise after 3 attempts`, and the action handler returned `status=error` (`core/ai/action_handler.py:3845-3853`).
- **What the player saw:**
  1. The correct escape narration (`marsh-raw-1.ndjson` seq 606).
  2. The status "Updating character info..." for 10.8 s (seq 611-702).
  3. The line `That action could not be completed safely. No further actions from that response were applied.` (seq 702).
- **Run setting:** the run used a parity clone with `COMPRESSION_ENABLED = False` (disclosed).

**O2: same error class at combat end.** 2026-09-07, `issue116`.

- `legacy-server.log:3920-3950` shows the request `Following the turn's events: Completes her required turn after all hostile creatures are dead..` for scout_elen. It has no mechanical effect.
- The same `ValueError` was raised three times, then `Final consolidated update failed for scout_elen`.
- The raw answer was not retained, so "it was `{}`" is inferred.
- The caller only logs the failure (`core/managers/combat_manager.py:5734-5741`). It always runs inside a live scope: `run_combat_simulation` holds one (`combat_manager.py:3303-3305`, `live_provider_call.py:340-344`).

**O3: pre-#357 armor poisoning. Superseded on main; not acted on here.**

- **Request:** `Uses one arrow to attack Skeleton_2, dealing 8 piercing damage.` (`legacy-server.log:3840`, `:3890`).
- **Pre-state:** Thane was at 50/50 HP (`:3895`).
- **Answers:**
  - Attempts 1 and 3: ammunition -1.
  - Attempt 2 (`:3906`) also returned `hitPoints: 42`, a misread of the damage Thane dealt.
- **Why every answer failed:** the sheet carried `99 is greater than the maximum of 10 at path: equipment.2.dex_limit`, written earlier in the same run by an older T051 correction (`:3304`, `:3380`, `:3469`). The requested arrow was lost.
- **Why it is superseded:** #357 (948ff048, 2026-09-11, an ancestor of main) added prevention (`core/validation/character_validator.py:2613-2621`) and in-memory T051 recovery before T079 (`update_character_info.py:1519-1549`). #357's live acceptance observed 99 -> null with HP committed in one write.
- **Failed approach (NEQ-OPS-04):** r1's Task 2 (commit around pre-existing violations) duplicated #357's single path. #357 had already rejected that option (`docs/audits/2026-09-11-issue-357-armor-schema-contract-plan.md:482-484`). It was withdrawn in r2.

**Real-data scans (round 1, read-only).**

- Owner checkout: `modules/`, `data/` and root `characters/` contain no `"dex_limit": 99`.
- 137 owner sheets: 3 raw root `additionalProperties` hits (an `inventory` holding only empty currency, purged on every update).
- 3,645 kit sheets: 18 invalid, all armor `dex_limit` 99. There are zero non-armor and zero container-level violations.

## 3. Root cause (NEQ-OPS-02)

**O1/O2 are class (d): a deterministic-vs-agentic disagreement that breaks the coherence rule.**

- The T079 prompt says "Do not include unchanged fields" (`:1610`, `:1627`).
- For a change with no mechanical effect, the only contract-correct answer is `{}`.
- The gate (`:1141-1148`, `:2068-2073`) rejects `{}`, so on the ordinary path the loop gives up after 3 attempts with a false failure.
- **Origin of the rejection:** 715732d5 (the function first appears in 36bd7ed0, which is not an ancestor of main). The goal came from 12ddb548 (HIGH-6, also not an ancestor of main): never report success when a real change produced nothing.

**The staged travel-sibling T079 path is unreachable on main** (CODE-PROVEN; #241 second-instance comment).

- `core/managers/effects_runtime.py:241-247` calls `classify_effect(..., structural_reissue=True)`, but `core/ai/effects_agent.py:220` has had no such parameter since 4b53aace (2026-08-24). Every staged `updateCharacterInfo` sibling therefore raises `TypeError` before T078 or T079 runs.
- The reviewed turn also rejects that sibling. Within-module travel accepts only `updateTime`/`updatePlot` (`main.py:10271-10365`), and cross-module travel accepts only `updatePartyTracker` + `updateTime`.
- If the path were reached, the exception would escape `action_handler.py:3579`, `main.py:5617`, `process_ai_response` (`main.py:6911-6927`, which catches only supersession and JSON errors) and `main.py:9621`, and would stop the engine at `main.py:8035-8037`, then `web_interface.py:5059-5082`.
- r1/r2 claims that the staged loop "reissues forever" and that "Load hangs" cannot happen on main. They are withdrawn.
- #241's future fix must give staged preparation a terminal the player can continue from, with the party at the origin.

**The cancel signal is swallowed** (CODE-PROVEN).

- `:2506` re-raises `LiveProviderSuperseded` only when `commit_guard is not None`. That condition came from 2e6ad1f8 (2026-09-13, the #323 baseline import, "No behavior change in this commit"), and no production caller passes `commit_guard`.
- The swallow itself is an accident of the catch-all from f5e84dd5. `LiveProviderSuperseded` and T079's required-live status both arrived later, in b7f7a863.
- **Today:** on the ordinary path, a superseded T079 is counted as a failed attempt and reissued. The reissue fails immediately at the authority check, twice, and the function returns `False`.
- **What the player sees:** the ordinary path looks the same with or without the swallow. `action_handler.py:3854-3863` catches every `Exception`, including supersession, and `main.py:6682`/`:5006-5013` emits the safe-failure line during the Load (issue I-9). The cost of the swallow is misclassification and wasted reissues. Once #241 makes the staged path reachable, it would also produce an endless loop there.

**B2-vii: the count keys on every failure class** (live-scope entrants).

- Inside a live scope, T079 is a required live task. The transport already reissues transient and empty failures (`live_provider_call.py:46`, `:1691-1698`).
- What reaches the loop's count is:
  - completed-invalid answers;
  - swallowed supersession;
  - `LiveProviderCompletedError`. The #240 contract says deterministic errors return "to the existing caller immediately" (`live_provider_call.py:146-153`), yet the loop retries them. Owner-checkout evidence that retrying this class is futile: `modules/logs/game_errors.log:3354-3452` shows three identical `insufficient_quota` 429s that retries did not heal. That record is dated 2025-09-07 and comes from the old raw-SDK path (`client.chat.completions.create`), before the live transport existed. It shows the class is futile to retry; the changed `LiveProviderCompletedError` path itself is CODE-PROVEN only (CUST3-3, ACC3-5).
- Non-live provider errors reach the loop only from two entrants that run outside a scope:
  - the effect-reversal expiry for unmigrated campaigns (`main.py:8810`, in the main loop before `:9414`; #300);
  - the terminal-mode synchronous startup kickoff (`main.py:8680-8683`, `8713-8717`, then `1165`).
- Their transient class needs a live scope, which is the owning boundary (issue I-8). This plan leaves their handling unchanged.

## 4. Spec-pin (NEQ-REVIEW-04)

**Identities.**

- The character file comes from `get_character_path(name, role)`.
- The ordinary path holds the per-character update lock and the `.effects.lock` lease (`update_character_info.py:1403-1422`, `effects_runtime.py:107-115`). The staged preparation (`effects_runtime.py:238-262`) holds neither.
- The callsite is `T079` (`:111`). Lock order is unchanged.

**Source of truth.** The character sheet JSON on disk. Model answers are proposals (NEQ-CORE-06).

**Commit points (unchanged).**

- Ordinary: `commit_character_sheet` (`:2327`).
- Staged: `apply_staged_character_update` (`effects_runtime.py:283-298`). Unreachable on main (section 3).

**Loop outcomes.** "The call" means the provider-call statement at `:1978-1983`.

| Outcome | What produces it | Policy |
|---|---|---|
| `superseded` | `LiveProviderSuperseded` anywhere in the pre-commit loop | Re-raised by the loop's generic handler on every path |
| `provider_deterministic` | `LiveProviderCompletedError` raised by the call | Logged, then re-raised by the loop's generic handler at once (the envelope and `http_status` stay available to the caller, #240) |
| `bounded_failure` | Any of: a JSON decode error; a non-empty delta with no recognized field; an incomplete delta (`:2093`); critical-field loss (`:2224`); a schema-invalid merged sheet (`:2267`); any other exception from the loop body or the call, including capture/config errors and, unchanged from today, non-live `ProviderCallError` (I-8, #300) | Counted |
| `confirmation` | A `{}` answer whose immediately preceding T079 answer in this update was not `{}` | Not counted (Task 1) |

**Confirmation rule (LEAN3-1).** A `{}` answer is accepted only when the immediately preceding T079 answer in the same update was also `{}`. Any other preceding answer (none, a non-empty delta, or an unparseable reply) triggers the confirmation note instead. The rule reads the answers themselves, not which notes were appended.

**End states** (ordinary path; the staged path is unreachable on main).

| # | End state | Loop result | What the player sees |
|---|---|---|---|
| 1 | Success with a change | Sheet committed; `True` | Narration, and the sheet matches it |
| 2 | Confirmed no change (`{}`, note, `{}`) | The unchanged sheet flows through the existing preparation and commit. The post-commit validators run as for any update. On disk, only differences attributable to normalization or to T051/effects validation appear. | Narration, with no failure line. Startup welcome (web/headless): the welcome completes as APPLIED. |
| 3 | `bounded_failure` at the D-432-1 bound | `False` | Ordinary action: `SAFE_ACTION_FAILURE_MESSAGE` after the narration, and the narrated change is absent from the sheet. Combat end: log only, and the narrated change is absent with no player line (I-1). Time-bound effect reversal: released to pending and re-claimed on the next expiry scan (`update_character_effects.py:525-528`, `:553-558`). Rest-bound reversal (unmigrated rest entrant, `effects_runtime.py:98-104`): released to pending, re-claimed only at the next qualifying rest, with no player line (`:597`; #300 comment). Startup welcome (web/headless): the safe-failure line, then the kickoff is marked failed and the welcome note removed (`main.py:808-845`). Terminal kickoff: its caller's existing handling (I-8). When the last counted failure comes through the JSON or generic handler, the tail's 1 s pause delays this end state by 1 s (LEAN3-3, disclosed). |
| 4 | `provider_deterministic` | Raises `LiveProviderCompletedError` at once | Every caller's existing catch-all gives the same terminals as end state 3: ordinary action (`action_handler.py:3854-3863`, generic line, no provider-specific message, I-10), combat end (`combat_manager.py:5741`, log only, I-1), reversal (`update_character_effects.py:541-547`, released to pending), startup welcome (`main.py:808-845`). |
| 5 | `superseded` | Raises | `action_handler.py:3854-3863` turns it into `status=error`, so the safe-failure line appears during the Load (I-9). `combat_manager.py:5741` logs it and the loop continues. `update_character_effects.py:541-547` releases the claim to pending. Startup welcome (web/headless): the same catch shows and persists the safe-failure line (`main.py:6674` -> `_handle_ordinary_action_failure`, `:4971-5013`), then `:794-795` raises and `:818-820` ends the welcome as SUPERSEDED. The welcome's supersession controls stay open until `main.py:444`, so the triggers are Load, player input (`web_interface.py:2946`) and Exit (`:4377`) (I-9 addendum; CUST4-2, PX4-4, COMPAT4-1). |

**Part 2 pages cited.**

- p5 NEQ-EFFECTS-01
- p8 NEQ-WORLD-04
- p9 NEQ-SAVE-01
- p11 NEQ-PROVIDER-01 (`create_completion` is untouched)
- p12 NEQ-SCHEMA-01/02
- p13 NEQ-ACCEPT-01..03

**README promise.** "an intelligent AI that remembers every decision" (README.md:22) and "Character Sheets" (README.md:233).

## 5. Tasks

**Task 0: rollback point.** The plan-only commits (r1-r5; hashes in section 0) come before any code change.

**Task 1: `{}` is a typed "no change" answer, confirmed once. Fixes O1/O2 (D-432-2 option A).**

1. **The check.** `_is_meaningful_character_delta` (`:1141-1148`) returns `True` for an empty dict. It still returns `False` for a non-dict, and for a non-empty dict with no recognized schema field. Its docstring's word "meaningful" becomes "recognized".
2. **The effects clause.** Keep `declarative_effects and managed_effect_operation` (`:2068-2070`) in one local variable, read at both the gate and the confirmation check (SP-5, SP2 fyi). When it is true, `{}` needs no confirmation, because the engine-owned effect operation is itself the change.
3. **The confirmation.** The loop keeps one local boolean, `previous_answer_was_empty`, initially False (LEAN4-2):
   - When the reply text is read (`:1992`, before the parse at `:2067`), remember `prior = previous_answer_was_empty` and set `previous_answer_was_empty = False`. An unparseable reply therefore leaves it False when the JSON handler takes over. A call that raises before any reply arrives does not touch it.
   - After a successful parse, if the value is exactly `{}`, set `previous_answer_was_empty = True`, then:
     - if `prior` is False: append the note below, advance `attempt` by one (as the three branch sites do), and reissue with `continue`. This is uncounted and skips the tail pause (LEAN4-3, FF4-2).
     - if `prior` is True: accept. Log `info("T079 confirmed no mechanical change for <name>")` and continue through the existing completeness check, preparation and commit, unchanged.

   ```
   Your previous answer was {} (no character-sheet field changes). If the described change alters any field on this sheet (hit points, spell slots, equipment, ammunition, currency, experience, conditions or any other field), return those fields now. Narrative descriptions that no rule tracks, such as being wet or muddy, are not sheet changes. If it changes nothing on the sheet, return {} again.
   ```

   - The note is appended exactly as the existing correction notes are (`messages[-1]["content"] += ...`). No count or length bound applies. The example words avoid "tired", because exhaustion is a tracked condition (PX4-2).
   - R3 check: after the change, the loop body contains exactly four `continue` statements, the three existing branch sites plus this one (GL4-1).
4. **Disclosed limits.**
   - After confirmation, T079 is the only authority on "no mechanical change". The completeness regex (`:1151-1251`) is not a safeguard (I-2).
   - The note lists field types, so it is a leading prompt (LEAN2-3). The added clause about narrative descriptions answers PX3-2. Acceptance treats any post-note change the narration did not claim as FAILED.
   - Worst case on the ordinary path: at most 2 x `bounded_failure_limit` = 6 T079 calls, against today's 3. Every confirmation needs a non-`{}` answer before it, and every non-`{}` failure is counted, so an update sends at most `bounded_failure_limit` notes. Example: `{}` (note), an invalid delta (count 1), `{}` (note), invalid (count 2), `{}` (note), invalid (count 3), exit. When every answer is `{}` the worst case is 4 (LEAN4-1, GL4-1, FF4-1, PX4-1, CUST4-1, COMPAT4-2).
   - Two existing paths already reach a no-change success without this confirmation, and this plan leaves them unchanged: on a migrated campaign with no managed effect operation, `{"temporaryEffects": [...]}` passes the gate and is popped to `{}` (`:2074-2077`); and a lower `experience_points` is dropped (`:1086-1088`) (LEAN3-5; D-432-2; optional issue I-11).

**Task 2: withdrawn in r2** (section 2, O3). The number is kept so that ledger references stay stable.

**Task 3: class-keyed exit (B2-vii; D-432-1).**

- **Step 0 (audit, before code).** Commit the entrant table. Columns: caller, file:line, live scope present?, reachable?, terminal on `False`, terminal on a raised `LiveProviderCompletedError`, terminal on supersession. Rows:
  - `effects_runtime.py:98` and `:130` (via `action_handler.py:3835`);
  - `effects_runtime.py:253` (unreachable: #241);
  - `combat_manager.py:5734` (live: `:3303-3305`);
  - `process_effect_expirations.py:54` (non-live: `main.py:8810`; #300);
  - `process_effect_expirations.py:101` (zero production callers, only `__main__`);
  - `update_character_effects.py:740` (live, through `effects_runtime.py:104`);
  - the terminal-mode kickoff path (non-live: `main.py:8713-8717` -> `1165`);
  - the zero-caller wrappers `updatePlayerInfo`, `updateNPCInfo`, `update_multiple_characters_parallel`, `update_party_parallel` (`:2574-2830`);
  - the startup welcome handback in web/headless mode (live: `_apply_welcome` sets the welcome scope, `main.py:752`; terminals `main.py:797`, `:808-845`) (COMPAT3-2).
- **Step 1.** Add `LiveProviderCompletedError` to the import at `:110` (LEAN4-4). In the loop-level generic handler (`:2505-2507`), before anything is counted, re-raise `LiveProviderCompletedError` after logging `FAILURE: T079 provider refused <name> (deterministic, <http_status>)`. There is no nested `try` around the call. The exception, with its envelope and `http_status`, reaches the caller unchanged, which is the handback shape the #240 contract prescribes and the data I-10 needs (LEAN3-4). Every caller's existing catch-all turns it into the end state 4 terminals.
- **Step 2.** In the same handler, re-raise `LiveProviderSuperseded` unconditionally by dropping `commit_guard is not None and`.
  - The post-commit handlers at `:2451` and `:2469` keep their condition. They run after the primary commit, and raising there would report a committed update as failed.
  - Warrant: #432's class-keyed mandate (supersession is not an unusable answer) plus the A3(e) control arm on main before this hunk lands (LEAN2-6).
- **Step 3.** Replace the counting.
  - The local `max_attempts = 3` (`:1921`) becomes `bounded_failure_limit = 3`: a local constant, with no configuration surface (LEAN3-2, SP3b-1).
  - `bounded_failure_count` starts at 0 and is never reset. It is incremented at exactly five sites (GL3-2): the incomplete-delta branch (`:2115`), the critical-field branch (`:2242`), the schema-invalid branch (`:2269`), the JSON-decode handler (`:2482`), and the generic handler (`:2505`, after the Step 1 and Step 2 re-raises). R3 check: `grep -c "bounded_failure_count += 1" updates/update_character_info.py` returns 5.
  - The loop condition at `:1971` becomes `while structural_reissue or bounded_failure_count < bounded_failure_limit`.
  - The per-site `return False` exits at `:2115`, `:2242` and `:2269` are deleted. Those branches keep their existing notes, if any (the critical-field branch has none and reissues the same request, as today), and their `continue` (CUST4-3).
  - The tail at `:2552-2556` no longer tests anything. It advances the `attempt` ordinal and keeps the existing 1 s pause, which predates the live transport (f5e84dd5). The `while` condition is the only place the bound is checked (SP3-2). The added 1 s before end state 3 is disclosed in section 4.
  - `attempt` stays only as the debug call ordinal (`:2001`, `:2015`).
  - R3 check: after the change, `grep -n "max_attempts" updates/update_character_info.py` returns nothing inside `_update_character_info_unlocked`, and `pyflakes` reports no undefined name.
- **Step 4.** Log lines.
  - The debug line at `:1976` keeps its `STATE_CHANGE: Attempt` prefix and becomes `STATE_CHANGE: Attempt <attempt> (bounded failures <n> of <limit>)` (GL3-3, COMPAT3-3). A3(e) relies on that prefix.
  - The terminal line at `:2569` becomes `FAILURE: T079 answers stayed invalid for <name> (<n> bounded failures)`.

**Task 4: documentation.**

- `docs/architecture/provider-routing.md`: leave `:54` (the dated #323 delta about Gemini `usage`) unchanged. Add a dated "#432 T079 exit delta (2026-09-24)" section, following the file's dated-delta convention, that states the class-keyed exit, the deterministic re-raise and the confirmed `{}` contract (CUST3-1).
- `docs/architecture/save-load-reset-lifecycle.md`: leave `:197-199` unchanged; that sentence is about `safe_json_dump` callers and stays true. Add a dated "#432 T079 exit delta" note, following the file's convention: unguarded T079 callers now propagate pre-commit supersession out of the loop; post-commit validator supersession (`:2451`, `:2469`) is still swallowed when unguarded; the #323 guarded text at `:33-40` is unchanged. R3 check: `grep -c "unguarded callers keep their existing behavior" docs/architecture/save-load-reset-lifecycle.md` still returns 1 (GL3-1, COMPAT3-1, NL3-2).
- `docs/architecture/travel-transitions.md`: no change. Its staged-sibling flow is unreachable on main until #241 is fixed, and this plan does not change that terminal (CUST2-1).
- #193 Part 5: append D-432-1..3 once ruled (NEQ-LEDGER-01).
- Issue comments after landing:
  - #432 and #324: landed scope.
  - #431: a confirmed `{}` is now committed, which interacts with the history window (NL-2).
  - #357: the A2a result.
  - #300: the reversal entrant's handling (the round-3 rest-reversal comment is already posted).

**Task 5: acceptance (section 8).** Serial, one operation at a time.

## 6. GL-1 Behavioral Contract

Dispositions use GL-1 tokens.

| Changed element | Origin | Goals | Disposition |
|---|---|---|---|
| `{}` rejection (`:1143-1144`, raise `:2068-2073`) | 715732d5 (first in 36bd7ed0, not on main, no issue); goal from 12ddb548 (HIGH-6, not on main); engine-effect exemption 3525150b | (a) never report success when a real change produced nothing; (b) reject dicts with only unknown keys; (c) no silent no-op on Gemini narration | (a) RETIRED in part (D-432-2): one typed confirmation, after which T079 is the authority. (b) PRESERVED (`:1146-1148`); proving check: `grep -n "any(field in properties for field in updates)"` still hits. (c) PRESERVED: narration fails `json.loads` or yields unknown keys; the schema-None guard at `:1952-1965` is unchanged; proving check: `grep -n 'MODEL_PROVIDER == "gemini" and char_update_config.get("response_schema") is None'` still hits. |
| Single `attempt <= max_attempts` budget (`:1921-1922`, `:1971`, `:2115`, `:2242`, `:2269`, `:2552-2556`) | f5e84dd5 (2025-05-31; moved in 2c472143). Per-site exits: incomplete-delta exit 715732d5 (`:2116-2120`); schema-invalid exit message f5e84dd5 (moved in 2c472143); critical-field exit c4097669 (2025-06-13, "Fix character spell data corruption and add spell slot tracking"; goal: never commit critical-field or spell loss, PRESERVED because the branch still refuses to commit and now counts); b7f7a863 added only `and not structural_reissue` (GL3-6, GL4-2). Deleted log lines: the three `FAILURE: Max attempts reached ...` strings at `:2117`, `:2243`, `:2270`; a repo grep finds no consumer | Every update terminates and returns; the reversal caller relies on the return | PRESERVED for `bounded_failure` (D-432-1(i)); proving checks: A3(f) and the Step 3 R3 greps. RETIRED for `LiveProviderCompletedError` retries (D-432-1(ii); #240 contract; the class is observed futile to retry on the old 2025-09-07 raw-SDK path, and the changed path is CODE-PROVEN). RETIRED for supersession counting (D-432-1(iii)). |
| `structural_reissue` bypass (`:1971` and the exits) | b7f7a863; `commit_guard` wiring at `:1429/:1438` from 2e6ad1f8 with zero production callers | A required staged sibling is fixed before movement | PRESERVED for `bounded_failure` by the loop condition (Step 3); proving check: `grep -n "while structural_reissue or bounded_failure_count < bounded_failure_limit"` hits once. No acceptance check is possible: the staged path is unreachable on main (#241). |
| Supersession re-raise condition (`:2506`) | 2e6ad1f8 (#323 baseline, "No behavior change") | Re-raise for the #323 guarded caller | RETIRED for unguarded T079 callers (D-432-1(iii)); proving check: A3(e). `save-load-reset-lifecycle.md:197-199` concerns `safe_json_dump` and is unchanged (Task 4). |
| #357 pre-gate armor recovery (`:1519-1549`) | 948ff048 (#357; D-357-1..4) | Recover damaged armor through T051 in one atomic write | UNCHANGED |
| Schema-invalid branch and correction notes (`:2267-2288`) | f5e84dd5; notes 31f5e8db | Never commit an invalid sheet; give actionable feedback | UNCHANGED except that it counts as `bounded_failure` |
| Completeness regex (`:1151-1259`) | 715732d5 lineage | Stop partial application of coupled changes | UNCHANGED; no longer called a `{}` safeguard (I-2) |
| Success consumers of a confirmed no-change: `effects_runtime.py:137-147` (rest lifecycle, keyed on prose) and `:101-104`; reversal claim completion at `update_character_effects.py:563-568` (COMPAT-3) | 3525150b lineage | Run the lifecycle after a successful update; complete a reversal claim on success | PRESERVED (they run on every success); proving check: A4. The prose keying is issue I-2. The reversal-claim effect of a wrong confirmed `{}` is disclosed in D-432-2. |

Removed retry patterns, listed as the r1 audit requires: `LiveProviderCompletedError` retries, and supersession reissues.

## 7. FS-1

| Hit | Exhaustion terminal | Class |
|---|---|---|
| `bounded_failure_count < bounded_failure_limit` (ordinary) | End state 3 | TERMINATES for the `bounded_failure` class; legal only with D-432-1(i). Non-live `ProviderCallError` is included, unchanged from today: CONTINUES at the reversal entrant (pending/resume), TERMINATES at the terminal kickoff (I-8). |
| `provider_deterministic` (N=1, re-raised) | End state 4 | TERMINATES; legal only with D-432-1(ii), for the class as coded (section 9) |
| Confirmation (one note per non-`{}`-preceded `{}`, then acceptance; at most `bounded_failure_limit` notes per update) | End state 2, or end state 3 through the count | CONTINUES (bounded: at most 2 x `bounded_failure_limit` calls) |
| `time.sleep(1)` in the tail (`:2554`) | Reissue; after the final counted failure from a handler, the loop exits 1 s later | CONTINUES; the final-iteration delay before end state 3 is disclosed (LEAN3-3, FF3-3) |
| Staged-path unbounded `bounded_failure` | Reissue with a correction note | Unreachable on main (#241). The notes grow the request without trimming; a context-length 4xx would become `provider_deterministic`. Split: I-4. |
| `_fire_primary_with_retry(max_attempts=3)` for non-live empties (`multi_model_capture.py:350-377`) | `ProviderEmptyResponse` becomes `bounded_failure` | Inherited. CONTINUES at the reversal entrant; TERMINATES at the kickoff (I-8). |
| OpenAI SDK default `max_retries=2` on the non-live path (`utils/openai_client.py:86-89`; zeroed only with a timeout, `api_client.py:800-801`) | `ProviderCallError` becomes `bounded_failure` | Inherited; flagged, not added. This non-live retry stack parallels the live transport's reissue and is owned by I-8 and #300 (SP3b-2) |
| `.effects.lock` 30 s (`update_character_info.py:1412-1422`; `effects_runtime.py:109-115`, `:283-287`) | Busy turned into a refusal | Inherited B2-ii; #324 comment, I-3 |

## 8. Acceptance (NEQ-ACCEPT-01..03; evidence block NEQ-EVIDENCE-04 on every row)

**Common conditions**

- **Harness and driver.** Headless, real OpenAI, current bindings. Driver: `run_headless.py serve --game-dir`, following the kit's `242-down-scene/build_combat.py` / `drive_combat.py` pattern (the harness named in #193 p13 does not exist on main).
- **Fixtures.** Built fresh, with `prompts/` and `schemas/` refreshed from the checkout. Record the hash of every prompt file.
- **Inline prompt text.** The T079 prompt and the note are inline code, so for each call record the parsed note text and the capture's `source_revision`.
- **Compression.** `COMPRESSION_ENABLED` stays at its default (True).
- **Where T079 answers come from.** The capture directory.
- **Per-call record (item 1).** Every T078, T079, T051, T052 and T054 call, including the staged advisory validator if reached. For each call:
  - `response.model`;
  - latency relative to the player input;
  - capture line;
  - whether each post-commit validator hit its cache or made a model call (NL-3).

  For T079 also record:
  - the number of history messages sent (from the capture's `input.messages`);
  - for every `{}` answer, whether the message that sets the change's context is among the sent messages, judged against the transcript (NL-2, NL2-1, NL3-1).

- **Item 4 grep, per row.**

  ```
  T079 confirmed no mechanical change
  T079 provider refused
  T079 answers stayed invalid
  could not be completed safely
  Final consolidated update failed
  blocked_conflict
  "status": "fallback"
  LiveProviderSuperseded
  ```

  Zero hits are stated as zero.

- **Status duration.** Record the "Updating character info..." status duration per update.

**Verdict rules (every row)**

- An ACCEPTED `{}` on a change string with a mechanical effect is FAILED.
- A post-note answer that changes a field the change string does not claim is FAILED.
- A `condition_affected` entry added by a post-note answer, absent from the pre-state, and outside `schemas/char_schema.json` `properties.condition.enum` (excluding `none`) is FAILED, even if the change string mentions it; for example "soaked" (PX3-2, ACC4-5).
- A first `{}` followed, after the note, by a correct non-empty answer is A3(g) PASSED.

**Review**

- The Player-Experience seat reviews every row's transcript.
- Five narration claims are spot-checked against disk.
- A3 counts only runs on the branch revision.

**Rows**

- **A0. Real-save scan (informational; no verdict consumes it since Task 2 was withdrawn).** Run this literal command, read-only:

  ```
  python3 <kit>/432-433/scan_sheets.py schemas/char_schema.json <root>
  ```

  Roots: `/mnt/c/dungeon_master_v1/modules`, `/mnt/c/dungeon_master_v1/characters`, `/mnt/c/agent-room-fleet-kit/local-data`. The script is the Consumer/Compat seat's round-1 scanner, copied into the kit folder before use. Report counts per class.

- **A1. No-change answer at the play layer (O1).**
  - Setup: branch; the Boggard Marsh fixture from `build_combat.py`, whose HP-1 edit is disclosed; the marsh-raw-1 command sequence. The driver answers the first two main-prompt roll requests with the literal strings "I rolled 6 on the d20." and then "I rolled 17 on the d20." (O1's `conversation_history.json` entries 43 and 45). `drive_combat.py` answers roll prompts randomly today (`:43`, `:103-118`), so the driver change is recorded (ACC3-4).
  - PASSED when all of these hold:
    - the DM emits an `updateCharacterInfo` with no mechanical effect;
    - T079 answers `{}`, the note is sent, and T079 answers `{}` again;
    - the log line is present;
    - on the full-sheet diff, every differing path is tied to a named normalizer or T051/effects-validator log line;
    - the transcript has no `could not be completed safely` line.
  - A post-note non-empty answer is judged by the verdict rules. If it is correct, A1 is NOT-REACHED for end state 2 and A3(g) PASSED is recorded (ACC4-4).
  - NOT-REACHED if no such action occurs. A1 is also subject to D-432-3, because end state 2 is the O1 fix itself.

- **A1b. Updater-layer diagnostic. Never cited as PASSED.**
  - Setup, in a fresh fixture directory:
    - Eirik's pre-state = the product backup (1/54, disclosed);
    - `conversation_history.json` = the `game-marsh-raw-1` file truncated before index 46;
    - record the effects-migration state and `party_tracker.json`.
  - Call `update_character_with_effects("eirik_hearthwise", <O1 string>, party, action_context=<O1 capture entry 0's "Accepted action context" message>)`.
  - Diff the first parsed request against O1 capture entry 0. Record both answers, the return value and the sheet diff.
  - Disclosed: the diff is never empty. A1b sends 10 history messages (on-disk entries 36-45) where O1 sent 9 (entries 37-45), and O1's last one carried a call-time party-stats note that the on-disk entry 45 does not hold. A1b's answers are therefore not strictly comparable to O1's (ACC2-6 fyi, NL3-1, NL4-1).

- **A2a. O3 forensics on main 7b20bc7d. Informs #357; not acceptance of this plan.**
  - Setup: restore `issue116/clean-reset-fixture/saved_games/save_20260907_125556` only through the product restore path (`run_headless.py:382-407`) into a fresh game directory with refreshed prompts.
  - Before the command, record Kira's on-disk `dex_limit` values.
  - Issue one ordinary command that changes Kira's sheet, for example "Kira takes a short rest and binds her wounds".
  - Record the T051 pre-check, T051's answers, T079's answers and the outcome.
  - If the DM emits no update for Kira, the row is NOT-REACHED.
  - If the change commits with the armor repaired, record that on #357.
  - If T051 exhausts and T079 is refused: escalate:@owner under #357.

- **A2b. Parity.** The A2a scenario on the branch. Every T079 call is judged by the verdict rules and A4.

- **A3. Gate polarity.** Each item is PASSED if reached on the branch. Otherwise it is NOT-REACHED, stated per item. No synthetic probe is added. D-432-3 applies item by item to A1 and to each of (a), (e), (f) and (g) that ends NOT-REACHED, and merge waits for every such ruling (ACC3-2, ACC4-4).
  - (a) `provider_deterministic`: one `T079 provider refused` line, then end state 4. The `FAILURE: Exception in character update` line (`action_handler.py:3854-3855`) carries `LiveProviderCompletedError` with its `http_status` (`live_provider_call.py:158-163`). There is no `action_handler.py:3845` line and no second T079 call for that update. The game accepts the next input (ACC4-3).
  - (b) The completeness INCOMPLETE correction still fires.
  - (c) Staged travel sibling: NOT-REACHED (unreachable on main, #241). Not attempted.
  - (d) Combat-end entrant: NOT-REACHED unless the fixture holds an active legacy-mode encounter, and none is named. New encounters are built agentic (`combat_builder.py:589-593`), and `combat_manager.py:5734` runs only for a legacy-mode encounter created earlier (`combat_state.py:621-624`). O2's class is accepted at the shared loop through A1 (ACC3-3). If a legacy encounter is reached, PASSED when all of these hold: `{}`, the note, `{}`; the confirmed log line; no `Final consolidated update failed` line (`combat_manager.py:5735-5736`).
  - (e) Supersession on the ordinary path. Trigger: send the restore command while T079 is in flight.
    - Driver: `serve --debug`. The driver sends `list_saves` then `restore` when it sees the NDJSON debug event `STATE_CHANGE: Attempt`, and records that event's seq and timestamp.
    - In-flight proof (ACC3-1, ACC4-1): the traceback of the `FAILURE: Exception in character update` line (`action_handler.py:3854`, logged with `exception=e`) runs through `_update_character_info_unlocked` at the T079 `capture_and_fanout` statement into `call_live_provider`, and this update has no T079 capture entry for that call. A supersession from any other origin (for example `classify_effect`) is NOT-REACHED, and so is a restore that lands after the update returned.
    - Control arm on main, run before Step 2 lands (the AP-5 observation): the same traceback test on the first `FAILURE: Error during update (attempt 1)` line carrying `LiveProviderSuperseded`. It then shows that line repeated, then `FAILURE: Failed to update character <name> after 3 attempts` in `modules/logs/game_errors.log`.
    - Branch arm PASSED when all of these hold:
      - the in-flight proof;
      - one `FAILURE: Exception in character update` line carrying `LiveProviderSuperseded` (`action_handler.py:3854-3855`);
      - in `modules/logs/game_errors.log`, no `FAILURE: Error during update (attempt`, no `FAILURE: Failed to update character <name> after` and no `FAILURE: T079 answers stayed invalid` line for that update. The `print("ERROR: Failed to update character info:", ...)` at `action_handler.py:3857` is expected on this path and is not a failure signal (COMPAT4-3);
      - the Load completes and the transcript shows the restore;
      - `ps --ppid <serve pid>` after the result shows no live-provider child.
    - The safe-failure line during the Load is expected on both arms (I-9) and is recorded, not judged.
    - The staged arm is NOT-REACHED (unreachable on main, #241).
  - (f) `bounded_failure` at the bound: exactly three counted-failure lines for the update, then one `FAILURE: T079 answers stayed invalid for <name> (3 bounded failures)`, then the `action_handler.py:3845` line; end state 3; and the game accepts the next input (ACC4-2).
  - (g) Confirmation gate: the note appears verbatim as the suffix of the last `input.messages` entry (`Changes to make: ...`) of the next T079 request, and the game continues.

- **A4. Parity across A1, A2b and A3.**
  - Every T079 call's change string and sheet diff are shown side by side and judged by Claude.
  - Zero accepted `{}` answers on mechanical changes.
  - Zero non-empty -> empty transitions.
  - Unclaimed changes are FAILED.
  - Any effect-reversal T079 call is tagged with its claim record before and after (`update_character_effects.py:563-568`). NOT-REACHED if none occur.

- **Hygiene.**
  - ASCII only in touched Python.
  - `pyflakes` undefined-name check on changed files.
  - No-Limits and Single-Path sentinel greps over the diff, pasted raw.
  - The local untracked test `/mnt/c/dungeon_master_v1/tests/test_t079_same_character_serialization.py:13` asserts the old `{}` rejection. It is updated locally (D-9: not tracked).

## 9. Owner decisions (execution blocked until ruled, NEQ-REVIEW-09)

**D-432-1: T079 class-keyed exit.** A new ledger class, like D-VR-15 and D-VS-12. Ratify all three:

- **(i) Bound.** On the ordinary path, 3 `bounded_failure` outcomes in total end the update with `False`. The terminals are exactly end state 3.
  - Non-live provider errors stay in this bound, as today. Their transient class belongs to a live scope for the terminal kickoff (I-8) and to #300 for the reversal entrant, which already resumes.
  - This departs from #432's literal "transient failures reissue" only for those two non-live entrants. Inside a live scope, the transport already reissues.
  - The same two entrants also keep today's handling of deterministic refusals. A quota 429 or other 4xx there still spends the bound on futile identical tries, because the #240 handback (`LiveProviderCompletedError`) exists only inside a live scope. Giving those entrants a live scope (I-8, #300) collapses this asymmetry (SP3-1).
- **(ii) Deterministic stop.** `LiveProviderCompletedError` ends the update at once. The loop logs it and re-raises it with its envelope intact. The class is exactly what the live transport hands back as deterministic (`live_provider_call.py:781-813`):
  - HTTP 4xx other than 408/409/429;
  - quota codes;
  - any structured stream error code other than `server_error` and `rate_limit_exceeded`, including `stream_ended`, which a Responses stream that ends with no terminal event carries (`api_client.py:576-578`, `:669-681`);
  - any error type the classifier does not recognize and that has no status (FF3-2).

  Whether `stream_ended` should instead be reissued is issue I-7. Until then this stop applies to it. For T079 today that means 1 attempt instead of 3 on an unobserved class.

  In player terms: a cut-off stream that today's retry might heal would instead show the safe-failure line and drop the response's later actions (PX3-2). The player sees the generic line, not the provider's own message such as "add credit" (I-10).

  Evidence note: the owner-checkout quota record (`modules/logs/game_errors.log:3354-3452`) is dated 2025-09-07 and comes from the old raw-SDK path. It shows that retrying the class is futile; it does not exercise the changed path (CUST3-3, ACC3-5).
- **(iii) Supersession.** Pre-commit supersession always propagates out of the T079 loop. Post-commit validator supersession (`:2451`, `:2469`) is still swallowed on unguarded callers, unchanged (GL3-4). The ordinary action handler still turns a propagated supersession into the safe-failure line during the Load (I-9).

Recommendation: ratify. The alternative, unbounded correction on the ordinary path, risks an unwinnable loop (the #194 scar).

**D-432-2: the no-change answer.** The trade in player terms: today a correct "nothing changed" produces a visible false failure (O1, OBSERVED). After the change, a wrong "nothing changed" would leave a narrated change off the sheet with no line shown. That second case is unobserved: across 7 debug logs and 65 T079 answers, the only `{}` answers were O1's correct ones.

- **(A) Confirm once, then accept** (Task 1, as written).
  - Cost: one extra T079 call per no-change request, about 2-3 s (O1 measured 1.8-2.8 s per call). The worst case is 6 calls (confirmations alternating with invalid answers) instead of today's 3, which is about 11-17 s of "Updating character info..." before the same failure line. When every answer is `{}` the worst case is 4.
  - Coverage is partial. The check tests key presence only. `{"hitPoints": <current value>}` for "takes 8 damage" passes today and would still pass.
  - The note lists field types, so a second answer may write a change that no narration explained. Acceptance fails any such change, and the note tells the model that narrative descriptions are not sheet changes (PX3-1(a), PX3-2).
- **(B) Accept the first `{}`.** This retires goal (a) entirely by owner ruling and costs no extra calls.
- **Under both options:**
  - An accepted `{}` runs the existing success consumers. For change text that mentions a rest without taking one ("considers a long rest but presses on"), the prose-keyed rest clear runs for the whole party (`effects_runtime.py:137-147`, `:415`; I-2). Today that input shows the false-failure line instead (PX3-1(b)).
  - On an unmigrated campaign, an accepted `{}` also runs `update_character_effects` (`effects_runtime.py:101-104`). Its phrase check (`update_character_effects.py:720`) matches "take a rest" even in "doesn't take a rest", so it can claim and reverse that character's rest-bound effects, ending a buff with no rest taken and no line shown (PX4-3(a); I-2 addendum).
  - For an effect reversal, an accepted wrong `{}` completes the reversal claim. The completed reversal removes its tracker entry (`update_character_effects.py:520`), so the expired effect stays on the sheet permanently, with nothing left to reverse it (COMPAT-3, PX4-3(b)).
  - Two other no-change paths already succeed without any confirmation, and this plan leaves them unchanged: a `temporaryEffects`-only answer on a migrated campaign with no managed operation is popped to `{}` (`:2074-2077`), and a lower `experience_points` is dropped (`:1086-1088`). The owner may track them as optional issue I-11 (LEAN3-5).
- **Today's side of the trade:** the false failure also drops every later action in the same response (`main.py:6671`) (PX3-1(c)).
- Recommendation: (A).

**D-432-3: gate-polarity fallback (ACC2-4, ACC3-2, ACC4-4).** For A1 and for each of A3(a), (e), (f) and (g) that ends NOT-REACHED, item by item, the owner rules on one of:

- close that item on CODE-PROVEN evidence. For (a) this may cite the owner-checkout quota record (`modules/logs/game_errors.log:3354-3452`), noting that it is from 2025-09-07 on the old raw-SDK path and shows only that retrying the class is futile;
- authorize one isolated controlled-error check for that item in the D-NPC-PARTY-5 form.

Merge waits for every such ruling.

**Issue authorizations.** New public issues need the owner (standing rule). The bodies are drafted in `agent-room-fleet-kit/local-data/432-433/issue-drafts-I1-I6.md`, plus the r3 additions below. File each one, yes or no:

- **I-1:** combat-end update failure is log-only (PX-1/FF-3).
- **I-2:** T079 completeness and the rest lifecycle infer from prose (AP-7). Includes the negated-mention example "wishes for a long rest but presses on" (CUST-3/GL-7/CUST2-3).
- **I-3:** `.effects.lock` 30 s busy-refusal in `effects_runtime.py` (FF-6).
- **I-4:** `structural_reissue` termination fork plus the dormant `commit_guard` mode. Includes the post-commit fork: `:2484`/`:2509` return True only in guarded mode; on the ordinary path, a post-save diagnostics exception (`:2380-2382`) is counted and T079 is reissued after the commit (SP-3/SP2-2/GL2-4). The staged half is unreachable on main until #241 (CUST3-2).
- **I-5:** two provider-error classifiers with divergent verdicts (SP-4).
- **I-6:** same-character staged siblings return `blocked_conflict` (FF-7/COMPAT2-4). Moot until #241.
- **I-7 (new, r3):** the live `_error_disposition` falls through to `deterministic` for unrecognized errors, including `stream_ended`. A truncated stream is a lost response and may belong in `retryable_transport` (FF2-1).
- **I-8 (new, r3):** the terminal-mode startup kickoff runs provider calls outside any live scope (`main.py:8680-8683`, `8713-8717` -> `1165`), so there is no transport reissue and no supersession (FF2-2). Addenda: deterministic refusals outside a scope are also retried to the caller's bound (SP3-1), and the non-live retry stack (SDK `max_retries`, `_fire_primary_with_retry`) parallels the live transport and would become dead code once the entrants run live (SP3b-2).
- **I-9 (new, r3):** `action_handler.py:3854` catches supersession as an action failure, so the safe-failure line appears between "Load accepted" and the restore, and `main.py:6655` is dead for character updates (PX2-2/COMPAT2-2/FF2-4).
- **I-10 (new, r3):** the T079 deterministic stop shows the generic line. The provider's own message (`provider_errors.py:71-80`, for example "add credit") never reaches the player (PX2-3).

- **I-11 (optional, r5):** T079 deltas that reduce to no change commit as success without the no-change confirmation (the `temporaryEffects` pop at `:2074-2077`; the XP-decrease drop at `:1086-1088`). Expected: the same handling as a literal `{}` (LEAN3-5).
- **I-12 (new, r6):** the T078 classifier `classify_effect` (`core/ai/effects_agent.py:220-275`) catches both `LiveProviderCompletedError` and `LiveProviderSuperseded` at `:260`, retries them, then re-wraps them as `EffectsAgentContractError` (`:275`), which discards the envelope and `http_status`. T078 runs just before T079 in the same entrant (`effects_runtime.py:120` -> `:130`). After #432, one update would treat these two errors differently in its two stages, and I-10 could never show a provider message for a refusal during T078. Direction: the same class-keyed exit as this plan's Steps 1 and 2 (SP4-1).
- **Addenda (r6):** I-2 also covers the unmigrated rest-phrase check at `updates/update_character_effects.py:720`, which matches negated mentions such as "doesn't take a rest" (PX4-3). I-9 also covers the startup welcome handback: player input, Exit or Load during the welcome's T079 shows and persists the safe-failure line before the welcome ends as SUPERSEDED (COMPAT4-1, PX4-4). The I-8 draft body now carries the non-live retry stack text (SP4-2).

Two findings went to existing issues instead of new ones: the staged `classify_effect` TypeError to #241, and the silent rest-bound reversal wait to #300 (comments posted 2026-09-24).

## 10. Tracked follow-ups

- #433: separate plan.
- #357: the A2a result.
- #241: the staged path.
- #324, #431, #367, #300.
- I-1..I-12: `escalate:@owner` until filed (I-11 optional).

## 11. Resolution ledger

**Round 1** (nine seats on r1, 6639a6f9)

- Verdicts: BLOCKING from every seat except No-Limits (PASS).
- 44 findings, all resolved in r2 (09bfbbed). The r2 ledger rows are preserved verbatim in the git history of this file (`git show 09bfbbed:docs/audits/2026-09-24-432-t079-class-keyed-exit-plan.md`).
- Summary:
  - Task 2 withdrawn (SP-2, CUST-1, LEAN-1, GL-1, COMPAT-1, ACC-1).
  - Transient branch removed (SP-1, FF-2, LEAN-2).
  - Confirmation step (GL-3, CUST-3, LEAN-5, PX-3).
  - Supersession re-raise (FF-1).
  - Classifier boundary (CUST-4, FF-4, LEAN-4, GL-5, COMPAT-5).
  - Acceptance rows (ACC-1..6, PX-2, PX-6, NL-2, NL-3).
  - Issue drafts I-1..I-6.

**Round 2** (nine seats on r2, 09bfbbed)

- PASS: No-Limits, Single-Path, Legacy-Contract (LGTM).
- BLOCKING: Custodian, Fail-Forward, Acceptance, Consumer/Compat, Player-Experience, Leanness.
- Every round-1 row was re-verified in code: RESOLVED, except the rows reopened below.

| Round | Seat | Finding | Reconciliation (NEQ-REVIEW-14) | Resolution |
|---|---|---|---|---|
| 2 | Player-Experience | PX2-1: staged path raises TypeError before T079; end state 4 mis-traced (engine stop) | GENUINE_FIX (plan text) + PRE_EXISTING_OUT | fixed: sections 3, 4, 6, 7; A3(c)/(e) staged NOT-REACHABLE; Task 4 travel doc unchanged; #241 comment (issue-#241) |
| 2 | Consumer/Compat | COMPAT2-1 = PX2-1 | GENUINE_FIX | as above |
| 2 | Custodian | CUST2-1 = PX2-1 (also GL-1 row 3, FS-1 staged, I-4/I-6 assumptions) | GENUINE_FIX | as above; I-4/I-6 note "moot until #241" |
| 2 | Fail-Forward | FF2-3 = PX2-1; end state 6 staged cite | GENUINE_FIX | as above; staged end state removed |
| 2 | Leanness | LEAN2-1: loop condition `:1971` still counts calls; confirmation spends it | GENUINE_FIX | task-3 step 3 (condition on `bounded_failure_count`; R3 grep) |
| 2 | Custodian | R-1 = LEAN2-1 | GENUINE_FIX | task-3 step 3 |
| 2 | Leanness | LEAN2-2: goal (a) uncited; coverage partial; offer (B) | GENUINE_FIX (disclosure) | D-432-2 options A/B, partial coverage stated |
| 2 | Leanness | LEAN2-3: the note leads the model | GENUINE_FIX | task-1 disclosure; verdict rule (post-note unclaimed change = FAILED) |
| 2 | Leanness | LEAN2-4: flag lifecycle; staged note growth | plan-polish | fixed-inline (section 4 flag rules; FS-1 staged row) |
| 2 | Leanness | LEAN2-5: Step 1 superseded branch duplicates Step 2 | plan-polish | fixed-inline (Step 1 catches only `LiveProviderCompletedError`) |
| 2 | Leanness | LEAN2-6: Step 0 superseded column; zero-caller `:101`; control arm before Step 2 | GENUINE_FIX | task-3 step 0; A3(e) control arm ordering |
| 2 | Fail-Forward | FF2-1: deterministic class wider than described (`stream_ended`) | GENUINE_FIX (disclosure) + PRE_EXISTING_OUT | D-432-1(ii) states the coded class; escalate:@owner (I-7) |
| 2 | Fail-Forward | FF2-2: terminal kickoff is a second non-live entrant; handback would cut its retries | GENUINE_FIX | `provider_handback` withdrawn (non-live errors unchanged); section 3; escalate:@owner (I-8) |
| 2 | Fail-Forward | FF2-4: ordinary-path supersession shows the safe-failure line | PRE_EXISTING_OUT | end state 5 disclosed; escalate:@owner (I-9) |
| 2 | Fail-Forward | FF2-5: FS-1 gaps; 6-call worst case | GENUINE_FIX | section 7 rows added; D-432-2 discloses the worst case |
| 2 | Custodian | CUST2-2: Step 2 warrant (no player-visible change on the ordinary path) | GENUINE_FIX | section 3 restated; Step 2 warrant = #432 mandate + A3(e) control arm observation |
| 2 | Custodian | CUST2-3: rest lifecycle prose keying widened by Task 1 | PRE_EXISTING_OUT | escalate:@owner (I-2 extended); GL-1 row |
| 2 | Custodian | R-2: non-live entrants other than reversal lose retries | GENUINE_FIX | moot: non-live handling is unchanged in r3 |
| 2 | Custodian | R-3: supersession doc belongs in save-load-reset-lifecycle | plan-polish | task-4 (`:198-199`) |
| 2 | Legacy-Contract | GL2-1: row 4 omits the documented #323 goal; end state 6 caller list | GENUINE_FIX | GL-1 row 4 RETIRED (D-432-1(iii)); end state 5 lists every caller; task-4 doc line |
| 2 | Legacy-Contract | GL2-2 = FF2-1 | GENUINE_FIX | D-432-1(ii) |
| 2 | Legacy-Contract | GL2-3: worst case 2x the bound | GENUINE_FIX (disclosure) | Task 1, D-432-2 |
| 2 | Legacy-Contract | GL2-4: post-commit diagnostics exception reissues T079 after commit | PRE_EXISTING_OUT (HYPOTHESIS reachability) | escalate:@owner (I-4 extended) |
| 2 | Legacy-Contract | Nits: GL tokens; 12ddb548/36bd7ed0 off main; `:1429/:1438`; row 8 cross-ref | plan-polish | fixed-inline (section 6) |
| 2 | Player-Experience | PX2-2 = FF2-4 | PRE_EXISTING_OUT | I-9 |
| 2 | Player-Experience | PX2-3: quota message never reaches the player | PRE_EXISTING_OUT | D-432-1(ii) disclosure; escalate:@owner (I-10) |
| 2 | Player-Experience | PX2-4: D-432-2 in player terms | plan-polish | fixed-inline (D-432-2) |
| 2 | Consumer/Compat | COMPAT2-2 = FF2-4 | PRE_EXISTING_OUT | I-9 |
| 2 | Consumer/Compat | COMPAT2-3: `after` also shaped by #357/T051/validators | GENUINE_FIX | end state 2; A1 attribution rule |
| 2 | Consumer/Compat | COMPAT2-4: I-6 addition; reversal re-claim loop ends on confirmed `{}` | fyi | I-6 draft note; recorded |
| 2 | Acceptance | ACC2-1: FAILED rule contradicts Task 1; confirmation gate untested | GENUINE_FIX | verdict rules; A3(g) |
| 2 | Acceptance | ACC2-2: A3 could pass on main (A2a) | GENUINE_FIX | "A3 counts only branch runs"; A2b |
| 2 | Acceptance | ACC2-3: A3(e) ordinary arm passes on unfixed code | GENUINE_FIX | A3(e) PASS criteria, in-flight proof, orphan check, control arm expectations |
| 2 | Acceptance | ACC2-4: no route if gate-polarity rows are NOT-REACHED | GENUINE_FIX | D-432-3 |
| 2 | Acceptance | ACC2-5: evidence block gaps | GENUINE_FIX | common conditions (note text, `source_revision`, item-4 greps, T052/T054, status duration) |
| 2 | Acceptance | ACC2-6: A1b history not pinned | GENUINE_FIX | A1b setup |
| 2 | Acceptance | ACC2-7: unfalsifiable verdicts | GENUINE_FIX | A1 full-diff attribution; A3(d); A4 reversal tagging; NL-2 detail |
| 2 | Acceptance | ACC2-8: A2a details | GENUINE_FIX | A2a setup |
| 2 | Acceptance | A0 literal command; A1 roll pinning | plan-polish | fixed-inline |
| 2 | No-Limits | NL2-1: history-length recording cannot fail as written | plan-polish | fixed-inline (item 1 record) |
| 2 | Single-Path | SP2-1: merge the two handback branches | moot | only one branch remains (Step 1) |
| 2 | Single-Path | SP2-2: amend I-4 with the post-commit fork | PRE_EXISTING_OUT | I-4 extended |
| 2 | Single-Path | SP2-3: cite #300 | plan-polish | fixed-inline (sections 1, 3) |
| 2 | Single-Path | SP2-4: single bound site | GENUINE_FIX | task-3 step 3 |
| 2 | Single-Path | fyi: gate predicate in one local variable | fyi | task-1 item 2 |

**Round 3, first pass** (nine seats dispatched on r3, 20679781; interrupted 2026-09-24 when the WSL `/mnt/c` mount failed with I/O errors). Only Single-Path returned: provisional PASS, no CRITICAL. The other eight seats were stopped with no report.

| Round | Seat | Finding | Reconciliation (NEQ-REVIEW-14) | Resolution |
|---|---|---|---|---|
| 3 | Single-Path | SP3-1: non-live deterministic refusals (quota, 4xx) still get the bound's futile tries; the #240 handback exists only in scope | GENUINE_FIX (disclosure) | D-432-1(i) states the asymmetry and its owners; I-8 draft extended |
| 3 | Single-Path | SP3-2: "checked in one place" is contradicted by the tail at `:2552` | plan-polish | fixed-inline (task-3 step 3: the tail no longer tests) |
| 3 | Single-Path | N1 (not checked, I/O error): other T079 call sites or a shared `LiveProviderCompletedError` handler would make Step 1 a duplicate | verified by controller | `git grep` at 7b20bc7d: one T079 call site (`update_character_info.py:1978`); the only other handler is level-up's own caller boundary (`level_up_manager.py:221`), the per-caller shape the #240 contract prescribes. Not a duplicate. |

**Round 3, re-run** (nine seats on r4, e566a175, reading a Linux-side copy at `/home/loup/review432` to keep load off the `/mnt/c` share; Legacy-Contract ran file-scoped git on `/mnt/c`).

- PASS/LGTM: No-Limits, Single-Path, Player-Experience, Legacy-Contract, Custodian, Consumer/Compat, Fail-Forward.
- BLOCKING: Leanness (LEAN3-1), Acceptance (ACC3-1, ACC3-2).
- Every round-2 row re-verified in code: RESOLVED, except ACC2-3 (continued as ACC3-1) and ACC2-4 (continued as ACC3-2).

| Round | Seat | Finding | Reconciliation (NEQ-REVIEW-14) | Resolution |
|---|---|---|---|---|
| 3 | Leanness | LEAN3-1: flag rules track notes, not answers (6 calls where 4 do; `{}` accepted after a critical-loss answer) | GENUINE_FIX | task-1 (accept `{}` only after a `{}` answer); section 4 rule; worst case 4 |
| 3 | Leanness | LEAN3-2: `BOUND` undefined; `max_attempts` survives at `:1921`, `:1976` | plan-polish | task-3 step 3 (`bounded_failure_limit` local) and step 4 (debug line) |
| 3 | Leanness | LEAN3-3: tail pause adds 1 s before end state 3 | GENUINE_FIX (disclosure) | end state 3; FS-1 sleep row |
| 3 | Leanness | LEAN3-4: nested `try` returning False discards the #240 envelope | GENUINE_FIX | task-3 step 1 (re-raise at the generic handler); end state 4 |
| 3 | Leanness | LEAN3-5: two existing no-change paths bypass confirmation | PRE_EXISTING_OUT | D-432-2 disclosure; task-1 limits; escalate:@owner (I-11, optional) |
| 3 | Acceptance | ACC3-1: A3(e) can pass without the re-raise running (capture timestamp is post-call) | GENUINE_FIX | A3(e) in-flight proof and branch criteria replaced |
| 3 | Acceptance | ACC3-2: D-432-3 fires only when (a) and (f) are both NOT-REACHED | GENUINE_FIX | D-432-3 item by item for (a), (e), (f), (g); A3(f) next-input clause |
| 3 | Acceptance | ACC3-3: A3(d) unreachable from named fixtures; "NOT-REACHABLE" is not a token | GENUINE_FIX | A3(c)/(d) text |
| 3 | Acceptance | ACC3-4: roll example wrong; driver cannot pin rolls | GENUINE_FIX | A1 setup |
| 3 | Acceptance | ACC3-5: quota record predates the live transport | GENUINE_FIX (disclosure) | section 3, GL-1 row 2, D-432-1(ii), D-432-3 |
| 3 | Acceptance | A3(g) wording; A0 has no consumer; A1b not comparable to O1 | plan-polish | fixed-inline (A3(g), A0, A1b) |
| 3 | Fail-Forward | FF3-1: rest-bound reversal waits silently for the next rest | PRE_EXISTING_OUT | end state 3 split; issue-#300 (comment posted) |
| 3 | Fail-Forward | FF3-2: `stream_ended` carries a code | plan-polish | D-432-1(ii) class as coded |
| 3 | Fail-Forward | FF3-3: final-iteration sleep; confirmation reissue path; `:1976` line | plan-polish | FS-1 row; task-1 (`continue`); task-3 step 4 |
| 3 | Fail-Forward | nit: handler catches `Exception`, not `RuntimeError` | plan-polish | fixed-inline (section 3) |
| 3 | Custodian | CUST3-1: Task 4 edits the wrong doc sentences | GENUINE_FIX | task-4 (dated delta sections; R3 grep); GL-1 row 4 |
| 3 | Custodian | CUST3-2: I-4 note missing; section 0 hashes | plan-polish | fixed-inline (I-4 line; section 0; task-0) |
| 3 | Custodian | CUST3-3 = ACC3-5 | GENUINE_FIX (disclosure) | as ACC3-5 |
| 3 | Consumer/Compat | COMPAT3-1 = CUST3-1 | GENUINE_FIX | task-4 |
| 3 | Consumer/Compat | COMPAT3-2: startup welcome handback entrant missing | GENUINE_FIX | task-3 step 0 row; end states 2-5 (verified `main.py:797`, `:808-845`) |
| 3 | Consumer/Compat | COMPAT3-3: `:1976` line; tail sleep; citation `:525-528` | plan-polish | task-3 step 4; end state 3 |
| 3 | Legacy-Contract | GL3-1 = CUST3-1 | GENUINE_FIX | task-4 |
| 3 | Legacy-Contract | GL3-2: increment sites unnamed (an incomplete answer could loop forever) | GENUINE_FIX | task-3 step 3 (five sites; R3 grep = 5) |
| 3 | Legacy-Contract | GL3-3 = COMPAT3-3 | plan-polish | task-3 step 4 |
| 3 | Legacy-Contract | GL3-4: (iii) should say pre-commit | plan-polish | D-432-1(iii) |
| 3 | Legacy-Contract | GL3-5 = LEAN3-3 | GENUINE_FIX (disclosure) | end state 3 |
| 3 | Legacy-Contract | GL3-6: row 2 origins; PRESERVED proving checks | plan-polish | GL-1 rows 2, 3, 4, 8 |
| 3 | Player-Experience | PX3-1: D-432-2 omits three player consequences | GENUINE_FIX (disclosure) | D-432-2 |
| 3 | Player-Experience | PX3-2: the note may turn flavor text into a lasting condition; (ii) in player terms | GENUINE_FIX | task-1 note clause; verdict rule; D-432-1(ii) player terms |
| 3 | Single-Path | SP3b-1 = LEAN3-2 | plan-polish | task-3 step 3 |
| 3 | Single-Path | SP3b-2: non-live retry stack row cites no issue | GENUINE_FIX | FS-1 row; I-8 addendum |
| 3 | Single-Path | SP3b-3: I-4 draft class name; I-8 summary | plan-polish | I-8 line; drafts file updated |
| 3 | No-Limits | NL3-1: A1b history pin off by one; source length not recoverable | GENUINE_FIX | section 8 record; A1b disclosure |
| 3 | No-Limits | NL3-2 = CUST3-1 | GENUINE_FIX | task-4 |

**Round 4** (nine seats on r5, 68a4a35f, Linux-side copy).

- PASS/LGTM from all nine seats: No-Limits, Single-Path, Player-Experience, Custodian, Leanness, Legacy-Contract, Fail-Forward, Consumer/Compat, Acceptance.
- Every round-3 row re-verified in code: RESOLVED (SP3b-2 PARTIAL, completed below).
- The seats labelled every finding plan-polish. Several change implementation steps (the placement of the previous-answer value; advancing `attempt` on the confirmation reissue) or acceptance criteria (A1, A3(a), (e), (f), the condition rule). Under NEQ-REVIEW-11, classification doubt resolves to code-class, so those rows are code-class below, and round 5 re-verifies them.

| Round | Seat | Finding | Class | Resolution |
|---|---|---|---|---|
| 4 | Leanness, Legacy-Contract, Fail-Forward, Player-Experience, Custodian, Consumer/Compat | Worst case is 6 calls (2 x limit), not 4 (LEAN4-1, GL4-1, FF4-1, PX4-1, CUST4-1, COMPAT4-2) | plan-polish (disclosure) | task-1 item 4; D-432-2(A); FS-1 confirmation row |
| 4 | Leanness | LEAN4-2: the previous-answer value must be reset before the parse, or an unparseable reply is skipped | code-class | task-1 item 3 (reset at `:1992`, set after a successful parse) |
| 4 | Leanness, Fail-Forward, Single-Path | LEAN4-3, FF4-2, SP4-3: the confirmation `continue` must advance `attempt` | code-class | task-1 item 3 |
| 4 | Leanness | LEAN4-4: Step 1 needs a new import | plan-polish | task-3 step 1 |
| 4 | Legacy-Contract | GL4-1: the `continue` count R3 check | code-class | task-1 item 3 (four `continue` statements) |
| 4 | Legacy-Contract | GL4-2: critical-field exit origin c4097669; proving checks; deleted log strings | plan-polish | GL-1 rows 1, 2, 3 |
| 4 | Custodian, Player-Experience, Consumer/Compat | CUST4-2, PX4-4, COMPAT4-1: the welcome SUPERSEDED path is `:794-795` -> `:818-820` after the safe-failure line; triggers include input and Exit | plan-polish + PRE_EXISTING_OUT | end state 5; I-9 addendum |
| 4 | Custodian | CUST4-3: the critical-field branch has no note | plan-polish | task-3 step 3 |
| 4 | Player-Experience | PX4-2: drop "tired" from the note (exhaustion is tracked) | code-class (prompt text) | task-1 note |
| 4 | Player-Experience | PX4-3: two more player consequences for D-432-2 | plan-polish (disclosure) + PRE_EXISTING_OUT | D-432-2; I-2 addendum |
| 4 | Single-Path | SP4-1: T078 `classify_effect` retries and re-wraps the #240 handback and supersession | PRE_EXISTING_OUT | escalate:@owner (I-12) |
| 4 | Single-Path | SP4-2: the I-8 draft body lacks the retry-stack text | plan-polish | drafts file; I-8 addendum line |
| 4 | Consumer/Compat | COMPAT4-3: "Failed to update character" also matches the expected print at `action_handler.py:3857` | code-class (test) | A3(e) criteria pinned to `game_errors.log` strings |
| 4 | Acceptance | ACC4-1: in-flight proof keyed on send time; `STATE_CHANGE` names no character | code-class (test) | A3(e) traceback-origin proof; `serve --debug` driver trigger |
| 4 | Acceptance | ACC4-2: A3(f) must identify the bound firing | code-class (test) | A3(f) |
| 4 | Acceptance | ACC4-3: A3(a) must separate re-raise from return False | code-class (test) | A3(a) |
| 4 | Acceptance | ACC4-4: A1 verdict for `{}`, note, correct answer; A1 under D-432-3 | code-class (test) | A1; A3 header; D-432-3 |
| 4 | Acceptance | ACC4-5: name the condition list | code-class (test) | verdict rule (schema `condition.enum`) |
| 4 | No-Limits | NL4-1: A1b sends 10 messages, not 9 | plan-polish | A1b disclosure |
