# Issue #357: T051 armor contract must follow the frozen character schema, with agentic recovery of already-damaged sheets

## Current disposition (2026-09-11)

Implemented and native-trial reviewed; owner authorized narrow shipment in live
#193 D-357-4. The historical planning/trial-only status below is superseded by
that ruling, not erased. Evidence and explicit coverage limitations are recorded
in 2026-09-11-issue-357-armor-schema-contract-acceptance.md. The original exact
transfer recovery arm remains NOT-REACHED; the disclosed ordinary short-rest
substitute proved recovery. Inherited retry exhaustion remains #324, accepted
for this narrow shipment by D-357-4, not solved here. No #363 repair is included.

## Historical status (review converged, 2026-09-11)

PLAN ONLY. Full review converged; isolated trial direction approved, not implemented.
Final post-review presentation/GO remains under NEQ-REVIEW-13. Revision 2 replaces
the held first draft after owner ruling D-357-1 (live #193 Part 5, ratified
2026-09-11; #293 comment 5641976338): include already-damaged sheets in
#357, recover them agentically through the existing armor agent (T051) and
the existing validated commit machinery, and never let code choose a
replacement armor value, silently discard data, or loosen the frozen schema.
The first draft's task O1 (code resets any out-of-schema `dex_limit` to
null) is RETIRED from proposed execution and kept only in the failed-
approach record below (NEQ-OPS-04). Written for the supervisor's
independent check and then the FULL blind #193 Part 3 panel; execution
requires full review and presentation under NEQ-REVIEW-13. The owner has
approved the proposed isolated trial and its inherited exhaustion limitation
(D-357-2); no shipment is authorized. Q-357-A is CLOSED for this trial only.

Worktree /home/loup/neq-worktrees/357-armor-schema-contract, branch
plan/357-armor-schema-contract. Captured live at revision time: HEAD
c7ede1268a3a7faba471b583bec2b9119c8f7095 == origin/main (`git merge-base
--is-ancestor HEAD origin/main` true; re-capture at every later phase,
NEQ-OPS-01). Revision is evidence, never runtime authority. No game,
provider, prompt, schema or production file changed during planning. Full
forensics (every capture entry, protocol line, on-disk diff):
/mnt/c/agent-room-fleet-kit/local-data/357-forensics.md (private). Bounded
design advice that this revision folds in and corrects:
/mnt/c/agent-room-fleet-kit/local-data/357-repair-design-advice.md.

## Authority and spec-pin

Live #193 v3.1, policy epoch updatedAt 2026-09-12T01:14:13Z (re-check before
implementation and before any merge decision, NEQ-OPS-03). Rules applied:
- Part 1: NEQ-CORE-01 (never-broken campaign), NEQ-CORE-03 B1 (fail-closed
  only at an uncommitted mutation boundary as a no-op; the detected-
  corruption facet of fail-closed is UNDECIDED, D-7 in #293), NEQ-CORE-04
  B2 (iv)/(vii) (count-keyed give-ups need a ratified class), AP-4/AP-5/
  AP-6/AP-7, NEQ-CORE-06 (models propose typed facts; code owns validation,
  atomicity, refusal), NEQ-CORE-07 leanness tests, NEQ-CORE-10 (frozen
  contracts read from origin/main), NEQ-EVIDENCE-01..04.
- Part 2 p8 NEQ-WORLD-04 (character sheet is player data; partial write =
  corruption); p11 NEQ-PROVIDER-01; p12 NEQ-SCHEMA-01 (frozen letter is
  authority; real-file compat scan; blocking-vs-diagnostic trace; existing
  games keep loading forever) and NEQ-SCHEMA-02 (preserve-then-override;
  acceptance diffs every non-empty -> empty transition); p13 NEQ-ACCEPT-01/
  02/03 and NEQ-TEST-02.
- Part 3 whole protocol; Part 5 NEQ-LEDGER-03 (compat is automatic live
  code), NEQ-LEDGER-07(a) (ratified bounded classes: T051 is NOT among
  them), NEQ-LEDGER-08/09, Fork-3 (loud failure, never DEBUG), D-LCR-1
  (lazy on use, one atomic write, no sweep), D-VS-6 (precedent: detected
  corruption of companion memory on Load is REPAIRED, never refused --
  companion-memory facet only, cited as precedent not authority), D-323-6
  (precedent: null as an explicit contract value), D-344-3 (#349 and
  #357-#360 stay separate), D-357-1 (this plan's mandate; it explicitly does
  NOT rule on provider failure policy or lock semantics).
- Part 6.6 NEQ-LEAN-04: a deterministic test whose subject imports network/
  LLM seams is out of bounds; recorded real responses may test parsing or
  dispatch only; expectations come from the schema, never from current
  output.
- Issue #324 (open, no ruling) owns the writer/validator bounded exits and
  the 30 s effects lease; its 2026-09-10 comment says the ordinary post-
  commit advisory validation must not be promoted into a mandatory pre-
  commit approval dependency without #193 review of those semantics. This
  plan's recovery entrant is designed against that sentence (section
  "Failure edges") and is the subject of Q-357-A.
- #148 owns the Gemini nullable-conversion mismatch (T051 inline-schema
  evidence posted as #148 comment 5639783067). #356 owns the effects-runtime
  `max_attempts=1` kwarg mismatch. #358/#360 own the ammunition-name no-op
  and narration-before-failure. None are repaired here.
Schematics: docs/architecture/progression-leveling.md flow step 16 / seam
15 describe the T079 boundary and say "Post-save smart validators may apply
a second atomic correction" (line 39) without noting that the correction is
schema-checked or that a pre-gate correction exists; task S3 reconciles that
sentence. provider-routing.md covers the T051 binding; no binding change.
README promise advanced: "Party Management - Recruit NPCs, manage
equipment" and "Save/Load System - Automatic progress saving with backup
protection" (README.md:218-224): a character must stay updatable after an
ordinary heal, including a character whose sheet was damaged by the old
guard. Promise that must not degrade: "SRD 5.2.1 Rules Engine" -- AC/armor
interpretation stays with the model; code adds no armor rule.

## Canonical definitions (spec-pin)

- Identity: a character sheet is `characters/<normalized_name>.json`
  (player) or the module NPC path, resolved by
  update_character_info.get_character_path.
- Source of truth per datum: `equipment[].dex_limit`, `ac_base`, `ac_bonus`,
  `armor_category`, `stealth_disadvantage`, `equipped` = the character
  JSON, constrained by the frozen equipment item subschema
  schemas/char_schema.json (equipment.items.properties: dex_limit
  {"type":["integer","null"],"minimum":0,"maximum":10}; ac_base integer
  0..30; ac_bonus integer -5..10; armor_category enum light/medium/heavy/
  shield/other; equipped and stealth_disadvantage boolean). `armorClass` =
  character JSON integer, value proposed by T051/T053 (model-owned
  arithmetic). The meaning of null/0/N in dex_limit is a data convention
  reflected by core/ai/inventory_context_matcher_v2.py:257-261 (non-null
  renders max-N; null omits that clause). That reader does not itself prove
  unlimited Dex or compute AC; interpretation stays agentic.
- T051 = AICharacterValidator.ai_validate_armor_class_with_result
  (core/validation/character_validator.py:1880-2005): projection
  extract_ac_relevant_data (:1044-1207; every item with item_type armor,
  "armor"/"shield" in the name, or an ac_base/ac_bonus field, carrying the
  five armor fields verbatim, :1134-1136), cache check (:1902), provider
  call, parse (:2332-2500: changed-only equipment delta keyed by source
  item_name), merge with deep_merge_dict/merge_equipment_arrays
  (update_character_info.py:516-593; per-item merge by exact item_name,
  every other field preserved), cache store of the merged projection hash
  (:1979-1982), result. It writes nothing but the validator cache file.
