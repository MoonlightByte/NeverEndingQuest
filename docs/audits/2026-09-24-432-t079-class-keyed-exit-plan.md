# #432 T079 character writer: class-keyed exit, no-change answers, pre-existing violations

Status: PLAN r1 (2026-09-24). Not reviewed. Nothing implemented. Execution needs the #193 Part 3 review to converge and the owner to approve (NEQ-REVIEW-13).

## 0. Provenance (captured dynamically; evidence, never authority)

| Item | Value |
|---|---|
| Branch | `fix/432-433-count-keyed-giveups`, created from `origin/main` |
| Base revision | `origin/main` = 7b20bc7d (ancestor check: `git merge-base --is-ancestor HEAD origin/main` at plan time) |
| #193 epoch | v3.1, `updatedAt` 2026-09-18T18:20:12Z (re-check before implementation, NEQ-OPS-03) |
| Provider / model for acceptance | `openai`; T079 resolves to `gpt-5.6-luna`, `reasoning_effort: none` (`model_config.resolve_callsite_config("T079","openai",0)`). Never the legacy GPT-4.1 provider. |
| Platform | WSL2 headless first; native Windows row owner-run |
| Owner assignment | 2026-09-21: "pick a new issue worthy of your brain that doesn't require the LM model"; #432 filed with owner authorization 2026-09-18 |

Line numbers below are at 7b20bc7d and are re-verified at implementation time.

## 1. Scope

In scope: the T079 retry loop in `updates/update_character_info.py::_update_character_info_unlocked` (1449-2571) and the empty-delta check `_is_meaningful_character_delta` (1141-1148).

Not in scope (each already tracked):
- #433: the player-turn resolver's `max_state_retries`. Its quoted terminal is dormant since b7f7a863. Forensics and re-scope were posted on #433 on 2026-09-24. A separate plan follows.
- #324: the T051/T052/T054 validator bounds and description caps. #432 takes over the T079 default-loop part of #324's "Bounded failure exits" section, and #324 keeps the rest.
- #431: the `history[-10:]` window at 1910 (No-Limits).
- #367: the turn loop's `PROVIDER_MAX_FAILURES`.
- #375: the storage processor's count.
- The level-up path (`level_up_manager.py:620`) calls `prepare_character_delta` with typed input and never calls T079. It is untouched.

## 2. Observed failures (NEQ-EVIDENCE-01: OBSERVED, with artifacts)

All artifacts live under `agent-room-fleet-kit/local-data/`.

**O1: false failure after a correct "no change" answer (2026-09-18, marsh-raw-1, openai gpt-5.6-luna).**
- The DM's accepted response had one action (`game-marsh-raw-1/modules/conversation_history/conversation_history.json` index 46): `updateCharacterInfo(eirik_hearthwise, "Escaped the quicksand with a successful Athletics check. Remains at 1 hit point; soaked and on unstable floating moss near the deep central water.")`. The change has no mechanical effect.
- T079 answered `{}` on all three attempts (`game-marsh-raw-1/debug/character_updates_log.json`: `raw_ai_response: "{}"`, model `gpt-5.6-luna`).
- Each answer raised `ValueError: T079 returned an empty or unrecognized character delta` (`game-marsh-raw-1/modules/logs/game_errors.log:1-15`; traceback line 2071 = the raise at 7b20bc7d:2071).
- Then `Failed to update character eirik_hearthwise after 3 attempts`, and the action handler returned `status=error` (`core/ai/action_handler.py:3845-3853`).
- The player saw the correct escape narration (`marsh-raw-1.ndjson` seq 606), then `That action could not be completed safely. No further actions from that response were applied.` (seq 702; `web/shared_state.py:20`, printed at `main.py:9691-9704`).

**O2: same class at combat end (2026-09-07, issue116 run).**
- `issue116/legacy-server.log:3920-3950`: `FINAL_CHANGE_STRING for scout_elen: Following the turn's events: Completes her required turn after all hostile creatures are dead..` (no mechanical effect).
- The same `ValueError` occurred three times, then `Failed to update character scout_elen after 3 attempts` and `Final consolidated update failed for scout_elen`.
- The raw answer was not retained in that run. The class is the same error; the answer being `{}` is inferred, not proven.
- The combat-end caller only logs the failure (`core/managers/combat_manager.py:5734-5736`).

