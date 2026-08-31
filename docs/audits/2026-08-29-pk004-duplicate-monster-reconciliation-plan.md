# PK-004 Duplicate-Monster Travel Reconciliation Plan

Status: **PLAN ONLY -- implementation blocked**  
Branch: `plan/pk004-travel-reconciliation`  
Baseline: `96ab1093dd9fd8e022f985383fd5dc119bdf5680`  
Date: 2026-08-29  
Scope: C03 -> D04 location-reconciliation dead-end only

No production code, schema, prompt, fixture, or persisted game state is changed by
this document. Implementation requires a clean six-lens review, Claude's independent
review, and explicit owner execution approval.

## 1. Authority and governing doctrine

This plan was prepared from the live GitHub issue
`MoonlightByte/NeverEndingQuest#193` (updated 2026-08-27), not a cached doctrine
copy. It applies:

- Part 1: B1/B2 fail-forward, AP-3 (recovery must not brick play), AP-6 (fix the
  responsible layer), AP-7 (no names/prose/digests as gameplay authority), the
  leanness law, evidence classes, lineage, and governance.
- Part 2: system pages 3 (module structure), 7 (identity), 8 (conversation and
  world consequences), 10 (single game thread/player pacing), 11 (provider
  routing), 12 (schema/state compatibility), and 13 (native acceptance).
- Part 3: FULL review because this changes a shared state-validation primitive
  used by both legacy and recoverable travel.
- Part 4: evidence-backed handoff, one implementation slice at a time, and a
  mandatory simplifier pass.
- Part 5: D-TRAVEL-2 remains binding; successful travel retains T013 departure,
  T063 arrival, and T064 stitching before control returns.

Owner doctrine for this incident is binding: the agent owns the semantic decision;
code shores up the mechanically unique completion. A small immediate-exchange
referee is permitted only when judgment remains. The main model and full
conversation are never re-looped to repair this value-shape mismatch.

## 2. Player contract and success statement

Once the travel agent has validly chosen D04 and T091 has decided which C03 threats
remain, code must map that answer onto the canonical C03 monster occurrences without
inventing, editing, merging, or silently losing real monsters. The already-committed
travel must then pass this reconciliation boundary and continue through the normal
three-agent transition chain. This narrow repair does not claim to fix the observed
startup prompt/wake-input handoff; that known player-contract failure is tracked and
verdicted separately as #248.

Success means all of the following:

1. A repeated structured monster value that corresponds to multiple canonical
   occurrences is legal and retains the agent-selected multiplicity.
2. Copies beyond the canonical multiplicity remain rejected by the existing
   ordered-subsequence gate; PK-004 does not change that unobserved policy.
3. Added, edited, or reordered structured entries remain rejected before mutation.
4. The preserved PK-004 checkpoint converges on restart instead of re-raising the
   same exception.
5. No code guesses from monster names, descriptions, faction prose, or narration.
6. Normal no-duplicate reconciliation and both existing callers retain their
   behavior.

## 3. Evidence inventory

### 3.1 Real gameplay evidence

- `C:\pkev\protocol-pk2.ndjson`, seq 284-291: the accepted C03 -> D04 turn
  reaches `Transitioning location...`; `_validate_removal_only_subset` raises
  `ValueError("AI response contains duplicate monster entries.")`; the engine exits.
- `C:\pkev\protocol-pk2-restart1.ndjson`, seq 1-14: untouched restart loads D04
  at 09:20, exposes a prompt prematurely, and re-enters the same pending
  reconciliation on the next input. The same ValueError exits the engine again.
- `C:\pkev\BUG_LEDGER.md`, PK-004: records the hard dead-end and untouched state.
- `/mnt/c/pk2/debug/api_captures/api_calls_master.jsonl`, call 47: the main DM's
  accepted immediate action is `transitionLocation(D04)`, `updateTime(15)`, and
  the immediate plot receipt. The main model did not author the monster list.
- The captured request projection for that turn contains one Rune-Scarred Vermin
  and three Straw Husk rows.

The T091 response body was not retained by the active capture configuration. That
limits claims about its exact count, but not the failure classification: strict JSON
parsing completed and the duplicate-fingerprint branch fired, proving that T091
returned at least two structurally identical entries. No response body will be
reconstructed from memory. Future acceptance enables the existing capture path and
records the real T091 request/response.

### 3.2 Canonical state and schema evidence

Both the live C03 document and untouched module backup contain four monster rows:

