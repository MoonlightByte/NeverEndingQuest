# Issue #363: companion-to-companion item handoff is misrouted by the referee into a storage operation

IMPLEMENTATION / SCOPED ACCEPTANCE COMPLETE. Original planning authority D-357-4;
post-review owner approval "move ofrwar with the narrow fix" is recorded as
live #193 D-363-1 (epoch2026-09-12T06:10:02Z). Approved plan SHA839cbce80f7134aec1eba1f9a970974efc5ad319d4ef30df65651e1d7f2c31c4.
Subsequent owner approval on 2026-09-12 authorizes committing and merging/pushing
the tested narrow fix and its evidence (#193 D-363-2). Separate inventory/storage
failures and naturally unreached branches remain disclosed, not waived or fixed.
Worktree: /home/loup/neq-worktrees/363-companion-transfer, branch
plan/363-companion-transfer. Revision evidence captured at planning (never runtime
authority): HEAD 948ff0480b87a6ef0c6c3a2aae4a956529de6503 == origin/main
(fast-forwarded by the controller after the #357 shipment; the observed run was on
c7ede1268a3a7faba471b583bec2b9119c8f7095 plus the isolated #357 patch, now shipped).
No game, provider, prompt, schema, test or production file changed during planning.
Execution C0-C2: two prompt files changed +6/-1, diff SHAac0db032a1cea4666c8f36ea4498260b808519d714cfd779cdcec18e2aba9ee7.
Unchanged byte regions verified; D1-D4 and simplifier passed. Independent audit,
No-Limits and Single-Path gates cleared proceeding to C3, not shipment. Evidence:
/mnt/c/agent-room-fleet-kit/local-data/363-implementation-report.md and
363-diff-{audit,limits,singlepath}.md. C3 live acceptance and independent PX/final
audit completed: #363 routing PASS (3/3 ordinary handoffs); separately owned
inventory/storage/PX failures retained, not waived. See
2026-09-12-issue-363-companion-transfer-acceptance.md for all verdicts and evidence.
New follow-ups #368/#369 and observations #370/#371 filed without repairs.
Private captures under C:/357-ev-pAaw3B and C:/344-ev-zJsssG stay local; nothing
raw is published here beyond the excerpts needed as evidence.

## Authority and spec-pin

Live #193 v3.1, policy epoch updatedAt 2026-09-12T03:53:56Z (recorded at session
start; re-check before implementation and before any merge decision, NEQ-OPS-03).
Read in full: Part 1, Part 2 p6/p8/p10/p11/p12/p13, Part 3, Part 4, Part 5
(through D-357-4), Part 6, all 19 changelog comments.

Pinned pages (body line numbers of the live v3.1 text):
- p6 NEQ-INV-01 lines 129-132: model maps scene -> structured slices; code owns
  arithmetic/conservation/transactions and never reads prose; corrections inject
  deterministic FACTS. TRAP: verb lists, shape heuristics, refusing instead of
  consolidating.
- p6 NEQ-INV-02 line 131 names a "Resolution seam: T109 (core/ai/inventory_resolver.py,
  utils/inventory_resolution.py)". CODE-PROVEN: neither file exists on origin/main.
  See "Doctrine drift" below (reported, not resolved by this plan; NEQ-CORE-10/R12).
- p8 NEQ-WORLD-04 line 141: the character sheet is player data; partial write =
  corruption; silently stopping consequences is a finding.
- p10 NEQ-WEB-01 line 150: on-disk state is the UI's truth, never narration.
- p11 NEQ-PROVIDER-01 line 156: CALLSITE_BINDINGS single source of truth; no new
  provider branch.
- p12 NEQ-SCHEMA-01/02 lines 162-163: play-path schemas frozen; preserve-then-override.
- p13 NEQ-ACCEPT-01..03, NEQ-TEST-01..02 lines 167-171: real native acceptance,
  negative controls, one probe at a time, no fabricated model output.
- Part 4 NEQ-OPS-02 line 252: validation-failure forensics from captured calls;
  COHERENCE RULE: two validators/gates on one path must not make contradictory
  demands, and a gate's own error note must not instruct behavior another gate
  rejects. This plan is a direct application of that rule.
- Part 1 AP-6/AP-7 (lines 52-53) and NEQ-CORE-06 (line 55): models propose typed
  facts, code owns identity/arithmetic/atomicity; no prose keywords, no name lists.
- Part 5 NEQ-LEDGER-07(b): the one approved storage schema exception (operations[]
  batch delta) is NOT touched; storage schema stays frozen and unedited here.
- Part 5 D-NPC-PARTY-3: one shared detached correction loop; the rejected drafts and
  review feedback stay transient (the #363 captures confirm this loop is what carried
  the wrong instruction to the DM).

Schematics consulted (docs/architecture on main): provider-routing.md (items 18, 21,
22: T065 evidence frame, correction owner), travel-transitions.md lines 18-19, 34
(T065 exact verdict; rejection revises latest draft; no mutation before verdict).
No schematic documents the ordinary inventory/storage path; none is superseded by
this plan, and no new schematic is introduced (AP-4). The README promise this plan
advances (README.md:22): "AI-powered Dungeon Master" that "remembers every decision" - a hand-off the
player ordered must change both sheets or the game must say it did not.

Canonical definitions pinned for this plan:
- Identity: a character is its canonical sheet file resolved through the existing
  ModulePathManager/normalize_character_name path; an item is the exact `item_name`
  (equipment[]) or `name` (ammunition[]) string on that sheet. No aliases added.
- Source of truth: committed character JSON under characters/ (player and party NPC);
  player_storage.json for location containers. Narration and history are never truth.
- Commit point: the existing per-character atomic write inside
  updates/update_character_info.py (`_update_character_info_unlocked`, per-file lock
  and `.effects.lock` lease) for handoffs; StorageManager backup/write/validate/
  cleanup for container operations. This plan adds no commit point.
- End states of an ordinary handoff turn: (a) both sheets updated by exactly the
  requested deltas; (b) referee rejection -> DM correction, no mutation; (c) writer
  failure -> existing SAFE_ACTION_FAILURE_MESSAGE, narration persisted once, later
  sibling actions not applied (main.py:6598-6628, 6671-6681); (d) silent writer no-op
  on identity mismatch = #358, out of scope here and never relabeled.
- Lock order: unchanged (per-character lock, then path lease). No new lock.
- Branch/platform/provider/model: plan/363-companion-transfer; acceptance on native
  Windows Python 3.12 with the configured real OpenAI provider; T067 bound to
  OPENAI_GPT56_LUNA_NONE and T065 to OPENAI_GPT56_LUNA_LOW (model_registry.py:413-431),
  capture selection labels identify gpt-5.6-luna; response.model itself is absent
  (UNKNOWN, not inferred from the label).

## Evidence base (raw captured calls, read in full as sent)

All captures: C:/357-ev-pAaw3B/B (private). Indices are zero-based JSON array
entries; "MSG[n]" is the n-th message of the request as sent.

