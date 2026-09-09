# Issue 334: remove retired quest-state input from module chronicles

Status: PLAN ONLY; FULL independent review pending; implementation NOT authorized.
Policy: live #193 v3.1, updatedAt 2026-09-08T23:17:00Z, refreshed 2026-09-09.
Owner selected #334 for investigation and a reviewed proposal before code.

## 1. Goal and scope

Give the existing T038 chronicler ONE authoritative quest-status source: the
module's canonical plot snapshot. Stop sending the retired party-tracker quest
list as a competing status report. Keep the model responsible for writing the
story; code neither decides quest outcomes nor parses narration for completion.

Production allowlist: core/managers/campaign_manager.py, exactly the two-line
removal specified below. Documentation: this plan, its review/execution reports,
and a narrow delta in docs/architecture/module-lifecycle.md. No new model call,
guard, public helper, store, schema, migration, setting, retry, timeout or lock.
No quest synchronization, save cleanup, plot writer change, prompt style rewrite,
history scrubbing, summary regeneration sweep, or companion-memory repair.

Worktree: /home/loup/neq-worktrees/334-quest-status-plan
Branch: docs/334-quest-status-plan
Inspected HEAD and fetched origin/main: e38095c088bfb0150209057241b66a4417e001f2.
This is evidence, not runtime authority. Re-fetch and verify live branch/ancestry
at execution and shipment gates. WSL-only worktree registry; NEVER prune foreign
registrations. Native tests use an independent native-valid checkout/export.

## 2. Evidence and root cause

OBSERVED saved data: local-data/332-acceptance-7Tjnl2/before-A1 and after-A1:
Keep_of_Doom/module_plot.json nested SQ003 is completed; party_tracker.json
activeQuests SQ003 is not started. #332 did not introduce or change that pair.

OBSERVED real T038 consumer input, preserved under
/mnt/c/agent-room-fleet-kit/local-data/322-acceptance-oZxruI:
- A1-regeneration/model_captures/T038.json, record 0, invocation
  d940b972-cf12-4d19-8769-68fe161831fc, 2026-09-08T20:40:36.120531+00:00.
- A2-A5-continuation/model_captures/T038.json, record 0, invocation
  8fe6c821-c570-4bac-9053-43c22da9f9b5, 2026-09-08T22:26:52.978120+00:00.
Both actual requests contain canonical STRUCTURED PLOT DATA followed by the
retired Quest Status list. The first explicitly gives SQ003 completed with its
successful ward-restoration impact, then not started in Quest Status. Selected
binding is selected|gpt-5.6-luna|none. A1 is maintenance regeneration; A2 is the
preserved transition evidence. This proves contradictory input, NOT that every
generated summary or player journal actually gave a wrong quest result.

CODE-PROVEN current chain (line numbers at inspected HEAD):
1. updates/plot_update.py:238-271 writes the canonical target/delta. Its old
   tracker quest update at 273-329 is explicitly deprecated and disabled.
2. schemas/party_schema.json:114 retains activeQuests as deprecated optional
   saved data. CampaignManager.sync_party_tracker_with_plot:2140-2149 immediately
   returns False; restoring sync would contradict the established single source.
3. complete_module captures party/plot at campaign_manager.py:2967-2969 and
   passes its plot snapshot through _complete_module_once:3334-3341 to T038.
4. _generate_module_summary:3734 reads activeQuests; 3851 already serializes the
   full plotPoints tree, including nested sideQuests and their status/impact;
   3869 injects the obsolete Quest Status line alongside it. T038 calls the
   existing capture/provider path at 3888-3898.
5. regenerate_failed_summary reaches the same builder at 4302-4308 with its
   explicitly selected module plot snapshot (4268), not a second prompt path.
6. web/web_interface.py:4098-4174 derives quests from current canonical plot;
   core/headless/state_reader.py:102-115 also reads canonical module plot.
   UI variables named activeQuests are local derived arrays, not this save field.
