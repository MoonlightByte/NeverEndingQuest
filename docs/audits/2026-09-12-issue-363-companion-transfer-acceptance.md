# Issue #363 narrow companion-transfer routing acceptance

Date: 2026-09-12 UTC. Owner authority: #193 D-363-1.
Base: 948ff0480b87a6ef0c6c3a2aae4a956529de6503.
Worktree: /home/loup/neq-worktrees/363-companion-transfer.
Status: implementation and scoped acceptance COMPLETE; owner authorized narrow
commit/merge/push on 2026-09-12 (#193 D-363-2). This is NOT an end-to-end
inventory-safety certification. Separate failed outcomes remain open.

## Change and architecture

Only the long and compressed T065 validator prompts changed (+6/-1). Container
storage remains storageInteraction's authority. An ordinary character-to-character
handoff instead uses the existing pair of updateCharacterInfo actions: giver
removal and receiver addition. The model still interprets player intent. Existing
writers execute the operations; no item-name lists, prose parsers, schema changes,
new tools, hard-coded characters, retry changes, or new persistence were added.
Stored-item duplicate-deduction rejection and distinct-fee ordering are preserved.

Approved plan SHA: 839cbce80f7134aec1eba1f9a970974efc5ad319d4ef30df65651e1d7f2c31c4.
Product diff SHA: ac0db032a1cea4666c8f36ea4498260b808519d714cfd779cdcec18e2aba9ee7.
Post-edit raw SHA-256:

- Compressed: 46fa006d7c7fc58d244d3d5caf9ff583907c5482157d2450c8ac57973c85fb77.
- Long: 4be464cfea7bb8d370b44666e65106e9de8b1fd7233cd69e1b89f6cc59d802b8.
- Compressed as sent: 4f40ce772cc55937f05f287b38f86b0fa5f19f928c12317f17ab177f8b18708e.

All 15 live T065 requests matched the edited compressed prompt after the loader's
newline normalization. The long prompt received static, not live-path, validation.
DM prompts, Python, schemas, bindings and private settings were unchanged.

## Focused gates

- D1-D4 prompt/spec/preservation/loader checks PASSED; simplifier required no change.
- Untouched byte regions and mixed line endings preserved in both files.
- `git -c core.whitespace=cr-at-eol diff --check`: exit0. Ordinary diff-check treats
  the existing CRLF regions as trailing whitespace; no broad EOL rewrite was made.
- Full Part3 plan review: all eight seats CLEAN. Independent implementation audit,
  No-Limits and Single-Path gates CLEAN. Final evidence audit: no #363-scope blockers.
- No Python compile or unit-suite pass is claimed for this prompt-only diff.

## Native real-OpenAI evidence

Actual C:/Python312/python.exe (win32, Python 3.12.3), run_headless.py serve; one
command at a time on a copied authentic save. No game-state edits or synthetic
model responses. Source export matched all 1997 tracked files plus the reviewed
prompt overlays; private configuration was copied separately and never published.
Capture model labels indicated luna none/low; actual returned model identity is
UNKNOWN because these sinks may substitute a requested/configured label.

| Arm | Routing / control result | State / player result |
| --- | --- | --- |
| A1 Bren -> Dain, five arrows | PASS: T065[0] first candidate accepted; two character updates; no storage/T049; writers reached | FAILED conservation and truth: giver19 unchanged, receiver19+5 split entries (#358/#360) |
| A2a player -> Astrid, shield | PASS: T065[2] first candidate accepted, correct paired route | FAILED: writer only unequipped giver while adding receiver Shield (#368); ordinary player correction later removed giver item |
| A2b Mira -> player, lute | PASS: T065[5] first candidate accepted, correct paired route | Count conserved and narration truthful; exact identity-string clause FAILED (Lute -> Mira Quill's Lute/type change); observation #370 |
| A3 container authority | PASS: T065[7] correctly rejected character-update-only storage; [8..10] accepted storageInteraction; T049[0..2] present | First implicit cache FAILED (#369/#364); player-named cache store and retrieve PASSED, proven on disk |
| A3 duplicate stored-item deduction rejection | NOT-REACHED | No duplicate candidate naturally emitted |
| A3 impossible spare-shield handoff | PASS: in-fiction refusal, no actions | Nine snapshot files unchanged |
| A3 inventory query | PASS: no actions | Nine snapshot files unchanged |
| A3 handoff-as-storage rejection | NOT-REACHED | DM never proposed that incorrect candidate |
| A4 explicit writer-error / safe-message branch | NOT-REACHED | Writers reported success; their silent failures above are not this branch |
| A5 Save, intervening turn, Load, relaunch | PASS | All seven sheets match saved bytes; history 45 -> 47 -> 45; usable resumed prompt; clean exit |
| A6 repetition | 3/3 distinct ordinary handoffs first-candidate accepted | No universal reliability claim; correction-only turns excluded from sample |

Including two correction-only turns gives 4/5 first-candidate acceptance. The one
rejection concerned a no-op receiver update and unrelated plot change, not a
storage demand. All five handoff/correction turns had zero storage dispatch.
The positive storage controls emitted the dispatch marker twice per operation
(two log sinks, not two actions), making handoff zero counts non-vacuous.

## Independent PX and limitations

Independent PX review verified three truthful outcomes and three false claims
across its five claims (one claim had failed and successful retry outcomes):
arrows, duplicated shield and failed initial cache were falsely narrated as done.
Named-cache success, impossible-handoff refusal and post-Load recap matched disk.
These separately owned failures were not waived or fixed by the routing change.
Companion dialogue still contained record/review phrasing; existing E8/#359-class
observation remains. No full browser or long-prompt live-path claim is made.

Conduct disclosure: the operator first asserted an unobserved chest. The DM
refused it; this is not a valid storage-success sample. The later cache was
created through gameplay, and the named store/retrieve provide the real control.

An initial welcome generation reached the existing 600s transport backstop and
reissued successfully. This was not an elapsed deadline added by #363. It is an
out-of-scope liveness observation, not a guarantee about healthy response time.

## Separate issue dispositions

- #358 ammunition exact-name mismatch; #360 narration before reliable commit.
- #368 observed shield handoff interpreted as unequip, duplicating ownership.
- #369 observed absent storage_name synthesized as schema-invalid null.
- #370 equipment identity-retention investigation: quantity conserved; harmful
  gameplay consequence of possessive display-name change NOT proven.
- #371 post-store T053 unsupported-field responses exhausted three attempts;
  validation skipped. Exact rejected field UNKNOWN (capture outputs empty).
- #364 storage failure continuation; #365 default storage policy; #366 storage
  ammunition omission; #367 provider retry-bound follow-up remain separate.
- #293 doctrine drift (absent main T109 seam), #324/#202 existing writer/lease
  boundaries remain outside this diff. No superseded architecture was restored.

## Evidence and preservation

Private root: /mnt/c/363-ev-wXKOTp; fixture /mnt/c/363-game-h0kTLC;
export /mnt/c/363-src-xfu3RF. Legs A and A5 contain complete protocol, per-prompt
sheet/storage snapshots, task captures, input files and process receipts.
A has 5013 protocol lines; A5 has 151. Master/character sinks are under sinks/.

Authoritative detailed report and independent reviews are in
/mnt/c/agent-room-fleet-kit/local-data/:

- 363-native-acceptance-report.md (per-turn text, capture indexes and physical lines).
- 363-implementation-report.md; 363-diff-audit.md; 363-diff-limits.md;
  363-diff-singlepath.md.
- 363-final-px-review.md; 363-final-audit.md.

Load: A seq4978 selected_applied, seq4980 restart exit, process exit0.
Relaunch: A5 prompt seq110; supported Quit seq143 player_exit; process exit0.
Operator confirmed no remaining python.exe. Controller independently rehashed
all 716 original fixture files: zero changes; all seven restored sheets match save.
Raw captures/configuration stay private. No original saves were altered; no
commit, push, merge, or issue closure had been performed at the acceptance handoff.
