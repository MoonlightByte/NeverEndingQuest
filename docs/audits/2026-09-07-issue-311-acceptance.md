# Issue 311 scoped acceptance and closeout

Status: Scoped acceptance complete 2026-09-08. Owner explicitly accepted the
accepted-Save-owner live arm as NOT-REACHED and authorized closeout and push.
This is not an all-arm PASS or a main-branch merge verdict.
Product source: 6295077b98c2c51078fa66113c7b498ac6027dfd.
Baseline: 99876535b4c9d24c29384236d52d03bfddc621be.
Branch: fix/311-module-final-memory, isolated worktree; publish this branch only.

## Scope and architecture

This fixes missing module-final companion memory, not memory quality generally.
The existing model extracts facts from the frozen departing module's history;
code owns the committed visit identity, publication authority and storage.
The same saved canonical episode drives missing companion POV projection on
replay. Already-saved canonical facts are not re-extracted by that replay path.
Distinct committed module visits use distinct module-visit-N coordinates.
Existing identity, schema, models, prompts, stores and gameplay actions remain.

Product commits:

- a1e022fe: unlocked completion-owned extraction, correct frozen inputs.
- d11bfec5: shared saved-canonical POV projection and partial replay.
- 6295077b: committed visit identity and interruptible authority contention wait.

Owner's latest instruction: no unrelated repairs. Other findings remain separate.

## Evidence convention

All bare artifact names below are under the private evidence root
`C:/agent-room-fleet-kit/local-data/` (WSL `/mnt/c/agent-room-fleet-kit/local-data/`).
Raw provider captures and game saves are deliberately not tracked.
Native runtime: C:/Python312/python.exe; source export C:/311-native-src-QVO77o
has all four product-file hashes matching the reviewed worktree.
Real OpenAI and actual run_headless.py serve; one player input at each prompt.
Primitive checks are supplemental, never substitutes for live gameplay.

## Acceptance matrix

| Boundary | Verdict | Evidence |
| --- | --- | --- |
| Module-final extraction, canonical episode and both eligible POV links | PASS | 311-c2b-live-recovery-verdict.md; master line225, real T1089.406s |
| Missing-canonical crash/restart | PASS | Same report, committed visit3, new ordinal143, recovered prompt231 |
| Canonical-present/POV-missing real cut and replay | PASS | 311-real-partial-replay.md |
| Complete same-visit replay, no extra canonical mutation | PASS | 311-complete-replay-verdict.md |
| Distinct module visits at equal old marker count | PASS | 311-c2b-controls-and-visits.md |
| Actual file contention and release | PASS | 311-native-epoch-hold-release/observation.json |
| Actual final-T108 network-wait Quit, Load and Reset | PASS | 311-actual-t108-controls.md; parent/child stacks and post-control state |
| Accepted Save itself owns final T108 | NOT-REACHED; owner accepted limitation 2026-09-08 | 311-remaining-gate-reachability.md; no healthy normal entrant identified |
| Ordinary Save, later turn, Load | PASS | 311-c2b-controls-and-visits.md; saved and restored sidecar comparisons |
| Solo module completion | PASS | 311-solo-completion-verdict.md; no extra T108 |
| Ordinary location capture | Reached; legacy retention FAILED separately | 311-location-retention-observation.md; 311-location-legacy-coordinate-addendum.md; #317 |
| Ordinary combat exit and memory | PASS actual extraction/projection, old canonical preservation and playable exit; independent raw-artifact review agrees | 311-final-combat-verdict.md; 311-native-final-combat-resume |
| Targeted recall selection and consumer delivery | PASS only for selection/delivery | 311-c2b-controls-and-visits.md |
| Original-promise factual recall | FAILED, pre-existing/out-of-scope #283 | 311-c2b-live-recovery-verdict.md |
| Regeneration failure preserves memory | PASS | 311-native-regeneration-evidence |
| Successful regeneration | NOT-REACHED behind out-of-scope #322 | Same evidence root |
| Final source audit | PASS, no new scoped blocker | 311-final-source-audit-closeout.md |

No universal narration-quality, all-memory-preservation or all-arm PASS is claimed.
The Save-owned call cannot be passed using ordinary Save or a synthetic entrant.

## Final real combat control and shutdown

The prepared attempt reached a genuine TW05-E2 battle through normal play. Actual
T1082026-09-08T06:59:42.365302Z,OpenAI luna/low,10.403s,1703+783tokens contains
combat rounds, damage and victory. New episode444ee941-1653-54b8-a238-7341f9440309,
ordinal149,combat-TW05-E2,combat_telemetry. Prompt4843->6224: revision150->151,
one new canonical ID, zero changed old canonical rows, both Thane/Elen POV links.
Completion5979/5980 and normal prompt6224/state6225: combatnull,PC54/54HP,
XP7057,both companions. Non-author reviewer independently checked these artifacts.