7. conversation_utils.py:930-952 has the old full-tracker DM injection commented
   out. The #332 T065 plot evidence and existing DM plot formatter stay unchanged.

Lineage, verified with --follow rather than mistaking a license-header commit:
- ee2401b88542bcc9a42f30de3983a5f33ed30f1f (2025-06-15), Implement agnostic
  campaign management system: original campaign_manager.py:193/207 read and
  presented activeQuests to the chronicler. Goal: preserve adventure outcomes.
  No linked issue recorded in that commit; this is the recovered code origin.
- 5de59d1e retained that input while adding structured plot to the chronicle.
- a69b8983801020acdc19b322dbc2c978f3051b55 (2025-07-26), Implement SRD-compliant
  calendar system and improve quest display, deprecated tracker synchronization
  in favor of module_plot.json. ARCHITECTURE.md:445-450 records that ownership.
- ab91ee82 removed full tracker JSON from the main DM context. T038 was missed.
- Baseline 691b5a2f still reads the old list at 3035 and injects it at 3170.
Thus this is a pre-existing missed consumer, not a newly broken canonical writer.

## 3. Spec pin and architectural promises

#193 Part 2 p8 lines 139-142 NEQ-WORLD-03/04: bubbles, regenerated chronicles,
consequences are player data. p9 lines 144-146 NEQ-SAVE-01/02: unchanged Load and
continuity. p11 lines 155-157 NEQ-PROVIDER-01/02: unchanged routing/observational
capture. p12 lines 160-163 NEQ-SCHEMA-01/02: frozen schemas and preserve values.
p13 lines 166-172 NEQ-ACCEPT-01..03/NEQ-TEST-02: serial real acceptance.
Line pins refer to the recorded policy epoch; named rule IDs remain primary.
Schematics read: module-lifecycle.md, progression-leveling.md; historical overview
ARCHITECTURE.md. README Living Summary Generation & Chronicle System and Living
World Persistence promise coherent remembered adventures; this repairs conflicting
input without promising deterministic model recall or rewriting existing memories.

| Datum | Source / commit / end-state contract |
| --- | --- |
| Quest identity | Existing (module, quest ID); no global ID join or name matching |
| Committed status/impact | Existing supplied module_plot snapshot, nested side quests included |
| Authored descriptions | Plot data, not proof future objectives happened |
| Actual adventure | Complete existing filtered conversation; never replaced by the plot |
| Party NPC roster | Existing supplied party snapshot, unchanged |
| Retired activeQuests | Old save data retained byte-for-byte by this patch, not current authority |
| Story interpretation | Existing T038 model; no new referee or deterministic prose test |
| Summary publication | Existing summary commit/export/archive paths, unchanged |
| Memory and campaign | Existing T039/T108/import paths, unchanged; no history migration |
| Missing plot | Existing explicit None/empty behavior and history input; no fallback to stale list |
| Cancellation/failure | Existing currentness/reissue/Load/Reset/Quit behavior, no new terminal |
| Locks | Existing snapshot/publication order; no acquisition, release or wait changed |

Native acceptance: real Windows Python + configured OpenAI at freshly verified
candidate source; record interpreter, provider, binding, returned model when present
(do not invent response.model), per-call timing and capture coordinates. No binding
edits. WSL development checks are not native gameplay evidence.

## 4. Proposed change and GL-1

task-1: Delete only the active_quests assignment in _generate_module_summary and
the Quest Status interpolation in its user_prompt. The canonical Plot Structure
serialization, history, Party NPCs, both prompts otherwise, and all control flow
remain byte-identical. No source precedence selector or replacement list needed.

