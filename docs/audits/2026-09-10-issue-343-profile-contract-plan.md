# Issue 343: supply the profile contract the model is asked to satisfy

Status: PLAN ONLY. No product edits, acceptance runs or implementation authority.
Owner delegated next-issue selection and full #193 planning after #345 shipment.
Execution requires presentation of the converged plan and subsequent owner approval.

## 1. Authority and scope

Canonical authority: live GitHub #193 v3.1, policy epoch2026-09-10T16:03:33Z.
Part1 read this session; relevant Part2 p7 NPC01/02, p8 WORLD04, p10 WEB01/03,
p11 PROVIDER01/02, p12 SCHEMA01/02, p13 ACCEPT01..03/TEST01..02 consulted.
Part2 source lines134-169 in the live body carry these system pages; rule IDs
are stable, line numbers are evidence. Read schematics npc-voice-ooc.md and
provider-routing.md before design. Their historical anchors are not current
authority; this plan rechecks the T107 slice below, not all old schematic claims.

Worktree: /home/loup/neq-worktrees/343-profile-contract-plan.
Branch: plan/343-profile-contract. Fetched main and worktree HEAD at review freeze:
aee5978c741c50b322775937e150187e1327f244, the published #345 closeout.
Revisions
are review evidence, never runtime or durable identity authority. No worktree prune.
Another agent owns #323; no overlap or level-up work here.

README player promise: responsive web storytelling (README205/214 onward),
consistent character/companion context and continuity (README394-441).
This repair targets repeated completed-invalid profile calls, not a promise that
all turns become fast. #348/#284 own transport recovery and the600s stall issue.

Runtime allowlist: core/npc/profile_service.py only.
Documentation: a focused T107 contract subsection in docs/architecture/npc-voice-ooc.md,
this plan/review/execution records. No broad historical schematic rewrite.
The prompt text file, voice_contracts.py, model bindings, schemas, cache identity,
stores, voice consumers, failure policy, lifecycle, transport and game data stay
byte-identical. Tests/evidence local and ignored; no tracked tests.

## 2. Observed incident and challenged diagnosis

OBSERVED: real #337 native Windows/OpenAI capture
/mnt/c/337-ev-qdSV6b/A1/model_captures/T107.json entries0/1, invocation IDs
ff74f2ac-20f9-45fe-9ffc-40cc1cb11665 and15902e82-d0d1-4bd8-8dc9-80137a7dfb74.
Read both complete requests and outputs, including the entire as-sent system text.
Both complete responses return voice:string; selected binding luna/none, JSON mode,
durations4.919/4.198s; response.model is not retained (UNKNOWN).
First call prompt/completion tokens460/198; retry484/161. No transport error on
these calls. Source has real structured NPC facts; missing personality evidence
does not explain why voice has the wrong type.

The first system message lists twelve top-level names, but never the required
voice object containing cadence:string, diction:string, taboos:array. Retry adds
only "invalid_contract", not the validation path/type. No response schema is
otherwise transmitted on this OpenAI JSON-mode path. The issue is an insufficient
contract at the model input boundary, not proof that luna lacks reasoning ability.
No model/effort switch, deterministic personality mapping, or extra specialist is
justified by these artifacts.

CODE-PROVEN against current source:
- profile_service.py:89-109 validates the complete response, then normalizes it;
  schema failures already raise ProfileContractError with an exact path/message.
- voice_contracts.py:117-176 defines the frozen twelve-key profile schema;
  profile_response_schema():473 returns a deep copy of that same authority.
- profile_service.py:211-230 builds the private request without that schema.
- profile_service.py:323-325 throws away the informative error for invalid_contract.
- profile_service.py:366-373 returns a matching persisted model profile without a
  new call; fallback provenance is retried. Only validated successes enter cache.
- The schema rejects both actual captured responses at path[voice], keyword type
  (independent pure JSON-schema validation this session). This proves parsing,
  not a repaired gameplay experience.

Lineage: prompt and build_messages/error classification originate at main ancestor
7504a717 (feat(npc): P0+P1 forward-port NPC voice system onto main w/ luna registry).
93a17bad removed a cap but did not supply nested grammar. This failure predates
#337/#345; their code did not modify T107. Raw #345 repeats corroborate persisted
fallback across later beats; an unrelated header stall also occurred and remains
separate. Do not attribute all recorded latency to this shape mismatch.

## 3. Smallest sound design