- T051 entrants (all funnel through :1880 and the two cache checks :1685
  and :1902): (a) post-commit smart validation, update_character_info.py:
  2271-2281 -> validator :1720 check_validation_needs -> :1748; (b) party
  parallel validation, update_character_info.py:2619/2632 -> validator
  :1810/:1834 (dormant: no external production callers); (c) the effects/prepare
  entrant core/managers/effects_runtime.py:262, CODE-PROVEN unreachable
  today because of the #356 kwarg mismatch (TypeError -> receipt
  "attempted_unavailable"); (d) NEW in this plan: the pre-gate recovery
  call inside `_update_character_info_unlocked` (task S2). Direct storage
  at storage_manager.py:428/:578 uses validate_character_file_safe (:2834)
  and T053 (no six-field armor writer). Staged storage :796 cannot reach
  T053 because of the sibling unsupported-keyword defect tracked in #356.
  The observed ordinary entrant is effects_runtime.update_character_with_effects
  :97-132 (lock -> lease -> T078 -> _update_character_info_unlocked); S2
  covers it, and acceptance records T078 as well as T051/T079.
- Commit points: T079 path commits at update_character_info.py:2215 after
  the whole-sheet jsonschema gate (:2144) and repair (:2178) under the per-
  character lock and effects lease (:1323-1358); prepare_only returns a
  receipt at :2180-2188 (before = disk snapshot :1423, after = merged
  sheet) that core/managers/effects_runtime.py:279-294 applies only when
  disk == before (else "blocked_conflict") or recognises when disk ==
  after; post-commit validator corrections commit at :2287; storage-path
  corrections at character_validator.py:2870.
