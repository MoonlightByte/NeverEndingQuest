# Issue 369: implementation and extended acceptance

Date: 2026-09-12. Scope: only optional storage_name projection in store_item.
Subsequent owner D-369-3 authorizes committing and shipping this narrow fix with
the disclosed separate failures unchanged. Earlier no-publication statements
below describe the acceptance run's authority at the time, not a current hold.
Owner implementation/testing authority: live #193 Part5 D-369-1 and D-369-2;
continuation policy epoch 2026-09-12T15:36:32Z. No commit/push/merge authority exercised.

## Result

Implementation and focused development checks PASSED. Independent pre-live diff
review, fresh simplifier, No-Limits and Single-Path checks PASSED. Under D-369-2,
extended real native Windows/OpenAI testing reached and passed omitted-name and
supplied-name implicit creation, same-container retrieve/re-store, manager
ownership refusal and Save/Load/relaunch. The original unreached attempt below
remains historical evidence, not relabeled. See the continuation addendum for
exact limits: A4 player-visible truth FAILED separately, and an earlier referee
decision removed the item instead of storing it. No global inventory-safety PASS.

Product delta: +2/-1 core/managers/storage_manager.py only. Existing name default,
explicit names/empty strings, frozen schema, ownership checks, writes and rollbacks
are unchanged. Exact-byte verification found no other source changes.
Candidate file SHA256: 837ceaba4912de33e2fa3fac966d9a32c93bec5b31bad0092f3b3ccae74c9775
Diff SHA256: 6c3371d08d10d7a1a2cff73e86ba4d376a2d77c3e1b652a9403651cd44e3e590
Base observed: b7d86bdc on main; not runtime authority.

## Development evidence (not gameplay simulation)

/tmp/369-contract-check.py parses the actual old/new dictionary projection AST,
checking only serialization and the real frozen schema. Missing becomes valid
without a storage_name key; named and empty strings retain exact values; null,
number and object fail the unchanged outer schema. D1/D2/D3 pass. All other source
bytes and schema bytes match HEAD. py_compile and undefined-name gate pass;
pyflakes retains seven baseline unused/style diagnostics, verified against HEAD.
Whitespace, added ASCII and LF profile pass. No production test hooks or mocks.
Detailed raw checks: /mnt/c/agent-room-fleet-kit/local-data/369-development-gates.md.
Independent reviews: 369-implementation-review-0.md through -2.md in that folder.

## Native provenance

Actual C:/Python312/python.exe, win32 Python 3.12.3, real OpenAI, actual
run_headless.py serve with observation relay. Source C:/369-src-mdTGbq is git
archive plus reviewed file overlay; manifest 1999 tracked files, no mismatch.
Game C:/369-game-DpBarM copied from authentic C:/357-game-b-gF7QPg. Prompts/schemas
refreshed. Original 716-file hash comparison independently repeated: zero changes.
Evidence C:/369-ev-aO8llh; no background model variants or state customization.
No named container exists initially. Item chosen is canonical Shield quantity1.
Selected bindings T067/T049 luna none, T065 luna low; actual response.model UNKNOWN
because captures expose selection labels, not a verified returned model field.

## Historical first attempt (before D-369-2 continuation)

The first harness submission mistakenly used text rather than content and was
rejected before gameplay (protocol physical line145). Same sentence resubmitted
correctly at line146, epoch1789226120.646762; no different probe or prompt shopping.

Player input:
> Before we go any closer, I unbuckle my shield and tuck it into the dry hollow under the roots of this thorn tree we are hiding behind. It will clank and catch every branch if I try to sneak with it, and we can pick it up here on our way back out.