Approach A (selected): in the existing build_messages function, append an explicit
JSON Schema block to the existing system prompt, serialized directly from
profile_response_schema(), using json.dumps with ASCII and compact separators.
The unchanged prompt remains the grounding/authoring instruction; the injected
schema is the complete shape contract and SAME object definition used by local
validation. No second handwritten schema/example and no new store, helper, flag,
provider branch, request type or model call. Current complete schema serialization
is1412 characters; measure actual token cost, do not call characters tokens.

In seed's existing except ProfileContractError branch, retain the precise str(exc)
as retry_reason rather than replacing it with invalid_contract. Existing private
build_messages correction will carry it. Mark correction explicitly as diagnostic
data about the previous response, not source facts or commands; continue to ask
for the complete schema-conforming object using the unchanged canonical source.
Do not parse the error prose to determine retries, permissions, identity or writes.
Only this typed contract exception supplies details; broad provider exceptions
retain existing provider_failure text (no credential/endpoint exception leakage).
No prior malformed response is published, cached, persisted or treated as history.

Schema output stays advisory to the DM: model chooses grounded cadence/goals/etc;
code checks shape/identity and owns atomic storage. A schema is not an NPC behavior
rules engine. Existing trimming/uniqueness validation remains as-is. No personality
default, name matching, boss special case, new confidence gate or inferred fact.

Rejected alternatives:
- Prompt-only duplicated example: could fix voice today but creates a second
  manually maintained grammar and does not expose the existing precise retry error.
- Coerce voice:string into an object: masks the failure, invents field assignment,
  and weakens the shared contract. Not a sound boundary repair.
- Change model/effort or structured-output API mode: no evidence it is needed;
  changes provider compatibility/cost beyond this observed missing-input defect.
- Repair all profile liveness/cache/parallelism now: different mechanics and owner
  transport decisions; tracked separately, not prerequisites for contract repair.

## 4. Spec pin: entrants, authority and terminals

Entrants: recruitment action_handler.py:2503/2600 -> seed_profile_best_effort;
OOC voice_context.py:1053-1059 and combat:1358-1364 -> profile_for_packet_best_effort
-> seed_profile_best_effort:462 -> default service.seed -> build_messages -> T107.
Every uncached seed uses the same request builder, with provider-specific existing
format overlays unchanged. Gemini still has its existing wire-schema conversion;
OpenAI/legacy JSON mode and local adapter remain unchanged. No parallel runtime.

Canonical facts: existing character file and lifecycle source, NPC ID from the
RelationshipStore identity. Profile shape: profile_response_schema. Persistent
profile: RelationshipStore profiles[npc_id], store_profile:573-588 through existing
whole-document validate/atomic _mutate. Validated cache entry is not a new commit
authority; value sourceCanonical and PROFILE_VERSION stay identical.
Successful current model profile is a no-op: no new call/reseed/version bump.
Matching fallback retries through existing path, may become a validated model
profile. Existing profile and episode/relationship histories must not be wiped.

Flow: request + full schema -> real completed response -> unchanged validator ->
existing cache/persisted profile -> T105 packet -> DM advisory/narration. On typed
invalid output: same existing private correction loop with more useful diagnostic;
invalid output never accepted. On exhaustion: existing loud fallback and later
retry, unchanged. Broad provider catch, transport reissue semantics and cancellation
are inherited, NOT newly ratified by this repair. Their counts are not defended as
legal transient limits; #348/#284 track the known caller-policy gap explicitly.
No wait, acquire, scope, thread, lock order, retry-count or exception topology change.
Cache lock still only covers dictionary operations; store lock never newly spans
a provider call. Existing Load/Reset supersession must be observed, not assumed.

## 5. GL-1 behavioral contract and implementation slices

| Replaced/retained behavior (main origin) | Goal | Disposition / proving arm |
|---|---|---|
| build_messages system content,7504a717 | Grounded private profile from canonical facts | PRESERVED with same prompt/source, complete shared schema added; A1/A4 |
| generic typed-contract retry label,7504a717 | Reject invalid data and request correction privately | PRESERVED with exact diagnostic; schema unchanged; A2 |
| caller MAX_ATTEMPTS/broad catch,7504a717 | Existing per-beat failure continuation | UNCHANGED/PRE_EXISTING_OUT under #348/#284, not new approval; A2/A5 observations |
| success cache/sourceCanonical gate,b1da8f0f and existing lineage | Reuse validated same-source profiles | PRESERVED byte-identical; A3 |
| schema/store/source selection | No invented facts, preserve companion data | PRESERVED byte-identical; A1/A3/A4 |