E1 OBSERVED - the DM proposed the correct contract twice. T067[1]
9d04ffa3-dd53-44b4-be6e-28f9b07d298b (03:02:52Z, 5.975 s) answered player input
inbox/001.json with two updateCharacterInfo actions (remove 5 from giver, add 5 to
receiver) plus updatePlot. On the player's explicit correction turn (inbox/002.json,
"This is not about any chest or stash"), T067[3] e0b0f606-... again proposed exactly
two updateCharacterInfo actions with the derived counts 14/24. Both match the DM's
own contract @INV&CURRENCY.transfer "EXACTLY TWO updateCharacterInfo actions: remove
from giver, add to receiver" (prompts/system_prompt_compressed.txt:90; long form
prompts/system_prompt.txt:647-651). The as-sent T067 system prompt equals the
newline-normalized prompts/system_prompt_compressed.txt (25041 chars; raw-file
SHA starts10f1013fe44059fe, as-sent SHA startsf5571b557a7727e3).

E2 OBSERVED - the referee rejected that contract twice and ordered the wrong action.
T065[0] d3401d22-338a-45c0-9447-a8b41759cf5d (03:03:06Z, 6.482 s):
{"valid":false,"reason":"The arrow transfer is valid in principle, but item transfers
must use storageInteraction as the sole inventory-transfer authority. The two
updateCharacterInfo actions improperly modify ... replace them with one
storageInteraction action ..."}. T065[2] 05100c4e-... on the correction turn:
"item transfers must use storageInteraction as the sole transfer authority. Replace
the two updateCharacterInfo inventory actions ...". The referee's phrase quotes its
own prompt line. Its complete system prompt (MSG[0], 18348 chars) equals
prompts/validation/validation_prompt_compressed.txt after the production loader's
newline normalization and trailing-newline stripping. Raw-file SHA starts
7d083c8a1fb7ce58; as-sent SHA starts 97c7a3b60ef9fdbd. These are deliberately
distinguished; raw bytes are not identical.

E3 OBSERVED - the corrected candidate was then ACCEPTED by the referee. T065[1]
5ed23da5-... "correctly handled by a single storageInteraction action"; T065[3]
6ab891ae-... "uses storageInteraction as the sole item-transfer authority". The
accepted candidates (T067[2] bb96494a-..., T067[4] 3420197a-...) carried
{"action":"storageInteraction","parameters":{"description":"Transfer 5 arrows from
<giver> to <receiver> ...","characterName":"<one character>"}}. The correction was
delivered through the shared correction loop: T067[2] MSG[55] "Review corrections,
NOT player dialogue ... [{"stage":"validator","reason":"... must use
storageInteraction ..."}]".

E4 OBSERVED - what storage did with it. protocol.ndjson L490-L496: "Received 2
total actions ... Separated into 0 character updates and 2 other actions" (the writer
was never reached). L501-L507: T049 parsed the description into
{'action':'store_item','character':'Dain Alder','item_name':'Arrows','quantity':5,
'location_id':'TW05','location_description':'Bandit Stronghold','storage_type':'chest'}.
L523-L525: "FAILURE: Failed to store item - Character does not have Arrows". L526:
"Updating plot progression..." (the sibling updatePlot still ran). Correction turn
repeats it at L881-L905 with character 'Bren Tor'. T049.json[0]/[1] show the
"CHARACTER INVENTORY (all items)" context sent to T049 listed only the weapon and
armor equipment entries - no ammunition - so no exact name could have matched.

E5 OBSERVED - no truthful result reached the player. Between the delivered
narration L489 ("Dain now carries 24 arrows, while Bren has transferred 5 arrows to
him") and the next prompt L642 there is no narration/system/error event of any
kind (full non-debug event listing of protocol.ndjson: types narration 4, status 44,
prompt 4, state 4; zero system-channel notices). The failure went only into
conversation history as a user-role line ("Storage Error: Failed to store item:
Character does not have Arrows", persisted at indices 33 and 36 of
C:/357-game-b-gF7QPg/modules/conversation_history/conversation_history.json) and
into the log. Four persisted assistant entries (29, 31, 34, 37) claim 24 arrows.

E6 OBSERVED - sheets never changed. state_snapshots before-launch, prompt-130,
prompt-637, prompt-985, prompt-1481, exit-1486: bren_tor.json sha 0bd542716b23 and
dain_alder.json sha d4f3188deea4 identical across the transfer and correction turns
(both ammunition [{"name":"Arrow","quantity":19}]); dain_alder changed only at the
later short-rest turn (HP 8->12, sha 4d88468f3812). player_storage.json in the game
dir is the pre-existing empty container list (2026-09-09); no chest was created
because store_item fails item lookup before create_storage (storage_manager.py:335-358).

E7 OBSERVED - control arm at the original setting, same prompt bytes, opposite
verdict. C:/344-ev-zJsssG/A2/model_captures/T065.json[11]
a4df791b-d63b-49d3-955e-e4871b371324 (2026-09-11T03:11:33Z): the identical two
updateCharacterInfo candidate (same changes text) was ACCEPTED ("Correctly transfers
five arrows ... updates both inventories"). Its MSG[0] sha256 prefix 97c7a3b60ef9fdbd,
18348 chars == the B run's MSG[0]. Therefore the current validator text produces
either verdict for the same shape: 1 accept (A2) vs 2 rejects (B). Why B differed is
HYPOTHESIS only (B's history additionally held the A2-era false "24 arrows" narration,
a persisted SAFE_ACTION_FAILURE_MESSAGE at history index 6, and the welcome-back
recap repeating "24 arrows"; temperature 0.1 / reasoning low). No claim is made that
the prompt line always rejects; the claim is that it permits rejection of the DM's
own mandated contract, and that the referee's error note then instructs an action
the deterministic layer cannot execute.

E8 OBSERVED (related, separately tracked): the DM's own NPC projection for the giver
listed EQUIP=[Shortbow, Leather Armor] with no ammunition (T067[1] MSG[8]); the DM
had the count only from the player's earlier correction. That is #359 and is not
repaired here.

## Root cause versus symptoms (NEQ-OPS-02 classification)

Classification: (d) deterministic-vs-agentic disagreement expressed as (b) a prompt
contract defect, on the validator side only. The DM contract and the executing code
agree (handoff = two updateCharacterInfo, executed by the character writer); the
compressed validator prompt disagrees with both.

CODE-PROVEN chain:
1. prompts/validation/validation_prompt_compressed.txt:54 (git blame b7f7a8631,
   2026-08-24, "fix(travel): make agentic transitions recoverable", ancestor of
   origin/main): "storageInteraction: sole store/retrieve item-transfer authority;
   REJECT duplicate updateCharacterInfo for those items; a distinct fee update may
   precede it". The same commit wrote the DM side as "sole authority for item
   movement into/out of storage" (system_prompt_compressed.txt:19) and the long-form
   validator as "storageInteraction itself owns removal/addition of the stored
   items" plus "REJECT a redundant updateCharacterInfo that adds or removes the same
   items handled by storageInteraction; updateCharacterInfo is permitted here only
   for a distinct fee or unrelated character change" (validation_prompt.txt:791-792;
   definition229-234 says "items in containers at locations", lineagec88affc08;
   trade example14 at741-760 uses two updateCharacterInfo). Only the compressed
   validator line carries "item-transfer authority" without container/stored-item
   scope. This corrects the first draft's inaccurate quotation, not the diagnosis.
2. The same compressed validator file says the opposite elsewhere: @CLARIFICATIONS 5
   "Item loss/drop/trade REQUIRES updateCharacterInfo" and 9 "Trading MUST update ALL
   parties' inventories" (lines 223, 227, lineage abdeafbd7 2025-08-29). The validator
   prompt is internally incoherent on this exact question, and it lacks any explicit
   statement of the DM's two-action handoff rule.
3. main.py:3854-3863 load_validation_prompt selects the compressed file whenever
   model_config.COMPRESSION_ENABLED is true (model_config.py:1052, default True), so
   the incoherent text is the production validator contract on every provider
   (config selection at main.py:3734-3741 changes only the model profile).
4. The referee's rejection reason is fed verbatim to the DM as the correction
   (main.py:10521-10545: "Your previous response failed semantic validation.
   Reason: {validation_reason}. Return the complete corrected JSON response."). The
   semantic-rejection loop has no rejection cap (B2-vi completion wait). The
   enclosing turn's inherited retryable-provider failure-count stop is separate
   (#367, below), so this is not a blanket B2-compliance claim. With this prompt,
   the observed rejected candidates were corrected by
   producing an action the deterministic layer cannot honour.
5. Deterministic capability of storageInteraction (the action the referee demanded):
   - core/ai/action_handler.py:4384-4451 ordinary handler: T049 parse
     (process_storage_request) then execute_storage_operation.
   - core/managers/storage_processor.py:159 "Determine the appropriate storage action
     (create_storage, store_item, retrieve_item, view_storage)"; :167 "NEVER return
     action 'error'"; :176 "If the request is unclear, default to store_item";
     :263-267 storage_type defaults to "chest"; :120-129 context inventory is built
     from equipment[] only. schemas/storage_action_schema.json enum has exactly those
     four actions. There is no character-to-character operation and no "not a storage
     request" outcome; a handoff description is forced into store_item + chest.
   - core/managers/storage_manager.py:142-154 `_find_item_in_character` and :156-172
     `_remove_item_from_character` read equipment[] only; ammunition[] is invisible
     to storage. :295-461 store_item moves character -> container; :463-611
     retrieve_item moves container -> character; :613-623 the travel-owned staged
     path accepts only the same four actions. No code path anywhere on main moves an
     item from one character sheet to another via storageInteraction.
   Consequence: even a correctly named equipment item routed this way would have been
   moved into a newly created container at the party's location, not to the
   receiver - a fictitious chest with the giver's property in it. The observed
   name/array mismatch prevented that worse outcome by accident.
6. Truth failure at the storage handler (distinct entrant from #360):
   action_handler.py:4435-4441 on execution failure appends a user-role "Storage
   Error: ..." line and falls through to :4771 `create_return(needs_update=...)` with
   status "continue". The ordinary loop (main.py:6674) therefore never sees an error,
   never emits SAFE_ACTION_FAILURE_MESSAGE (web/shared_state.py:19-22 via
   main.py:4885-4897), and runs later siblings. By contrast the updateCharacterInfo
   handler returns status "error" on writer failure (action_handler.py:3837-3845) and
   the processor-failure branch of the same storage handler returns needs_response
   (:4412-4419). Three different failure semantics in one action family.

Symptoms that are NOT the root: the Arrow/Arrows plural (that is #358's writer
identity defect and in this run did not matter, item 5 above: storage never reads
ammunition[]); the DM's later acceptance of the storage action (it was told to);
the persisted false narration (delivery seam #360; here additionally caused by item 6).

Falsifiable statement of the fix: with the validator contract restored to the same
scope the DM already has, the DM's first candidate for an ordinary companion
handoff (two updateCharacterInfo) is accepted at the referee, no storageInteraction
appears in the accepted actions, T049 is not invoked, and the two updates reach the
character writer. Conservation is then the writer's existing responsibility; where
the writer fails on identity, #358 owns that failure and the acceptance record says so.

## Actual capability map on origin/main (what exists, no assumptions)

| Capability | Owner on main | Notes |
|---|---|---|
| Character-to-character handoff | T067 proposes two updateCharacterInfo -> T065 verdict -> action_handler.py:3798 -> effects_runtime.update_character_with_effects -> updates/update_character_info.py (T078 classify, T079 delta writer, deep_merge, per-file atomic write) | Sequential, stop-on-first-error (main.py:6586-6632); each write is atomic per sheet; no cross-sheet transaction; silent no-op on unmatched negative ammunition delta (#358, merge_ammunition_arrays 595-648) |
| Location container store/retrieve/create/view | storageInteraction -> T049 -> StorageManager | equipment[] only; container tied to current location; travel-owned staged variant (action_handler.py:742-767, storage_manager.py:613-867) |
| Two-sheet atomic transfer | none on main | efd0075a (T109 substrate, branch slice-prototype) and ffb8f8a0 (character_transfer.py, inventory_resolution_service.py, branch fix/storage-two-action-loss; +5416/-1700) are NOT ancestors of origin/main; not doctrine, not baseline (NEQ-CORE-10) |
| Prepared/apply receipts for one character | effects_runtime.prepare_character_update / apply_staged_character_update (234-294) | used only by the travel checkpoint; value-compare then one write; not wired into ordinary turns |

## Current and proposed flow

Current: T067 proposal (two updateCharacterInfo) -> normalization/T114/preflight ->
T065 with an incoherent storage line -> sometimes rejected with an instruction to use
storageInteraction -> DM complies -> referee accepts -> T049 forces store_item/chest
-> StorageManager fails (or, with a matching equipment name, moves the item into an
invented container) -> "Storage Error" hidden in history -> siblings run -> false
narration persists.

Proposed: identical flow; the validator prompt states the same contract the DM and
the code already have - container movement is storageInteraction's sole domain;
character-to-character handoff is two updateCharacterInfo and never a storage
action - so the DM's correct first candidate is accepted and the writer is reached.
No code, schema, model binding, store, flag or new call.

### Selected approach: restore contract coherence in the validator prompt (task-1)

Edit prompts/validation/validation_prompt_compressed.txt only at these anchors,
preserving each edited line's existing EOL byte-for-byte (the file is mixed:
181 CRLF / 56 LF lines; line 54 is LF, lines 162-179 and 218-237 except 221 are CRLF;
wholesale EOL churn is an automatic FAIL under NEQ-OPS-01):

1. Replace line 54 (@ACTIONS.storageInteraction) with (single line, LF):
   `storageInteraction: ONLY for items moved between a character and a player
   storage container at a location (store/retrieve/create/view); it owns that
   container movement, so REJECT a duplicate updateCharacterInfo for the same
   stored items; a distinct fee update may precede it. NEVER for handing, giving,
   trading or sharing items between characters (player or party NPC): that is
   updateCharacterInfo per character (@CLARIFICATIONS 17) and a storageInteraction
   proposed for it is INVALID (no container is involved; it cannot perform the
   requested giver-to-receiver movement)`
2. Append to @CLARIFICATIONS after line 234 (CRLF):
   `17:Character-to-character item handoff = EXACTLY TWO updateCharacterInfo actions
   (remove N from giver, add N to receiver, delta language, exact item as on the
   giver's supplied sheet); never storageInteraction, never one-sided, never demand
   a container. A container operation followed by a handoff of the retrieved items
   is two distinct movements and needs both`
3. Add two @VALIDATION_EXAMPLES entries after line 166 (CRLF):
   `true_character_handoff: {"valid":true,"reason":"Giver removes N of an owned
   item and receiver adds N via two updateCharacterInfo actions; no container
   involved"}`
   `false_handoff_as_storage: {"valid":false,"reason":"Character-to-character
   handoff proposed as storageInteraction. No container is involved; use two
   updateCharacterInfo actions: remove from giver, add to receiver"}`

Edit prompts/validation/validation_prompt.txt (the non-compressed sibling loaded
when COMPRESSION_ENABLED is false) so both validator texts carry the identical
contract (Single-Path: one behavior, two loaders of one rule; pre-existing pair):
4. After line394 (last sub-bullet of rule12, CRLF) insert rule13 with the same
   content as item2 above; do not renumber existing rules.
5. In the STORAGE TRANSACTION VALIDATION block after line 792 (LF) insert one line:
   `   - A character-to-character handoff is never a storageInteraction; require two
   updateCharacterInfo actions (remove from giver, add to receiver) and REJECT a
   storageInteraction used for it`.

Not changed: prompts/system_prompt*.txt (the DM already holds the correct contract
and emitted it 2/2 times; AP-5 needs an observation that THAT path failed - none),
schemas/*, storage_processor.py, storage_manager.py, action_handler.py, main.py,
updates/update_character_info.py, model_registry.py, config. Zero Python hunks.

Wording constraints honoured: no item names, no character names, no code-side
keyword list, no model-input/output cap, no provider branch, no new action, no
"default" behaviour. The verb examples mirror the existing DM contract; EXACTLY
TWO is the existing pairwise action shape, not a context or response-length cap.
The rule names the STRUCTURAL fact code already enforces (a container is the only
thing StorageManager can move items to or from), which is exactly the fact the
referee lacked.

### Alternatives considered and rejected

A. Relax the validator by deleting line 54 entirely. Rejected: AP-2/GL-1 - it drops
   the real goal that a stored-item movement must not be double-applied by a
   duplicate updateCharacterInfo (the b7f7a863 goal). Preserved instead.
B. Teach T049/StorageManager to perform character-to-character transfers.
   Rejected: AP-4 (no mandate), frozen schema enum change (NEQ-SCHEMA-01), creates a
   second transfer authority beside the character writer (NEQ-LEDGER-09), and the
   unmerged branches show the size of that road (+5416 lines).
C. Add a deterministic pre-validator that rewrites storageInteraction into two
   updateCharacterInfo when the description "looks like" a handoff. Rejected: AP-7
   prose parsing, AP-6 code inventing meaning; exactly the verb-list scar (Part 6 S3).
D. Add a typed `transferItem` action with a code-owned two-sheet transaction.
   Considered the eventual right boundary if per-character writes prove unable to
   conserve; NOT chosen now: AP-4 requires the observed failure it answers, and the
   observed failure here is routing, not a two-write conservation loss (the only
   observed conservation loss is #358's identity no-op). Recorded as a tracked
   possibility under #358/#360 outcomes, never silently included.
E. Make the storage execution failure return status "error" so the existing
   SAFE_ACTION_FAILURE_MESSAGE fires (one-line classification, action_handler.py
   :4435-4441). Sound and small, but it changes failure semantics for genuine
   container operations and cannot be reached in live acceptance without a real
   storage failure (no fabricated responses, NEQ-TEST-02). Surfaced as owner
   question Q-363-B; default disposition: separate issue (below), not silent inclusion.
F. Change the DM prompt to prefer storageInteraction for all transfers (make the
   contracts agree the other way). Rejected: the code cannot execute it (root cause
   item 5); would institutionalize the fictitious chest.

## Behavioral contract for the replaced line (GL-1) and lineage

| Deleted/replaced text | Origin | Goals | Disposition |
|---|---|---|---|
| validation_prompt_compressed.txt:54 "sole store/retrieve item-transfer authority; REJECT duplicate updateCharacterInfo for those items; a distinct fee update may precede it" | b7f7a8631 (2026-08-24, fix(travel): make agentic transitions recoverable; no linked issue number in the message; companion long-form wording at validation_prompt.txt:791-792 and DM wording at system_prompt_compressed.txt:19 landed in the same commit; storage fee ordering lineage abdeafbd7 2025-08-29) | (1) storageInteraction owns stored-item movement; (2) reject a duplicate updateCharacterInfo for the SAME stored items; (3) a distinct fee update may precede it | PRESERVED: all three phrases retained verbatim in meaning in the replacement line (task-1 item 1); proving check D2 (both files contain each goal phrase) plus acceptance A3(i) (genuine container operation still accepted, duplicate still rejected when emitted) |

No Python, schema, lock, retry, ordering, fsync or persisted field is deleted.
FS-1 grep of the candidate diff is expected empty (prompt text contains no
timeout/attempt/max_tokens tokens; the No-Limits scan must be pasted raw over the
two touched prompt files and will show existing "[:" only if present - none found
at review: grep -nE '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat'
over both files returned no hits). Single-Path minimum:
`grep -nE 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback'`.
Pre-existing bounds NOT touched and disclosed for the
Fail-Forward seat: storage_processor.py:280 `max_attempts = 3` on the ordinary
storage path (unbounded only under structural_reissue on the travel path) - tracked
under #324's bounded-exit family, PRE_EXISTING_OUT for this plan; its log label at
:380 prints `attempt + 1` (off by one: "succeeded on attempt 2" was attempt 1) - fyi.
The ordinary effects lease (core/managers/effects_runtime.py:106-112) has an inherited 30-second
busy-to-refusal edge (#324/#202). The enclosing turn stops after five retryable
provider failures (utils/provider_errors.py:338/353, main.py:10591-10602; #240 lineage),
now separately filed as #367. Neither is endorsed or repaired by this prompt fix.

## Scope boundaries (separate issues stay separate)

- #358 (writer identity: T079 "Arrows" vs sheet "Arrow"; updates/update_character_info.py
  :1585-1591 standard plural names; :1726-1733 delta rule; merge_ammunition_arrays
  :595-648 exact-lowercase key, unknown negative dropped, unknown positive appended).
  After task-1 the handoff reaches this writer; on the observed fixture the giver
  side would silently no-op and the receiver side would append a second ammunition
  entry - non-conservation OBSERVABLE in #363 acceptance but OWNED by #358. See
  Q-363-A. This plan does not edit the writer, its prompt, or its merge.
- #360 (publication of success narration before writers succeed). Not touched; the
  storage handler's "continue"-on-failure (root cause item 6) is a distinct entrant
  that #360's action-result-boundary trace must include - filed as issue draft below.
- #359 (DM projection lacks NPC ammunition). Not touched.
- #324 (writer/validator context caps and bounded exits) owns the T049 3-attempt exit.
- #276/#262 caps, #326/#190 canonical naming: untouched.
- T109/slice pipeline: not on main; nothing here depends on it or revives it.

Doctrine drift to report (R12, NEQ-DOC-01; not resolved here): #193 p6 NEQ-INV-02
cites "Resolution seam: T109 (core/ai/inventory_resolver.py,
utils/inventory_resolution.py)". `git ls-tree -r origin/main` has neither file; they
exist only in efd0075a (slice-prototype) and ffb8f8a0 (fix/storage-two-action-loss),
neither an ancestor of origin/main. The live inventory authority on main is the table
above. Ledger row 363-D1 escalates a #293 documentation item; this plan neither
implements nor cites T109 as authority.

## Implementation slices AFTER approval (allowlist)

C0 Re-capture live branch/HEAD/ancestry and #193 updatedAt; STOP on mismatch with
   this plan's pins or on any later owner ruling touching inventory/validation.
   Confirm the two validator files are byte-identical to the planning hashes
   (7d083c8a1fb7ce58..., 9ff3e5cd094a2db9...). Preserve the private B/A2 captures.
C1 Edit exactly two files: prompts/validation/validation_prompt_compressed.txt and
   prompts/validation/validation_prompt.txt, per task-1 items 1-5, ASCII only,
   per-line EOL preserved (edit as bytes; verify with `git diff --stat` = 2 files and
   a byte-level EOL count unchanged except the inserted lines).
   FILE ALLOWLIST: those two prompt files plus this plan document and, at execution
   close, one acceptance evidence document under docs/audits/. Nothing else.
C2 Development checks D1-D4, simplifier pass (no-op expected: prose only), raw
   sentinel scans pasted, independent non-author post-implementation audit
   (NEQ-REVIEW-15 five points).
C3 Serial native real-OpenAI acceptance A1-A6 with the Player-Experience seat on the
   transcript; honest PASSED/FAILED/NOT-REACHED per row; no mid-run repair.
C4 Evidence and owner presentation. Commit/push/merge/closure are separate owner gates.

## Focused development checks (not gameplay proof)

D1 Byte checks: both edited files ASCII-only; EOL histogram unchanged except the
   inserted lines match their neighbours' EOL; no tab/Unicode; diff touches only the
   named anchors.
D2 Contract-coherence check (deterministic text assertions, local untracked test or
   shell): both validator files contain each preserved goal phrase (container
   movement authority; duplicate-updateCharacterInfo rejection for stored items; fee
   may precede) AND the handoff rule (two updateCharacterInfo, never
   storageInteraction); the DM prompts' @INV&CURRENCY.transfer / CRITICAL ITEM
   TRANSFER RULE unchanged (hash equality with planning hashes 10f1013fe44059fe...,
   f546daae8cf31b3d...).
D3 Loader check: statically trace main.load_validation_prompt selection of the
   edited compressed text under COMPRESSION_ENABLED=True and long text under False;
   do not import main or simulate a player. Runtime proof is the actual native
   T065 request. A recorded real T065 request from the B captures may be
   re-assembled with the new MSG[0] to verify assembly/size only - never to claim a
   verdict (NEQ-TEST-02, Part 6.6).
D4 Sentinel greps pasted raw over the diff and both files: No-Limits pattern and
   Single-Path pattern; py_compile/pyflakes trivially N/A (zero .py hunks) - stated,
   not skipped.

## Native acceptance and negative controls (real player layer, serial, one at a time)

Environment: native Windows, Python 3.12, configured real OpenAI provider, registry
bindings unchanged (T067 luna/none, T065 luna/low, T049 luna/none, T079 per registry)
verified at run start. Record model labels from their actual sinks: T067/T065
master api_calls_master.jsonl `model` (main_dm/validation); T079
character_updates_log.json `model_used`. ALL THREE have fallback ambiguity:
core/ai/api_client.py:244-246 and utils/capture/live_provider_call.py:692/1005
can substitute the requested model, and update_character_info.py:1904 can use
config. A logged label alone is NOT proof of the provider-returned model. Record
the label and its source separately; mark response.model UNKNOWN/reported-or-fallback
unless raw response or a complete non-fallback provenance trace proves it was
provider-returned. Do not infer served model from equality with the request label.
T078 has no persisted success-model sink on this baseline.
Missing/unverifiable returned model is explicitly UNKNOWN, never replaced by the
requested model or selection label. Disclose that evidence limit to the owner;
no telemetry repair or evidence waiver is implied. Fresh short source
export from the reviewed commit with its prompt directory copied fresh (miss-log
2026-09-04: record sha256 of every prompt file as loaded and match the checkout;
never reuse a fixture's stale prompt dir). Fixture: an authentic saved game with a
party of at least two companions whose canonical sheets list, for the giver, an
item with quantity >= 2 (equipment[] or ammunition[]); chosen from the actual
fixture at execution and named in the evidence, never hard-coded in product text.
Verify both multi-model capture enablement and capture_config.json enablement at
run start. A T079 capture present for the tested turn is the positive control for
absence-of-T049 evidence; missing captures mean NOT-REACHED for that evidence row,
never a zero-call PASS. Snapshot every sheet and player_storage.json before and after each operation (sha256
plus full JSON diff). Player inputs are ordinary natural sentences; no model output,
dice, or state is injected. Control arm at the original setting = the B run (E2/E4)
and the A2 run (E7) already on record; no additional original-setting arm is needed
for the claim "the validator line permits misrouting" - and no claim "always" is made.

A1 Ordinary companion -> companion handoff (the #363 turn shape). Assert, with the
   #193 evidence block per call: (1) T065 first verdict on the DM's first candidate,
   capture entry and line; (2) accepted actions contain exactly two
   updateCharacterInfo (giver, receiver) and zero storageInteraction; (3) no T049
   capture entry is written for the turn (positive control above); paste the
   actual "Separated into N character updates and M other actions" log (N=2),
   and count "Processing storageInteraction action" in the turn's protocol/log
   window (zero, grep pasted). That same marker must be positive in A3(i), else
   the log-negative assertion is NOT-REACHED, not PASSED; (4) both
   writer calls reach updates/update_character_info.py (T078/T079 captures present);
   (5) on-disk: giver item quantity decreased by N, receiver increased by N under the
   SAME exact item identity string, other fields unchanged in value (full diff
   pasted). Existing repair_character_data additions and ammunition-array sorting
   are recorded separately as normalization, not silently omitted or attributed to
   this prompt edit; unexpected value loss/change is FAILED and investigated;
   player_storage.json unchanged; (6) delivered narration verbatim beside the disk
   diff - the counts it states must equal disk, else the PX seat records a TRUTH
   failure; (7) next prompt usable. If (5) fails because the writer produced a
   different identity than the sheet (silent no-op and/or a second entry), record
   rows 1-4 by their own outcome and row 5 as FAILED attributed to #358 with the T079
   capture cited - never relabeled, never repaired mid-run (Q-363-A). An accepted
   correct candidate followed by an incorrect writer quantity with matching identity
   is a separate writer failure; capture and file it, do not relabel it as routing.
A2 Player -> companion and companion -> player handoffs (the PC is a partyMembers
   string, companions are partyNPCs entries; distinct role/projection through the
   shared path resolver). Same
   assertions as A1.
A3 Negative controls (gate polarity, NEQ-ACCEPT-02):
   (i) Genuine container operation at the current location: the player stores an
   owned equipment item "in a chest here", then retrieves it. Referee must ACCEPT a
   storageInteraction; StorageManager must create or use the actual container and move the item
   (player_storage.json diff, sheet diff); retrieval reverses it. If the DM also
   emits a duplicate updateCharacterInfo for the same stored item, the referee must
   REJECT that duplicate (if the DM never emits one, that branch is NOT-REACHED).
   Paste the positive "Processing storageInteraction action" marker count to
   establish the A1 log assertion's polarity.
   (ii) Unowned or excess handoff: the player orders a handoff of more than the
   giver's sheet holds. Expected: in-fiction refusal or referee rejection with no
   mutation on either sheet and the game continuing (B1: refusal as narration).
   If accepted then over-applied, record FAILED, both sheet diffs and the exact
   boundary where quantity changed. The existing merges can drop an overdrawn stack
   (update_character_info.py:590-591/639-641); if that mechanism fires, file the
   separate conservation defect, not a task-1 success or an invented new prompt task.
   (iii) Inventory query without change: no updateCharacterInfo, no storage call.
   (iv) If the DM naturally proposes a storageInteraction for a handoff, the referee
   must reject it with the two-action correction and the corrected candidate must
   pass; if it never happens, record NOT-REACHED (no fabricated candidate).
A4 Truthful failure: cannot be forced legally. If any writer fails during A1/A2, the
   existing SAFE_ACTION_FAILURE_MESSAGE must be delivered and later siblings not
   applied; otherwise NOT-REACHED. Check the failing sheet for a partial write.
   Do not claim cross-sheet atomicity: an earlier sibling may already have committed
   (main.py:6598-6628). If the giver changed but the receiver did not, record the
   handoff's conservation verdict FAILED, file the separate two-sheet commit gap
   with captures/diffs, and retain the independent routing verdict. No rollback
   machinery is added to #363, and this failure never becomes a blanket PASS.
A5 Save after a completed handoff, one intervening ordinary turn, Load: both sheets
   show the transferred quantities after Load; displayed history matches disk;
   controls truthful during Save/Load (existing #355 behaviour, not re-certified).
A6 Repetition for stability evidence, not determinism claims: at least three distinct
   handoffs across A1/A2 (different giver/receiver pairs or items). Report the
   first-candidate acceptance count as a plain fraction; a single referee rejection
   of a correct two-action candidate is a FAILED row for task-1, not noise.
PX seat (standing): reviews every transcript for second-person address, no invented
   rolls, no private review/"records" language leaking into companion dialogue
   (E8/#359 class stays separately tracked), five TRUTH-TO-DISK spot checks.

Attribution for A1-A4: every row has verdict, evidence, and owning boundary. Failures
after correct routing remain FAILED at their own layer (#358 identity, #359 missing
projection, #360 narration, #364 silent storage failure, #366 ammunition lookup),
never hidden by a routing PASS. Any newly observed independent defect is filed,
not fixed mid-run. The final report separates routing, conservation, and player
truth; it does not certify end-to-end transfer safety from prompt coherence alone.

Evidence block per call (NEQ-EVIDENCE-04): callsite ID, response.model or explicit
UNKNOWN with the sink/provenance limit above, latency
relative to the input timestamp, capture file/index/line, parsed request keys
carrying the contract (T065 MSG[0] sha256 and the candidate actions[]), player text
verbatim, degrade/fallback/invalid event count with the grep used, fixture provenance
(distinct sheets, party assembled through play, prompt hashes as loaded).

## Review protocol and applicability

Triage: FULL. Trigger: replacement of a play-path contract line (GL-1 tripwire on
deletion/replacement) and a player-visible surface, although the diff is prose-only,
< 50 lines, zero .py hunks, FS-1 clean, no schema/lock/threading/persisted format.
Escalation is one-way; the owner asked for the full plan (D-357-4).

Seat applicability (each seat re-verifies in current code; a bare N/A is rejected):
- Architecture Custodian: AP-1..AP-7 on a prose contract; wrong-layer check (fix at
  the classified layer, NEQ-OPS-02); doc reconciliation (no schematic changes; the
  #293 p6 drift row); leanness tests (b)/(c) if no Leanness seat: no gate added,
  no recovery added.
- Fail-Forward DA: B1/B2 verbatim; traces the unbounded correction loop (main.py
  :10521-10545) to its player-visible terminal state with the new contract; names
  the pre-existing T049 max_attempts=3 and its exhaustion branch (needs_response,
  :4412-4419) as PRE_EXISTING_OUT; confirms no busy->refuse class is introduced.
- Acceptance DA: owns A1-A6 verdict taxonomy and negative controls; artifact-or-
  HYPOTHESIS on every claim; one operation at a time.
- Consumer/Compat DA: the validator prompt is a shared primitive consumed by T065 on
  every provider; checks both loader branches, LM Studio strict-template tail
  unaffected (prose only), no schema or save-format change; real-save compat scan
  not applicable to a prompt (state why, do not skip).
- Legacy-Contract DA: runs GL-1 on the replaced line (table above); two-strikes
  check: this is the first fix for this symptom; #344's referee amendment (D-344-2)
  was a different rejection class (false-unknown), not a prior fix of routing.
- Player-Experience DA: conditional (player-visible narration/truth) and standing on
  acceptance transcripts; contract lines (7) truth to disk and (5) failure is a
  scene, not silence, apply.
- Leanness DA: conditional trigger not met (no new symbol, mechanism, guard, config,
  or >200 lines); Custodian carries (b)/(c). If dispatched anyway, the zero-callers
  audit is vacuous (no symbol) - state it.
- No-Limits Sentinel and Single-Path Sentinel: standing; must paste raw scans of the
  candidate diff plus both touched prompt files; the compressed/long validator pair
  is a pre-existing loader selection (COMPRESSION_ENABLED), not a new parallel path -
  disposition to be written explicitly, not assumed.
- Conditional gates: Schema-Freeze (confirms zero schema edits; storage enum
  untouched), Platform/Provider (prompt consumed on all providers; acceptance on the
  default provider only - disclosed limit), Hygiene (ASCII, EOL bytes, no tracked
  test modification, no git add -f), Limits Gate (no numeric bound in diff).

Reviewers receive this plan path, the resolution ledger, live #193 and current
source; never the author's reasoning or another seat's draft. Convergence completes
review only; the owner approves execution after presentation (NEQ-REVIEW-13).

## Scope recommendations for post-review owner approval

Default proposal is the narrow prompt-only task. Separate defects have already
been filed under the standing no-scope-creep rule. Q-363-A/B explain the alternatives
for the owner's plan review; they do not authorize expansion or block review of
this narrow proposal. Execution of even the narrow proposal awaits owner approval.

Q-363-A - #358 inclusion for end-to-end conservation proof. The #363 acceptance can
prove routing, writer reach, and no fictitious chest with any owned item. Proving
"conserves quantities" on the observed ammunition fixture also requires #358's
writer-identity repair. Options: (1) keep #358 separate; A1 row 5 on ammunition is
recorded by its real outcome and attributed to #358 if it fails; conservation is
additionally proven on an item whose identity the writer reproduces exactly (an
equipment[] entry, chosen from the fixture). (2) Include a narrow #358 writer-identity
alignment in this plan (would add updates/update_character_info.py to the allowlist
and a T079 contract change; needs its own GL-1 row for the "standard plural names"
instruction f808e379 and its own acceptance). Recommendation: (1). Rationale: different
layer (T079 vs T065), different lineage, and #358 deserves its own investigation of
whether the plural instruction or the merge key is the boundary to fix; folding it
in widens a prompt-only referee fix into a writer contract change.

Q-363-B - storage execution failure never reaches the ordinary action-failure
boundary (root cause item 6). Options: (1) file as its own issue (draft below) and
let #360's action-result-boundary trace absorb it; (2) include the one-line status
classification here. Recommendation: (1): after task-1 the #363 path no longer
reaches storage, the change alters genuine container-failure semantics, and it
cannot be exercised live without a real storage failure.

363-D1 (documentation, non-blocking for execution): #293 entry for the p6
NEQ-INV-02 T109 seam reference that does not exist on main (draft: "NEQ-INV-02 names
core/ai/inventory_resolver.py and utils/inventory_resolution.py as the resolution
seam; neither is on origin/main (efd0075a slice-prototype, ffb8f8a0
fix/storage-two-action-loss, not ancestors). Owner to rule: mark the seam as
unmerged design or re-point p6 to the live path: T067 two-action proposal -> T065 ->
update_character_info.py writer; storageInteraction -> T049 -> StorageManager for
containers only.").

## Tracked follow-ups

Controller filing update: issue draft1 is now #364; draft2's forced-store/chest
mechanism is #365, and its distinct ammunition-array omission is #366. All are
separate, not implementation tasks here. The #193 pointer drift was posted to
#293 comment5643401181; no policy or runtime change is proposed by this plan.

- #358: writer identity no-op (Arrow/Arrows) - separate; A1 row 5 attribution rule
  above; Q-363-A.
- #360: success narration persisted before/without writer success - separate; the
  storage handler "continue" entrant is filed for it (issue draft 1).
- #359: DM projection lacks NPC ammunition - separate; E8 evidence added there if the
  owner wants the #363 capture indices recorded.
- #324: T049 bounded 3-attempt exit and log label off-by-one - separate; fyi rows.
- #367: enclosing turn abandons retryable provider work after five failures;
  CODE-PROVEN only, no attribution to this incident; no change here.
- Issue draft 1 (to file the same turn if Q-363-B = option 1): "storageInteraction
  execution failure returns status continue and never reaches the ordinary
  action-failure boundary". Body: CODE-PROVEN action_handler.py:4435-4441 appends a
  user-role "Storage Error" line and falls to :4771 status "continue"; main.py:6674
  therefore never emits SAFE_ACTION_FAILURE_MESSAGE and later siblings run
  (OBSERVED C:/357-ev-pAaw3B/B protocol L523-L528: failure then "Updating plot
  progression...", zero player-visible notice between L489 and L642; persisted
  history indices 33/36). Contrast: updateCharacterInfo failure returns "error"
  (:3837-3845); storage processor failure returns needs_response (:4412-4419). Ask:
  one failure semantics for the storage action family inside #360's action-result
  boundary; no new store, no prose parsing, no retry cap.
- Issue draft 2: "T049 cannot say 'not a storage operation' and defaults a
  non-container request to store_item plus an invented chest". Body: CODE-PROVEN
  storage_processor.py:159/167/176/263-267 and schema enum; OBSERVED T049.json[0]/[1]
  in C:/357-ev-pAaw3B/B converting a character-to-character description into
  store_item with storage_type chest at the party location; StorageManager reads
  equipment[] only (:142-172) so ammunition can never be stored or retrieved; had
  the name matched an equipment entry the item would have entered an invented
  container. Ask: with #363's referee fix in place, decide whether T049 needs a typed
  "not_storage" outcome (schema exception, owner-gated) or whether the referee
  contract is the sole guard; no synonym/verb heuristics.
- Possible future boundary (no issue yet; AP-4 needs the observation): a typed
  two-sheet transfer commit if #358/#360 acceptance shows per-character writes cannot
  conserve even with correct identity. Record only.

## Resolution ledger

Review status: COMPLETE. All eight independent R3 seats returned no blocking
findings on SHA5c9c786a8fa373e0d22f63e3723eabdbcfed343990fac4bac9e75d8f9d29dcdf,
including Acceptance's source verification closing AC-7. The sole new R3 finding
is cosmetic NL-4 (missing utils/ in a citation), fixed inline below. Apply
NEQ-REVIEW-11 plan-polish termination: full-coverage R3 completed, all previous
task/test corrections re-verified, no code-class correction outstanding, only
citation/ledger changes now. No further ceremonial dispatch required. Reports:
/mnt/c/agent-room-fleet-kit/local-data/363-r3-<seat>.md (custodian, failforward,
acceptance, compat, legacy, px, limits, singlepath). This completes PLAN review
only: no product files changed, no acceptance run, no implementation approval.

History: R2 full eight-seat review completed on SHAe1aaf9f0. Seven returned
no blockers. Acceptance confirmed all raw E1-E8 evidence and previous corrections,
but found the returned-model fallback also exists upstream for T067/T065; that
remaining evidence task was corrected and subsequently verified by full R3.
R2 also corrected its own earlier claim that the old StorageManager prefix never
appears: it DOES appear dynamically in B (24 lines), so the old assertion was
unreliable, not universally vacuous. The source-specific marker and positive
polarity remain correct. No product scope or task-1 wording changed. R2 advisory
notes are logged below; none adds a test or task. No convergence claimed yet.

History: resumed full eight-seat R1 completed on SHA4040dcb4. Seven seats
returned no blocking findings; Acceptance blocked on the vacuous log assertion and
missing model-evidence attribution. Controller independently verified the actual
storage marker in source AND the failing B capture (protocol lines499/500,881/882),
the sequential write boundary, README citation and model sink caveats. Revisions
below change TEST assertions/evidence, not product scope: classify as task/test
changes, NOT polish termination. Full same-plan re-review still required before
convergence; no implementation authorization. Reports: local-data/363-r1-<seat>.md
(custodian,failforward,acceptance,compat,legacy,px,limits,singlepath).

|ID|Finding or decision|Disposition|
|---|---|---|
|363-F1|Compressed validator line 54 lost the "player storage" scope and the referee applied it to a companion handoff (E2, root cause 1)|task-1 item 1|
|363-F2|Validator prompt internally contradicts itself (@CLARIFICATIONS 5/9 vs line 54) and lacks the DM's explicit two-action handoff rule|task-1 items 2-3|
|363-F3|Long-form validator must carry the identical contract or the COMPRESSION_ENABLED=False loader keeps a divergent rule|task-1 items 4-5; D2/D3|
|363-F4|Referee's error note instructed an action the deterministic layer cannot execute (NEQ-OPS-02 coherence rule)|task-1 (removes the instruction at its source); Fail-Forward seat traces the loop|
|363-F5|storageInteraction has no character-to-character capability; T049 forces store_item + chest; StorageManager ignores ammunition[] (root cause 5)|issue-#365; issue-#366; PRE_EXISTING_OUT for this fix|
|363-F6|Storage execution failure never reaches the ordinary action-failure boundary; player saw success only (root cause 6, E5)|issue-#364; Q-363-B recommends separate work|
|363-F7|Conservation on the observed ammunition fixture depends on #358's writer identity|issue-#358; Q-363-A recommends separate work; A1 row-5 attribution rule|
|363-F8|Same validator bytes accepted the same candidate in A2 (E7): fix claim must be "permits misrouting", not "always rejects"|task-A6 (fraction reported, no determinism claim); defensible|
|363-F9|Replaced prompt line carries three goals from b7f7a863|GL-1 table: PRESERVED; D2 + A3(i)|
|363-F10|Mixed CRLF/LF in both validator files; wholesale churn = auto-FAIL|task-C1/D1 per-line EOL pin|
|363-F11|#193 p6 cites T109 seam files absent from origin/main|escalate: #293/p6-T109-seam-not-on-main (363-D1); non-blocking for this prose fix|
|363-F12|T049 max_attempts=3 on the ordinary path; log label off by one|fyi: #324 family, PRE_EXISTING_OUT; untouched|
|363-F13|DM projection lacked the giver's ammunition (E8)|fyi: #359, untouched|
|363-R1|Plan/execution approval|escalate:@owner: present converged plan; no implementation authorized now|
|363-LC-1|Long-form validator evidence misquoted in first draft|fixed-inline: exact source bullets substituted; diagnosis/design unchanged|
|363-LC-2|New rule13 placement after rule9 would scramble order|task-1 item4: insert after rule12 sub-bullets, no renumbering|
|363-LC-3|EOL histogram one-line error|fixed-inline:181CRLF/56LF; per-line pins unchanged|
|363-CUST-1/2|README quote provenance; misleading "no synonym list"|fixed-inline: README actual wording, no code-keyword rule claim; proposal unchanged|
|363-CC-1/SP-3|Line221 is LF despite stated CRLF range|fixed-inline: per-line exception stated; edit anchors unchanged|
|363-CC-2|Validator loaded at startup and some re-entry callers|fyi: fresh fixture and as-sent hash checks cover actual consumer; no new path|
|363-NL-1|Sentinel pattern omitted mandatory terms|task-D4: full minimum written explicitly; re-scan at implementation gate|
|363-NL-2|Possible multi-receiver interpretation of pairwise rule|fyi: no observed failure, existing DM pairwise shape unchanged; no speculative broader contract rewrite|
|363-SP-1/2/4|Existing dual text loader, optional example parity, legacy alias prose hit|fyi: one existing rule in both files, no new selector; optional prose expansion declined; stale selector comment is not behavioral authority|
|363-LC-4|Known origin commit has no linked issue|defensible: exact origin and goals verified, not unknown provenance|
|363-AC-1|A1 searched for a log token never emitted|task-A1/A3: real marker plus positive polarity; controller verified source4385 and B capture|
|363-AC-2|Unfillable returned-model field|task-evidence: real sinks when available, UNKNOWN when absent/fallback; no label substitution or telemetry fix|
|363-AC-3|Capture enablement not explicit|task-environment/A1: enablement plus within-turn positive control|
|363-AC-4/FF-3/PX-1|Excess handoff can over-apply; downstream failure attribution incomplete|task-A1/A3: keep FAILED at owning layer, file newly observed gap; no scope expansion|
|363-AC-5|Byte-identical overconstraint and writer absolute/delta distinction|task-A1: full value diff, disclose normalization and independent arithmetic failure|
|363-AC-6|PC/NPC path wording|fixed-inline: distinct role/projection, shared resolver|
|363-PX-2|Sheet-less NPC handoff hypothesis|fyi: no new proven rejection class; existing DM pairwise contract retained; not expanded to a new NPC system|
|363-PX-3|User-role storage error not replayed as player input|fyi: #364 already tracks silent failure and false-success replay|
|363-FF-1|Over-broad unbounded-loop claim|issue-#367; fixed-inline: semantic retry vs provider stop distinguished|
|363-FF-2|Inherited effects lease timeout|fyi: #324/#202, explicitly disclosed, no new timeout|
|363-FF-4|A4 promised cross-sheet atomicity not present on main|task-A4: per-sheet check plus distinct FAILED cross-sheet outcome; no implied rollback guarantee|
|363-CTRL-1|Acceptance reviewer did not open private captures|task-review: use actual /mnt/c/357-ev-pAaw3B/B and /mnt/c/344-ev-zJsssG/A2 (controller verified accessible), finish artifact verification in next pass|
|363-AC-7|T067/T065 upstream also substitutes requested model|task-evidence: all sinks now explicitly ambiguous without raw/proven non-fallback provenance; no telemetry change|
|363-AC-1-R2|Prior "never emitted" claim false for dynamic logger prefix|fixed-inline: R2 report/controller record corrects inference; actual marker/polarity test unchanged|
|363-CTRL-1-R2|Raw E1-E8 checked by Acceptance at /mnt/c paths|defensible: evidence verified; prior missing artifact read completed|
|363-FF-R2-1/2,LC-5,NL-3,CUST-R2|Dual log sinks and changing prefix inflate raw hits|fyi: raw line count is not action count; zero/positive polarity unchanged, no new test requirement|
|363-CC-3|Missing directory prefix on effects lease cite|fixed-inline: core/managers/effects_runtime.py; no behavioral/test change|
|363-CC-4|Logger may write literal unknown|fyi: UNKNOWN rule already covers unknown strings|
|363-PX-R2-1|Debug protocol flag affects marker visibility|fyi: existing protocol/log alternative and positive polarity handle it; no new test requirement|
|363-PX-R2-2|Partial transfer message may omit earlier committed loss|fyi: existing A4 transcript/diff and conditional separate-issue requirement cover it|
|363-SP-R2|No new pathway/cap, actual scans clean in proposal|fyi: standing sentinel checks repeated, no scope change|
|363-AC-7-R3|All-sink fallback caveat re-verified by Acceptance and other required seats|defensible: current evidence rule records UNKNOWN absent provider-returned provenance; no inference from requested label|
|363-NL-4|Provider-errors cite lacked utils/ directory|fixed-inline: cosmetic path prefix only; no code/task/test/callsite change|
|363-R3-CLOSE|Eight same-SHA reports, previous task/test findings verified; only cosmetic cite remained|fixed-inline: cite and review ledger stamped under NEQ-REVIEW-11 polish termination; execution remains owner-gated|

No product design ruling is presumed from the investigator; every uncited claim in
this document is HYPOTHESIS by definition (NEQ-EVIDENCE-02).
