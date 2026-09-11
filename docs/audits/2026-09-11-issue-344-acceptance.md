# Issue 344 acceptance: consolidated evidence, dispositions, owner shipment ruling

Authority: live #193 v3.1 (updatedAt 2026-09-11T16:25:02Z at packaging read),
Part 5 rulings D-344-1 (execution), D-344-2 (narrow C5 referee amendment) and
D-344-3 (2026-09-11: owner authorizes commit/merge of the narrow tested fix and
its focused evidence/docs after current-main merge checks). This document is
the consolidated acceptance stamp for that shipment. It records evidence; it
changes no product code, prompt, schema, fixture or issue. Publication status
at this stamp: OWNER-AUTHORIZED, NOT YET PUBLISHED. No commit, push, merge or
closure was performed while writing it; the supervisor handles git publication.

Reports cited below live under /mnt/c/agent-room-fleet-kit/local-data/ unless a
full path is given. Raw evidence roots are private Windows directories; no raw
capture, credential or provider payload is reproduced here.

## 1. Source under acceptance

- Worktree /home/loup/neq-worktrees/344-character-validator-evidence, branch
  plan/344-character-validator-evidence, HEAD 8c242fa1. origin/main fetched at
  packaging time is also 8c242fa1 (no divergence to reconcile yet).
- Uncommitted change set (`git diff HEAD --stat`): main.py 204 lines
  (+125/-97 across all files), docs/architecture/provider-routing.md +5,
  docs/architecture/travel-transitions.md +13. Untracked:
  docs/audits/2026-09-10-issue-344-character-evidence-plan.md,
  docs/audits/2026-09-10-issue-344-plan-review.md, and this file.
- main.py SHA256 0a847c594fff45682801bbe9c15666543848f8917344325b7146858aa947c117
  (rechecked at packaging). Pre-C5 reviewed SHA 3ce5fa182a90f9157ef965b9ed5237
  a4d7e816959f63f6d8c6daf56c005d4d1d (original #344 implementation before C5,
  not the unchanged mainline file).
- Change content: validate_ai_response (main.py:3232-3852) replaces the old
  inventory-only character block with one canonical character evidence frame
  (complete party plus normalized targets, full source values, native transient
  read handling), plus the C5 evidence-priority instruction inserted once at
  main.py:3666-3672. No new model call, no hardcoded character/item rule, no
  writer, lifecycle, schema, binding or scope change.
- Gates rechecked at packaging: py_compile PASS; `git diff --check` PASS;
  main.py CRLF count 0; touched docs ASCII-clean. Earlier audits recorded
  pyflakes undefined-name count 0 (344-opus-audit-report.md).

## 2. Review lineage (independent blind seats)

Original plan seats were Codex agents; subsequent implementation, C5 reviewers,
and acceptance workers used logged-in Claude Code Opus 5/high with Codex
supervision. Provider-backed game calls remained on the configured OpenAI models.

| Gate | Result | Evidence |
| --- | --- | --- |
| Original plan, nine seats | zero blocking findings on substantive SHA bafd1104; citation-polish cb46cb45 presented; owner D-344-1 | 2026-09-10-issue-344-plan-review.md (SHA 1fd682d6...) |
| Implementation code audit (non-author) | READY-FOR-LIVE at main.py 3ce5fa18; zero blocking | 344-opus-audit-report.md, 344-supervisor-audit.md |
| Synthetic intercepted-main tests | WITHDRAWN under NEQ-LEAN-04; never presented as a gate | 344-supervisor-audit.md |
| D3 native I/O primitive | PASS: real WinError32 while exclusive handle open, read succeeds after release, missing classified | 344-dev/native-read-result.md, native_read_primitive.py |
| C5 amendment plan, nine seats | all CLEAN on substantive SHA 2a7ed5ef; plan-polish 156b5429 under NEQ-REVIEW-11 | 344-c5-review-consolidated.md, 344-c5-r1-*.md |
| C5 implementation delta audit + simplifier | READY-FOR-LIVE; diff is exactly one hunk @@ -3663,7 +3663,14 @@, AST-equal apart from the reviewed literal | 344-c5-delta-audit.md, 344-c5-implementation-report.md |