- one Rune-Scarred Vermin, quantity 1..1;
- three structurally identical Straw Husk rows, each quantity 1..1.

The three Straw Husk canonical JSON values have the same value fingerprint, but
they are three array occurrences and therefore represent three permitted threat
instances. `schemas/loca_schema.json` and
`schemas/locationfile_schema_strict.json` define `monsters` as an array and do not
declare `uniqueItems`. Blanket set-deduplication would corrupt the official module by
collapsing three real occurrences into one.

### 3.3 Prompt evidence

`prepare_reconciliation` sends T091 only the origin monster list and immediate scene
history. Its system instruction says to return only a JSON array, keep exact original
entries, remove only threats that the scene establishes are no longer active, and
never add, reorder, or edit. With no established defeat in the departure scene, an
answer retaining the three identical Straw Husk occurrences follows the prompt.

The prompt is therefore not inducing an invalid duplicate. It exposes a contradiction
between legal canonical multiplicity and the code validator. No prompt change is
planned.

## 4. Root-cause proof

### 4.1 Root, not symptom

`_validate_removal_only_subset` already implements an occurrence-sensitive ordered
subsequence walk. That walk is capable of consuming the first, second, and third
identical canonical occurrences separately. Immediately before it, however, the
function rejects any repeated proposed fingerprint with a set-cardinality test. The
blanket uniqueness rule contradicts both the schema and the ordered-subsequence
contract.

The ValueError is therefore a validator defect, not evidence that the main travel
agent selected an invalid destination, not D04 content corruption, and not a prompt
comprehension failure.

### 4.2 Why the engine exits

`resolve_current_transition_reconciliation` catches only
`LiveProviderUnavailable`. The duplicate `ValueError` escapes through
`process_action`/`_resume_v2_location_transition` to the headless engine boundary,
which emits `exit reason=error`. No reconciliation receipt is frozen or committed.

### 4.3 Why restart repeats forever

Movement to D04 is already authoritative, but the location-reconciliation receipt
and phase remain pending. Restart correctly discovers the unfinished v2 workflow and
calls the same T091/validator seam. Because the rejected proposal was never receipted
and the canonical C03 list still legally contains repeated occurrences, the same
contradiction is reachable on every retry. Restart is replaying the durable work as
designed; the validator makes convergence impossible.

### 4.4 Lineage

- The strict uniqueness guard was introduced by `715732d5` and exists unchanged on
  `origin/main` (`691b5a2f`). On that baseline the legacy `run` path catches the
  validation error, retries three times, and returns `False`; it does not terminate
  the process, but reconciliation can be abandoned without applying the agent's
  result.
- Recoverable transition reconciliation and the uncaught durable caller were added
  by travel commit `b7f7a863`. That change turns the pre-existing representation
  contradiction into the persisted hard dead-end observed in PK-004.

Classification: a pre-existing validator contradiction became a branch-introduced
gameplay regression when the recoverable workflow made the validation result a
mandatory, uncaught phase.

## 5. Authority boundary

T091 remains the semantic authority for which original threats remain active after
the immediate scene. Code has only four mechanical authorities:

1. canonical structured equality of each original/proposed value;
2. the maximum available occurrence count of each exact original value;
3. original array order;
4. persistence of trusted original elements, never model-authored replacements.

Code does not decide whether a monster died, fled, surrendered, or remained hostile.
It does not merge same-named but structurally different monsters. It does not inspect
names or prose. It completes only the uniquely determined mapping from T091's
structured selection to canonical occurrences.

## 6. Approaches evaluated

### A. Delete only the blanket duplicate rejection

This makes legal canonical repeats pass through the existing occurrence-sensitive
ordered-subsequence walk. An accidental fourth copy of a canonical three-copy value
still reaches the end of the source list and raises. That is correct for the observed
scope: the retained T091 body is unavailable, so no evidence shows an over-cap copy;
the official source itself proves that legal repeated occurrences are what the
blanket guard cannot represent.

The deterministic completion is already present: the subsequence walk maps each
proposed exact value to the next matching trusted original occurrence. Removing the
contradictory pre-check lets that one correct mapping execute without adding a new
normalizer.

**Chosen as the smallest evidence-complete repair.**

### B. Occurrence-capping normalization, then the existing ordered-subsequence check

Before the subsequence walk, cap each exact proposed value to the number of identical
occurrences available in the original list, retaining proposed order. Then run the
existing ordered-subsequence validation and persist only deep copies of the matched
original occurrences.

