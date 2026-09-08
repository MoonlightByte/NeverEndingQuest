# Issues 322 + 328: campaign export contract and hub preservation

Status: C1-C4 implemented locally under D-322-1; native A1 PASSED and A3 FAILED.
2026-09-08 C6 AMENDMENT PLAN ONLY: owner approved adding validator hub evidence.
Section 10 supersedes the former two-reader-only scope and outdated approval
status below. C6 needs independent review and post-review owner presentation
before code. Existing implementation/evidence is retained, never relabeled PASS.
Prior reviews: 2026-09-08-issue-322-plan-review.md; execution record is separate.

## 1. Authority and boundary

Live #193 v3.1 read this session; updated epoch2026-09-08T18:57:23Z after
codifying the owner's scope ruling (prior epoch2026-09-08T05:44:56Z).
Owner scope ruling is now Part5 D-322-2: "incldue that and creat teh revissed plan".
Scope comment: #293 issuecomment-5590268747. No new policy is inferred.
D-322-1 remains pending execution approval AFTER this plan's review/presentation.
Fresh branch/mainline evidence: HEAD and origin/main6d18d09b, ancestor verified.
These are audit evidence only, never runtime identity. Recapture before execution.
Worktree: /home/loup/neq-worktrees/322-campaign-export-plan.
Branch: docs/322-campaign-export-plan, documentation uncommitted.

Relevant doctrine: Part2 p6 NEQ-INV-02 (persistent property); p7 NEQ-NPC-01/02;
p8 NEQ-WORLD-03/04; p9 NEQ-SAVE-01/02; p11 NEQ-PROVIDER-01/02;
p12 NEQ-SCHEMA-01/02; p13 NEQ-ACCEPT-01..03/NEQ-TEST-01/02.
Read mainline module-lifecycle, provider-routing and companion-memory schematics;
actual source below corrects outdated consumer claims. README22,441,453:
remember consequences and restore module-specific history without inventing it.

Production allowlist (three files, narrow seams only):
- core/managers/campaign_manager.py: T039 instruction string, existing hub import
  loop with lossless structural adaptation, one shared hub-context formatter.
- core/ai/conversation_utils.py: existing established-hubs context block only.
- main.py: existing established-hubs DM-note block plus C6 validator evidence
  assembly only (section 10). Sanitization, gates and review loop unchanged.
Docs: this plan, its review/acceptance record, narrow module-lifecycle schematic
note. No T038 wording, archive source, T108, identity, model binding, transport,
lock order, save format, schema-file or generic lifecycle redesign.
No install/model download, tracked tests, production hooks or unrelated fixes.

## 2. Evidence and lineage

Private root: /mnt/c/agent-room-fleet-kit/local-data/.
OBSERVED #322: 311-native-regeneration-evidence/model_captures/T039.json record0,
timestamp2026-09-07T21:40:14.620366Z. Entire sent request and output read.
System: "Extract campaign-relevant data from module completion summary.
Be concise and factual." User message contains the full real T038 chronicle,
five goals and key names, but no container/member types. Real OpenAI selected
luna/none12.291s,5269in1343out; actual response.model absent from this capture.
Output is valid JSON but four arrays plus unlockedModules objects, all rejected
by campaign_manager.py127-157's five-key/four-map/string-list contract.
result.json returnedFalse79.406s; summary/campaign before/after compare equal;
recorded archive/sidecar hashes match. This proves this incident, not universal
model failure, a provider stall or a destructive write.

Prompt origin: ae007a83 "Implement complete hub-and-spoke campaign system",
campaign_manager.py407-418 at that commit; current blame699d15e6 is a license
sweep, not authorship. Validator:715732d5 provider-aware runtime integration.
Both precede #311 and are mainline ancestors.

