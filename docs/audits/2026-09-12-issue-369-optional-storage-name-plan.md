# Issue #369: preserve an omitted optional storage name

Status: IMPLEMENTED AND TESTED; owner D-369-3 authorizes narrow shipment.
Author/controller: codex-wsl. Planning and execution chronology follows; later
explicit owner rulings below supersede earlier phase restrictions.
Execution addendum 2026-09-12: after presentation, owner approved implementation
and testing verbatim: "approval to impleent and test the narrow fix". D-369-1 is
now ratified in live #193 Part 5. Original planning status above is historical;
implementation and testing are authorized, commit/push/merge are not.
Testing continuation 2026-09-12: D-369-2 authorizes further ordinary real-play
testing after the first NOT-REACHED arm, including clarification that gear is left
at this location rather than carried. Prior stop-after-unreached wording is
superseded; exact verdict bars, no synthetic/state/prompt edits, and narrow product
allowlist remain. A3/A5 may use the first actual container from A1 or A2: their
ID/conservation/persistence assertions are identical. A1 itself still requires
real omitted storage_id AND storage_name, never inferred from a named operation.

## Shipment authority (2026-09-12)

Owner D-369-3 authorizes shipment of the tested narrow fix and evidence, with the
disclosed outside-scope failures retained. #374 is a separate investigation and
reviewed-plan task, not included in this implementation. No gameplay changes
have been made since the reviewed native candidate.

## 1. Scope and policy epoch

Live #193 v3.1, updatedAt 2026-09-12T13:00:08Z, read 2026-09-12.
Authority: https://github.com/MoonlightByte/NeverEndingQuest/issues/193
Failure: https://github.com/MoonlightByte/NeverEndingQuest/issues/369

Planning checkout: /home/loup/neq-worktrees/369-optional-storage-name,
branch plan/369-optional-storage-name. Captured HEAD and origin/main are
b7d86bdc1f316ddfd2bd75983f19e5597384399c; merge-base --is-ancestor succeeds.
These are observed provenance, not runtime or enduring revision authority.
Fetch and recheck ancestry, policy epoch and later owner rulings before implementation
and shipment. Do not use the dirty shared checkout; never worktree prune from WSL.

Product allowlist: core/managers/storage_manager.py only, the implicit-create
dictionary in StorageManager.store_item. Documentation: this plan and a sanitized
acceptance record. Tests/review artifacts remain local/untracked. No schema,
prompt, provider, model binding, retry, transaction, UI, name-identity or inventory
writer changes. No new public helper, store, marker, recovery loop or configuration.

Player promise: README.md:715-717 and :864-867, location-based storage with
automatic inventory transfers. This fix removes one internally generated invalid
operation; it does NOT certify all inventory safety or failure narration.

## 2. Verified failure, lineage and scope boundary

OBSERVED: /mnt/c/363-ev-wXKOTp/A/model_captures/T049.json[0], timestamp
2026-09-12T06:49:41.881545+00:00. Parsed response:

```json
{"action":"store_item","character":"Eirik Vane","location_id":"TW05","location_description":"A dry hollow beneath the roots at the party's current hiding place, beneath a notched trunk; the lute is wrapped in oilcloth.","item_name":"Mira Quill's Lute","quantity":1}
```

The record labels selection gpt-5.6-luna|none and latency_s 4.053; actual
response.model is not independently exposed here and is UNKNOWN, not inferred.
No storage_id or storage_name key exists. This is a real model response, not a test stub.
Protocol /mnt/c/363-ev-wXKOTp/A/protocol.ndjson physical line 3368 / seq3351:
`Storage operation validation failed (ValidationError: None is not of type 'string'`.
Physical lines 3386-3388 / seq3369-3371 report failure to create/store.
Original #363 acceptance preserves the unchanged item and empty playerStorage.

CODE-PROVEN: storage_manager.py:348-354 inserts storage_name via dict.get,
turning absence into None. Its next create_storage call validates the synthesized
operation at :220 against schemas/storage_action_schema.json:25-27 (string only).
The schema does not require storage_name. Thus a valid omitted optional field
becomes invalid due to our dictionary construction, before any container write.
create_storage:248 ALREADY implements the absent-name default using container type
and canonical location name. No new name or semantic decision is needed.