Consequences:

- original `[A, B, B, B]`, proposed `[A, B, B, B]` -> preserve all four;
- original `[A, B, B, B]`, proposed `[A, B]` -> preserve the agent's removal of two;
- original `[A, B, B, B]`, proposed `[A, B, B, B, B]` -> discard only the
  impossible fourth B, preserve all real occurrences;
- same display name but different structured values -> separate occurrence budgets;
- reordered, edited, or newly invented entries -> still fail the subsequence gate.

This can be structurally safe only if unknown values are rejected before capping;
otherwise a zero-budget edited/invented value is silently erased. More importantly,
the over-cap firing path is unobserved and no owner ruling retires the existing
fail-closed-on-excess behavior. D3 alone would be a synthetic justification for extra
machinery.

**Rejected under AP-5/leanness. Reconsider only with observed evidence and a separate
owner ruling.**

### C. Catch ValueError and mark reconciliation unavailable

This would keep the engine alive by skipping the result, but it would discard an
available semantic decision, weaken state truth, and treat data-contract defects as
provider outages.

**Rejected as fail-open and wrong-layer.**

### D. Ask a referee model or re-run the main model

No semantic judgment remains when the only mismatch is an occurrence beyond the
canonical maximum. A referee adds latency and another failure surface; replaying the
main conversation violates the explicit owner boundary.

**Rejected as unnecessary and over-engineered.**

### E. Prompt-only tuning

The current prompt correctly instructs exact preservation and must allow legal
canonical multiplicity. A model can always repeat an extra structured value, so a
prompt-only change cannot make the mechanical boundary safe.

**Rejected as insufficient.**

## 7. Proposed production change

Allowlist: **one production file only**:

- `utils/reconcile_location_state.py`

Within `_validate_removal_only_subset`:

1. delete only the set-cardinality pre-check that rejects every repeated proposed
   value;
2. retain list/type checks, exact canonical JSON value representation, and the
   existing occurrence-sensitive ordered-subsequence matcher byte-for-byte;
3. continue returning deep copies of matched original objects;
4. update the docstring/comment so it states that exact repeated values are legal
   only to the extent that separate ordered source occurrences exist.

Do not change T091 prompt/model/provider routing, durable checkpoint schema,
`action_handler`, `main.py`, locks, receipts, narration, or the three-agent transition
chain. Do not add a general catch around reconciliation.

## 8. Implementation slices after approval

Implementation remains blocked. If approved, execute one slice at a time:

### C1 -- Forensic negative controls

Using local ignored checks only, freeze the current behavior for canonical repeated
occurrences, excess copies, genuine removal, same-name/different-value entries,
reorder, edit, and invention. Record the pre-change failure and prove the oracle is
based on full structured values.

### C2 -- Remove the contradictory uniqueness pre-check

Make the one-file change described in section 7. Run the C1 checks immediately.

### C3 -- Consumer and compatibility checks

Exercise both `prepare_reconciliation`/`apply_reconciliation` and legacy `run`
boundaries without changing their contracts. Verify that caller return values,
before/after state, lock ordering, and exact-value persistence are unchanged.

### C4 -- Mandatory simplifier pass

Remove redundant machinery, keep the logic local to the existing validator, and
confirm the diff contains no prompt, schema, caller, logging, or unrelated cleanup.

### C5 -- Native real-game acceptance

Run section 10 on a separate byte-copy of the preserved campaign. No merge, push to
the integration line, or activation follows automatically.

## 9. Development checks (local/ignored)

All checks are ASCII-only and remain untracked:

| ID | Input / boundary | Required result |
|---|---|---|
| D1 | `[A,B,B,B]` -> `[A,B,B,B]` | all four trusted originals preserved |
| D2 | `[A,B,B,B]` -> `[A,B]` | exactly the agent-selected two remain |
| D3 | `[A,B,B,B]` -> `[A,B,B,B,B]` | existing rejection preserved; no mutation |
| D4 | same name, different descriptions/quantities | no merge; ordered exact values remain distinct |
| D5 | reordered originals | rejection; no state mutation |
| D6 | edited or invented object | rejection; no state mutation |
| D7 | non-list or malformed JSON | existing rejection preserved |
| D8 | canonical proposal object is mutated after validation | persisted result remains deep-copied trusted originals |
| D9 | `[A,B,B,B]` -> `[A,X,B]`, `[A,B-prime,B]`, and `[X]` | unknown/edited values remain visible to and rejected by the existing matcher |
| D10 | current equals after / current equals before / current equals neither | existing already-committed / commit / blocked-conflict polarity preserved |
| D11 | repeated invocation after committed status | no second area mutation |