- End states: T079 success = one atomic replace; T079 refusal = attempts
  exhausted (unratified bound :1785, #324), revert, `False`,
  SAFE_ACTION_FAILURE_MESSAGE (web/shared_state.py:19); T051 exhaustion =
  FAILED result (unratified bound :1941, #324), callers fail open (post-
  commit WARN :2296-2308, storage WARN :2848-2853). None of these bounds or
  terminal statements change; see "Failure edges" for what the new path
  inherits and Q-357-A.
- Lock order and currentness: character update lock -> effects lease (30 s
  busy-refusal branch :1339-1346, #324 flagged not added); the sheet is
  read once under the lock (:1412) and replaced under the same lock. The
  effects/prepare entrant (effects_runtime.py:249-256) runs
  `_update_character_info_unlocked` lock-free with structural_reissue=True
  and prepare_only=True and relies on the before/after comparison at
  apply. Unchanged.
- Platform/provider/model at evidence: native Windows game process, OpenAI,
  T051 bound OPENAI_GPT56_LUNA_NONE (model_registry.py:376-383; observed
  capture key `selected|gpt-5.6-luna|none`), T079 per registry. Re-verify
  at execution.

## Evidence and root cause (summary; artifacts in the forensics file)

E1 OBSERVED (two independent native runs, five validations; independently
re-verified by the controller on 2026-09-11): whenever the T051 projection
carries `dex_limit: null`, the model's first structurally clean answer
echoes null unchanged; character_validator.py:2464-2471 rejects it ("must
be numeric"); the retry message names no legal range; the model then
invents a number to satisfy the code: 99 (Dain, A2 entry 5 a1becb16 and C5
e07d0c35), 0 (Torvald's Shield, fb5541f1 and a08313fd), 4 (Bren,
aafb08fd). 99 violates the frozen maximum of 10 and is written unchecked at
update_character_info.py:2287; 0 and 4 are schema-valid but semantically
questionable and silent. Draft7 polarity independently confirmed: null
accepted, 99 rejected; authentic prompt-130 snapshot validates, prompt-809
fails only on equipment[1].dex_limit.
E2 OBSERVED: the next ordinary T079 update for Dain (arrows +5, three
identical valid deltas 5fe79c93/9f491d87/ce49db2b) was refused three times
by the whole-sheet gate on the pre-existing equipment[1].dex_limit 99
(protocol L2984/L2995/L3006), reverted, and surfaced as the generic failure
after narration had already promised 24 arrows (#360). Precise statement of
the block: an ordinary update whose delta leaves the invalid value in place
is refused before commit. A T079 delta that itself rewrites the invalid
field could pass the gate (CODE-PROVEN possible, never observed); there is
no guaranteed or automatic recovery, and the observed ordinary update did
not recover.
E3 CODE-PROVEN: no self-heal exists on the observed path. The cache stored
the poisoned merged hash as validated (:1979-1982); the smart validator
skips T051 while the projection is unchanged (:1902-1916); the post-commit
T051 (:2271) is never reached when the gate refuses. T053 writes armorClass
only; the effects entrant is broken by #356.
E4 OBSERVED on disk: 87 character FILES on this machine carry dex_limit 99.
They are copied/saved artifacts (fixture copies and backups) of a few
character lineages -- Dain (3, #344 runs) and one older Ranger Thane/Scout
Elen lineage (84 files across 311/322/334 fixture roots, poisoned between
two backups on 2026-08-22) -- not 87 independent campaigns. Four NEQ
install directories sampled: zero. External prevalence: unmeasured
(HYPOTHESIS only). All 87 poisoned items are "Studded Leather" items with
item_type armor, therefore inside the T051 projection.
LINEAGE: guard 715732d5 (2026-07-17), inside a 3,190-line validator rewrite
that replaced an accept-everything parser; no incident cites the null
rejection. Schema dex_limit line a3ca76d6 (2025-06-02); ac_base line
360a9755 (2025-06-23). All are mainline ancestors.

Classification (NEQ-OPS-02): (d) deterministic-vs-agentic disagreement --
the deterministic layer contradicts its own frozen schema and issues a
demand the model can satisfy only by inventing a value or omitting the
field. Not (a): the model was right first. Not (b): prompt bytes as sent
equal the repo file and do not mention dex_limit. Fix at the deterministic
layer only.

Boundary this plan keeps: code decides only whether a proposed or merged
field value is inside the frozen schema's letter (type, enum, range,
null-ness) and tells the model exactly that letter when it is not. Which
value is RIGHT for a given armor -- null for light, 2 for medium, 0 for
heavy, whether a shield has a cap -- stays with the model, exactly as
today. No armor table, no name matching, no "99 means unlimited" sentinel,
no code-chosen replacement value, no per-character case enters code.

## Selected design: prevention plus agentic recovery through existing T051

Two deliverables, named separately because they answer different failures:
prevention (new writes; E1) and recovery of already-invalid state (E2/E3/
E4). Both use ONE schema-derived predicate and the existing T051 corrector,
retry conversation, merge and commit machinery. Net new mechanism: one
module-level helper and the field family it reads; no store, marker, flag,
format, bound, table, default value, runtime, lifecycle or binding change.

### Task A (prevention): schema-derived field check at the T051 boundary

Replace the four hand-written type guards for the six mutable armor fields
(character_validator.py:2448-2471) with one check of each present mutable
field of each returned equipment item against the frozen equipment item
subschema, read from the same schemas/char_schema.json the writer loads
(`updates.update_character_info.load_schema`, lazy-imported exactly as
`deep_merge_dict` is at :1973). The parser-local set
`mutable_equipment_fields` (:2408-2411) becomes the module-level field
family the helper reads (`_T051_ARMOR_FIELDS`, same six names, moved not
duplicated). Helper contract (`armor_contract_errors`, module level, one
new symbol, cited to E1/E2/E3, four production callers listed below):

```
armor_contract_errors(items, item_schema) -> list[str]
  for each item in items, for each field in _T051_ARMOR_FIELDS present in
  item: jsonschema.Draft7Validator(item_schema['properties'][field])
  .iter_errors(item[field]) -> "equipment '<item_name>'.<field> <err.message>;
  the character schema for <field> is <json.dumps(subschema, sort_keys=True)>"
```
Inside the existing per-item loop (after the immutable-field check) the
parser raises CharacterValidationResponseError with the helper's messages
for that item. Effects, all derived from the schema letter:
- `dex_limit: null` passes; an unchanged echo produces no equipment update
  (existing changed-only normalization :2473-2483), so Dain's attempt 2
  would have been accepted as `{'armorClass': 16}`.
- `dex_limit: 99` (or -1, 2.5, "2", true) is rejected with the schema's
  exact message ("99 is greater than the maximum of 10; the character
  schema for dex_limit is {...}"). The model chooses the correction.
- `armor_category` moves from "any string" to the schema enum; `ac_base`/
  `ac_bonus` from "int or float" to integer within bounds (Draft 7 treats
  12.0 as integer, so integral floats behave as today); boolean checks
  preserved (Draft 7 rejects 0/1/"true" for boolean and bool for integer).
  Compat scan: zero existing valid values affected.
Schema loading: once per validator instance, lazily, via the writer's
`load_schema`; if the file is missing, unreadable, or lacks
properties.equipment.items.properties, the helper RAISES a RuntimeError
naming the path. No default subschema or silent accept/reject. Inside the
T051 try (parser/S1a), failure follows its existing correction/result path.
At S1b's :1685/:1902 call sites, outside that try, it propagates to existing
caller exception handling; post-commit except :2323 logs a generic WARN at :2324 without
exception detail (pre-existing #324), not a fabricated FAILED result.
The writer itself cannot reach T051 without the schema
(update_character_info.py:1408 loads it first and raises on failure).

### Task S1 (recovery, validator side): merged-proposal validity and cache truth

S1a Merged-proposal validity. After `merged_data = deep_merge_dict(...)`
(:1974) and before `_update_ac_cache` (:1982) and the success return
(:1984): `errors = armor_contract_errors(self.extract_ac_relevant_data(
merged_data)['equipment'], item_schema)`; if non-empty, raise
CharacterValidationResponseError("T051: the merged equipment still
violates the character schema: <errors>. Return each listed item in
validated_character_data.equipment with a schema-valid value and describe
the change in corrections_made"). This is inside the existing try, so it
feeds the existing same-call correction turn (:1991-2003, "VALIDATION
ERROR: {e} ..."). Why: checking only the fields the model returned is not
enough -- if the model omits the poisoned item, the changed-only delta is
empty, the merge retains 99, and the result would be blessed as success
and cached. With S1a an uncorrected invalid source can never become a
success, a cache entry, or a persisted correction. Valid untouched player
data is preserved by construction: the merge only touches fields the model
proposed, a proposal needs corrections_made (:2488-2492), and S1a rejects,
never edits.

S1b Cache truth. `_is_ac_validation_cached` (:1404) gains the projection as
an argument (private method; its two callers :1685 and :1902 both hold
`ac_data`) and returns False when `armor_contract_errors(ac_data[
'equipment'], item_schema)` is non-empty, logging at WARN which item/field
is out of schema. A cache entry may vouch only for a projection whose armor
values are actually valid. Consequences: today's poisoned cache entries
(hash of the 99 projection) become inert without any file change or
migration; a valid projection hits exactly as today; after S1a, new entries
are only ever written for valid merged projections. No hash marker, no
provenance flag, no force/bypass parameter, no cache format change: value
validity, not a digest, decides (AP-7).

### Task S2 (recovery, writer side): pre-gate T051 for a source sheet whose armor projection is invalid

One block in `_update_character_info_unlocked`, after the existing load/repair
try/except ends (:1429), before the backup (:1432) and the T079
prompt build (:1457):

```
validator = AICharacterValidator()
projection = validator.extract_ac_relevant_data(character_data)
armor_errors = armor_contract_errors(
    projection['equipment'], schema['properties']['equipment']['items'])
if armor_errors:
    warning("VALIDATION: %s carries out-of-schema armor data; asking T051 to
             correct it before the update: %s" % (character_name, armor_errors))
    result = validator.ai_validate_armor_class_with_result(character_data)
    if result.success and result.changed:
        info("VALIDATION: T051 corrected %s before the update: %s"
             % (character_name, validator.corrections_made))
        character_data = result.data
    else:
        warning("VALIDATION: T051 could not correct %s before the update
                 (%s); continuing with the unrepaired sheet" % (...))
```
Trigger narrowness (controller concern 1): the trigger is the SAME helper
and field family the parser and cache use, applied to the T051 projection
of the loaded sheet. It does not fire on unrelated whole-sheet errors
(forensics F10: 136 files invalid at attacksAndSpellcasting/spellcasting
paths), on armor items T051 cannot see (not in the projection), or on any
valid sheet. On the working path it is a read-only value comparison and a
no-op (AP-5). A sheet invalid on BOTH an armor field and an F10 path
triggers T051, is healed in memory, and is then refused at the gate on the
F10 path exactly as today; because nothing commits, the next update repeats
the (bounded, existing) T051 conversation -- disclosed, overlap count to be
measured by the Consumer/Compat seat from the existing scan output, not
rescanned here.
Why here: the block runs before the one gate that refuses the update, on the
only path where T051 is otherwise unreachable, using the sheet already read
under the lock; the correction lives in memory, T079 prompts from the
corrected sheet (:1457-1465), the delta merges onto it (:2078), the gate
(:2144) and repair (:2178) run as today, and ONE atomic replace (:2215)
carries both the model's armor correction and the requested change (D-LCR-1
spirit: lazy on use, one write, no sweep, no marker).
Data adoption: `result.data` is the deep-merged sheet (every other field
preserved); it is adopted only on `result.success and result.changed`. On
NO_CHANGE or FAILED the loaded sheet continues unchanged and today's
refusal follows. `persisted_character_data` (:1423) remains the disk
snapshot, so the prepare_only receipt's `before` and the acceptance diff
show the 99 -> model-value transition explicitly (NEQ-SCHEMA-02); the
disk backup (:1433) still captures the pre-heal file.
No double write, no erased change (controller concern 5): the pre-gate call
writes nothing to the sheet; the requested update commits once at :2215.
The post-commit smart validator (:2271-2281) re-reads the disk; its AC
projection hash now equals the hash S1-validated and cached during the
pre-gate call (:1979-1982), so no second T051 call and no second AC write
occur on the ordinary case (`validation_result.changed` False for AC);
inventory/currency validation runs exactly as today. If T079's own delta
changed AC-relevant data, the post-commit T051 runs exactly as today.
Prepare/effects entrant (controller concern 5): the block executes inside
`_update_character_info_unlocked`, so the lock-free prepare_only call
(effects_runtime.py:249-256) also gets it; the receipt's `after` then
contains correction plus delta and `before` the disk snapshot;
apply_staged_character_update (:279-294) writes once only when disk still
equals `before`, otherwise "blocked_conflict"/"already_committed" -- no
premature write, receipts preserved, ordinary lock order unchanged. Side
effect to disclose: the pre-gate T051 writes the validator cache file
(:1982) lock-free on that entrant, as the T079 prepare already performs
lock-free provider work; the cache is validator-owned, not the sheet, and
S1b makes it incapable of blessing an invalid projection. #356 keeps that
entrant's advisory validation unreachable; unchanged here.
Lock and currentness (D-357-1 excludes lock semantics; nothing changes):
the pre-gate call runs under the same ownership as today's T079 and post-
commit T051 (character lock -> effects lease); the sheet is read once and
replaced under that lock; no new lock, no new order, no new deadline.

### Task S3 (docs): one-sentence schematic reconciliation

docs/architecture/progression-leveling.md line 39 (step 16): state that
post-save corrections are schema-checked at the T051 boundary and that a
source sheet whose armor projection is out of schema is offered to T051
once before the schema gate. Doc-only, C4.

### Failure edges, each traced to its terminal state (Fail-Forward DA input)

- Pre-gate T051 exhausts its existing three attempts (:1941, unratified,
  #324): WARN, continue with the unrepaired sheet; T079 attempts (:1825),
  the gate refuses (:2144-2158), `return False`, SAFE_ACTION_FAILURE_
  MESSAGE on locked ordinary entrants. The player-visible terminal state
  on those entrants is byte-identical to today's for that sheet; the
  prepare_only structural-reissue loop remains as disclosed below. This plan does NOT claim that inherited state is
  constitutional: the T051 and T079 bounds are unratified (NEQ-LEDGER-07(a)
  lists no T051 class; B2(vii) governs count-keyed give-ups), the detected-
  corruption facet of fail-closed is undecided (D-7), and #324 owns the
  liveness question. The plan adds no bound, deadline, reissue or cap and
  changes no failure policy (D-357-1 scope). The trial records exhaustion
  as FAILED (exhaustion, #324), never PASSED. Whether the trial may
  proceed with that inherited terminal state is resolved by D-357-2 for
  the isolated trial only; it is not a permanent failure-policy exception.
- Pre-gate T051 succeeds but the sheet still fails the gate (F10 path, or a
  T079 delta that re-introduces an invalid value): today's refusal, no
  write, disclosed NOT-REACHED unless observed.
- Pre-gate T051 succeeds, T079 then exhausts: nothing is written (the
  correction lived in memory); disk still carries 99; the cache carries the
  corrected hash (the self-heal case the :1976-1978 comment describes), so
  the next update repeats the pre-gate heal. No partial write
  (NEQ-WORLD-04).
- Model omits the poisoned item or proposes another invalid value: S1a
  rejects inside the same call; the correction turn names the item, field,
  value and schema letter; the model chooses again; exhaustion as above.
- Model proposes a schema-valid but semantically wrong value (e.g. 0 for
  studded leather): not code-detectable without inventing armor rules
  (AP-6, F4); recorded verbatim under its corrections_made string;
  disposition by the review's oracle (see A4 verdict lines), never a code
  change here.
- Schema load failure follows the exact inside/outside-try terminals in
  Task A, not always a FAILED result. The writer already loads the same
  schema at :1408. No silent default or new error framework.
- Malformed source shapes (e.g. item_name:null) may raise in the S2
  projection before T079. Existing caller handlers receive that exception;
  no write occurs. This differs from an ordinary gate refusal and is not
  claimed repaired here. The real-file compatibility scan found zero such
  shapes; no new broad malformed-character repair is added. The separate
  prepare entrant and its existing structural-reissue freeze remain #324.
- Effects lease timeout / sheet load failure: unchanged, before the seam.
- Gemini: the inline T051 schema strips null (model_config.py:11-27/:459;
  #148 comment 5639783067). Omission can preserve an already-valid null;
  it cannot repair an invalid99 without another valid proposal. Do not
  infer universal Gemini refusal from the conversion mismatch. NOT-REACHED natively
  (evidence provider is OpenAI); owned by #148.
- structural_reissue=True entrant with a sheet that stays invalid: the T079
  loop never exits (CODE-PROVEN, not observed, #324). The pre-gate heal
  reduces the cases reaching it; not its fix.

### What is deliberately NOT changed

Prompt file (no observed prompt failure; AP-5); frozen schema; model
bindings/registry; cache file format; retry loops, bounds and messages
(their "VALIDATION ERROR: {e}" prefix now carries the schema letter because
`e` does); write sites :2215/:2287/:2870; lock order; effects lifecycle;
repair_character_data (the retired O1 rule is NOT added).

## Failed and rejected approaches (NEQ-OPS-04 record; none are live instructions)

- O1 (draft 1, RETIRED by supervisor hold and D-357-1): extend
  repair_character_data so any out-of-schema equipment dex_limit is reset
  to null. Why it failed: null is a legitimate armor value (no Dex cap),
  not "unknown"; the poisoning mechanism is category-agnostic (T079 stores
  null on any category; 826 nulls exist on disk across categories), so a
  Chain Shirt or Chain Mail that travelled null -> 99 would be reset to
  "unlimited Dex" by code, schema-valid and therefore never flaggable again
  (F4). Code asserting an armor fact (AP-6, NEQ-CORE-06) and a code-authored
  non-empty -> empty transition on player data (NEQ-SCHEMA-02). Its
  companion checks D3 and the "O1 branch" of A4 are withdrawn with it.
- Whole-sheet-gate trigger for S2 (advice T5's preferred shape): call T051
  whenever `validate_character_data` fails. Rejected (controller concern
  1): fires on every unrelated F10 error and on armor items outside the
  projection; the projection-based predicate is the same schema letter and
  field family with no wasted calls.
- Presence-only hash marker in the projection to defeat cache hits for
  invalid projections (advice T4 alternative). Rejected (controller concern
  3): a digest is not repair authority (AP-7); a cache hit must require
  actual value validity; no new marker or format.
- Output-fields-only validation (draft 1's task A alone as the recovery
  guarantee). Rejected (controller concern 2): an omitted poisoned field
  passes a present-field check and the merge retains it; S1a is required.
- A' schema check only on mutated fields: lets a poisoned echo through and
  keeps two contracts; listed for the Legacy-Contract seat.
- A'' add None to the isinstance guard for dex_limit only: keeps the
  drifted hand-written constants; 99 still accepted and persisted.
- B whole-sheet jsonschema check before the post-validation writes :2287/
  :2870: a new mandatory gate with an entrant-coverage obligation (T052/
  T053/T054/effects-validator writes) and no live firing path; recorded as
  a reviewer design alternative (not an owner question).
- C prompt-only description of dex_limit: the model already echoed null
  5/5; the failure is in code (AP-5).
- D loosen the frozen schema: the schema is authority; 99-as-unlimited is a
  sentinel; D-357-1 forbids loosening.
- E hard-code "light armor -> null" or per-character cases: banned (AP-6).
- O2 make delta-untouched violations diagnostic (WARN and commit): changes
  the frozen gate's polarity for every field (#324 territory) and leaves
  invalid data forever.
- O3 no repair; O4 owner-run offline script (NEQ-LEDGER-03): rejected by
  D-357-1.
- Draft 1's D1 imported/stubbed core/validation/character_validator.py to
  drive the parser on recorded responses. Rejected (NEQ-LEAN-04): the
  module imports api_client and capture seams; D1 is now pure Draft 7 on
  frozen values and parser/repair claims come only from native acceptance.
- Draft 1's Q3/Q4/Q5 as owner questions: disposed (Q3 -> #148 comment
  5639783067; Q4 -> D-344-3 already keeps #349 separate; Q5 -> existing
  behavior, fyi). Q2 -> reviewer alternative B.

## Spec boundaries and behavioral contract (GL-1)

Production allowlist: core/validation/character_validator.py (tasks A, S1);
updates/update_character_info.py (task S2, one block plus the extended
import on :127); docs/architecture/progression-leveling.md (task S3). No
schemas/, prompts/, model_config.py, model_registry.py, web/, main.py,
core/managers/, core/effects/ change. No tracked tests, fixtures or
captures (C: has ~13 GB free; no fixture copies during planning).

| Replaced branch / origin | Goal | Disposition and proof |
| --- | --- | --- |
| equipped bool check :2448-2451 (715732d5) | reject non-boolean equipped | PRESERVED by schema {"type":"boolean"} via helper; D1 polarity, A-series native |
| stealth_disadvantage bool check :2452-2457 (715732d5) | reject non-boolean flag | PRESERVED by schema {"type":"boolean","default":false}; D1 |
| armor_category str check :2458-2463 (715732d5) | reject non-string category | PRESERVED and aligned to the schema enum; D1; compat scan 0 non-enum values on disk |
| numeric check ac_base/ac_bonus/dex_limit :2464-2471 (715732d5) | reject bool/str garbage in numeric fields | PRESERVED by schema integer types and bounds; D1 |
| same branch: rejection of `None` for dex_limit | (no enumerated goal; contradicts the frozen letter; origin = bulk rewrite with no incident) | RETIRED under issue #357 (owner-filed observed failure) and D-357-1; D1/A1 prove null accepted, 99 refused |
| parser-local `mutable_equipment_fields` :2408-2411 | the T051-mutable field family | PRESERVED as the module-level family the helper reads (moved, byte-equal members) |
| `_is_ac_validation_cached` :1404-1429 hash-equality hit | skip T051 when the projection is unchanged | PRESERVED for valid projections (A2/A5 observe cache hits); hit additionally requires value validity (S1b) |
| unknown/immutable/source-reference/duplicate/correction-required checks :2384-2447, :2488-2492 | typed contract of the response | PRESERVED byte-identical |
| changed-only normalization :2473-2486 | write only genuine changes | PRESERVED byte-identical |
| retry loops, bounds, merge, write sites, lock order | existing liveness/fail-open and atomicity | PRESERVED byte-identical (#324 unchanged; D-357-1 scope) |
| repair_character_data :1004-1069 | schema-compliance repairs before validation | PRESERVED byte-identical (O1 retired, nothing added) |

Deletions in a play-path file exceed insertions for the replaced guard
block (about 24 lines removed, about 12 added at that site): GL-1 tripwire
acknowledged; the table above is the contract. Overall the diff is net
positive (S1, S2 add lines).

## Consumer-family audit and Schema-Freeze compat scan

Symbol family: the T051 parser is the ONLY model-driven writer of the six
armor fields; siblings T053/armorClass and `_require_contract_integer`
retain their pre-existing coercing 1..100 contract (:2360-2368), not the
schema's bare integer letter. That different field is outside this repair;
startup and T079 writers validate whole sheets against the same file;
combat completion copies equipment wholesale. Readers: T051 projection
:1134-1136, inventory_context_matcher_v2.py:257-261,
inventory_context_integration.py:106-107. No code arithmetic reads
dex_limit. New helper callers (NEQ-ZC-01): parser per-item check, S1a
merged check, S1b cache truth, S2 pre-gate trigger -- four production
callers, two modules. Cache-check family: :1685 and :1902 are the only two
`_is_ac_validation_cached` callers; both receive S1b. Full table: forensics
section 4.

Compat scan (NEQ-SCHEMA-01; existing result reused, to be RE-RUN by the
Consumer/Compat seat and again at execution against the owner's real game
directories): throwaway /tmp/357/scan_armor_fields.py over 24 roots, 1,204
character files, 1,434 armor items: dex_limit null 826, 0 68, 2 244, 4 1,
absent 208, 99 x87 (invalid); ac_base/ac_bonus all integer; armor_category
all within enum; flags all boolean. So the only on-disk values the new
check rejects are the 87 already-invalid 99s, which the T079 writer refuses
today. Tightening classified NON-BLOCKING for every valid existing file;
BLOCKING only where the frozen gate already blocks -- and for those files
S2 now offers the existing corrector before the block. Additional item for
the seat's re-run: count the overlap between the 87 armor-invalid files and
the 136 F10 files (S2 trigger frequency for sheets that stay refused).
Validator cache files: no format change; existing entries stay readable;
poisoned entries become inert by value check, not by edit.

R1 independently re-ran a larger, explicitly different population:
112 character directories, 1470 parseable sheets, 1778 projected items;
104 files/110 items with99 in four lineages, zero armor/non-armor-error
overlap and zero out-of-projection invalid armor fields. Raw data and
scanner: /tmp/357r1c/{scan.py,scan_result.json}; reviewer report
/mnt/c/agent-room-fleet-kit/local-data/357-r1-compat.md. Do not compare
these counts as a time trend or distinct campaigns. Prior87 count is its
original24-root sample. Some sheets have three invalid items; A1/A4 do
not prove that multi-item branch. Four unparsable artifacts include three
deliberate test broken_record files and a zero-byte temporary sheet.
Unrelated non-armor schema failures remain forensic observations (many
test/backup artifacts), not newly proven player incidents. At execution
verify the chosen authentic fixtures; do not repeatedly rescan the drive.
Family completeness: startup_wizard.py:1455-1469 sets ac_base at creation;
character_effects_validator.py:190 reads armor_category. Both unchanged.

## Implementation slices (isolated trial only, after review)

C0 re-capture main/policy epoch/ancestry; re-verify every owner ruling
issued after this plan's approval (NEQ-OPS-03); confirm no overlapping
#323/#324/#349/#356 edits to the two files; pin EOL (both LF); baseline
hashes of the frozen schema (checkout and `git show origin/main:schemas/
char_schema.json`) and the prompt file.
C1 tasks A and S1 in character_validator.py; simplifier pass; pyflakes
undefined-name gate; ASCII check; py_compile.
C1b task S2 in update_character_info.py (one block, one import).
C2 focused development checks D1-D5 (local, untracked; D-9); raw No-Limits
/ Single-Path / FS-1 scans of the diff and touched files pasted;
independent non-author post-implementation audit (NEQ-REVIEW-15).
C3 serial native real-OpenAI acceptance A1-A6, one operation at a time,
independent PX transcript review; report FAILED/NOT-REACHED honestly; no
mid-run repair.
C4 evidence, S3 schematic sentence, owner presentation. Commit/push/merge/
closure are separate owner gates (D-357-1 authorizes none).

## Focused development checks (deterministic aids, never gameplay proof; NEQ-LEAN-04)

D1 schema polarity on FROZEN inputs with pure jsonschema Draft 7 against
the equipment item subschema read from `git show origin/main:schemas/
char_schema.json` (NEQ-CORE-10), no import of character_validator or any
module that imports api_client: recorded real T051 values -- A2 entry 4
(437cd589) dex_limit null -> valid; entry 5 (a1becb16) 99 -> invalid with
"99 is greater than the maximum of 10"; C5 a08313fd Shield 0 -> valid;
aafb08fd 4 -> valid; the authentic prompt-809 Dain sheet equipment[1] ->
the one invalid path, prompt-130 -> none. Synthetic VALUES (not model
prose): true, "2", 2.5, -1, 11 for dex_limit; -6 for ac_bonus; "Light" for
armor_category; 0 for equipped -> each invalid with its own Draft 7
message; ac_base12.0 and dex_limit2.0 -> valid integer, dex_limit12.0 ->
invalid maximum. Expected results come from the schema
letter, never from current output. What D1 does NOT prove: the parser's,
merge's or cache's behavior -- those claims come only from A-series native
runs.
D2 the frozen subschema is byte-identical at the three sources the code
reads: checkout schemas/char_schema.json, origin/main, and the game
directory copy loaded by the writer at run time (hashes recorded), together
with the native jsonschema version.
D3 diff oracle for A4 (evidence tooling, not a test of the subject): a
standalone dict-diff of the prompt-809 fixture files before/after the
native A4 run listing every changed path. Separate the model-authored armor
repair from T079's captured ammunition delta and existing post-commit
corrections. The original plural-Arrows delta can leave Arrow19 plus a new
Arrows5 row; it need not produce one Arrow24 row. Giver removal can also
no-op (#358). Preserve those failures; do not score them as armor failures
or as successful ammunition transfer. Declare every non-empty -> empty
transition and provenance of every changed value (NEQ-SCHEMA-02).
D4 caller-family grep: `_is_ac_validation_cached` has exactly two callers,
both updated; `armor_contract_errors` has exactly four production callers;
no other caller of the replaced guard lines; model_config/model_registry/
prompts/schemas unchanged (`git diff --stat`); pasted NEQ-ZC-01 grep.
D5 raw sentinel scans pasted for the diff: expect zero new hits; pre-
existing hits in character_validator.py (:1130 [:200], :1294 [:150],
max_attempts=3 at :1941/:2065/:2930/:3726) and update_character_info.py
(:1785 max_attempts, :1339 timeout_seconds) are #324 PRE_EXISTING_OUT,
flagged not added. Complete R1 raw scans/dispositions are in the independent
limits/singlepath/failforward reports: include writer :1780 history[-10:]
(#324), log-only slices/retention, :2408 sleep(1) (pause), :2530 result()
(completion wait), and inert comments. Refresh raw scans after code changes.

## Native acceptance and falsifiers (NEQ-ACCEPT-01/02/03, serial)

Fixtures: isolated copies of authentic complete game directories, current
source exported without WSL git pointers. (a) /mnt/c/354-web-xLy1be, the
actual pre-heal game used by #344 C5: Dain3/12, null dex_limit, Torvald5/5.
This is an independent baseline, not a byte-identical replay of A2 history.
(b) /mnt/c/344-game-EW1GPd including its real modules/validation_cache.json:
Dain's sheet is byte-equal to prompt-809, dex_limit99/Arrow19. The prompt
snapshots contain only sheets/tracker, NOT complete games, and are comparison
artifacts, not sufficient restore sources. Preserve original game/history.
Record fixture-a cache state (and whether the valid source misses). For b,
record the authentic Dain poisoned cache entry and its equality to the
invalid projection before launch; known entry f0e3b08f...1a461c3 is evidence,
not a runtime identity. Missing/mismatched cache => S1b firing NOT-REACHED.
Prompt directory refreshed from the checkout (2026-09-04 miss-log rule),
schema and prompt hashes recorded as loaded. Windows Python 3.12, real
configured OpenAI, T051/T079 bindings verified from the registry at run
time. Never edit character values in a live game, never inject or fabricate
a model response. One operation at a time. Every verdict carries the
NEQ-EVIDENCE-04 block: per call the callsite ID, response.model, latency
relative to the player input timestamp, capture index and protocol line;
parsed request keys (the T051 user payload's equipment entries with
dex_limit as sent, the parsed T051 RESPONSE values and corrections_made,
and T079 REQUEST's corrected equipment values); player-visible text
verbatim; count of degrade/fallback/invalid events with the grep used;
fixture provenance.

A1 PREVENTION (fixture a; same command as #344 A2: Torvald heals Dain with
Lay on Hands). Expect: zero pre-gate T051 calls (capture index shows no
T051 entry before each update's T079 entry -- negative control for S2);
T079 commits HP 3 -> 8 and pool 5 -> 0 exactly once; post-commit T051 runs
for each changed sheet; Dain's dex_limit stays null on disk; if the model
changes AC 15 -> 16 that is its existing arithmetic contract (record, do not
relabel); Torvald's assumed Defense (AC 18 -> 19), if it recurs, is recorded
FAILED under #349, not #357. Full before/after diff of every character file
with every non-empty -> empty transition listed (expect zero). Falsifier:
any "must be numeric" rejection, any write of a
value outside the frozen subschema, any pre-gate T051 call = FAILED.
Record any schema-valid model-chosen dex_limit change separately as model
quality, not a deterministic default. Null echo acceptance is proven only
if the captured RESPONSE actually contains null; omission means that parser
branch is NOT-REACHED, even if disk remains null.
A2 NEXT UPDATE (fixture a, after A1; same arrow-transfer command). Expect:
Dain's T079 delta commits on the first schema-valid attempt; no SAFE_ACTION_
FAILURE_MESSAGE; disk shows the ammunition change; post-commit log shows
the AC projection cache HIT for an unchanged valid projection (negative
control for S1b: valid hits still hit); before/after diff limited to
ammunition plus any schema-valid post-commit corrections. "Arrows"/"Arrow"
mismatch (#358) recorded under #358. Falsifier: any "greater than the
maximum of 10" writer rejection, any revert, any generic failure, any
T051 call for Dain's unchanged projection.
For A2/A4 record the DM's action order. A sibling update failing before
Dain's update makes the Dain-specific repair/cache checks NOT-REACHED.
A3 FIRING-PATH CONTROL for task A: fires only when a model proposes an
out-of-schema value or a poisoned source reaches T051; neither is
manufactured. The invalid-source trigger is exercised by A4; the parser or
merged-result rejection branch needs an actual rejected proposal and is
NOT-REACHED if the model repairs immediately. If it occurs naturally in
A1/A2/A4/A5, capture the correction and show whether the game continues.
A4 AUTHENTIC POISONED RECOVERY (fixture b; the arrow transfer). Expect,
in order: S2 WARN naming Studded Leather dex_limit99, then a DISTINCT S1b
WARN rejecting the authentic invalid cached projection (not just a cache
MISS); a
captured pre-gate T051 call carrying the authentic invalid source. A valid
first-attempt repair is success, not an acceptance failure. If the model
echoes, omits or reinvents an invalid value, capture the schema rejection
and correction turn; if it repairs immediately, that retry branch is
NOT-REACHED. The successful repair carries a corrections_made string;
T079's captured request must show the corrected sheet. ONE primary commit
at writer:2215 carries the model's armor correction plus T079's actual
ammunition delta. The plural-Arrows delta can produce Arrow19 + Arrows5,
not one Arrow24, and leave the giver unchanged (#358). That remains a
separate transfer FAILURE, not a #357 success. No second T051 for an
unchanged corrected projection. Record any pre-existing post-commit write
at :2287 with its T052/T054/deterministic trigger and full changed paths;
do not mistake it for an early repair-only commit. Exact commit ordering
is CODE-PROVEN from the diff plus observed logs; absent intermediate disk
capture must not be described as OBSERVED. Final disk diff is OBSERVED.
Any99->null transition needs model-response provenance, never a code guess.
Verdict lines are SEPARATE:
(i) PRESERVATION/ATOMICITY: correction and requested delta share the one
primary write; no early repair-only write, no unexplained changes outside
armor/requested delta, no code-chosen armor value -- PASSED/FAILED.
(ii) LIVENESS: primary update committed -- PASSED, or FAILED (exhaustion,
#324); a sibling preventing this path is NOT-REACHED. (iii)
MODEL CORRECTION QUALITY (model-owned): the chosen value recorded beside
the SRD armor table for that item; a legal value that differs from the
SRD expectation is recorded as an OBSERVED model-quality finding for the
review's disposition (F4), not as a #357 code failure and not as PASSED.
Falsifiers for (i): unexplained armor mutation, invalid armor write, a
repair-only write before the primary commit, or unexplained unrelated
field loss. A pre-existing T079 feedback repair after T051 exhaustion is
recorded with its captured response under #324; it does not prove T051
recovery. Record zero/nonzero post-commit writes separately with evidence.
The #358 transfer verdict and narration claims remain separately FAILED
when applicable; do not paper over a giver/receiver conservation defect.
A5 Save then Load around A2, then one more ordinary update (e.g. spend
1 gp): Load is never refused; the update commits; zero pre-gate T051
calls; sheet diff limited to the request.
A6 Player-Experience review of all transcripts (second person, no invented
rolls, no bookkeeping talk substituted for the requested action, five
narration claims spot-checked against disk; in A4 the player must see the
arrow transfer happen, not validator chatter). If #358 prevents that,
record the exact narration/state discrepancy as #358 FAILED separately;
do not label the combined player experience PASSED. Record A4 input-to-
narration/final-prompt latency and any missing truthful progress.

Naturally-unreached branches, stated up front, never relabeled PASSED:
T051 retry exhaustion under the new checks (unless it occurs in A4); Gemini
and LM Studio T051 paths (#148); F10-plus-armor sheets; the effects/prepare
entrant (#356 keeps its advisory validation unreachable; its pre-gate S2
path is CODE-PROVEN only); combat-side equipment copies; T079 deltas that
themselves rewrite armor fields; loading an already-poisoned save through
Load; multi-item poisoned armor sheets and duplicate-source-name cases.

## Review protocol and owner gate

Triage: FULL (play-path replacement with deletions > insertions at the
guard site -> GL-1; typed contract adjacent to frozen schemas; a new
provider-call entrant on a play path; cache semantics). Nine seats,
parallel and blind, each reading this plan, the resolution ledger, live
#193 and current source: Architecture Custodian (AP-4 citation of the one
new symbol; wrong-layer check on S2's placement; doc reconciliation S3),
Fail-Forward DA (trace every edge in "Failure edges"; confirm no new bound;
name the inherited #324 exits explicitly; assess the #324 comment's "no
promotion to pre-commit dependency" sentence against S2's refused-path-
only trigger), Acceptance DA (A4 verdict lines and oracles; negative
controls A1/A2/A5; one-at-a-time), Consumer/Compat DA (scan re-run;
overlap count; cache-file compat; entrant table), Legacy-Contract DA (GL-1
table; A vs A'), Player-Experience DA (A6; #360 narration ordering as
context), Leanness DA (citation of helper/S2 to E1-E3; coverage: every T051
entrant passes S1; net-negative test: worst case of S2 equals today's
refusal plus one bounded existing conversation; cascade: no special
cases), No-Limits Sentinel, Single-Path Sentinel (pre-gate and post-commit
use the ONE T051 method; confirm no second corrector). Conditional gates:
Schema-Freeze (no schema file change; audit the compat scan; helper reads
the same file the writer reads), Platform/Provider (CRLF prompt file
untouched; Windows acceptance; OpenAI-only evidence stated), Hygiene
(ASCII, no tracked tests, no `git add -f`). Pre-scan results for the
plan-only state (product diff empty): D5 and the independent raw reports
are the complete baseline. No-Limits model-context hits in the touched files
:1130/:1294 and writer :1780 = #324 PRE_EXISTING_OUT; Single-Path hits are docstring/
provider-select words at :125/:1791/:1933/:2082/:2811/:2918/:3743 =
pre-existing routing branches, fyi; FS-1 hits max_attempts at :1941/:2065/
:2930/:3726 and update_character_info.py:1785/:1339 = #324, flagged not
added. The executed diff must paste fresh scans. Convergence authorizes
nothing by itself; owner authority D-357-1/D-357-2 covers this isolated
trial. Present the converged result before execution; new scope forks
still require a ruling. Q-357-A is resolved for the trial (NEQ-REVIEW-09).

## Owner decisions (new questions escalate via #293)

Q-357-A CLOSED FOR TRIAL by D-357-2 (owner: "approve trial"). The
pre-gate T051 correction reuses the existing T051 conversation and its
existing, unratified three-attempt exit (#324). When it exhausts on an
already-invalid sheet, this plan leaves the requested update refused
exactly as today (no new bound, no reissue, no cap, no failure-policy
change -- D-357-1 excludes those). Question: does the owner accept that
inherited, unratified terminal state for the #357 trial, with exhaustion
recorded FAILED (exhaustion, #324) and the liveness ruling left to
#324/D-7 -- or must #357 wait for the #324 ruling before its trial?
Owner accepted retaining this existing behavior for the isolated trial.
Any exhausted repair is FAILED, not PASSED. Broader liveness remains #324;
this does not ratify permanent shipment with the limitation or new bounds.

Disposed, not owner questions: Q2 (write-site whole-sheet gate) is
reviewer alternative B; Q3 Gemini is #148 comment 5639783067; Q4 #349
separation is D-344-3; Q5 validator-driven AC corrections on an unrelated
heal are existing behavior (fyi).

## Tracked follow-ups

- #363: native trial referee/storage handoff contract mismatch; exact transfer
  recovery arm NOT-REACHED. Owner authorized separate #193 planning, not an
  expansion of this armor patch. Evidence in the acceptance record.

- #357 this repair (tasks A, S1, S2, S3).
- #324 bounded validator/writer exits, the 30 s lease, the :1130/:1294
  description slices and writer :1780 history window: unchanged, flagged not added; the structural_reissue
  unbounded loop on a persistently invalid sheet is CODE-PROVEN there.
- #356 effects_runtime.py:262 kwarg mismatch: unchanged; keeps entrant (c)
  advisory validation unreachable. Staged storage :796 is also affected;
  independently verified sibling evidence added in comment5642436230.
- #361 dual file/embedded T051/T052 prompt sources, pre-existing and
  separately filed from Single-Path SP-2; no prompt-source repair here.
- #148 Gemini T051 inline schema strips null (comment 5639783067): no
  duplicate issue; Gemini path NOT-REACHED here.
- #349/#188 unowned Defense entitlement: separate (D-344-3); recurrence in
  A1 recorded under #349. Projection omits classFeatures when no name
  matches (character_validator.py:1143-1157) -- evidence for that issue.
- #358 "Arrows"/"Arrow" no-op; #360 narration before the failure message:
  separate; may recur in A2/A4.
- F10: unrelated non-armor violations (136 in the original sample,161 in
  the larger R1 sample) are FYI forensic observations. An unchanged invalid
  field can fail the gate; T079 may independently repair it. No new live
  player incident established, no broad migration or issue invented from
  test/backup sample counts. Outside the six-field repair.
- docs/architecture/progression-leveling.md line 39 sentence updated in C4.

## Resolution ledger

| ID | Finding or decision | Disposition |
| --- | --- | --- |
| 357-F1 | T051 guard rejects schema-valid null echo, forcing fabricated numbers | task-A (schema-derived field check); D1/A1 |
| 357-F2 | Invalid T051 value persisted without schema check at :2287/:2870 | task-A plus task-S1a (merged-proposal validity) close the only observed entrant; alternative B recorded for reviewers |
| 357-F3 | Already-poisoned sheets refuse ordinary updates that leave the value in place (E2/E3) | task-S1b + task-S2 (agentic recovery via existing T051, D-357-1); A4 positive test; O1 retired |
| 357-F4 | Schema-valid but semantically wrong values (Shield 0, light 4) | defensible: not code-detectable without inventing armor rules (AP-6); A4 verdict line (iii) records verbatim; model-owned |
| 357-F5 | armor_category/ac_base/ac_bonus tightening to schema letter | task-A; compat scan: zero existing valid files affected; Consumer/Compat re-runs |
| 357-F6 | Gemini inline schema strips null | issue-#148 (comment 5639783067); NOT-REACHED here |
| 357-F7 | #349 Defense assumption observed again in the same captures | fyi: separate by D-344-3 |
| 357-F8 | Pre-existing bounds/slices in touched files | fyi: issue-#324 PRE_EXISTING_OUT, flagged not added |
| 357-F9 | Schematic step 16 omits schema check and pre-gate correction | task-S3 one-sentence doc reconciliation |
| 357-F10 | 136 older files fail the frozen schema on unrelated paths | fyi: outside #357; forensics record; supervisor may file |
| 357-F11 | Poisoned cache entry blesses an invalid projection (E3) | task-S1b (cache hit requires value validity; no marker) |
| 357-F12 | Model may omit the invalid item so the merge retains it | task-S1a (merged-proposal validity before success/cache) |
| 357-F13 | Recovery path inherits unratified T051/T079 exits (#324) and undecided D-7 | override: owner D-357-2 permits unchanged limitation for isolated trial only; exhaustion remains FAILED |
| 357-F14 | Effects/prepare entrant is lock-free during proposal | defensible: existing entrant behavior; receipt before/after comparison at apply; cache side effect disclosed; #356 unchanged |
| 357-R1 | Plan review and execution approval | override: owner D-357-1/2 permits isolated trial direction and inherited exhaustion only; NEQ-REVIEW-13 post-review presentation/GO before execution, no publication |

## R1 controller reconciliation (full ledger supplement)

All nine blind reports completed on f6cdbe6b; files357-r1-<seat>.md
under /mnt/c/agent-room-fleet-kit/local-data. No product changes. Raw
scans and source checks are in those reports, not replaced by this table.
No scope or authority expansion. The fixture/oracle corrections are TEST
class, not plan-polish: re-dispatch all nine on the revised frozen plan.

| Seat / row IDs | Controller disposition |
| --- | --- |
| Acceptance F-ACC-1 | task-A4: use authentic full game with poisoned cache; record matching cache precondition and distinct S2/S1b events; missing firing evidence is NOT-REACHED |
| Acceptance F-ACC-2; PX F-PX-1 | task-A4/D3/A6: score primary correction+delta commit separately from existing post-commit writes and #358 transfer failure; no assumed Arrow24 row |
| Acceptance F-ACC-3/4/5/6 | fixed-inline: response-null and corrected T079 request evidence, sibling-order NOT-REACHED, T078 entrant, canonical verdict labels, schema library version |
| PX F-PX-2/3/4/5/6 | fixed-inline/fyi: epoch, poisoned-Load NOT-REACHED, latency capture, D-357-2 exhaustion/#360, existing model AC correction |
| Custodian FYI-1/3/5/6/7 | fixed-inline: migrated entrant, exact schema-load exception terminal, display wording, startup ac_base reader/writer family, integral-float field specificity |
| Custodian FYI-2/4; Leanness FYI-2/3/4/5 | fyi: projection/schema exceptions, extra read-only instance/projection cost, cache last-writer-wins; exact placement after load try stated; no broad recovery wrapper added |
| Legacy FYI-1/2/3/4/5 | fixed-inline/fyi: epoch, placement, schema-load terminal, schema lineage, existing armorClass1..100 outside six fields |
| Legacy FYI-6; SP-7(a); Compat C2; Leanness FYI-7 | issue-#356: independently verified storage sibling, comment5642436230; do not fix here |
| Limits FYI-1/2/3/4/5 | fixed-inline/fyi: full baseline scans referenced, native library version, epoch, exact exceptional terminal; no new limits |
| SP-1/3/4/5/6/7(b)/8 | fixed-inline/fyi: raw scans, Gemini omission retains invalid99, existing T079 repair provenance, separate envelope/schema engines, old AC contract, capture line metadata hygiene, placement |
| SP-2 | issue-#361: two prompt sources, filed separately; do not replace fallback with a crash in this wave |
| Leanness FYI-1/6 | fixed-inline: dormant batch and epoch |
| FF-1/2/4/5/6/7 | fixed-inline/fyi: malformed-source terminal, existing advisory ordering, busy-lock debt324, duplicate-source NOT-REACHED, scoped locked-versus-prepare terminal, unrelated AC bounds |
| FF-3 | override: owner D-357-2, isolated trial only; exhausted repair FAILED |
| Compat C1/3/4/5/6/7 | fixed-inline/fyi: actual scan population, multi-item NOT-REACHED, precise placement/load terminal, unchanged lock cost, measured null categories, duplicate merge guarded by existing parser |

Additional precision: the T051 response-envelope validator remains its
existing helper; it cannot express the frozen enum/range/null letter and
is not a competing equipment-schema authority. Gemini omission leaves
invalid99 behind and S1a rejects that merged result (#148). Existing T079
feedback may independently repair armor after T051 exhaustion; the call
carrying the delta must be identified, never misattributed to T051.
The byte-identical exhaustion-message claim covers locked ordinary
entrants only; prepare_only may still loop under existing #324 behavior.

## R2 controller reconciliation and convergence

All nine independent R2 reports on frozen SHA256
5fb464e01f3a1e05718c61fcba95012d8bcaeacc81f929028891481ab7a3bff1
returned CLEAN with zero blocking findings. The controller read all nine
reports in full and verified terminal completion of each CLI session.
Raw reports: /mnt/c/agent-room-fleet-kit/local-data/357-r2-<seat>.md.
R1's test-class changes received full R2 re-verification; none remain pending.

| R2 finding family | Disposition |
| --- | --- |
| Custodian/Acceptance/Legacy/FS1 noncanonical ledger token | fixed-inline: legal override token, explicitly retains post-review GO and no publication |
| All seats policy epoch | fixed-inline: live 01:14:13Z; only D-323-11 added, unrelated specialist-level-up trial; no #357 rule changed; C0 rechecks overlaps |
| FS1 ordinary-versus-prepare terminal precision | fixed-inline: put the existing qualification beside the failure statement; no terminal changed |
| PX WARN line citation | fixed-inline: except at2323, log at2324 |
| Limits/Single-Path duplicate abbreviated baseline | fixed-inline: D5/raw reports are complete; writer history window named in short summary and follow-up |
| Compat cache-WARN ordering advisory | fyi: no failing input; existing name/hash checks and A4 matching-entry evidence remain the contract. Independent diff audit checks eligibility at the existing hit branch; no new code step, test or schema-load order is prescribed by this advisory |
| Remaining R1 accepted FYIs re-verified by R2 | fyi: unchanged recorded scope/ownership; no additional repair |

Termination classification: remaining corrections above are exclusively
wording/citation/ledger formatting; no code steps, tasks, types, state,
tests or call sites changed. NEQ-REVIEW-11 plan-polish termination applies
after the completed full-coverage R2 pass; no ceremonial third dispatch.
This completes design review, NOT implementation or gameplay acceptance.
NEQ-REVIEW-13 requires presenting this result and obtaining post-review GO;
D-357-2's trial-only exhaustion allowance is unchanged. No code, game run,
commit, push, merge or closure has occurred in this planning phase.

## Revision record

Controller revision 3: owner "approve trial" recorded as D-357-2 in live
#193, closing Q-357-A for this experiment only. Six-member mutable-field
count corrected; A4 first-attempt repair is valid and retry conditional;
Gemini omission is not incorrectly called universal refusal. No product
changes; full nine-seat blind review still required.

Revision 2 (2026-09-11, single writer, no code): folded D-357-1; retired
O1 into the failed-approach record; replaced the recovery design with S1a/
S1b/S2 (existing T051 pre-gate, merged validity, value-validity cache
hits); narrowed the trigger to the T051 armor projection; rejected the
hash-marker alternative; rewrote D1-D3 under NEQ-LEAN-04; split A4 into
three verdict lines; corrected E2/E4 wording (observed block, no guaranteed
recovery; 87 files are copies of a few lineages); moved Q2-Q5 out of the
owner-question list; added Q-357-A and ledger rows F11-F14. No product
ruling is presumed from this author's recommendations.