Lineage: blame :348-355 -> 18e7052f9, "Fix all file paths after code
reorganization". Follow-history shows the same insertion in c88affc0,
"Implement comprehensive player storage system with enhanced location summaries".
Both are mainline ancestors; #369 documents this inherited defect. #363 changed
only validator prompts and did not introduce this code. No historical issue link
was found in those commit subjects; the observed-failure issue is #369.

The scene's cache-vs-chest policy is #365, not a license to change storage_type.
False success / continued siblings after storage failure is #364/#360. This plan
must not turn either into a PASS, and does not alter their machinery.

## 3. Spec-pin: authority and end-to-end path

#193 Part 2 p6 NEQ-INV-01/02 (body lines ~128-131): model maps scene to typed
operations; code owns arithmetic, conservation and writes. p12 NEQ-SCHEMA-01/02
(~165-168): frozen schema, preserve existing values. p13 NEQ-ACCEPT-01..03 and
NEQ-TEST-01/02 (~172-177): real native acceptance, negative controls, serial play.
p10 NEQ-WEB-01/03: one game thread and truthful progress. Stable rule IDs control
if live issue line numbers drift. Part 1 AP-4/5/6/7, B1/B2 and GL-1 apply.
Read docs/architecture/README.md and web-headless-surfaces.md in full; the index
contains no dedicated inventory schematic. Storage code below is the direct
authority mapping, not a newly invented architecture document.

Ordinary input -> T067 proposed storageInteraction -> T065 validation ->
core/ai/action_handler.py:4384+ -> storage_processor.process_storage_request
(:449), T049 capture (:322) -> execute_storage_operation (storage_manager:922+)
-> store_item:295 -> validate outer operation:300 -> load/backup character and
storage -> verify owned equipment -> implicit create dictionary:348 ->
create_storage:216 -> validate:220 -> location from party_tracker:195+ ->
safe_write_json storage:271 -> remove item in memory -> write character:425+
-> existing AI character validation -> write storage contents -> existing result.
The processor path above is core/managers/storage_processor.py (not core/ai).

Authority table:
| Datum | Authority | Proposed change |
|---|---|---|
| Intent/container request | DM and T049 typed proposal | None |
| Optional name presence/value | Validated operation, schema | Preserve membership and exact value |
| Default display name | Existing create_storage type/location expression | Make reachable for missing key; do not duplicate it |
| Location | Canonical party_tracker through existing resolver | None |
| Item identity/quantity | Character equipment and storage contents | None |
| Durable storage | player_storage.json existing safe writes | None |
| Narration | Non-authoritative player output | Inspect; do not claim state from prose |

Commit/locking: this path has sequential existing safe writes and backups, NOT a
new all-files atomic transaction. Preserve every write/rollback/lock ordering.
safe_write_json owns each file's existing lock/write primitive. No lock is added,
removed or moved across provider waits; _STAGED_STORAGE_LOCK is untouched.
On the fixed input, schema succeeds and existing creation/transfer continues.
Explicit invalid fields still fail the outer schema before this projection.
Unowned items remain rejected before container creation. Busy/transport/failure
handling remains inherited, not newly bounded or represented as globally safe.

Caller-family compatibility: create_storage also has a direct dispatch path;
prepare_staged_operation:613+ constructs travel-owned storage in memory without
this offending intermediate dictionary. It already handles missing name at :667.
Do not unify these runtimes, change empty-string semantics, or absorb travel
transaction work. No new second pathway is introduced. Existing named storage,
existing storage_id and direct create behavior stay byte-identical.

## 4. Smallest sound change and alternatives

Remove only the unconditional storage_name entry from create_operation. Immediately
after constructing that dictionary and before calling create_storage:

```python
if "storage_name" in operation:
    create_operation["storage_name"] = operation["storage_name"]
```

This is membership, not truthiness. Missing remains missing. Supplied strings,
including empty string (legal under the frozen schema), remain exactly supplied.
Explicit null/number/object remains invalid at the existing outer schema; do not
silently normalize invalid input. No strip, coercion, alias, name list or fallback.
Expected product delta: +2/-1, one existing method. Candidate fragment is a plan,
not an implemented patch; post-code scans must inspect the ACTUAL diff.