**O3: a real change lost to a violation the delta did not introduce (2026-09-07, issue116 run).**
- `issue116/legacy-server.log:3898-3918` (ranger_thane): T079 deltas `{"ammunition":[{"name":"Arrows","quantity":-1}]}` and `{"hitPoints":42,"ammunition":[...]}` were each rejected with `99 is greater than the maximum of 10 at path: equipment.2.dex_limit`. The run ended with `Max attempts reached. Reverting changes.`, then `Final consolidated update failed for ranger_thane`. Thane's HP 50 -> 42 and one arrow were silently lost.
- The same class hit scout_kira three times (`:3865-3887`, `equipment.31.dex_limit`).
- The `99` was written earlier in the same run by the T051 AC correction ("Changed dex_limit from null to numeric value 99", `:3304`, `:3380`, `:3469`). The schema allows `integer|null` with a maximum of 10 (`schemas/char_schema.json:356`).
- On 7b20bc7d, T051 checks every proposed armor value against the schema (`core/validation/character_validator.py:2613-2621`), so that writer is fixed.
- Saves written before the fix still carry the value: `issue116/clean-reset-fixture/saved_games/save_20260907_125556/characters/ranger_thane.json` (Studded Leather Armor, 99) and `scout_kira.json` (three armors, 99). Every T079 update for those characters fails on today's main.

Real-data scan of the owner's main checkout (`modules/`, `data/`): zero `"dex_limit": 99` (command in section 8, row A0).

## 3. Root cause (NEQ-OPS-02 classification)

**O1/O2 are class (d), a deterministic-vs-agentic disagreement, and break the COHERENCE RULE.**
- The T079 prompt instructs "Do not include unchanged fields" and "Only include top-level keys ... if a value within them has changed" (`update_character_info.py:1610`, `:1627`).
- For a change with no mechanical effect, the only contract-correct answer is `{}`. The gate rejects exactly that answer (`:1141-1148`, `:2068-2073`).
- The loop cannot be won by construction:
  - On the ordinary path (`structural_reissue=False`) it gives up after 3 answers and reports a false failure.
  - On the staged travel-sibling path (`effects_runtime.py:253`, `prepare_only=True, structural_reissue=True`) it reissues forever. The generic handler (`:2505-2550`) appends no correction note, so the identical request repeats. This is CODE-PROVEN, not observed.

**O3 is class (d) as well.**
- Validation runs on the merged sheet (`prepare_character_delta` `:1101-1103`). A violation that already existed before the delta is blamed on the delta.
- The only escape is for T079 to edit an unrelated field outside the requested change, which the prompt forbids. The correction note ("Please fix the validation error", `:2284`) contradicts the prompt contract.