| Deleted element / origin | Original goal | Disposition and proving check |
| --- | --- | --- |
| active_quests lookup, ee2401b8 | Supply quest outcomes to chronicler | PRESERVED through existing module plot serialization at 3851; D1/D2 and A1/A2 |
| Quest Status prompt line, ee2401b8 / retained 5de59d1e | Include quest status in adventure history | PRESERVED through full canonical plot tree; retired competing source removed under task-1 / #334, pending owner execution approval |
| Saved activeQuests field, schema and writers | Load old saved games | PRESERVED unchanged; D3 and A1 saved-field comparison |
| Full history, NPCs, T038, T039, T108, scope and commit behavior | Remember and propagate real adventure | PRESERVED unchanged; byte comparison and real transition / regeneration evidence |

No goal is deleted. We do not assert removing obsolete input repairs prior stored
summaries. #318/#326 cover distinct fidelity/attribution concerns; no fix here.

## 5. Execution slices (only after reviewed-plan presentation + approval)

C0 / task-2: Re-read live policy and later owner rulings, verify clean branch and
main ancestry, freeze source EOL and real before-data/captures. No gameplay runs
on owner originals. Preserve evidence; no bulk copies during planning.
C1 / task-1: Apply the exact two-line removal. No production edits outside the
one-file allowlist; no reformats. Independent simplifier checks no extra machinery.
C2 / task-3: Focused development gates below; document the narrow consumer delta
in module-lifecycle.md, qualifying its historical authority with current code.
No superseding of earlier acceptance reports or changing tracked tests.
C3 / task-4: Serial native acceptance A1 then A2, independent PX review; report
partial or unrelated failures honestly. No repair beyond scope mid-acceptance.
C4 / task-5: Independent NEQ-REVIEW-15 all-five audit, both sentinel raw scans,
owner presentation. Commit/push/merge/issue closure need separate authorization.

## 6. Development checks (not gameplay evidence)

D1: Static byte/AST diff proves only the two specified lines removed. Compare
the unchanged plot/history/roster expressions and both call entrants. No import
or execution of a network-facing subject behind mocked models.
D2: Inspect real saved plot serialization and the actual baseline captures: nested
SQ003 completed and its impact are already present in canonical plot; removing
the separate line preserves them. Agreeing, missing, empty and contradictory
activeQuests shapes all cease to influence the prompt by absence of any read.
Explicit plot None/empty uses unchanged branching; no stale fallback is added.
D3: Full schema and state-writer paths unchanged; inventory genuine saved optional
activeQuests shapes without editing them. Existing loader behavior is preserved,
not replaced with synchronization. Compare snapshots before/after real arms.
D4: WSL/native py_compile, changed-file pyflakes undefined-name gate, diff --check,
ASCII added content, per-region EOL preservation, no tracked-test/schema edits.
Run relevant existing tests as dev aids; baseline failures receive attribution,
not opportunistic repair. Both sentinels scan proposed diff plus touched file.

## 7. Native acceptance, serial and narrowly scoped

Use a copy of the authentic retained /mnt/c/322-game-IbP7La campaign (official
Keep_of_Doom + The_Thornwood_Watch) or its preserved before snapshot. Inspect
module, location and reachable travel before proceeding. Never edit quest state,
fake model responses, or force a missing failure flag. Restore through supported
Load if needed. Refresh fixture prompts from candidate source and record actual
loaded hashes; record campaign_manager.py bytes as T038 prompt source. No stale
prompt fixture. Capture full requests, responses, commands, status and disk.

A1 REQUIRED - actual module departure to the other installed official module,
one player command at a time via run_headless.py serve/HeadlessClient on native
Windows with real OpenAI. The source fixture must actually contain conflicting
canonical/tracker SQ003 and reach T038; otherwise NOT-REACHED, not PASS. Prove
the sent request has the source module's exact canonical nested statuses/impacts
and no retired Quest Status section. Preserve full supplied conversation/roster.
Prove T038 and subsequent export/publication complete; T013/T063/T064 chain and
next actionable prompt still work. Compare old activeQuests before/after (patch
must not rewrite it), canonical plot, visit count, summary and companion stores:
only existing expected travel/lifecycle changes, no loss of prior entries. Read
the resulting chronicle and actual player output: status-input correctness and
semantic story fidelity get separate verdicts; never convert model speculation
into a completed quest or call every prose error fixed. Record five grounded
claims, pacing/ack, agency and a clean subsequent player turn + Save/Load resume.