Rejected: allow null in schema (weakens contract); fill arbitrary name/empty string
(overrides existing default); duplicate default computation (two authorities);
force model to emit a name (unnecessary model burden/prompt change); add a micro-call
(no judgment missing: schema already decides presence semantics); rewrite storage
transactions or error narration (independent defects, broader scope).

Agentic-first: models still decide what the player meant. Code fixes the mechanical
translation of an already accepted tool argument. No interpretation is hardcoded.

## 5. GL-1 behavioral contract

| Existing behavior, origin | Goal | Disposition | Proof |
|---|---|---|---|
| Unconditional name projection, 18e7052f9/c88affc0; #369 | Forward optional custom name | PRESERVED for present keys; RETIRED only absence-to-null bug under #369 task-2 | D1 presence table; A1/A2 |
| create_storage:248 absent default, same initial storage lineage | Usable display name without custom naming | PRESERVED, reused unchanged | A1 default from actual type/location |
| Outer/inner schema gates:131/220/300 | Reject invalid shape before write | PRESERVED | D2 schema polarity; firing live branch only if reached |
| Ownership checks before implicit create:325-342 | No creation/transfer of unowned item | PRESERVED | A4 no-op state comparison |
| Existing-ID path:345 and storage writes/rollback | Existing container use, quantity conservation and recovery | PRESERVED byte-for-byte | A3 retrieve/re-store; diff audit |
| Travel staging and direct create | Other entrants keep their contracts | PRESERVED byte-for-byte | D3 caller-family/static A/B |

No other branch, field, persisted value or original goal is removed.
Preservation means exact supplied field values and unchanged persisted shape;
the intermediate dictionary insertion order changes and has no semantic consumer.
Timestamp/UUID fields are not expected to be identical across separate live runs.

## 6. Tasks (execute only after owner approval)

task-1 / C0: Read live #193 and #369 again, policy/ancestry/cleanliness capture;
freeze source, schema and prompt hashes and EOL profile. Inspect real capture and
independently record the exact missing-key causal chain. No product edits in C0.
Record authentic saved storage examples for compatibility, without altering saves.

task-2 / C1: Implement only section 4 in storage_manager.py. Preserve per-region
EOL and unrelated bytes. No extra fixes, schemas/prompts/tests tracked or new files
of runtime code. Verify product allowlist, raw diff and GL-1.

task-3 / C2: Focused development gates, clearly NOT gameplay acceptance:
D1 static/pure dictionary+schema contract checks for missing, named, empty, null,
number and object; valid absent input must stay schema-valid after projection;
present valid string byte/value preservation. No mocked provider or simulated game.
D2 frozen schema validates absent/name/empty, rejects explicit invalid types.
Ownership-invalid live check belongs A4, not fabricated model output.
D3 source/caller-family audit proving direct create/staged path/default/write order
unchanged; compare authentic records' schema validity before/after unchanged schema.
py_compile and pyflakes undefined-name gate; ASCII added-lines, EOL and whitespace
check. Fresh non-author simplifier pass, behavior unchanged. No new abstraction.

task-4 / C3: Serial native-Windows actual run_headless.py serve acceptance below;
no stubs, state edits, scripted response injection or overlapping probes. Use an
isolated short-path authentic game copy, configured OpenAI, current prompt files
refreshed and hash-verified, actual selected binding and response.model recorded.
Use C:/Python312/python.exe if still the configured native interpreter; verify
it before boot, never install or substitute a bare launcher blindly.

task-5 / C4: Non-author post-implementation audit (NEQ-REVIEW-15), final PX review,
actual-diff sentinel scans, report exact verdicts. Owner gates commit/merge and issue
closure; plan review is NOT execution or ship approval. No other issue repairs.

## 7. Acceptance, predetermined before code