T067.json[1] (+25.6s from input, duration7.252s) proposed updateCharacterInfo and
updatePlot, NOT storageInteraction. Its changes asked to unequip/hide Shield but
explicitly said it remains in Eirik's possession. T065.json[0] (+38.1s,
5.653s) accepted first candidate, citing continued possession. T079.json[0]
(+45.3s,3.245s) proposed equipment Shield equipped:false and armorClass16.
T078[0] occurred +42.0s. A later T051 response failed AC-breakdown validation once
and corrected successfully (protocol line422 onward); no patch attribution.
No T049 capture exists. Raw protocol turn window lines146-549 contains zero
Processing storageInteraction action, Storage Error, and None is not of type
matches. The zero schema-error count is NOT proof of the fix: storage never ran.
One character action appears twice in diagnostic sinks, not two actions.
Raw fallback/degrad/SAFE_ACTION/could-not-be-applied scan is zero on this window.

Actual player narration (protocol physical line316, seq310):

You ease the shield from your arm and slide it into the dry hollow beneath the thorn tree's roots. The oak and steel make only the faintest scrape against bark before the roots swallow the outline. You mark the spot by a forked twig and a pale stone, giving the party a way to recover it if you withdraw.

Astrid watches the concealment, then nods. "Leave it here, then. A quiet approach may preserve more lives than a brave charge."

Bren remains low, eyes fixed on the gate. "Fine. Less clanking. Do not mistake my cooperation for obedience."

Carys studies the hiding place and the palisade in turn. "The marker is sufficient. We reduce noise without abandoning the equipment."

Dain checks the thornbushes around the hollow. "A shield is useful, but not if it announces us before we reach the wall."

Mira gives a quiet grin. "I shall miss its heroic clanking, but stealth makes a better song than a panic."

Torvald keeps watch over the route back. "The equipment remains recoverable. Proceed with discipline."

The shield is no longer equipped and is hidden nearby; no sentry reacts. The party remains concealed outside Bandit Stronghold at 11:05 AM. The locked gate, concealed pit, three visible sentries, signal horn, and corruption-marked supplies remain ahead. How do you proceed?

Disk comparison before-launch/prompt-543: Shield remains quantity1 in Eirik's
sheet, equipped true->false, armorClass18->16. player_storage.json unchanged and
playerStorage empty. Other six sheets and party_tracker unchanged. The turn
records the hiding story in plot/history, but this is not evidence of a storage
container. No inventory quantity loss or non-empty->empty change observed.
Next main prompt seq543 / physical line549 at +67.8s; history40->44 including
welcome and gameplay pairs. No general claim that hidden-story persistence fails.

| Arm | Verdict |
|---|---|
| A1 omitted-name implicit creation | NOT-REACHED: T067/T065 chose character update, no T049/manager call |
| A2 custom-name implicit creation | Not run; no PASS claimed |
| A3 storage retrieve/re-store | Not run; A1 created no container |
| A4 unavailable-item refusal | Not run |
| A5 Save/Load preservation | Not run |

Supported Quit returned ok:true, player_exit seq548, process_exit0. Operator
checked no leftover acceptance children; unrelated pre-existing HTTP server left
untouched. Original fixture independently rehashed unchanged. No edits outside
one product file and local documentation; related issues remain separate.

Full private operator report:
/mnt/c/agent-room-fleet-kit/local-data/369-native-acceptance-report.md.
Final independent PX review: /mnt/c/agent-room-fleet-kit/local-data/369-final-px-review.md.
It independently confirms NOT-REACHED from raw artifacts, no item loss, and no
patch-attributed defect. The story-versus-carried-gear observation is not evidence
of lost permanent storage; no new defect is asserted from this one turn. This partial
acceptance is not a merge recommendation. No wider issue repair or issue closure.

## D-369-2 extended live acceptance

Raw report: /mnt/c/agent-room-fleet-kit/local-data/369-native-acceptance-report.md.
Evidence root: /mnt/c/369-ev-aO8llh. Source export and candidate hashes above
remain identical. Original source fixture: 716/716 files unchanged; exported
source: 1999/1999 tracked files unchanged. New fixture B:
/mnt/c/369-game-hMDwj2. No gameplay state edits or synthetic provider results.

