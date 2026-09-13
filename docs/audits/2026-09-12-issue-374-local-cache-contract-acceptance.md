# Issue 374: local-cache referee contract acceptance

Status: IMPLEMENTED; LIVE MATRIX AND INDEPENDENT AUDIT COMPLETE WITH FAILURES; SHIPMENT HELD.
Date: 2026-09-12. No commit, push, merge or closure authorized/performed.
Worktree: /home/loup/neq-worktrees/374-local-cache-contract.
Base observed: 8562e270dde6b94d05bb21b97ce7b51fb810baf4.
Reviewed plan: 2026-09-12-issue-374-local-cache-contract-plan.md, SHA256
7ec894c55d177c6fdfa9824429db82389bdc75b4e69aa986e68956bf961ca5f1.
Its frozen status/owner gate reflect the review snapshot; subsequent owner GO is
live #193 Part5 D-374-1, epoch 2026-09-12T16:54:25Z. This execution record does not
change the reviewed plan or authorize shipment.

## Implementation and static evidence

Two prompt files only, four lines replaced (+4/-4): full lines229/384, compressed
54/225. No Python, schema, model binding, writer, retry or runtime mechanism change.
Existing storage ownership, duplicate additions/removals, distinct fee ordering,
handoffs, view/create/retrieve/store and required parameters remain intact.
Generic contract follows player intent; no item/place-specific logic.

| Prompt | Disk SHA256 | Runtime-normalized SHA256 |
|---|---|---|
| Full | 506d67c2cd3667b62622c450472c1f3fa7997a2007f96733a66fb4b3a0b62006 | 1ac1a8b25810956722bc6a83a32c4136371d1a28e01cc15fdc7498d4e00242d2 |
| Compressed | 593bcaba23324a942922e04a5166fc068a36174acafff750d6d420ea80b77dd1 | fa47de4b8a38968bbf6c5445038737da0abc0408da86fc263fb9865bd8e60cf0 |

65/65 static contract checks passed. Independent diff/simplifier, No-Limits and
Single-Path reviews found no blocking candidate defect. Controller reran static
checks and byte-level EOL comparison: full only229/384 changed, other899 lines
byte-identical; compressed only54/225 changed, other238 lines byte-identical.
Every edited line retains its baseline terminator. CRLF-aware diff check passes.
Full CRLF848/LF53; compressed CRLF184/LF56. ASCII-only additions.

Recorded development failures: apply_patch normalized three edited CRLF lines;
mechanical restoration of their original terminators passed byte comparison.
Two local checker mistakes (case/tokenization) corrected, not product defects.
Controller initially invoked the EOL script without its required compare arguments;
corrected invocation passed. Plain git diff --check flags preserved CR at EOL;
git -c core.whitespace=cr-at-eol diff --check passes without repository config edits.

Private evidence in /mnt/c/agent-room-fleet-kit/local-data/:
374-development-gates.md; 374-c2-audit.md; 374-c2-no-limits.md;
374-c2-single-path.md; 374-plan-review-convergence.md. Raw provider captures and
private configuration are not committed. Static checks prove no gameplay outcome.

## Live verdicts

Serial native C:/Python312 real-OpenAI run_headless.py serve evidence is under
/mnt/c/374-ev-gdyhCb, copied source /mnt/c/374-src-f9pOen, fixture A
/mnt/c/374-game-K6gSX5, fixture B /mnt/c/374-game-6IPeO4. Original 357 fixture
untouched. Actual compressed prompt equals candidate normalized hash.

Complete private operator report:
/mnt/c/agent-room-fleet-kit/local-data/374-native-acceptance-report.md.
All three legs A/A3/B finished with returncode0 (Load restart or supported Quit).
Original fixture 716 files unchanged; exported 2001 tracked files unchanged.
No product repair during acceptance. Returned response.model is UNKNOWN: captures
expose requested binding labels, not the returned provider model field.