All arms use real ordinary player turns, one command then read complete response
and disk before choosing another. No combat, new module, or large test folder needed.
Start from an authentic save with an owned equipment item, an established location
and no ambiguous extra containers. Preserve original source/save; verify hashes.
Existing #363 evidence is baseline, not proof of this new candidate.
Run A1 and A2 on separate pristine copies of that saved state, with NO existing
containers at the current location. storage_processor.py:250-261 otherwise fills
a missing storage_id from an existing container and bypasses implicit creation.
Use A1's resulting container for A3 and its final clean state for A5. No concurrent
games; quiesce one copy before starting the next. Copies are test setup, not edits
to in-game authoritative state. Record the processor's post-processed operation
as well as raw T049 output to prove the actual manager boundary was reached.

| Arm | Required observation | Verdict bar |
|---|---|---|
| A1 omitted name, new container | Real T049 store_item lacks BOTH storage_id and storage_name; manager creates and stores | Actual omitted-name branch reached, no synthesized null, one new container, existing default display name, exact item count conserved, next playable prompt |
| A2 supplied custom name | Real T049 store_item omits ID but supplies name | One container retains exact supplied name, conservation, next prompt |
| A3 existing container + retrieve | Real retrieve then store against same actual ID | Same container/metadata, no new creation, quantities conserved both ways |
| A4 unavailable item | Ordinary request to store an item character does not own | Narrated refusal/no mutation; distinguish model refusal from manager ownership gate. Only reached layer gets PASS |
| A5 persistence | Supported Save, later normal turn, Load/restart | Storage and character state equal saved clean state, available playable prompt and history |

A1 cannot pass if T049 names the container or emits separate create_storage.
Record NOT-REACHED and return to owner if normal play cannot reach it; no prompt
shopping or forcing output. A2 likewise must reach implicit-create, not merely
direct create. Direct-create observations may be reported as extra controls only.
Do not demand A4 schema-malformed output from a model; D2 proves schema contract,
live malformed branch is NOT-REACHED unless naturally observed. No error weakening.
The inner gate's historical firing is already observed at protocol physical line
3368, before this fix; that baseline is not a post-fix malformed-input PASS.
The internal create dictionary is not logged. A1's no-null conclusion combines
the real omitted-key T049/manager-boundary evidence, default deviceName on disk,
zero None-is-not-of-type events for that turn, and D1/source verification. It is
not a claim that the internal dictionary itself appeared in a runtime capture.

Snapshot before/after player_storage.json, relevant character file(s), party_tracker
and conversation. Compare item identity, quantity sums, container IDs/names/location,
metadata and every non-empty->empty change, allowing only intended movement/equipped
state and timestamp/access-log changes. Item choice is fixture evidence, never code.
If an independent writer/validation error prevents completion, mark the arm FAILED
or BLOCKED, identify the issue and stop rather than silently changing the oracle.
Do not relabel #364/#360 false success as a pass for inventory/player truth.

Each evidence block: input timestamps and exact player text; full protocol and
capture physical lines/indices; T067/T065/T049 and later writer-validation call
durations relative to input; actual response.model or UNKNOWN with reason; exact
typed payload key presence; verbatim narration beside state; zero or counted
invalid/retry/fallback/degrade events with scan command; fixture/protocol/prompt
hashes; clean Quit and zero leftover acceptance children. No browser or universal
inventory-safety claim. Independent PX reviewer checks narration against disk.
Record deviceName beside the narrated container noun; any cache/chest mismatch
keeps its separate #365 PX verdict, rather than being repaired or hidden here.
Historical A5 snapshots in /mnt/c/363-ev-wXKOTp show a named container and are
compatibility evidence only, not a substitute for candidate A2 implicit creation.

## 8. Part 3 review protocol and gates