A2 REQUIRED entrant coverage - existing regeneration operation on an authentic
failed-summary snapshot, if one is preserved; use original evidence to locate it.
Real OpenAI T038 request must reach the same corrected builder and retain selected
module snapshot despite any other active module. Verify summary/archive/visit and
memory preservation per existing regeneration contract. Label direct maintenance
API invocation MAINTENANCE, never player-experience PASS; inspect the resulting
summary through the real player interface where available. If no legal failed
summary can be recovered, report NOT-REACHED and ask owner to accept the explicit
coverage gap; do not fabricate one or claim A1 proves this distinct entrant.

No new gate or bound is added; negative controls are the actual conflicting
retired-field input (must not enter model context) versus canonical successful
outcome (must remain), unchanged missing/empty handling and an old-save reload.
Unchanged general provider/cancellation failure branches not reached by these
arms remain NOT-REACHED, never swept into PASS. No universal latency claim.

All verdicts PASSED/FAILED/BLOCKED/NOT-REACHED, evidence OBSERVED/CODE-PROVEN/
HYPOTHESIS. Per-call timing/model/capture coordinates, full text, lifecycle event
counts and fixture provenance accompany reports. Real acceptance is never parallel.

## 8. Review applicability and gates

FULL: play-path prompt deletion triggers GL-1 regardless of tiny diff.
Standing seats: Architecture, Fail-Forward, Acceptance, No-Limits, Single-Path.
Conditional seats: Consumer/Compat (shared T038 entry), Legacy-Contract (deletion),
PX (chronicle and prompt). Leanness not triggered: zero new mechanisms/symbols/
guards/settings; Custodian still checks coverage/net-negative recovery. Schema
freeze is unchanged-file proof; Platform/Provider and Hygiene apply. No large-
change trigger. Reviewers independently confirm applicability.

Review the entire plan and resolution ledger blind in separate read-only agents;
controller alone edits. Three concurrent seats maximum under session capacity;
independent batches remain blind. Same-SHA convergence plus clean confirmation
per #193, or its strictly plan-polish-only termination exception. Sentinel review
uses the proposed patch artifact, explicitly PROPOSED (not implemented), plus
actual touched-file bytes and raw scans. Re-run on landed diff after execution.

D-334-1: OPEN execution gate. Present reviewed source-removal plan; owner approves
implementation only afterward. No new runtime product design exception requested.
D-334-2: OPEN later ship gate; current task authorizes no commit/push/main merge.

## Tracked follow-ups

- #335 (filed this turn): deprecated manual sync CLI returns false success without
  comparing anything. Separate tooling diagnosis; no repair in #334.
- #318: existing chronicle fidelity/retention concern; retain its own scope.
- #326: existing export/identity attribution concern; no reconciliation here.

## Resolution ledger

| Finding | Evidence class | Resolution |
| --- | --- | --- |
| Conflicting old quest list reaches T038 | OBSERVED real captures + code | task-1 |
| Source/saved compatibility and shared entrants | CODE-PROVEN | task-2; task-3; task-4 |
| Historical synchronization intentionally retired | CODE-PROVEN lineage/schema | defensible: keep old saved field, never restore redundant authority |
| Manual sync CLI falsely reports already synchronized | CODE-PROVEN | issue-#335 |
| Existing summary/attribution limits | Existing tracked concerns, not new diagnosis | fyi: #318/#326; no new scope |
| Review and execution authority | Owner approved planning only | task-5; D-334-1/D-334-2 remain owner gates |

No failed implementation attempts; no product edits or live runs in this phase.