These prove the mechanical primitive; they do not substitute for gameplay acceptance.

## 10. Native Windows, real-OpenAI acceptance

Use `run_headless.py serve` with `HeadlessClient`, one command at a time, on a
separate byte-for-byte copy of the official Pumpkin King campaign. OpenAI is the only
provider. No synthetic gameplay, state edits, fake responses, or direct internal
function injection count as acceptance. Capture the actual T091 request, response,
provider, and model.

### A1 -- Exact preserved hard-dead-end recovery (primary gate)

Start from the untouched `movement_committed` PK-004 checkpoint and canonical C03
file. Because current startup exposes a prompt before `resume_required` work runs,
submit an explicit resume-only player command after reading that prompt. The broader
prompt/wake-input defect is #248 and receives its own verdict; this plan does not
pretend to repair it.

Required:

- the existing operation resumes; no new player action is executed ahead of it;
- T091 receives only the origin list and immediate origin scene;
- the captured T091 result contains at least two structurally identical canonical
  occurrences; otherwise the mandatory repaired-boundary verdict is `NOT-REACHED`;
- reconciliation accepts exactly that legal canonical multiplicity;
- disk retains exactly the multiplicity selected in the captured T091 response,
  with no merged or model-authored replacement values;
- party location remains BOO001/D04;
- the staged 15-minute receipt advances 09:20 -> 09:35 exactly once;
- reconciliation, departure, narration, deferred-action, and completion receipts
  converge; the checkpoint is retired normally;
- T013, T063, and T064 complete, one stable transition narration is published, and a
  real D04 player prompt returns;
- no traceback, engine exit, duplicate narration, duplicate plot/time application,
  or technical error reaches the player.

Restart the completed copy once more: it stays D04/09:35, does not call T091 again for
the completed operation, and does not duplicate narration or state.

Record two separate verdicts:

- `PK-004 duplicate reconciliation`: may pass only if the repeated-value boundary is
  reached and the transition completes without the duplicate ValueError;
- `player continuation`: must honestly report any premature prompt, consumed wake
  input, or second semantic beat as `FAILED (#248)`, never as a PK-004 success.

### A2 -- Fresh official duplicate-multiplicity travel

On a fresh legitimate play path through C03, make the immediate C03 -> D04 travel
after reading each real response. The official module's repeated Straw Husk rows are
the negative control: code must not collapse them merely because their structured
values are equal. Travel completes and returns control in one semantic beat.

### A3 -- Normal no-duplicate travel regression

Perform a connected, ordinary travel whose source monster list has no repeated
structured values. Prove identical reconciliation semantics, complete three-agent
narration, exact-once time/state, and returned control.

### A4 -- Agent-removal authority

Use a real scene in which committed narration establishes that a threat is no longer
active, then leave the location normally. The captured T091 selection removes only
the supported occurrence(s), code does not restore them, and same-name surviving
occurrences remain according to the model's structured count.

### A5 -- Player-experience and scoped restart evidence

For A1-A4 inspect protocol, conversation history, checkpoint, area JSON,
party tracker, and API captures. The player sees changing truthful progress during
provider work, no technical validator text, and no code-selected player action. The
known pre-recovery prompt/wake-input behavior is recorded under #248 with its own
verdict. This plan does not inject a crash after a pending T091 receipt and does not
claim the frozen-receipt guarantee tracked by #247.

Transcript review is mandatory, not aesthetic sampling:

- acknowledge player input within one event cycle;
- when work exceeds roughly ten seconds, show truthful changing progress rather than
  one stale line;
- address the sole PC in second person;
- reveal only perceived/triggered facts and invent no mechanics, actors, player
  choices, rolls, or outcomes;
- cite at least five load-bearing narration claims and verify each against committed
  disk state and attributed dialogue/history.

### A6 -- Repaired-boundary polarity and evidence ledger

The real gameplay arms prove that the former blanket duplicate gate is actually
reached by a captured repeated T091 result and now opens. D3/D5-D9 remain local
development evidence only; they do not establish native acceptance of the separate
invalid-output paths tracked by #249. Every arm records `PASS`, `FAIL`, `BLOCKED`, or
`NOT-REACHED`; mandatory `NOT-REACHED` blocks the PK-004 acceptance verdict.