## 3. Live evidence runs (native Windows Python 3.12.3, real OpenAI, no stubs)

| Run | main.py | Roots | Reports |
| --- | --- | --- | --- |
| E2-original native serial run (A1/A2/A3 arms, 9 player turns) | 3ce5fa18 | evidence C:/344-ev-zJsssG/A2, game C:/344-game-EW1GPd, source C:/344-src-qm7BCm, PID 19328, exit 0 | 344-native-acceptance-report.md, 344-live-failure-audit.md (independent forensic + A5 PX), 344-supervisor-audit.md |
| A4 real React browser Save/Load run | 3ce5fa18 | evidence C:/344-a4-1jStu2, game C:/344-web-xbJlZV | 344-a4-acceptance-report.md, 344-a4-independent-review.md |
| C5 fresh native serial run (5 player turns + Quit) | 0a847c59 | evidence C:/344-c5-ev-NFJdSF/C5, source C:/344-c5-src-OrnQDe, game C:/344-c5-game-yoRuE1, PID 44688, exit 0 | 344-c5-native-report.md, 344-c5-px-audit.md (independent, legs 1-2 only) |

Provenance common to all runs: source export = 1992 tracked files byte-equal to
the worktree (manifest diff [] missing []), 27 prompt hashes and 19 schema hashes
equal, no .git pointer; fixture copied intact from the authentic E2 game
C:/354-web-xLy1be (132 original hashes unchanged after every run). Bindings at
execution: T065 selected|gpt-5.6-luna|low temperature 0.1, T067 luna|none,
provider openai. Server-returned response.model is recorded by the game's
api_calls_master.jsonl in the original run (gpt-5.6-luna on every row) and is
UNKNOWN from the C5 capture artifacts (field not exposed there).

## 4. PASS dispositions (with artifact paths / call IDs)