C0 (no product edits): freeze source/prompts/schemas and real Save inventory,
refresh policy/main; capture baseline failures above and all affected consumers.
C1: implement only the two request/diagnostic changes in profile_service.py;
preserve file EOL and ASCII additions. Update focused T107 schematic subsection.
C2: mandatory fresh-context simplifier, py_compile/undefined-name and exact diff
checks; both sentinels over actual diff+touched file, schema/consumer scans.
C3: serial native real-OpenAI acceptance below; no mid-run repair. Two failed
in-scope fixes on same symptom -> stop, reproduce and bisect the causal mainline
change using fresh Git evidence, not more prompt tweaks (Legacy-Contract/GL-1).
C4: independent five-point audit and PX transcript review; present evidence and
any NOT-REACHED owner decisions. Commit per approved execution workflow only;
publication still needs owner authorization. No changes to other issues.

## 6. Acceptance designed before code

Dev checks (not player acceptance): unchanged schema accepts known valid real
profile and rejects captured voice:string; build_messages contains exact complete
schema and unchanged source; typed diagnostic retained with no provider exception
details; no new API kwargs/bindings/caps. These are pure serialization/parsing
checks only, no monkeypatched gameplay/LLM/UI. Existing real invalid response may
exercise parser/diagnostic construction, never substitute for a live retry verdict.
Native py_compile and pyflakes undefined-name check on touched Python; WSL same.

Fixture: fresh short native source export and fresh copy of legitimate #345
pre-hostility Save222853, official Thornwood six-companion party, existing fallback
profiles. Refresh all prompt bytes from candidate. Private source/saves preserved;
no deleting profiles to force reseeding, no fabricated NPC/encounter or responses.
Current provider verified OpenAI; existing T107 luna/none binding unchanged.
Only one live operation at a time, actual run_headless.py serve/HeadlessClient and
gameplay guidelines. Capture enabled with no comparison variants.

| Arm | Required evidence and negative polarity |
|---|---|
| A1 cold repair | Real quiet turn with existing fallback profiles: T107 as-sent canonical schema, real voice object, unchanged validator success, persisted model provenance and matching values. T105 actually consumes the profile; DM returns actionable prompt. Per-companion counts, invalid/fallback events, timing/tokens. A completed call alone is not PASS |
| A2 correction | If naturally completed-invalid occurs, next actual T107 request contains precise field/type diagnostic, same source/full schema; later success or truthful inherited terminal. No invalid persistence. If no invalid response occurs, live correction firing NOT-REACHED, explicit owner disposition; pure parser check not substitute |
| A3 warm/Save/Load | Next quiet turn with unchanged source has no unnecessary T107 regeneration. Diff source values rather than assuming sameness; if source legitimately changes, report regeneration separately. Supported Save, real subsequent turn, Load, resumed play: valid model profile retained, companion history/relationships not cleared. Profile equality, source equality and actual per-call captures prove no-op |
| A4 consumer/agency | Verify real T105 packet and subsequent DM narration use grounded profile, not invented deeds/promises/allegiances; five narrated claims vs canonical source. Reach one ordinary typed combat if legally available; same shared profile builder in that consumer. If not reached, record it; no hidden legacy fixture lever. Existing valid profile must not be regenerated solely because prompt improved |
| A5 lifecycle/pace | Supported Quit and Load at safe boundaries; existing data remains resumable. If real wait/supersession occurs, record exact quiescence and any broader inherited failure, no repair here. Input acknowledgment, pre/post-narration gaps and cold/warm wall-clock measured; no universal speed guarantee |

Every arm retains full as-sent system, loaded file/schema hashes, model call IDs,
reported model or UNKNOWN (selected binding distinct), per-call durations relative
to input, tokens/cost only when exposed, parsed consumer fields, complete visible
narration, fallback/invalid counts with raw searches, before/after canonical files,
Save/Load/exit/orphan receipts. Five claims/PX independently reviewed. Negative
controls are real observed paths, never hypothetical PASS. Compare measured cold
and unchanged-source warm costs; no cross-fixture causal performance claim.