Normal Save6589/6590 creates174-file save_20260908_000243. Saved/live equal:
ledger4c32d0861310ded49a2dfe8ef0f24887c00892a04b0517c97f9ccc1ce415de22;
NPC0a7a106fa4c1196414b72876283bfe97fe162732102437f3e2af4933d44df106.
Quit6591-6594,exit0,relayclosed. Known native game/child PIDs absent; accessible
owned-source/game process scan empty. No live testing remains running.

Prior defeated combat and narrated spar remain NOT-REACHED attempts, not rewritten
as passes. A T107 network-header wait during approach was cleared through normal
Quit/resume, not product/config changes; read-only stack evidence is retained.

## Final focused development checks

Four changed files compile; git diff --check99876535..HEAD passes.
311-scope-primitives.py D2 passes exact executing-control registration and rejects
sealed/unowned/impostor/superseded owners. Existing external control sealing stays.
311-memory-primitives.py validates authentic sidecars, preserves canonical bytes
through missing-POV and complete replay, distinguishes committed visits, retains
old records in that path and rejects invalid visit metadata loudly without writes.
Native311-native-authority-primitive.py demonstrates real WinError32: release
resumes at1.000s, cancellation at1.015s, original bytes unchanged. Expected
invalid-input diagnostics are negative-control output, not live gameplay errors.

## Independent review

Required non-author source and PX reviews found no introduced #311 blocker.
The PX reviewer inspected canonical ca98692f-a033-5513-ac9a-97c50b5c7699 and both
NPC-ID-keyed POV links in311-native-complete-projection-replay/after_replay.
Raw network Quit17-23, Load41-43, post-Load211/212, Reset784-786 and post-Reset39/40
show truthful completion and appropriate next player state. Ordinary Save595/596,
later ten-minute narration786/prompt918 and Load942-944 were independently read
in311-native-visit4-canonical-cut/protocol.ndjson. Earlier wrong-module save-name
Load failure237 remains recorded, not hidden. Replay says late morning at12:46:
that separate narration discrepancy does not become a full PX PASS.

## Explicitly excluded work

#283 recall, #317 archive/location-coordinate reuse, #318 retention design and
#322 export/regeneration remain separate. #190 fixture name alignment was the
owner-approved roster-data correction, not an identity-code rewrite; #326 owns
further canonical-name pressure testing. Existing escape/rest observations are
under #264/#301. Existing hostile-NPC faction issue #279 was corroborated; ongoing
Spirit Guardians execution versus narrated reach is filed for investigation as
#327, not assumed a proven regression. Summary-fidelity observations added #318.
No fixes to those issues were absorbed into this closeout.

Latest #317 corroboration: an ordinary location capture replaced one legacy
close-N row's module_consolidation content with location_summary content. That
caller and store are byte-identical to baseline; the new module-final identity
is not its coordinate. Evidence: issuecomment-5580238278. Do not count that
negative control as complete retention success or silently waive its failure.

## Closure boundary

Plan A3's accepted-Save-owned final T108 remains NOT-REACHED: no healthy normal
gameplay entrant was found. Exact ownership primitives and ordinary Save/Load
passed but are not its live substitute. On 2026-09-08, responding to the explicit
request to accept this limitation, the owner stated: "I agree, lets accept it so
we cna close it out. If aeverbythign is done lets make sure we commti and push".
This clears the remaining scoped closure gate without relabeling the arm PASS
or adding machinery merely to force a test. Commit and publish the isolated
branch, then close #311 with this evidence and disposition. No main-branch merge
or unrelated repair is included. The separate findings above remain separate.

## Owner-authorized main integration (2026-09-08)

Owner subsequently authorized merging and pushing main. Integrated branch tip
073d75a1 into main tip 553c8128 in a separate integration worktree, without
conflicts. Main's intervening launcher changes are preserved. All four memory
product files are byte-identical to the live-accepted branch, not reimplemented.
Post-merge D2 authority checks, authentic-sidecar schema validation (revisions
151/591), D1/D3 canonical and POV replay, D4 distinct visits and invalid-metadata
negative controls passed. Seven deliberate invalid-metadata diagnostics were
expected. The first replay-check invocation lacked local config in the fresh
worktree; rerunning with the existing test config on PYTHONPATH passed without
product edits. Compilation passed for the four memory files and the three
intervening launcher Python files; staged diff whitespace checks passed.
These are focused post-merge checks, not a new live provider run. Prior native
Windows/OpenAI evidence above remains the live acceptance for unchanged code.