| Arm | Controller disposition | Raw evidence under /mnt/c/374-ev-gdyhCb |
|---|---|---|
| A1 clarified cache | Referee PASS; first durable movement and narration FAIL #377; ordinary correction stores exactly1, not retroactive PASS | A T065[2], T049[0]/[1], prompt-1281/1652 |
| A1b original ordinary sentence | PASS: referee rejects removal-only; DM repairs to storage; exactly1 item moves, full metadata retained, AC16, truthful narration | B T065[0]/[1], T049[0], protocol L378, prompt-533 |
| A2 retrieve | FAIL #378: equip writer adds1 before storage retrieves1, total2; same cache ID retained | A T065[5], T079[3], T049[2], prompt-2643 |
| A2 re-store | Count/ID/routing PASS after normal duplicate correction; referee rejects duplicate removal and obtains storage-only; metadata already reduced on prior retrieval, AC stale #371 | A T065[7]/[8], T049[3], prompt-3346 |
| A3 Save/turn/Load/relaunch | Persistence PASS: cache, sheet, tracker and history byte-equal to saved versions; intervening turn absent after Load | A protocol L3488/L3763; A3 prompt-110; save_20260912_103037 |
| A3 resumed retrieval | FAIL #378 repeated (2/2); no third retrieval; normal correction restores1 | A3 T065[0], T079[0], T049[0], prompt-603/934 |
| A4 carried unequip | Routing/ownership PASS; first equipment/AC outcome FAIL, player correction PASS, not a clean first-attempt equipment verdict | A T065[0]/[1], prompt-555/956 |
| A5 handoff | Routing and total quantity PASS; receiver identity split FAIL #358, related #370 | B T065[2], T079[0]/[1], prompt-996 |
| A6 unavailable item | Manager gate PASS, zero mutation; models accepted phantom; false narration FAIL #364/#360, then corrected | B T049[1], protocol L1158/L1192, prompt-1310 |
| A7 permanent destruction | Routing PASS; actual decrement and player correction FAIL #358 (Arrow/Arrows), false narration | B T079[2]/[3], prompt-2031/2449 |

Boundaries: A1 used ordinary unequip plus correction to reach owned/carried/
unequipped state; its preceding conversation is NOT byte-identical to the old
incident. A1b uses pristine original fixture and byte-identical ordinary sentence,
and is the cleanest narrow-contract evidence. No new old-prompt baseline trial;
historical captures only. Neither regression nor pre-existing prompt behaviour
is proven for #378 merely because its execution code is unchanged.

Save/Load preserved already-stale AC18; it did not fix armor. Its resumed recap
said AC16 and is not globally truthful. Full-mode live, browser, short travel
away/back and power-loss atomicity are not claimed. Static parity is not live
acceptance of the full prompt.

Controller raw checks confirmed candidate prompt bytes and cache/removal/retrieve
claims. Five truth checks: A L1123 cache claim FALSE (empty); A L1472 stored item
TRUE but AC16 FALSE; A L2327 one retrieved shield FALSE by count2; A L3223 same
cache TRUE; B L378 stored/not-carried TRUE; B L1158 rope stored FALSE. Operator
report has full private transcript paths and per-call timing; no secrets copied.

No overall inventory or all-arms PASS. The narrow cache interpretation has live
proof, but addition-side duplicate protection failed twice. Shipment is HELD for
owner disposition, not silently approved by filing #378. No unreviewed prompt
amendment or inventory repair has been made.

## Tracked follow-ups

#364/#360 failure propagation/narration; #365 default container representation;
#366 ammo lookup; #368 handoff ownership; #370 identity retention; #371 armor;
#373 empty-name divergence; #324 other validator bounds; #375 ordinary T049
count exhaustion; #376 obsolete full-prompt action aliases; #377 create_storage
ignores its supplied items and reports success; #378 retrieve/equip duplicates;
#379 zero-valued effect description overrides actual value in T051. No repair or
closure of these issues is part of #374. Main remains unchanged during acceptance.