For every paid arm retain timestamped NDJSON, all relevant request/raw-response pairs
with actual provider/model, T091 call count, wall time, and before/after diffs of the
checkpoint, source area, party tracker, and conversation history.

## 11. Legacy/consumer contract (GL-1)

| Existing goal / consumer | Disposition | Proof |
|---|---|---|
| T091 decides semantic survivor set | PRESERVED | captured A1/A2/A4 T091 inputs and outputs |
| Exact original entries only | PRESERVED | D5-D8 plus disk diff |
| Removal-only ordered subsequence | PRESERVED | D2, D5, D6 |
| Blanket rejection of any repeated provider value | Origin: `715732d5 feat(multi-model): integrate provider-aware game runtime` (no linked issue located). Goal: prevent provider-created occurrences while persisting only trusted removal-only originals. Blanket rejection of legal canonical repeats: RETIRED by D-PK004-2; no-new-occurrence conservation: PRESERVED by subsequence exhaustion. | D1/D3/D4/D5/D6/D9, A1/A2 |
| No new/edited/reordered occurrence | PRESERVED | D3, D5, D6, D9 |
| Legacy `location_manager -> run` (zero current player callers) | PRESERVED | C3 compatibility checks only; no native-player claim |
| Durable `action_handler -> prepare/apply` | PRESERVED | A1/A5 |
| CAS/lock/write verification | PRESERVED | D10-D11 and disk receipts |
| Three-agent transition narration | PRESERVED | A1-A3 event/capture order |
| One immediate semantic beat | UNCHANGED: A2/A3 normal travel must preserve it; A1 restart continuation remains KNOWN FAILED (#248) and cannot be credited to PK-004 | Separate A1 continuation verdict; A2/A3 handoff proof |
| Provider/model routing | UNCHANGED | diff allowlist plus captured model/provider |
| Persisted schemas and legacy saves | UNCHANGED | zero schema/migration diff; restart arms |

## 12. Fail-forward and recovery contract (FS-1)

Healable condition in scope:

- a proposed repeated exact value maps one-for-one to separate canonical ordered
  occurrences -> accept the agent's legal structured selection and continue.

Over-cap copies remain rejected by the existing matcher. The repair introduces no
retry counter, fallback action, deadline, referee call, or main-model replay.

Out of scope and intentionally still protected:

- edited, invented, reordered, non-list, or malformed proposals;
- stale area values (`current != before && current != after`);
- file/lock/write failures.

Their existing gates remain. Generic exception-to-player fail-forward is not silently
solved by weakening those gates; existing issue #211 tracks the startup exception
class. Any separately proven active-turn exception-policy gap must be filed rather
than folded into PK-004.

## 13. Compatibility and rollout

- No persisted field, schema, migration, feature switch, provider change, or prompt
  contract change.
- Exact structured object comparison remains the authority; display names and prose
  never enter the decision.
- Existing non-empty values are preserved unless T091 selected their removal.
- The fix applies unconditionally at the shared validator boundary; no
  Pumpkin-King/C03/D04/name-specific condition is allowed.
- Old checkpoints heal through the existing replay path; no checkpoint rewrite or
  manual state repair.
- Tests and evidence remain local/ignored per owner policy.

## 14. Risks and mitigations

| Risk | Mitigation / evidence |
|---|---|
| Collapse real identical monsters | remove only blanket guard; existing occurrence walk maps each source row; D1/D4/A1/A2 |
| Treat same name as identity | use exact structured value already used by validator; D4 |
| Hide reorder/edit/invention | retain ordered-subsequence gate; D5/D6 |
| Model copy becomes authoritative | persist deep-copied original elements; D8 |
| Replay duplicates state | existing committed receipt/CAS plus D10/D11/A1 completed restart; pending-receipt gap is #247 |
| Prompt retry loop returns | no prompt or caller changes; diff allowlist |
| Scenario hard-code | no names, IDs, module paths, or prose branches; A3/A4 |
| Broader exceptions masked | no generic catch; #211/follow-up separation |

## 15. Tracked follow-ups and non-goals

- #211: startup transition-recovery exceptions can still terminate the engine.
- #247: a complete pending T091 receipt is not frozen across restart; a second T091
  decision can overwrite it. PK-004 A1 starts before that receipt and does not claim
  the two unimplemented partial-write crash boundaries.
- #248: startup exposes an actionable prompt before v2 resume and can process its
  wake input after completing the old travel. PK-004 records a separate player-
  continuation verdict and does not call that behavior fixed.
- #249: non-duplicate invalid T091 output, busy-lock, and state-conflict paths lack a
  complete fail-forward/correction policy. PK-004 preserves their gates rather than
  weakening them.
- #138: plural monster names/quantity materialization is a separate monster-instance
  representation defect and is not changed here.
- TW-019, #246, and TW-013 are explicitly excluded by owner scope.

No new referee, generalized transaction framework, schema identity, migration,
dedicated retry coordinator, or model prompt is justified by PK-004.

## 16. Review protocol

This is a FULL Part 3 review. Six independent lenses review the same SHA, without
seeing one another's verdicts:

1. Architecture -- authority boundary, data flow, replay, concurrency/locks.
2. Fail-Forward -- B1/B2, duplicate recovery, gate polarity, no abandonment.
3. Acceptance -- native real-game evidence and falsifiable oracles.
4. Consumer/Compatibility -- both callers, legacy data/schema/provider behavior.
5. Player Experience -- pacing, narration, agency, prompt/control handoff.
6. Leanness -- AP-1..AP-7, four leanness tests, one-file scope.

Any blocking finding changes the plan, produces a new SHA, and requires all six to
confirm that same SHA. After convergence, Claude independently reviews the full plan.
Implementation remains blocked until the owner explicitly approves execution.

### Round-1 finding disposition

| Finding | Disposition in revision 2 |
|---|---|
| Excess-copy capping lacked observed/ratified authority and was not lean | REMOVED; Approach A is now chosen |
| Zero-budget unknown values could be silently erased | ELIMINATED by removing the entire capping design; D9 remains a negative control |
| Pending T091 receipt can be overwritten across restart | TRACKED separately as #247; unsupported A5 claim removed |
| Invalid output/lock/conflict paths can terminate | TRACKED separately as #249 (+ #211); native-pass overclaim removed |
| Repaired duplicate branch could be NOT-REACHED | A1/A2 now require captured repeated T091 values or verdict NOT-REACHED |
| Legacy `run` has no current player caller | GL-1 corrected; compatibility-only proof |
| Startup exposes prompt and reuses wake input | TRACKED as #248 with a separate mandatory PX verdict |
| PX transcript oracles were incomplete | Five factual checks, second person, disclosure, acknowledgment, and progress added |

## 17. Resolution ledger

| ID | Decision | Status / authority |
|---|---|---|
| D-PK004-1 | Structured-identical original rows are separate legal occurrences, not automatic duplicates | Evidence-settled by official module + schema |
| D-PK004-2 | Delete only the blanket repeated-value rejection; retain over-cap rejection in the existing occurrence walk | PROPOSED -- panel/Claude/owner gate |
| D-PK004-3 | Keep ordered-subsequence, exact-value, deep-copy, CAS, and write-verification protections | PROPOSED -- panel/Claude/owner gate |
| D-PK004-4 | No prompt change or referee call; no semantic judgment remains in the defect | PROPOSED -- panel/Claude/owner gate |
| D-PK004-5 | One-file production allowlist: `utils/reconcile_location_state.py` | PROPOSED -- panel/Claude/owner gate |
| D-PK004-6 | Pending-receipt, startup prompt/wake-input, and generic invalid-proposal policies remain separate | TRACKED in #247/#248/#249 (+ related #211) |
| D-PK004-7 | Implementation authorization | OPEN -- owner only after six-lens + Claude review |

## 18. Stop conditions

Stop and return to design review if any of these occurs:

- evidence shows repeated original entries are not independent occurrences;
- deleting the blanket guard changes any behavior beyond letting the retained
  ordered-subsequence walk consume legal repeated source occurrences;
- the real T091 response requires semantic judgment rather than exact-value mapping;
- the fix requires a schema, prompt, receipt, caller, or second production-file change;
- A1 cannot recover the untouched checkpoint without manual state editing;
- any acceptance arm loses state, duplicates time/narration, bypasses the three-agent
  narration chain, or introduces/worsens prompt/control behavior beyond the separately
  baselined #248 failure. A1 must still record #248 as `player continuation: FAILED`;
  that known separate verdict is not credited as success and does not by itself force
  a PK-004 redesign.

At a stop condition, do not improvise, widen scope, or implement a fallback. Revise
the complete plan and repeat all review gates.