FULL conservatively: replacing a live operation projection; GL-1, optional-field
guard and shared manager consumer sweep. Separate blind seats: Architecture,
Fail-Forward, Acceptance, Consumer/Compat, Legacy/GL-1, Player Experience, Leanness,
No-Limits, Single-Path. Independent logged-in Claude Code agents (Opus 5, medium,
per owner's delegation preference), read-only; controller alone edits this plan.
Each receives this file and full ledger, live rulebook, role/lane/warrant/write
authority/evidence contract, never another review. R1-R15 apply. No agent runs play.
No-Limits/Single-Path scan full touched file and proposed exact fragment now; no
implemented-diff verdict yet. Actual candidate diff rerun is mandatory post-code.
Inherited hits must name origin and existing issue/ratified exception, not be erased
or mislabeled clean; new genuine findings receive separate issues per Zero-Deferral.
Schema-Freeze: no schema delta; verify bytes. Platform-Provider: native acceptance
mandatory, no routing delta. Hygiene/ASCII/EOL/secrets/tracked-test gates mandatory.
Reconcile every finding and rerun required seats to same-SHA convergence plus clean
confirmation, except strictly plan-polish termination under NEQ-REVIEW-11.
All approvals remain conditional on owner execution approval after presentation.

## Tracked follow-ups

#364 storage failure propagation and #360 false success; #365 forced default chest
policy; #366 equipment-only storage lookup; #358 ammunition name removal; #368
equipment handoff ownership; #370 identity retention; #371 post-storage T053
unsupported-field correction. These are OPEN, separate tasks, not this fix.
#374 records the D-369-2 continuation's referee-directed removal instead of a
recoverable local cache (T065 rejects storage, writer removes item). Not repaired
or absorbed here; the successful manager transactions remain separately verdicted.
#324 tracks shared character writer/validator bounds. No acceptance workaround is
treated as repaired behavior. This plan supersedes no previous implementation plan;
#369 issue is the current defect record, #363 acceptance the historical observation.
#373 tracks CODE-PROVEN empty-name divergence between direct and travel-staged
construction. No blank-name gameplay failure is claimed: the inspected T049 set
has only one supplied name, Notched Root Cache, and no empty-name response.
Inherited storage_manager.py:798 max_attempts=1 belongs to #324; :803 fallback is
a status field, not a new mode. :242 uuid slice is local random identity generation,
not truncation of model context. These full-file scan hits remain unchanged.

## Resolution ledger

| ID | Finding | Disposition |
|---|---|---|
| F1 | Optional name absence is synthesized as null | task-2 |
| F2 | Valid explicit name including empty must not be replaced | task-3 |
| F3 | False success and later inventory failures are not this boundary | issue-#364 / issue-#360 (existing follow-ups, not newly filed claims) |
| F4 | Schema expansion/default-name invention would exceed scope | defensible: frozen schema plus existing default suffice |
| D-369-1 | Execution after reviewed-plan presentation | Owner APPROVED; #193 Part 5 D-369-1, implementation/testing only |
| R1-A | Architecture/FF/Consumer empty-name FYI, Single-Path SP-1 | issue-#373; code-proven divergence, no observed gameplay harm; separate from #369 |
| R1-B | Acceptance FYI1/2: historical gate and internal-dictionary observability | fixed-inline: source/static proof distinguished from runtime proxy; no new test or gate |
| R1-C | Consumer named-container evidence; Leanness processor path citation | fixed-inline: historical compatibility citation and explicit full path |
| R1-D | PX container noun vs deviceName | fixed-inline: clarify existing transcript-versus-state requirement; #365 remains separate |
| R1-E | Legacy insertion order and restored-default notes | fixed-inline: exact values preserved, no intermediate byte-order guarantee |
| R1-F | No-Limits inherited UUID/attempt and Single-Path status hits | defensible: UUID is not model truncation; status field is not a mode; issue-#324 owns inherited attempt bound |
| R1-G | Leanness prompt-name examples; model omission still legal | fyi: no prompt change; section 4 unchanged |
| R1-H | FF failure narration, rollback and schema polarity notes | fyi: existing #364/#360 and D1/D2 already cover these; no broader safety claim |

Independent review results and final content hash will be recorded separately so
the exact reviewed plan can remain frozen. FULL round 1: all nine separate blind
seats LGTM on SHA28e2403ffce9ca981a4c24cf6de03df77c0adc39b108bcda3b50dab4a99f238d.
Only plan-polish/advisory findings; controller folds above change no code steps,
types, state, tests or callsites. NEQ-REVIEW-11 plan-polish termination applies
after this full-coverage round; no code-class correction awaits re-verification.
Review is complete, not implementation approval. D-369-1 awaits owner response.
The preceding sentence is the historical review disposition, superseded only by
the execution addendum at the top; all technical scope and acceptance bars remain.