| Item | Evidence |
| --- | --- |
| C0 isolated source + authentic unchanged fixture | manifests c5-fixture-manifest.json and src-manifest.json; e2-original-hashes-before.txt 132/132 match after each run |
| C1 one complete character evidence boundary; D2 full values | C5 T065.json[0..8]: system frame (msg[31]/[33]/[23]/[25]) 25382-25509 bytes, 7/7 records status available, 49 keys each, deep-equal to prompt-130/prompt-609 snapshots (nulls, zeros, empty lists kept); original run 12 requests JSON-equal to snapshots, controller recheck via 344-dev/captured_frame_audit.py |
| Raw final player/candidate pair after compression | every T065 request ends with the verbatim player line and the candidate; no frame compression logged |
| A1 correct Perception +3 (original symptom of #344) | original: T065[8] f9f1c8bd-baf2-4086-812c-9e99399098bb accepts +3, real die 18 -> 21, narration seq2031. C5: T065[7] 4129efea-dcf5-4708-bd81-58ad02b084a6 accepts request for +3 (frame carries wisdom 12 / proficiencyBonus 2 / Perception), narration seq1729; genuine die 4 (C5/dice-rolls.txt, rolled after the request) -> 7; T065[8] 0c34af50-f73c-4231-9629-833c8030829e accepts the honest failed observation; no re-roll |
| A2 requested HP/resource exactly once | original: prompt-809 Dain 3->8, Torvald LoH 5->0. C5: T065[3] 135fcbe7-4d02-46bf-8f18-025e6935a030 rejects "no confirmed Lay on Hands reserve" citing 5/5; T065[4] 7f442e1d-d6e3-4875-b3e8-a4a862c0bf75 accepts; T079 73eb84fb / c9e1d658 one write each; prompt-609 -> prompt-1284 hitPoints 3->8, usage.current 5->0; party_tracker, XP, time unchanged |
| A2 exhaustion negative control | original: prompt-1077 still HP 8 / reserve 0. C5: T065[5] 17271c42-2eb3-434f-9116-70b4c9038581 rejects Astrid "no healing left" against Healing Word 2/2 (sheet-backed, not invented); T065[6] 981cbb20-29c6-4906-9e7e-697eac7c9f7b accepts; prompt-1284 -> prompt-1573 no change in all 8 files |
| C5 false-unknown rejection branch (344-F12) | REACHED: T065[0] af3f959f-e62d-466b-8261-07f0f128580b rejects "arrow count is not recorded" citing Arrow 19; T065[1] d25a0afe-b756-453b-ae1c-b72643553310 rejects "no verified coin" citing gold 10; T065[2] f6bdfb4a-eb4c-4a00-8b55-971d3d667a90 accepts. Corrections were private (T065 rejection -> T067 revision); the only player message is the original query. Delivered narration seq485: 9/9 claims TRUE against saved sheets (344-c5-px-audit.md section 3). No state mutation across the query |
| C5 instruction physically present | the exact D-344-2 sentence is in the same system frame on all 9 C5 T065 requests, frame sha256 c805e1d9... (turns 1-2) |
| A3 meaningful semantic rejection retained | original: contradictory-resource rejection T065[2]->[3]; invented-overheard-fact rejection T065[5]->[6]. C5: the referee still rejects, revises and accepts honest drafts; no always-valid path (verdict parsing unchanged) |
| A4 Save -> play -> Load -> usable next turn (real React) | save_20260910_202948 (38 files); T065[0] 303f8bd2-7cef-4478-8ee8-cb9587bfe026 frame == save; restore_complete "Restored 38 files"; T065[1] dff02cd9-7f8a-4e73-8a92-e1e5bb505202 uses saved source, turn-1 text absent from all 36 messages |
| A4 Load while a real T065 is in flight | provider child PID 35384 ESTABLISHED TLS at armed trigger 1789097736.242; Load accepted on live_scope branch (web/web_interface.py:3146-3178); no validation row logged for turn 3; post-restore history len 49 == save; next T065 4091d90d-7092-4bf1-80c9-65e496a087b6 7/7 == save, cancelled input absent. Precision caveat: exact instant within the ~5 s window not pinned |
| A4 browser control/progress truth | ui_progress events, disabled controls, screenshots in C:/344-a4-1jStu2; 0 pageerror, 0 native dialogs |
| D4 compile / undefined names / EOL / ASCII / callers | PASS at 3ce5fa18 and rechecked at 0a847c59 (section 1) |
| Cleanup / quiescence | original Quit seq3085 exit 0; A4 exit_acknowledged, no python.exe, nothing listening on 8371; C5 Quit c5-quit-1 result ok, player_exit, relay returncode 0, tasklist PID 44688 absent, stderr.log 0 lines |

## 5. Retained FAIL dispositions (separate layers; NOT waived; NOT relabeled)

D-344-3 accepts these as disclosed separate failures for shipment purposes.
They are not part of the #344 code path, are not repaired here, and remain
FAILED in their own issues.

| Item | Verdict | Evidence | Tracking |
| --- | --- | --- | --- |
| A2 unrelated-field preservation (T051 armor layer) | FAIL, recurred in both runs | original: Torvald armorClass 18->19 via assumed Defense fighting style (level-1 Paladin, no such feature), shield dex_limit null->0, equipment_effects added; Dain armorClass 15->16, equipment[1].dex_limit null->99 (schema max 10). C5: identical mutations, T051 c58d2364/9c3f0005/e07d0c35 (Dain), 8c34c054/48478553/a08313fd (Torvald), protocol L1012-L1160; prompt-609 -> prompt-1284 diff | #357 (schema poisoning), #349 (unowned style); #188 related |
| A3 inventory query, original run | FAIL at 3ce5fa18 | T065[9] 8580ed34-18ba-4d67-807e-c5215967773a accepted "arrow count is unknown" while its own frame msg[31] held Dain Arrow 19 and gold 10 for every companion; delivered seq2275; player clarification T065[10] accepted 19 | in-scope 344-F12 -> D-344-2 amendment. The C5 run at 0a847c59 reached and passed the rejection branch (section 4) on changed source; this row is kept as the original evidence, not erased, and no favorable-rerun waiver is claimed |
| A3 ammunition transfer, writer and delivery | referee PASS, writer FAIL, delivery FAIL | T065[11] a4df791b-d63b-49d3-955e-e4871b371324 correct accept; T079 idx3 a4cb7b52-565c-4673-8424-af8ecb4f049d returned "Arrows" -5 (sheet name "Arrow") -> silent no-op reported SUCCESS for Bren; Dain three attempts reverted on dex_limit 99; narration seq2785 "Dain now carries 24 arrows" delivered before "could not be completed safely" seq2996; disk prompt-3080 Bren 19 / Dain 19, Bren leather dex_limit null->4 | #358 (Arrow/Arrows no-op), #357 (blocked update), #360 (false-success publication) |
| A5 PX claim 1: private-record language in companion dialogue | FAIL | original seq2275/seq2521 ("not recorded here", "The record is clarified"); C5 delivered narration seq485 still says "recorded on your current sheet" (sheet language to the player); C5 rejected drafts carried the same tell privately | #359 (NPC projection/private-record language) |
| A5 PX claim 3 / hidden-fact disclosure | FAIL (out of #344 scope) | original turn 3 T065 idx4 17ba9caa-1b48-4e6d-baa0-9062dd5123ca accepted exact pit placement and an invented signal horn with no check; C5 pit mentions are fixture-inherited prior disclosures, not new | #80 / #260 (comment 5629050197 carries the roll/passive/prior-knowledge caveat), #337 location evidence |
| A5 PX claim 4: truthful successful delivery | FAIL on original turns 7 and 9 | see A3 rows above (seq2275 false unknowns; seq2785 vs seq2996) | #360, #359 |
| A5 PX claim 2: agency / dice | MIXED | PASS turns 5-6 (real die, +3 = 21); FAIL turn 3 (DC 15 resolved with no roll) and turn 4 (no roll for eavesdropping); no invented rolls anywhere. Not a universal roll mandate | #260 caveat comment |
| NPC projection omits ammunition; T105 advice claims no record | FAIL (PRE_EXISTING_OUT) | character_sheet_compressor.py:276-318 / DM Note omit NPC ammunition; all C5 T105 outputs still advised "not recorded" and the referee overrode them | #359; #276 identity caps (comment 5628144334) |

## 6. NOT-REACHED / NOT-CHECKED / UNKNOWN (disclosed, not PASSED)

| Item | Status |
| --- | --- |
| Genuine-absence polarity (a truly unrecorded value reported unknown) | NOT-REACHED; no fabricated fixture used |
| Missing / unreadable / permanently malformed character path; transient-read retry; whole-main sharing-violation cancellation | NOT-REACHED in play; D3 primitive is the only I/O evidence; "record unavailable" count 0 in every run |
| Active effects vs stored base interpretation | NOT-REACHED; temporaryEffects [] on every real sheet in every frame |
| Nonparty normalized-target update, apostrophe/hyphen names, duplicate-path dedup | code-reviewed only; not live-reached |
| A4 restoration of CHANGED character values across Save -> mutation -> Load | NOT-REACHED; only conversation history (49 -> 33/35/36 -> 49) discriminated the Load |
| Quit while T065 in flight | NOT-REACHED |
| Actual travel / non-membership semantic guard | NOT-REACHED; unchanged code reviewed |
| Hidden-fact guard in the C5 session | NOT-REACHED (not exercised) |
| Independent PX of C5 legs 3 (exhaustion, A1, quiescence) | NOT independently checked; 344-c5-px-audit.md scope ends at prompt seq1284; controller read the narrations, dice receipt and Quit receipts |
| Twenty-turn PX coverage | not this issue; #354 retains it |
| Server-returned model string in C5 captures | UNKNOWN (not exposed by artifacts); selected label gpt-5.6-luna on every call |
| Causal attribution of the C5 verdicts to the added sentence | NOT CLAIMED; single run proves instruction presence plus observed verdicts, not universal model compliance |

## 7. Out-of-scope observations recorded, not repaired

- C5 turn 3: T084 compression call hung 600.078 s until the per-generation
  backstop reaped the child (protocol L1421-L1451); truthful heartbeats shown,
  turn completed, no intervention. Linked to existing #213 (comments
  5630396746 / 5630507700); provider liveness #348/#284 unchanged.
- "[ERROR] Failed to compress LocationSummary_e66baf1f" on every validation
  prep in every run (pre-existing, #213 evidence).
- "NPC store health: episode_capture_missing_lifecycle_authority" at C5
  protocol L581 after turn 1; recorded, not attributed.
- Stale debug label "[MAIN.PY] Using model: gpt-5.2" (main.py:7353-7363);
  registry binding overrides it.
- Cost/latency (measured, no dollar claim, no isolated causal comparison):
  C5 T065 prompt tokens 21505-24576 over 9 calls, latency 4.66-9.84 s; original
  run roughly +6-8k T065 tokens vs the unpaired E2 baseline, 4.88-7.75 s. The
  25382-byte frame is the added request size. Turn wall times in C5: 159 s,
  209 s, 666 s (stall), 42 s, 36 s.

## 8. Owner shipment ruling and publication status

D-344-3 (live #193 Part 5, 2026-09-11): after presentation of the completed
prompt amendment, the native correction/healing/exhaustion/Perception evidence
and the separately tracked armor-writing/narration failures, the owner asked to
commit and merge the narrow fix to main and then take on the other work under
supervision. The ruling authorizes publication of the reviewed #344 code and
focused evidence/docs after current-main merge checks; it preserves the section
5 failures and section 6 NOT-REACHED rows as such, not PASSED; it does not
absorb #357-#360 or #349 into this shipment; the next issue starts with
diagnosis and #193 planning/review only, implementation subject to
presentation and approval under NEQ-REVIEW-13.

Status at this stamp:
- Publication: OWNER-AUTHORIZED, NOT YET PUBLISHED. This packaging task made no
  git stage/commit/push/merge, no issue mutation, no product edit, no new test.
- Shipment content: main.py (0a847c59...), the two focused architecture docs,
  the plan, plan review and this acceptance document. Nothing else.
- Pre-publication obligations for the publisher (NEQ-OPS-03): re-read #193
  updatedAt/version before merge/push; merge checks against current main
  (origin/main == 8c242fa1 at packaging time); rerun compile / diff --check on
  the merged result.
- Issue #344 stays OPEN until the owner or publisher closes it; #357, #358,
  #359, #360, #349, #213 remain OPEN and separately tracked.

No overall "all branches PASS", no universal model-compliance claim, and no
relabeling of any FAIL or NOT-REACHED row is made by this document.

## 9. Supervisor final merge gate

Current main remains8c242fa1, identical to the acceptance baseline; the merge
introduces no untested combined source. Main.py remains0a847c59. Fresh compile,
diffcheck, ASCII/EOL and undefined-name checks PASS; pyflakes still reports61
inherited non-undefined warnings, not a clean general lint result.
Independent logged-in Opus5/high merge sentinels CLEAN; raw scans/dispositions
are in local-data/344-ship-limits.md and344-ship-singlepath.md. The transient
0.25 wait continues re-reading; it is not a failure deadline.

Custodian large-change sweep (controller, non-author): the total patch exceeds
1000 changed lines because the plan/review/acceptance records are included.
All six paths reviewed; only main.py changes gameplay. Against Part2 p6/p7/p8/
p11/p12: one evidence boundary replaces projection, canonical identity remains
the existing resolver, full pre-action sheets remain data, interpretation stays
agentic, provider bindings/writers/persisted schemas untouched. Against p9/p10:
existing supersession and unlocked waiting preserved; no lifecycle mechanism
added. GL1 maps deleted inventory goals in the plan. Docs match code. No
additional mechanism, schema contract or alternate runtime found. This is a
static architecture gate, not new live coverage. Publication authorization is
the owner's D-344-3, not reviewer consensus.