| Arm | Final scoped verdict and raw evidence |
|---|---|
| A1 omitted name | PASS: Acont T049.json[0] really omits storage_id AND storage_name. Post-processed operation remains nameless. Implicit create produces storage_fd26a8fb, Chest at Bandit Stronghold, with Shield x1. Prompt-1403 -> prompt-1769: one item moves from sheet to container, zero schema-null failure, usable prompt. |
| A2 supplied name | PASS: B T049.json[0] omits ID and supplies Thorn Root Cache. Manager creates storage_94161573 with that exact name; Shield x1 transfers; prompt-457. |
| A3 retrieve/re-store | PASS: Acont T049.json[1] retrieves and [2] re-stores using storage_fd26a8fb. Prompt-1769 -> 2069 -> 2372: same container, no duplicate creation, total Shield count stays one; sheet byte-identical round trip. |
| A4 ownership | Manager PASS: Acont T049.json[3] requests unowned Lantern. Protocol lines2581-2583 reject it; prompt-2372 -> 2651 all nine observed files identical. |
| A4 player truth | FAIL: narration line2547 claims both items stored despite refusal. Existing #364/#360 class, not changed. Normal player correction accepted at line2831. Model refusal and live malformed-schema branches NOT-REACHED. |
| A5 persistence | PASS: save_20260912_084958; later ordinary turn; Load selected_applied, clean restart; saved storage, sheet, tracker and history byte-identical on disk. A5 relaunch reaches prompt and truthful cached-shield recap, then clean Quit. |

A1 storage model call duration3.293s; retrieve3.259s; re-store3.667s;
unowned-item3.547s; A2 supplied-name3.552s. These are individual captured T049
durations, NOT whole-turn latencies. All returned response.model fields remain
UNKNOWN; selection labels identify configured luna bindings only. The internal
create dictionary is not logged: omitted-name proof combines captured real op,
post-processing trace, persisted default, source audit and static projection test.

Save restored history from48 to46 entries after the intervening scouting turn;
relaunch correctly adds its welcome pair. The intervening turn changed history,
not inventory. This is ordinary Save/Load evidence, not power-loss/atomicity proof.
No browser testing or universal storage/inventory safety claim is made.

All A/Acont/A5/B processes ended with returncode0 by supported Quit or Load
restart; no acceptance children remain. Unrelated HTTP server left untouched.

### Separate failures preserved, not repaired

- #374, Acont turn1: T065[0] rejected storageInteraction as a local drop/cache, directed
  updateCharacterInfo removal, and the writer removed Shield while no storage
  existed (prompt-648). A normal player correction restored it at prompt-1403
  before successful A1. This path never enters the modified manager block.
- A4 false-success narration on actual manager refusal: #364/#360.
- T053 post-storage validation errors: #371. B retains armorClass18 after storing
  the equipped shield; this is NOT a correct-armor-stat PASS. A's shield was
  already unequipped before storage. No validator/armor logic changed here.
- Player-correction writer lost three item metadata keys relative to original:
  #370/#358 identity-retention class. Subsequent A3 round-trip preserved the
  corrected record; B stored its full original record. Do not conflate those.
- Default chest vs narrated hollow remains #365. Cosmetic first-attempt log
  says attempt2; actual B capture has one T049 call, not a retry.

The narrow optional-name transaction is now empirically exercised, unlike the
historical first attempt. Remaining failures prevent a clean end-to-end player
truth verdict, not evidence of a defect in the +2/-1 name projection. Independent
continuation review is recorded separately in local-data/369-continuation-final-review.md.

Final independent audit/PX reviewer (Claude Opus5 medium, separate session) re-derived
all scoped verdicts from raw artifacts and found no blocker attributable to the
narrow patch. It independently verified 1999 source and 716 original-fixture hashes,
the actual missing-key payload against old/new projection, and every transfer and
restore snapshot. Reviewer limits above are preserved. #374 filed; #371 received
the captured offending field and stale-AC evidence. No commit, merge or push.