CODE-PROVEN #328, independently identified by three review seats:
authentic campaign-before.json13-25 has Shadowfall Keep hubType=stronghold,
services=[rest,storage,sanctuary,information], ownership=party.
campaign_manager.py4402-4404 overwrites a complete hub with the new value.
A map containing just status/details loses these established fields. A scalar
also passes existing outer validation. conversation_utils.py815-828 assumes
a mapping and joinable services: defaults invent settlement/basic services/party,
or a scalar raises and a broad catch drops the ENTIRE world-state context.
main.py9133-9143 independently defaults type/ownership. Original arrays never
committed, so no observed destructive #311 incident is attributed to this path.
Writer's old goal: ae007a83 import consequences;715732d5 changed target ownership.
Both consumer defaults originated329496ba, "Fix module transition system and
enhance hub details"; services join changed be4df1cb, "fix(context): preserve
complete world and validation history (#262)". Reverify ancestry at execution.

## 3. Architectural flow and canonical owners

Accepted source history/plot/party
  -> existing T038 chronicle
  -> existing T039 structured proposal (explicit container/hub-field instructions)
  -> existing generated-export validator
  -> existing transaction: preserve existing hub fields, overlay supplied facts
  -> committed summary + campaign maps + module availability
  -> one shared factual hub formatter, used by both DM-context readers and,
     after reviewed C6, the semantic validator's independent evidence context.

| Boundary | Canonical owner | Required behavior |
| --- | --- | --- |
| Historical events | original archive + existing T038 | No new archival source or rewritten old episodes |
| New consequences | T039,3910-3947 | Model proposes meaning, no Python prose interpretation |
| Export admission | _is_valid_campaign_export_data127-157 | Entire validator unchanged, including historical fallback compatibility |
| Hub field base | latest campaign state inside _commit_module_summary_locked3428 onward | Merge against commit-time persisted hub, not stale pre-model copy |
| Other campaign categories | existing import loops4395-4408 and availability4410 | Unchanged behavior, no new injection feature |
| Publication | existing pending/preimage/currentness transaction | Existing rollback and epoch checks, no new store/lock |
| Read context | conversation_utils.py811-824 and main.py9133-9141 | Same formatter; all stored facts, no fabricated defaults |
| Other context | action_handler.py4522 -> accumulated summaries4826; summary injection | Distinguish T038 prose/worldState from typed-map propagation |
| Companion episodes | #311 existing T108/stores | Normal completion unchanged; regeneration never rewrites sidecars |

get_campaign_context is only called by an unused utility. It is NOT the evidence
target. No direct relationship/artifact-map DM injection was found: persisted
export success is not falsely labeled per-category live injection. Do not
activate that unused utility or add a broader context pathway.

Both ordinary completion3322 and regeneration4263 use _generate_module_summary.
Regeneration reads latest original archive4189-4207, preserves visit metadata
and publishes through the same transaction; failure4275 keeps prior summary.
Generation happens outside phase locks; commit uses existing party/completion/
campaign order and exact owner/currentness. Nothing holds a new lock or runs a
new model. Transport retry/reap and LiveProviderSuperseded remain untouched.

## 4. Exact proposed mechanics

### C1 - Teach the existing model the contract

Keep full T038 text and all five extraction goals. Replace only final generic
format instruction. Proposed wording (JSON braces doubled inside Python f-string):

    Return only one JSON object with exactly these keys:
    {"relationships": {}, "artifacts": {}, "hubs": {}, "worldState": {}, "unlockedModules": []}
    This illustrates container types, not permission to omit supported facts.
    The first four categories must be objects, never arrays, with non-empty
    string keys naming the source entity, item, hub or world-state fact.
    Keep supported status and detail in the values; do not invent or rename facts.
    Each hubs value must itself be an object of recorded facts. Use existing
    hubType, ownership, services, description or other fact fields when supported.
    services, when stated, is a list of service names. Omit fields the source
    does not establish; omission is not deletion of previously recorded details.
    Do not supply null, blank or empty-object defaults for unknown information.
    An explicit empty services list means the source establishes no services;
    never use it merely because services were not mentioned.
    A new supported field value may update an earlier fact; record explicit
    changed ownership as its actual value, not a blank or guessed party owner.
    unlockedModules is a list of non-empty exact module identifier strings,
    not objects or proposed adventure titles. Include only explicitly established
    identifiers and unlocks; an unresolved lead does not establish an unlock.
    Use empty category objects and an empty unlock list when no facts support
    entries. Preserve uncertainty and attributed beliefs; no invented details,
    extra top-level keys, markdown fences or commentary.

Do not add a universal nested format to relationships/artifacts/worldState.
T039 still receives the same chronicle, not a new atlas/registry packet.
No claim of new mechanical identity enforcement: broader reconciliation #326.
No model change absent matched baseline control. #318 upstream T038 invention
is separate; do not hide it by weakening factual acceptance.

### C2 - Preserve hub fields at the existing writer

Keep the ENTIRE existing structural validator unchanged. New T039 instructions
ask for hub objects, but old checkpoints and tracker-derived fallback may contain
valid scalar/list hub values. Never route those accepted facts into a new refusal
or empty-fallback branch. No new services/type gate is needed: the formatter
safely serializes every persisted JSON value.

Adapt a non-object hub value mechanically to an object whose existing details
field contains that EXACT value; do not parse, summarize or infer it. Mapping
values remain unchanged. Apply the same structural rule to the existing record
and incoming record at the one import seam, regardless of origin. details already
exists in authentic T039 output; this adds no schema/version or separate legacy
mode. It is per-use lossless representation, not a migration scan. Old stored
values remain directly readable without rewriting them on Load/startup.

Within _handle_module_completion_export's existing hubs loop:
- Match only the exact already supplied key; no alias/fuzzy/name normalization.
- First derive the effective incoming patch, excluding only null, blank strings
  and empty objects as no-fact values. Do this BEFORE adapting/writing the base.
  If no effective fields remain, leave an existing record exactly unchanged and
  do not create a new empty hub. False, zero and empty lists are effective data.
- For existing object: deep-copy its complete contents as the base. An existing
  non-object becomes details with its exact value; absent key has an empty base.
  A no-fact incoming proposal leaves the record byte-equivalently unchanged,
  rather than rewrite it merely to adapt its shape.
- For an effective incoming non-object, the patch is its exact value under details.
  This preserves existing type/services/ownership, including when resuming an
  old accepted scalar checkpoint. No raw fact is silently discarded. If details
  itself is explicitly updated, replacing that one field is a new value, just
  as replacing a supplied description field; no historical field-value archive
  is introduced. Unspecified old fields remain intact.
- Apply supplied top-level fields individually. Missing field is no update.
  Null, blank string and empty object carry no new fact and do not overwrite an
  existing nonempty value. False and zero are real values, not discarded by a
  generic truthiness test. A nonempty supplied field replaces that field.
- Explicit services=[] means known no services and replaces the old services.
  Other lists, including empty lists, are explicit supplied field values; do not
  union lists and resurrect removed services. Prompt must not emit unknown defaults.
- Updates are field-level, not inferred recursive reconciliation. A supplied
  nonempty nested value is one new value; unrelated top-level fields survive.
- No entry-level deletion, key renaming, invented ownership/type, new timestamps
  or mutation to the caller's proposal/old input objects.
- Other category loops and the existing atomic transaction remain byte-preserved.

The model decides WHAT changed; code implements presence-based field updates,
not story inference. Preservation oracle: omitted services/type/ownership and
establishment metadata stay identical; a real explicitly changed field takes
effect. Services clearing must be an actual supported model fact, not a default.
This is not a global campaign merge library or a retrospective data migration.

### C3 - One truthful, compatibility-safe read formatter

Add one pure public formatter in campaign_manager.py, e.g.
format_campaign_hubs(hubs), initially with the two current DM consumers:
conversation_utils hub block and main DM-note hub block. C6 adds the validator
as its third production consumer. No second formatter or new file/store.
Serialize the complete stored hub map using JSON, including names and every
nested field/value; prepend a short factual authority instruction:

    Recorded hub information follows. Use only recorded facts. Missing or null
    fields do not establish a type, service or owner. An explicit empty services
    list records no services. Do not infer party ownership from hub membership.

Use no character/list budget, recency window, .get defaults or service joining.
Empty map produces no hub section, as before. Historical scalar/list/null hub
values are rendered as recorded JSON, not coerced or silently dropped; there is
no source-type-dependent second behavior. The formatter does not mutate disk.
No hubs-specific parsing error can suppress separate module-availability text.
Unexpected non-JSON corruption is outside this plan's persisted JSON contract,
not license for a new corruption gate. Existing outer I/O failure paths remain.
No new credential/hidden-location fields are introduced; same campaign records
are already intended context, but complete-field exposure gets PX review.

Both callers consume this exact string. Keep module availability, current
location/party note, other context and caller ordering unchanged. Do not activate
unused get_campaign_context or change establish_hub's separate creation action.

## 5. GL-1 behavioral contract

| Replaced behavior | Mainline origin / goal | Disposition and proof |
| --- | --- | --- |
| Generic format sentence |ae007a83 hub/spoke, mechanical blame699d15e6| PRESERVED five goals + full source, explicit type guidance; real request/output |
| Structurally admitted hub values |715732d5 validator| PRESERVED validator and historical fallback/replay; all admitted JSON hub values adapt without losing unrelated fields |
| Whole hub replacement4404 |ae007a83 and715732d5 import| PRESERVED apply genuinely new facts; omitted established fields no longer erased under owner D-322-2; omitted vs explicit services-change checks |
| Consumer default party/settlement/basic services |329496ba andbe4df1cb| RETIRED under D-322-2; neither source nor data establishes these defaults; existing explicit values still rendered |
| Consumer mapping assumptions / services join |same reader lineage| PRESERVED hub context purpose through one complete JSON formatter; historical values cannot raise solely due shape |
| Existing available-module and nonhub context |unchanged| PRESERVED byte-identical unrelated blocks, actual input payload contains both |
| Regeneration visits/archive/POV |existing lifecycle +#311| PRESERVED exact before/after archives/sidecars/visit metadata |
| Load/Reset/Quit and transaction fencing |existing lifecycle| PRESERVED byte-identical code, scoped control/live acceptance |

No new store/marker/schema/version/flag/provider path/model call/thread/lock.
One new pure formatter needs AP4 warrant #328 plus owner D-322-2 and three-callers
audit. Existing importer receives a field-overlay loop and structural adaptation;
no generic helper framework. Leanness DA now triggered by new public symbol/guard.
No runtime cap/retry-count change; inherited export fallback debt not newly blessed.
Coverage includes fresh provider export, tracker-derived fallback and an accepted
generated_summary replay that skips T039 (3261/3312): all reach import3525.

## 6. Execution slices after final approval

C0: capture fresh policy epoch/ancestry; establish isolated implementation branch;
inventory authentic campaign hub shapes, visit metadata and current fields.
Read existing normal establish_hub entrants for compatibility, do not refactor.
Pin regional EOLs in all three files; no whole-file normalization.
C1/C2/C3: implement the reviewed prompt, outbound boundary/import and shared
read formatter as separately inspectable slices; keep the combined change off
main until all pass. Each slice gets focused checks and a simplifier pass.
C4: baseline/candidate REAL model prompt probe at unchanged OpenAI luna/none,
same authentic T039 input. No fabricated model output or gameplay test claims.
Observe nested hub facts, no arbitrary postprocessing to make it pass. Two
failed fixes -> stop/repro/mainline layer-down bisect, not endless prompt edits.
C5: native real acceptance below, one operation at a time; failed arm -> preserve
evidence and stop, no mid-acceptance repair. Independent post-implementation
audit (all five NEQ-REVIEW-15 items) + owner verdict before merge/push.

## 7. Development checks and native acceptance

Development aids only, local/untracked: actual parser/serialization/I/O contracts,
not stubbed player/model behavior. Validate real corpus unchanged by historical
load path; candidate does not apply outbound admission during loading.
Negative primitive matrix:
- Original captured four arrays rejected; historically valid scalar/list hub
  values STILL accepted; real generated mapping accepted. No new admission gate.
- Existing checkpoint generated_summary with scalar hub (1436-1518,3261/3312)
  can be imported without running T039 or dropping existing stronghold fields.
  Primitive importer input, not a simulated live crash-replay test.
- Tracker-derived fallback containing a scalar hub plus relationships/worldState
  remains valid and preserves all categories; no new all-empty fallback.
- Existing rich hub + partial status/description retains omitted metadata.
- Empty proposal does not wipe old object; null/blank/empty-map fields preserve
  known values; false/zero retained; explicit empty services clears the list.
- Old scalar plus description:null/blank/empty-object leaves exact old scalar;
  effective-field filtering precedes any adaptation/publication decision.
- Source dictionaries remain unchanged; same-key repeated patch is idempotent.
- Complete formatter handles authentic maps and stored JSON scalar/null/list
  shapes without exception and without inventing defaults; no length loss.
Synthetic JSON for pure merge/format contract aids is not simulated gameplay.
Record firing branches as primitive evidence, never native live PASS.
Compile + pyflakes undefined-name, diff whitespace, FS1/sentinel raw scans.
All three formatter production callers required, plus family scan for other readers.

Real evidence fixture: copied authentic #311 Keep_of_Doom failure and original
archives; official Keep_of_Doom/The_Thornwood_Watch, short native-valid source,
OpenAI only. Actual run_headless.py serve or existing maintenance API explicitly
labeled. One game/command at a time. No gameplay save edits, artificial encounter,
fabricated history or synthetic model outcome. Verify runtime source and loaded
prompt bytes, not branch label alone. Refresh copied prompts from checkout.
Captured actual response.model or explicitly unavailable, selected profile,
T-ID/row, input-relative latency/tokens, full request/output/player text.
No private capture/keys tracked. Exact before/after state and lifecycle counts.

| Arm | Operation | Required evidence |
| --- | --- | --- |
| A1 | Real regeneration via existing maintenance API on authentic failed copy | T038/T039 run, provider export accepted and committed, methodTrue/export_failed=false; original archives, visit fields and both companion sidecars unchanged |
| A2 | Real ordinary cross-module departure and next playable turn | Complete T013/T063/T064 and T039; imported typed objects on disk; actual world-state/DM-note hub packet reflects authoritative preserved record; #311 final memory still runs; no false typed relationship-map injection claim |
| A3 | Owned stronghold and friendly/unowned place from authentic source/campaign | Compare original stronghold type/services/ownership/metadata, real proposed partial hub and final record; missing fields preserve facts; friendly place never gains invented party owner; complete main DM request and five narration claims checked |
| A4 | Real-model C4 probes + retained invalid gate | Original output rejected, actual new shape accepted; explicit positive unlock only when source supplies exact identifier, otherwise NOT-REACHED. Current invalid model response if natural -> existing fallback/previous-summary preservation and playable status; no manufactured live branch |
| A5 | Ordinary Save, subsequent turn, Load, Quit | Hub/campaign and companion files restore; actionable prompt; no orphan child. Pending-T039 cancellation only if naturally reachable; label NOT-REACHED otherwise |
| A6 | Genuine service/ownership change if normal gameplay supports it | Source establishes actual change, T039 proposed field and disk agree; no default clearing. If unavailable, retain primitive polarity and explicit NOT-REACHED owner disposition before closure; no invented request facts |

A3's actual hub preservation and all three real consumers are core gates, not waived
by mere type acceptance. If authentic source lacks a friendly hub, locate a
product-legal real scenario or report NOT-REACHED; do not fabricate state.
A6 verifies replacing facts, not speculative new capability; no retention-by-
ignoring every update. Zero fallback/omission counts stated when zero. Unrelated
nonempty->empty changes surfaced, not hidden. Player text judged independently.
A model's prose can repeat T038 facts without proving T039-map propagation.
No all-provider, all-memory-fidelity or universally hallucination-free claim.

## 8. FULL review and reconciliation

Required nine separate blind seats: Custodian, Fail-Forward, Acceptance,
Consumer/Compat, Legacy-Contract, Player-Experience, Leanness, No-Limits,
Single-Path. Each receives full current plan+ledger and policy. Owner scope is
closed, execution gate open. Full same-SHA review plus clean confirmation, except
the policy's narrow plan-polish exception. Code-class corrections must reverify.

Schema-Freeze: zero admission/verdict/schema changes; same accepted JSON data types,
per-use structural adaptation without metadata loss; authentic compatibility.
Platform/Provider/Hygiene apply; no profile changes, ASCII/EOL/secrets/tests.
Limits gate: no new numeric runtime bounds. FS1 applies all changed branches.
Large-change gate not anticipated; dynamically recalculate rather than waive.
Sentinels paste raw whole-file and candidate-diff scans; planning diff empty is
not implementation acceptance. Source caps elsewhere are classified with current
lineage/owner issue, never repaired incidentally or blessed by silence.

## Tracked follow-ups

- #322: T039 outer contract and unchanged failure-path observation.
- #328: IN SCOPE now for hub contract/writer/readers, not global data migration.
- #318: upstream T038 invention/retention, remains separate.
- #317: archive/round-trip retention, remains separate.
- #326: canonical naming pressure tests, no new identity mechanism.
- #293: other hash/retry/corruption decisions unchanged; D-322-2 scope resolved.
- Broader relationship/artifact-map direct injection not authorized; do not
  activate an unused helper or confuse matching chronicle prose with its output.

## Resolution ledger

| ID | Finding | Disposition | Proof |
| --- | --- | --- | --- |
| F1 | Wrong outer containers in actual T039 | task-C1 | Real captured baseline/candidate then A1/A2 |
| F2 | Invented adventure titles as module unlocks | task-C1 | Source-only exact identifiers, positive/absent actual evidence |
| F3 | Upstream chronicle invention | issue-#318 | Do not claim T039 restores original transcript truth |
| F4 | Archive/companion retention outside this seam | issue-#317 | No archival/episode edits |
| F5 | Historical schematic pending labels | fyi | Current source anchors; narrow new note only |
| F6 | Universal compliance unproven | task-C4 | Matched real probe, no binding change |
| F7 | Final execution approval | escalate:@owner | D-322-1 remains open after reviewed presentation |
| CC1/ACC1 | Wrong supposed live consumer | task-C3 | Both actual readers, category-specific attribution |
| CC2/PX1 | Hub overwrite and fabricated/default context | task-C2/C3 | Owner D-322-2, A3 core gate, #328 included |
| L1 | Evidence root/original prompt attribution | fixed-inline | Absolute private root +ae007a83 |
| L2 | Two-strikes missing causal bisect | fixed-inline | C4 explicitly requires it |
| SP1 | Incomplete manager private branch no live entrant | fyi | No production constructor found; no speculative deletion |
| FF2 | Already accepted scalar checkpoint bypasses fresh generation | task-C2 | One importer adapts incoming and existing values; checkpoint-shaped primitive |
| CC3 | Tightening shared validator would empty unrelated historical fallback | task-C2 | Dropped proposed validator tightening; unchanged fallback admission, preservation primitive |
| ARCH2 | No-fact mapping could erase an old scalar | task-C2 | Compute effective patch first; no-effective-fields preserves exact old value |

## 9. Owner presentation

D-322-2 scope is approved and codified; D-322-1 execution is not.
Explain: model supplies facts, code keeps recorded property details when no
replacement fact exists, both DM readers receive the same truthful record.
Existing services can still genuinely change; missing mention is not a change.
Approval of this plan would include clearer agent instructions and the narrow
lossless field overlay/formatter, not a rewrite of historical saves or an atlas.
After review, present exact unresolved limitations and STOP for final approval.

## 10. C6 amendment: canonical hub evidence for semantic validation

### Authority, evidence and bounded scope

Owner 2026-09-08: "Yes, mnarrolwy extend the plan to fix this gap" (D-322-4).
This authorizes the narrow plan extension; NEQ-REVIEW-13 still requires the
reviewed amendment's presentation before implementation. No new files in the
production allowlist: C6 touches main.py only, at validate_ai_response's evidence
assembly. No producer/importer, name, atlas, model, transport or save repair.
Current evidence HEAD5fcc5f1c, branch fix/322-campaign-export-hubs; original
implementation baseline origin/main6d18d09b. Reverify ancestry before execution;
these hashes are evidence, not runtime authority. Policy read live at epoch
2026-09-08T20:40:17Z; D-322-4 codification is the sole intended policy delta.
Spec-pin: #193 Part2 p6 lines129-132 persistent services, p8 lines139-143
world consequences, p11 lines155-159 provider/capture, p12 lines161-164
preservation, p13 lines166-171 real native serial acceptance. Read-path recovery
prohibition p2 and raw-input authority from Part1 remain binding. README promise:
recorded world consequences remain usable without inventing ownership/services.

OBSERVED A3, actual native OpenAI, copied official Thornwood/Keep_of_Doom game:
private /mnt/c/322-game-IbP7La/debug/api_captures/api_calls_master.jsonl495 has
complete canonical hubs in DM request messages2 and48; first draft lists four
services.496 reviews that exact draft but lacks canonical hubs, rejecting those
services as invented.497 removes them;498 accepts. Private evidence root
/mnt/c/agent-room-fleet-kit/local-data/322-acceptance-oZxruI/A2-A5-game-interactive,
protocolseq579 delivers "I cannot swear that any service there is ready."
Two independent source/PX audits confirmed the linkage; four other spot-check
claims passed. A1 was maintenance PASS; it did not prove this player path.

CODE-PROVEN main.py3056/3118-3124 strips generated user notes and system history;
3275-3279 selects that history;3469-3493 rebuilds validator context without hubs;
3566-3573 appends exact raw input/candidate;10384-10409 applies rejection feedback.
Sanitization lineage715732d55, prefix lineage932aceb00 (both mainline). Preserve
both goals. No missing-name heuristic is involved. #326 remains separate.

### Exact C6 mechanics

At validate_ai_response, after existing prefix compression and BEFORE
_assemble_validation_messages, read committed modules/campaign.json directly
with the existing UTF-8 JSON reader pattern (open/json.load). Use the shared
format_campaign_hubs on its hubs map. Add its nonempty result as ONE system
evidence message to validation_messages_to_send. It is outside compression and
outside accepted-history selection. The final raw-player/candidate pair and
strict-template tail remain assembled by the unchanged existing helper.
Use the formatter's existing wording verbatim; no additional narration rule,
required-services lint, string-matched approval or new model call.

Do NOT construct CampaignManager here: its initializer creates directories and
can run completion recovery (campaign_manager.py1865-1896). This new read must
not run recovery, take a transaction lock, mutate files or hold a lock across
provider work. Existing atomic file publication makes a successful read a
complete atomically published JSON document, not a global multi-file transaction
snapshot and never a partially written JSON document. Read per validator
invocation so Load/Reset and later accepted updates do not use a global cache.
The existing invocation/scope currentness checks reject superseded results;
there is no new acceptance/revision fence or persistent snapshot protocol.

Absent campaign file or absent/empty hubs: no fabricated map/owner/service;
omit the section, preserving the prior no-hub validation path. For unreadable
file (OSError/UnicodeError/JSONDecodeError) or non-object campaign root, emit a
WARN diagnostic naming the failure class, and include only the factual system
note "Canonical campaign hub information is unavailable for this review;
absence of this context does not establish absence of services or ownership."
Then continue through the EXISTING semantic validator: no approval, rejection,
empty verdict, fallback narration, new retry loop or recovery is manufactured.
The diagnostic contains no player data. No broad except, silent swallow or
catch of supersession/cancellation. Nested historical JSON values still use
the same lossless formatter; do not add an outbound schema gate on saved hubs.

This is evidence supply, not semantics enforcement: the validator judges the
candidate against committed facts, including unknown ownership and explicitly
empty services. It can still reject unsupported facilities. The DM remains
agentic, every action is still reviewed, and only the existing state writers
can change property. Existing replay/nonmembership bypasses are not widened.
No claim that three independently timed reads are a new global snapshot; if
acceptance observes live state-version incoherence, stop and report rather than
adding coordination machinery here.

### GL-1 and resolution ledger extension

| Branch/goal | Origin | Disposition | Proof |
| --- | --- | --- | --- |
| Strip system/DM-note history; retain raw input |715732d55| PRESERVED unchanged | source byte/AST compare; actual T065 raw pair |
| Existing NPC/location/module/inventory evidence |932aceb00| PRESERVED unchanged | prefix compare excluding added hub message |
| Compress historical prefix, not final semantic pair |existing main.py3501-3573| PRESERVED unchanged | packet ordering and exact raw/candidate capture |
| Hub facts absent from validator |A3 observed above| RETIRED D-322-4 | same recorded services reach T065 and survive narration |
| All verdict/refusal/retry/action/currentness branches |existing validate_ai_response and _review_dm_candidate| PRESERVED byte-identical | source diff + actual invalid and supersession observations as reachable |
| Missing campaign input |new evidence read only| task-C6 | no-hub old behavior; unavailable is not known-empty; unchanged validator terminal |

New ledger entries: A3-V1 missing authoritative validator evidence=task-C6;
C6-A1 post-review execution approval=escalate:@owner (present reviewed plan);
original F7 execution gate was CLOSED by D-322-1, not still open. C4 broader
attribution remains issue-#326 under D-322-3; no global factual PASS claimed.

### Implementation and regression acceptance after review/approval

C6a: fresh policy/ancestry/EOL check; add only the above main.py evidence block
and formatter import, inspect focused diff; update module-lifecycle schematic
third-consumer note. Compile/undefined-names/whitespace, exact no-change checks
for sanitization, _assemble_validation_messages, all verdict/gate/loop paths,
and C1-C3 producer/importer/formatter bytes. Mandatory simplifier and independent
postimplementation audit, raw FS1 and both sentinel scans. No tracked tests.
Pure JSON/I/O/format primitives may cover absent file, unreadable/bad JSON,
empty map, historical scalar/null values and full untruncated payload; they
are NOT live gameplay or forced model-failure evidence.

C6b: re-run the SAME recall request via native run_headless.py serve, real
OpenAI, one operation at a time, copied fixture with current source/prompts
hash-verified. Preserve original FAILED A3 transcript and capture. Require all
three actual messages (both T067 hub contexts and T065 system evidence) to carry
the complete committed record; T065 raw player/candidate remain exact adjacent
pair. Require player answer preserves four known services, owner, and friendly
hub support WITHOUT invented village ownership. Five independent PX claims.
The original rejection is historical baseline evidence, NOT proof that the
post-C6 validator still rejects unsupported claims. Separately require real
post-change semantic rejection -> correction -> playable continuation, checking
persisted history excludes the rejected draft and transient correction feedback.
This firing-path control must use actual live play, never injected model
outcomes. If not naturally reached, mark that criterion NOT-REACHED and withhold
its PASS; a positive three-consumer/narration PASS does not waive it. Unknown
ownership must not become party; empty services must
not become basic services (pure polarity plus live only when genuinely present).
Measure added request tokens and input-to-prompt time without attributing the
whole turn to T065. Publish actual model or unavailable, rows, complete text,
fallback/retry counts, save/campaign comparisons and quiescence receipts.

On clean C6b continue held A2, A5 and A6 under section7. A4's positive unlock,
absent-file/error live paths and cancellation are NOT-REACHED unless naturally
exercised; no corruption/state edits to manufacture a PASS. Failed core arm:
preserve artifacts and stop, no mid-acceptance repair. All unrelated findings
remain separate issues; no authority to commit/push/merge to main or close issues.

### Review applicability

FULL remains FULL (NEQ-REVIEW-03 one-way). Dispatch the same nine seats separately
with this whole revised plan/ledger, live policy and source: Custodian,
Fail-Forward, Acceptance, Consumer/Compat, Legacy-Contract, PX, Leanness and both
sentinels. Reconfirm changed evidence read/error branches and third consumer,
not just the successful old C3. No schema/store/lock/routing change proposed;
zero limits; shared-primitive entrant and new exception path still get explicit
compatibility, failure, hygiene, platform and source-family checks. A new plan
has no new product diff yet: sentinel empty C6 diff is not implementation proof.
Converge on one SHA plus confirmation or policy's plan-polish-only exception,
then present to owner. #326 remains outside; #328 covers this observed gap.

C6 review reconciliation: ACC-C6-1=task-C6b (new explicit post-change firing-path
and persisted-history checks; acceptance-design change, full re-confirmation
required). C6-P1=fixed-inline (wording only: atomic file publication is not a
global multi-file snapshot). NL-C6-FYI=issue-#317 (pre-existing five-message
transition-detection window; code-proven edge, gameplay impact unverified;
no repair in this scope). All remaining round-1 seats had zero blockers.