Explicit PX/consumer checklist for the existing A1-A5 transcript review: collect
20 real turns for the second-person sole-PC probe (zero third-person sole-PC),
and classify private/unperceived facts separately from facts true on disk. No
unrequested player choice or invented player dice. Check acknowledgment within
one event cycle, honest changing progress for waits over roughly10s, and Save/Load
start/completion with restored recent history. Where a browser is exercised, check
tab-hidden completion and truthful disabled controls; unexercised surfaces are
NOT-REACHED for owner disposition, never an assumed PASS. These are acceptance
obligations, not permission to repair other systems or prolong a blocked game.
Pin the OOC as-sent guidance and, if reached, actor-keyed npcVoiceIntents in both
T096 and T097 with capture lines. Grounded-looking narration alone proves no
delivery: guidance can be omitted by an exception while narration continues.
In the existing before/after profile/Save comparison, list EVERY nonempty-to-empty
transition, including diction and individual lists; do not equate intact episode
files with intact profiles. Inherited destructive fallback replacement is #350,
not a #343 writer repair or a reason to mislabel data preservation PASSED.

## 7. Review gates and decisions

FULL: shared request-builder replacement and error-message behavior, with GL-1;
owner explicitly requests #193 review. Separate blind seats: Architecture,
Fail-Forward (verbatim B1/B2), Acceptance, Consumer/Compat, Legacy-Contract, PX,
Leanness, No-Limits and Single-Path. Schema-Freeze, Platform/Provider and Hygiene
assessed by each applicable owner, not bare N/A. Scope is one Python file plusdocs;
no schema delta or new public symbol. Review all same SHA/full ledger, controller
single-writes; confirmation required after code-class revisions. Only pure polish
qualifies for NEQ-REVIEW-11 fixed-inline after full coverage. Non-author five-point
postimplementation audit remains mandatory after code and native acceptance.

D-343-1: execution OWNER-OPEN; present converged plan, no implementation before
explicit subsequent approval. D-343-2: any NOT-REACHED acceptance waiver is separate
and requires explicit owner disposition after evidence, not granted by this plan.

## Tracked follow-ups

- #348/#284: per-call monitoring and existing T107 transport/count/cancellation
  boundary. Precise current caller evidence added to #348 in this session:
  https://github.com/MoonlightByte/NeverEndingQuest/issues/348#issuecomment-5621732944
- #349: unowned Defense bonus during HP-only update, no character-writer repair.
- #350: existing source-change reseed publishes sparse fallback before replacement
  succeeds, potentially erasing a rich profile. Filed this review, CODE-PROVEN
  not incident-attributed; no profile writer changes in #343.
- #344: missing PC evidence in T065; #80/#260 hidden welcome facts, not this call.
- #323 belongs to other agent. #283 memory/affinity redesign not part of profiles.
- Broader historical schematic anchors retain their explicit historical scope;
  only T107 flow is recertified by this task, no competing architecture document.

## Resolution ledger

| ID | Finding / decision | Resolution |
|---|---|---|
| F1 | Complete responses have voice:string; required schema never supplied | task-C1 schema from same existing authority |
| F2 | Precise typed schema error discarded for generic retry text | task-C1 retain diagnostic, private only |
| F3 | Broad transport failures counted/returned as fallback | issue-#348 precise evidence added; PRE_EXISTING_OUT, no retry rewrite |
| F4 | Valid cache must not regenerate or lose old companion state | task-C3 A3, unchanged fingerprint/version/store |
| F5 | Added input tokens / success claims need real consumer evidence | task-C3 A1/A4 measurements |
| F6 | Historical schematic omits this T107 contract flow | task-C1 focused subsection only |
| CC-1 | Source-change fallback can erase previous model profile | issue-#350 filed this turn; PRE_EXISTING_OUT, no writer expansion |
| CC-2 | Before/after check must enumerate nonempty-to-empty profile fields | task-C3 explicit existing comparison criteria |
| PX-1 | Player-contract acceptance checklist was underspecified | task-C3 explicit20-turn, perceived facts, agency, progress/history and browser polarity evidence; full confirmation required |
| AC-1 | Name actual downstream delivery fields and capture lines | fixed-inline clarification of existing A1/A4 consumer proof |
| LC-1 | Two-strikes layer-down must include causal-mainline bisect | fixed-inline complete doctrine citation, not additional fix attempt |
| D-343-1 | Planning delegated, execution not yet approved | escalate:@owner after convergence |
| D-343-2 | Future unreached live negative path | escalate:@owner only if A2/A4 not reached; no prospective waiver |