**B2-vii: the count keys on every class.** The give-up counts every failure, whatever its class:
- completed-invalid answers;
- deterministic provider refusals (`LiveProviderCompletedError`, #240), which are retried two more times on the ordinary path and forever on the staged path;
- transient provider errors. These reach the loop only when T079 runs outside a live turn scope. That happens on the unmigrated-campaign startup path: `main.py:8810` `process_all_effect_expirations()` -> `apply_claimed_effect_reversal(..., update_character_info)`, which runs before the turn loop opens its scope at `main.py:9414`. Inside a live scope, T079 is a required live task, and the transport already reissues transient failures (`utils/capture/live_provider_call.py`).

## 4. Spec-pin (NEQ-REVIEW-04)

- **Identities:** the character file resolved by `get_character_path(name, role)` under the existing per-character update lock and the `.effects.lock` lease (lock order unchanged). T079 is callsite `T079`, registered at `update_character_info.py:111`.
- **Source of truth:** the character sheet JSON on disk. The typed model output is a proposal and never authority (NEQ-CORE-06).
- **Commit points (unchanged):**
  - Ordinary path: `commit_character_sheet` (`:2327`).
  - Staged path: `apply_staged_character_update` (`effects_runtime.py:283-298`), which treats an unchanged sheet as `already_committed`.
- **Failure classes** (typed, never prose; the new loop keys only on these):
  - `completed_invalid`: the model's completed answer is unusable. This covers a JSON decode error, a non-empty delta with no recognized field, an incomplete delta (`:2093`), critical-field loss (`:2224`), a delta-introduced schema violation, a completed empty provider answer (`empty` disposition outside a live scope), and any other local exception. That last group is the existing behavior for our own deterministic defects.
  - `provider_deterministic`: `LiveProviderCompletedError`, or a non-live provider error whose existing typed disposition is `deterministic`.
  - `transient`: a non-live provider error whose typed disposition is `retryable_transport` or `retryable_http`.
  - `superseded`: `LiveProviderSuperseded`, re-raised as today.
- **End states:**
  1. Success with a change. The sheet is committed; returns `True` or a receipt.
  2. Success with no change (`{}`). The unchanged sheet flows through the normal preparation and commit, which is idempotent; returns `True` or a receipt with before equal to after.
  3. Success on a sheet whose pre-existing violations the delta does not add to. Committed, with a WARN naming each pre-existing violation.
  4. `completed_invalid` exhaustion (ordinary path only). Returns `False` with the existing messages; the bound is owner decision D-432-1.
  5. `provider_deterministic`. Returns `False` immediately on every path.
  6. `transient`. Reissues and never ends the operation by count.
  7. `superseded`. Raises, unchanged.
- **Part 2 pages:**
  - p8 NEQ-WORLD-04: the character sheet is player data, and silently stopping consequences is a finding.
  - p12 NEQ-SCHEMA-01: the schema's letter is authority, and existing games keep loading and playing.
  - p12 NEQ-SCHEMA-02: preserve-then-override.
  - p11 NEQ-PROVIDER-01: `create_completion` stays a thin router; this plan does not touch it.
  - p13 NEQ-ACCEPT-01..03: real acceptance, gate polarity, one probe at a time.
- **README promise:** "an intelligent AI that remembers every decision" (README.md:22) and "Character Sheets" (README.md:233). What the narration says happened must be on the sheet. The plan advances this promise and must not degrade it.

## 5. Tasks

**Task 0: rollback point.** Commit this plan alone on the branch before any code change.

**Task 1: `{}` is the typed "no change" answer (fixes O1/O2; D-432-2).**
- `_is_meaningful_character_delta` (`:1141-1148`) returns `True` for an empty dict. It still returns `False` for a non-dict, and for a non-empty dict with no recognized schema field.
- Nothing else in the loop changes. The completeness check (`:2093-2122`) still runs after it. So a request whose explicit, mechanically coupled fields are missing (for example an explicit HP transition answered with `{}`) still gets the existing INCOMPLETE correction, and the safeguard is preserved.
- A `{}` answer then flows through `prepare_character_delta`: merging with `{}` leaves the sheet unchanged, followed by the existing normalization, purge and repair.
- The ordinary path commits that sheet (idempotent, the same work every update already does) and runs the existing post-commit validators. Those validators use their existing cache.
- The staged path returns a receipt whose `after` equals the prepared sheet. `apply_staged_character_update` then records `already_committed` or commits the normalization, exactly as for any receipt.
- Add one `info` line, `T079 reported no mechanical change for <name>`, so the no-op is visible in logs. Rename the helper's docstring meaning from "meaningful" to "recognized".

**Task 2: pre-existing schema violations are not blamed on the delta (fixes O3; D-432-3).**
- Placement: only the T079 loop's schema-invalid branch (`:2267-2288`). `prepare_character_delta` is not touched, so level-up stays unchanged (AP-5).
- On `not is_valid`, compute two error multisets with the schema's `iter_errors`:
  - M = errors of the prepared merged sheet (`updated_data`).
  - P = errors of the pre-merge sheet after the same normalization and purge steps (`normalize_status_and_condition`, `purge_invalid_fields`), so the two are comparable.
- Key each error by `(tuple(error.schema_path), canonical JSON of error.instance)`. The key is independent of array indexes, so a delta that inserts or removes an equipment item does not change it.
- If M is a sub-multiset of P, the delta introduced no violation:
  - apply the same final repair a valid sheet receives (`repair_character_data`);
  - proceed to `prepare_only` return or commit;
  - log one WARN per pre-existing violation (schema path and offending value);
  - record `pre_existing_violations` in the debug entry.
- Otherwise, the correction note names only the errors in M minus P, and the loop counts `completed_invalid` (Task 3).
- The pre-existing value is preserved untouched (NEQ-SCHEMA-02). This plan adds no repair or migration of it.

**Task 3: class-keyed exit (B2-vii; D-432-1).**
- Replace the single `attempt` budget with a count of consecutive `completed_invalid` outcomes (`completed_invalid_count`). Only that count can end the ordinary loop, at the D-432-1 bound.
- `provider_deterministic`:
  - A `LiveProviderCompletedError` returns `False` at once on both paths, with the existing error log. That ends today's two extra identical calls on the ordinary path and the endless reissue on the staged path.
  - For non-live provider errors, the class comes from the existing typed classifier in `utils/capture/live_provider_call.py` (`_primitive_error` -> `disposition`, which is type, status and code based and never prose). It is imported, not copied, so one classifier exists (NEQ-LEDGER-09).
- `transient`: sleep with the existing 1-second pause (`:2554`), reissue, and never increment `completed_invalid_count`.
- `superseded`: unchanged.
- Log text: every exhaustion line names the class and the count, for example `FAILURE: T079 answers stayed invalid for <name> (3 consecutive completed-invalid)`.
- The terminal line at `:2569` changes from "after 3 attempts" to the class wording.
- The staged path keeps its unbounded `completed_invalid` handling (`structural_reissue=True`), which is unchanged behavior. It gains only the `provider_deterministic` stop and the shared classifier.

**Task 4: documentation.**
- `docs/architecture/provider-routing.md`, the T079 paragraph at :54: one sentence on the class-keyed exit and the `{}` no-change contract.
- `docs/KNOWN_ISSUES.md`: note that pre-fix saves may carry `dex_limit` 99 from the old T051 correction, and that T079 now commits around it with a WARN.
- #193 Part 5: append the D-432-1..3 rulings once the owner rules (NEQ-LEDGER-01).
- Comment on #324 and #432 with the landed scope.

**Task 5: acceptance (section 8), serial, one probe at a time.**

## 6. GL-1 Behavioral Contract

| Changed element | Origin | Goals | Disposition |
|---|---|---|---|
| `_is_meaningful_character_delta` rejects `{}` (`:1143-1144`) | 715732d5 (2026-07-17, "feat(multi-model): integrate provider-aware game runtime"), no linked issue. Origin of the empty-dict rejection unknown: finding, escalated as D-432-2 | (a) reject narration purged to nothing (HIGH-6, `:1952-1959`); (b) reject dicts with only unknown keys; (c) reject `{}` | (a) PRESERVED: narration fails `json.loads` or yields unknown keys. (b) PRESERVED at `:1146-1148`. (c) RETIRED pending D-432-2: it contradicts the prompt contract (`:1610`, `:1627`) and caused O1/O2 |
| Single `attempt <= max_attempts` budget (`:1921`, `:1971`, `:2115`, `:2242`, `:2269`, `:2552`) | 715732d5 lineage; `structural_reissue` bypass from the #323 plan | Stop a model that keeps returning unusable output | PRESERVED for `completed_invalid` (D-432-1 bound); RETIRED for `transient` (B2-vii); `provider_deterministic` now stops immediately (the #240 rule in `LiveProviderCompletedError`'s docstring) |
| Schema-invalid branch treats every violation as the model's (`:2267-2288`) | 715732d5 lineage | Never commit a sheet the delta made invalid | PRESERVED for delta-introduced violations; a pre-existing violation no longer blocks (D-432-3) |

No deletion of an except, retry, ordering, fsync or lock pattern. The lock order and commit helpers are unchanged.

## 7. FS-1 (grep floor plus every numeric bound)

| Hit | Exhaustion branch | Class |
|---|---|---|
| `max_attempts = 3` / `completed_invalid_count` (ordinary path) | returns `False`, then action handler `status=error`, then `SAFE_ACTION_FAILURE_MESSAGE` (`main.py:9691-9704`); combat end logs only | TERMINATES for the `completed_invalid` class only. Legal only with the D-432-1 ratification (B2-iv, B2-vii scoped to a deterministic class; precedents D-VR-15 T097 and D-VS-12 T113) |
| `time.sleep(1)` in the loop (`:2554`) | none; it is a pause before a reissue | CONTINUES |
| `path_transaction_lock(..., timeout_seconds=30.0)` (`:1415`, `effects_runtime.py:112`) | inherited busy-refusal, not changed here | flagged, not added; owned by the #324 comment of 2026-09-10 |

## 8. Acceptance (NEQ-ACCEPT-01..03; evidence block NEQ-EVIDENCE-04 on every row)

All rows are headless, real OpenAI, current bindings, with a fixture built fresh from its source and prompt bytes hashed against the checkout (NEQ-REVIEW-16, 2026-09-04 rule). Runs are serial.

- **A0, real-save scan.** Grep the owner's `modules/` and `data/`, plus every kit fixture, for `"dex_limit": 99` and other schema violations on character sheets (`jsonschema` over every `characters/*.json`). Report the counts. This bounds how many real saves Task 2 touches.
- **A1, no-change answer at the play layer (O1).** On the branch, run the Boggard Marsh fixture with the marsh-raw-1 command sequence up to the quicksand escape.
  - PASSED when the DM emits a no-mechanical-change `updateCharacterInfo`, T079's answer is `{}`, the log shows `T079 reported no mechanical change`, the sheet is unchanged, and no `could not be completed safely` line appears.
  - NOT-REACHED if the DM emits no such action. A1 then stays open, and A1b runs.
- **A1b, same class at the updater layer (O1 input verbatim).**
  - In a fresh fixture game directory, call the production `update_character_info("eirik_hearthwise", <the O1 change string verbatim>)`. This is a real model call through the real function; the input is the captured DM string, not fabricated.
  - Record T079's raw answer and the return value, and diff the sheet before and after (no non-empty to empty transition, NEQ-SCHEMA-02).
  - Evidence class: OBSERVED at the updater layer. This row does not stand in for A1.
- **A2, pre-existing violation (O3), with a control arm.**
  - Load `issue116/clean-reset-fixture/saved_games/save_20260907_125556` in a fresh headless game on (i) main 7b20bc7d and (ii) the branch.
  - Play the same real command that changes Thane's sheet, for example an attack with his bow in a fight, or a short rest after damage.
  - Control arm: main rejects three times and the change is lost. This reproduces O3; without that reproduction the branch claim is HYPOTHESIS.
  - Branch: the change commits, `dex_limit` stays 99 untouched, the WARN names `...dex_limit.maximum` with value 99, and there is no failure line.
- **A3, gate polarity (NEQ-ACCEPT-02).**
  - A delta-introduced violation must still be rejected. Record any real T079 answer during A1 and A2 that fails schema for its own content. If none occurs, the row is NOT-REACHED; state that, and add no synthetic probe.
  - The `completed_invalid` exhaustion path at the D-432-1 bound: same rule, NOT-REACHED unless observed.
- **A4, parity.** Ordinary updates with real changes in A1 and A2 (damage, XP, ammunition) commit exactly as on main: same sheet fields, and T079 latency and tokens within the run's normal range.
- **Hygiene.**
  - ASCII only in touched Python.
  - `pyflakes` undefined-name check on changed files (NEQ-OPS-05).
  - No-Limits and Single-Path sentinel greps over the diff, pasted raw.

## 9. Owner decisions (execution blocked until ruled, NEQ-REVIEW-09)

- **D-432-1, the `completed_invalid` bound on the ordinary path.**
  - (a) Ratify: 3 consecutive completed-invalid T079 answers end the update with the existing truthful failure. Transient failures never count; deterministic provider refusals stop at once. This matches #432's fix direction and the D-VR-15 and D-VS-12 precedents.
  - (b) Unbounded correction retries, as on the staged path. The risk is an unwinnable loop that freezes the turn (the #194 scar).
  - Recommendation: (a).
- **D-432-2: accept `{}` as T079's typed "no change" answer.** GL-1: the origin of the rejection is unknown, and it contradicts the prompt contract. Recommendation: yes.
- **D-432-3: a delta that adds no new schema violation commits onto a sheet that already has one**, preserving the old value with a WARN, instead of refusing every update to that character until someone repairs the file. Recommendation: yes.

## 10. Tracked follow-ups

- #433: re-scoped by the 2026-09-24 comment; separate plan.
- #324: the T051/T052/T054 bounds and caps stay there.
- #431: the T079 `history[-10:]` cap.
- #367: the turn-loop provider count.
- `escalate:@owner`: level-up on a sheet that has a pre-existing schema violation. `level_up_manager.py:620` validates the merged sheet through the unchanged `prepare_character_delta`; whether it blocks forever on such a sheet is CODE-PROVEN-unverified. A new issue needs owner authorization; the draft is in section 11 when a reviewer confirms it.

## 11. Resolution ledger

| Round | Seat | Finding | Class | Resolution |
|---|---|---|---|---|
| (empty until the first review round) | | | | |