Attribution corrections to operator report (raw report retained): A7 ordinary
ammunition writer mismatch is #358, not storage lookup #366; A5 positive unmatched
addition also proves #358's previously code-only branch, related #370. Evidence
comment: https://github.com/MoonlightByte/NeverEndingQuest/issues/358#issuecomment-5647627472.
A-turn5 T051 value0/description+2 refusal is #379, distinct from #371's T053
unsupported-fields failures. #377/#378 were already filed by controller while
operator ran; its NEW/untracked descriptions reflect its independent viewpoint.
The acceptance doc was controller-authored during the run, not unexpected drift.

## Final independent audit and reconciliation

Logged-in Claude Code Opus 5 medium, session
617e45ff-4636-4d97-90fd-6597f532ab54, completed a non-author read-only REVIEW15
and PX audit after all games ended. Verbatim output is private local-data/
374-final-independent-audit.md. It independently verified all19 actual T065
prompt hashes, source/original fixture manifests, state conservation failures,
Save/Load history evidence, five narration claims, terminal receipts, the actual
diff, EOL/ASCII/allowlist and both sentinel scans. Core referee contract PASS on
this run; downstream failures retained; no new defect beyond filed follow-ups.

Audit reconciliation (no product delta): its request to refresh this document
was based on the earlier snapshot read before the controller update. The final
table and #378/#379 links are now above. Audit and operator loosely attributed
Arrow/Arrows to #366/#370; live #358 describes this exact writer mechanism and
now has the new positive-addition and negative-no-op evidence comment. History
is not in the relay's nine-file snapshots: save history hash3a5f48ff (42 entries),
restore backup's44 entries and the resumed A3 captured request jointly support
the rollback claim. Do not claim history was independently snapshotted.

Citation correction: A-turn5 protocol seq1951-1958 are PHYSICAL lines1964-1971;
description-over-zero message physical1969. Correction posted on #379; raw logs
unchanged. This does not change the failure verdict.

Final static rerun65/65 and CR-aware diff check PASS. Candidate and reviewed plan
hashes unchanged. Local branch remains based on8562e270; only the two prompt
files modified, two audit/plan documents untracked. No commit, push, merge or
issue374 closure. Main untouched. No further test game left running.

Recommendation: owner review before shipment, specifically the #378 addition-
side retrieve/equip overlap. Core cache routing is proven but the complete
planned transaction matrix is NOT all-green. No automatic expansion to fix
inventory ordering, armor or item identity; those remain separate issues.

## Subsequent #378 forensic correction (2026-09-12, no implementation)

After owner requested solving retrieval overlap, independent full call-order
trace showed BOTH real T067 candidates already ordered retrieve BEFORE equip.
The ordinary dispatcher reversed that order through the obsolete character-first
partition. Thus 'addition-side wording gap' was a tentative surface attribution,
not the root diagnosis. Referee acceptance of correctly ordered retrieve+equip
is legitimate. See the separate issue378 plan and private
local-data/378-forensics-result.md. No new prompt tuning is proposed; #374 prompt
bytes stay frozen. All duplicate counts and failed verdicts above remain true.
The proposed remedy is ordered tool execution plus a storage-failure handback;
it requires the separate reviewed #378 execution gate and has not been applied.

## #378 trial implementation addendum (2026-09-12; acceptance pending)

The preceding paragraph records the pre-implementation forensic checkpoint.
After owner D-378-1 and eight-seat confirmation, the isolated candidate now
implements listed-order dispatch and the existing storage-failure handback.
The #374 four passages remain byte-identical; one new ordering paragraph in
each validator prompt is separately attributable to #378. It permits legitimate
retrieve-then-equip and checks resolved prerequisites before combat/exit, with
no deterministic guarantee if both models accept a misordered candidate.
Static checks27/27, Linux/native compilation and undefined-name gates passed;
real #378 acceptance is pending. No earlier FAIL/NOT-REACHED is relabeled.
