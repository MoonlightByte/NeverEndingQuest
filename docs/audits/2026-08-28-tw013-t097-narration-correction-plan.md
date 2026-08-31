# TW-013 T097 Narration Correction Plan

Status: **PLAN ONLY -- NOT AUTHORIZED FOR IMPLEMENTATION**

## 1. Authority and scope

- Policy: live GitHub issue #193 v1.7, refreshed 2026-08-28 (`updatedAt`
  `2026-08-27T17:30:16Z`), especially Part 1 B1/B2/AP-2/AP-5/AP-7, Part 2
  Combat, Web/headless, Provider, and Acceptance, Part 3 FULL review, and Part 4
  single-writer/simplifier rules.
- Combat architecture: live issue #191, especially Sections 6.3, 6.4, 12.3,
  13, and 15. It preserves deterministic committed-fact fallback while banning
  phrase/title/number parsing as narration authority.
- Owner task: TW-013 brief SHA-256
  `8f1d0edae37b7ba4bcf92f6c8d538fa9fa29c033efe4607a03fb37b834bb23f4`.
  It authorizes a narrow root-cause correction of the T097 entity rejection and
  correction-loop liveness defect, but no implementation before review.
- Lineage: branch `fix/tw013-combat-narration-correction` is based on the
  owner-designated premerge candidate
  `7a953be1e84a950bedef8f8adbda36fda0426d8f`. It is incident evidence, not
  mainline compatibility authority. Its merge base with current
  `origin/main` is `691b5a2f06b472e31c7a123964844d9506862535`, and current
  `origin/main` resolves to that same revision.
- Scope: `core/ai/combat_agent.py`, `core/ai/combat_narration.py`,
  `core/managers/combat_orchestrator.py`, and the existing recovery-status
  selection in `core/managers/combat_manager.py`, plus the existing central
  supersession bridge in `utils/capture/live_provider_call.py` only. No
  encounter balance, mechanics, initiative, prompt history, persisted schema,
  provider routing, or UI change. This five-file scope can implement only D1-B. If the owner
  selects D1-A, scope is not inferred: revise and re-review the plan first.

This is FULL review: it removes a play-path guard, changes the T097 prompt
contract, restores a numeric correction bound, and owner-gates the correction
terminal.

## 2. Evidence-backed diagnosis

### 2.1 The real candidate and dossier

Authoritative artifacts are under:

`/mnt/c/dungeon_master_v1/.worktrees/premerge-combat-tip-validation/validation_evidence/thornwood_full_playthrough/fresh-20260828-115105/`

The preserved encounter `game/modules/encounters/encounter_TW05-E1.json` proves:

- mechanics had already committed four event IDs;
- `pendingDelivery.narration` was still null;
- `pendingDelivery.narrationAttempts` held 12 rejected T097 candidates;
- every rejection was `unknown_titled_entity`;
- the permitted names included `Bandit Captain Gorvek`, `Bandit Sentry`,
  `Bandit Warrior`, `Mara Voss`, and `Scout Kira`.

The first candidate was grounded in those facts. Its relevant phrase was
`Bandit Captain Gorvek levels a Heavy Crossbow at Scout Kira`.

### 2.2 Exact false-rejection mechanism

`build_scene_dossier` in `core/ai/combat_narration.py` correctly builds
`permittedNamedEntities` from canonical presentation names, action names, and
location. The payload captured at protocol sequence 6001-6067 contains the
correct list, so the list was neither empty, stale, nor instance-suffixed.

The defect is the consumer:

1. `_TITLE_RE` extracts only title-led substrings.
2. From the valid full mention `Bandit Captain Gorvek`, it extracts
   `Captain Gorvek`.
3. `lint_combat_narration` compares that substring for exact equality against
   the full permitted-name set.
4. `Captain Gorvek != Bandit Captain Gorvek`, so it emits
   `unknown_titled_entity`.

A direct check against the premerge candidate code returns:

```text
matches = ['Captain Gorvek']
reject = ['unknown_titled_entity']
```

This is not a Bandit Sentry suffix problem and not provider noncompliance. The
actual prompt, candidate, and permitted list agree; the deterministic parser
contradicts them.

### 2.3 Exact runaway mechanism

`_deliver_committed_turn` in `core/managers/combat_orchestrator.py` owns T097
correction. On the premerge candidate revision it:

1. starts at the durable `narrationAttempts` count;
2. loops while no narration is accepted;
3. invokes T097 again, records rejection, and continues;
4. has no exhaustion branch despite retaining a `max_narration_attempts`
   parameter;
5. eventually collides with the transaction layer's 12-attempt receipt limit;
6. propagates `CombatTransactionError` to `combat_manager`, which displays the
   neutral pause and executes `continue` without reading player input;
7. re-enters the same committed delivery and calls T097 again.

The real transcript records 19 pause messages, 20 `Resolving combat intents`
statuses, and 20 `The DM is checking the ruling` statuses. `commands.ndjson`
contains a queued `relay-quit`, but the engine never returned to its input
boundary. The stack shows the engine inside T097, and the encounter remains on
the same committed delivery. The pause message was therefore untrue: it did
not pause.

The preserved `game/debug/api_captures/api_calls_master.jsonl` contains no T097
row. The protocol debug stream proves the actual request, candidate, correction,
and configured model, but not the raw response envelope, actual
`response.model`, or token usage. Per the owner forensic procedure, one
instrumented real T097 turn is a pre-implementation evidence gate; unavailable
incident fields will not be invented.

### 2.4 Lineage

The two causes have different lineage:

| Behavior | Origin | Baseline `691b5a2f` | Premerge candidate `7a953be1` | Classification |
|---|---|---|---|---|
| `_TITLE_RE` exact-substring/full-name mismatch | `eb2ecd52` (2026-08-10) | Present byte-for-byte | Present | Pre-existing validator defect |
| Three-to-twelve bounded T097 correction | `eb2ecd52` | Present | Removed | Working baseline behavior |
| Deterministic committed-fact delivery after exhaustion | `eb2ecd52` | Present | Removed | Working baseline behavior, but its prose now violates newer no-bookkeeping/second-person contracts |
| Unbounded T097 loop | candidate commit `4290e711` (2026-08-24) | Absent | Present | Recent premerge-candidate regression |
| Outer `CombatTransactionError` pause then unconditional re-entry | typed combat lineage, exposed by the unbounded change | Could not run forever because delivery exhausted to fallback | Re-enters forever after receipt capacity | Amplifying symptom |

Candidate commit `4290e711` explicitly replaced the bounded `for` loop with `while`,
removed `max_attempts`, removed `render_committed_events`, and changed a valid
candidate exit from `break` to `continue`. Invocation-supersession checks added
by that commit are valuable and must remain.

### 2.5 Root-versus-symptom verdict

Both are defects and both are required for the observed blocker:

- **Semantic root:** invalid deterministic prose parsing falsely rejected a
  valid T097 response. A substring/alias patch would treat the symptom and
  deepen the AP-7 mechanism.
- **Liveness root:** the recent removal of the correction terminal allowed any
  persistent T097 rejection or contract failure to monopolize the game thread.
- **Symptoms:** the 12-entry receipt-cap error, repeated neutral pause, repeated
  status lines, stranded input, and OpenAI cost are downstream consequences.

Fixing only the parser leaves a latent runaway on the next genuine invalid
response. Fixing only the bound burns calls and preserves the false rejection.

## 3. Canonical contracts (spec pin)

| Datum / decision | Authority | Contract after TW-013 |
|---|---|---|
| Committed combat events | encounter `pendingDelivery.events` plus applied event IDs | Never rerun or mutate due to narration failure |
| Combatant identity | exact canonical combatant ID joined to accepted presentation name in the T097 dossier | Code supplies identity context; it does not rediscover identity by parsing narration prose |
| Narration meaning and wording | T097 model | Model narrates only committed facts and permitted context; code does not infer semantic truth from title/phrase matching |
| Narration event coverage | T097 `coveredEventIds`, reconciled by code | Exact ordered committed event IDs, unchanged |
| Completed-response correction evidence | durable `narrationAttempts` | Only completed candidate parse/contract/coverage/lint rejects consume the correction budget; rejected candidates never enter published history |
| Provider/transport unavailability | provider exception plus structured diagnostic class | Structurally reissue without consuming or persisting a model-correction attempt; never convert transport failure into deterministic narration exhaustion |
| Unexpected internal or transaction failure | exception type, not message prose | Never count as a model correction. Transaction/persistence faults propagate to existing recovery; other narration-internal faults keep the committed delivery pending and truthfully reissue without reporting the player action failed |
| Correction terminal | caller-supplied `max_narration_attempts`, restored to the baseline 3..12 range | If and only if TW013-D1 is ratified, completed-invalid exhaustion retains one approved deterministic terminal under the existing delivery ID |
| Retained narration | `pendingDelivery.narration` | Persisted once before publication; reconnect replays it |
| Player boundary | initiative/controller state | T097 never asks for input or announces a next turn. After publication, code recomputes the canonical window and skips an unconscious human actor |
| Public project promise | `README.md` AI-DM/turn-based-combat statements and combat example | Combat remains AI-narrated, turn-based, and initiative-driven; recovery prose cannot seize player agency or expose bookkeeping |

No persisted field, marker, store, lock, provider binding, response schema, or
gameplay schema is added.

## 4. Approaches considered

### Approach A -- retire prose identity policing and restore an exact-class terminal (selected)

Delete only `_TITLE_RE` and its `unknown_titled_entity` rejection. Keep the
existing T097 dossier and exact `coveredEventIds` contract. Add an explicit
prompt boundary that T097 narrates the committed beat only and never solicits
input or declares the next turn. Restore the baseline finite range for
**completed-invalid model candidates only**, and keep provider/transport and
internal/transaction failures outside that budget. On owner-ratified
completed-invalid exhaustion, retain one safe committed-result terminal and
resume from canonical initiative state.

Why: issue #191 explicitly prohibits phrase/title/number parsing as narration
authority. Removing the parser fixes the real contradiction without replacing
it with model self-attestation, schema churn, aliases, another provider call,
or a scenario-specific exception. Event coverage remains the code-owned
structural guard. The exact-class terminal fixes the independent liveness
regression without turning provider outages or code defects into fictional
combat prose.

### Approach B -- permit title suffixes/substrings (rejected)

Teach `_TITLE_RE` that `Captain Gorvek` is contained in
`Bandit Captain Gorvek`.

Rejected: it fixes this phrase but leaves prose/keyword parsing as identity
authority, creates alias/overlap edge cases, violates issue #191 and AP-7, and
invites another scenario list.

### Approach C -- only restore the retry bound (rejected)

Rejected: it masks the deterministic false reject and burns every correction
budget on valid narration.

### Approach D -- add a second narration-referee model call (rejected)

Rejected: no evidence requires another provider call. The existing exact
dossier and event-coverage contract already give T097 the required authority.
A second call adds cost, latency, routing, and failure handling without a new
local invariant.

### Approach E -- add typed named-reference self-attestation (rejected)

Adding `referencedCombatants[]` would not prove prose completeness: a response
could invent `Lord Vex` while returning an empty list. It would also change the
Gemini response schema and custom narrator contract without solving the
semantic problem. This is more machinery with weaker authority.

## 5. Pre-implementation forensic gate

Before production edits, run one instrumented real native-Windows T097 turn on
an isolated copy with configured OpenAI. Preserve the complete request, raw
response, actual `response.model`, token/cost record, candidate, lint result,
and encounter before/after. This fills the fields absent from the incident
capture and verifies that the sent prompt -- not a template -- has the stated
contract. Stop after one completed T097 turn; do not recreate the incident by
memory or repeatedly provoke rejection. If the call itself stalls, record it
under #186 and do not misclassify it as a completed-invalid response.

Also scan real encounter receipts for existing `narrationAttempts` rows with
`status="provider_error"`. Their count and recovery behavior determine whether
legacy receipts need a narrow compatibility interpretation; this plan does not
rewrite old receipts.

## 6. Implementation slices

### C1 -- Retire the prohibited title parser and pin the narration beat

Files: `core/ai/combat_agent.py`, `core/ai/combat_narration.py`.

1. Delete `_TITLE_RE` and only the `unknown_titled_entity` prose scan.
2. Keep the existing T097 JSON shape (`narration`, `coveredEventIds`) and all
   provider/model/custom-narrator contracts unchanged.
3. Add to the T097 prompt: narrate only this committed beat; never ask what the
   player does, invite a roll, declare whose turn is next, or manufacture a
   handoff. Initiative/controller code owns that boundary after publication.
4. Preserve exact coverage reconciliation, dossier facts-last order, model
   routing, and every non-title lint branch unchanged.

Development checks (local/untracked, backend contract only):

- the exact TW05-E1 dossier and first valid Gorvek candidate no longer receive
  `unknown_titled_entity`;
- no prose-title extraction remains;
- exact missing/duplicate/misordered event coverage still rejects;
- empty, internal-ID, bookkeeping, stale-condition, hostile-count, and length
  verdicts retain current polarity;
- the existing OpenAI/Gemini schema remains byte-equivalent;
- a custom narrator returning the existing tuple/string forms still succeeds
  without any new response field.

### C2 -- Separate completed correction from unavailable transport and faults

File: `core/managers/combat_orchestrator.py`.

1. Restore `max_attempts = max(3, min(..., 12))` from baseline. The numeric
   range is restored behavior, not a new configuration surface.
2. Count and durably record only a **completed response** rejected as
   `response_parse_error`, `response_contract_error`,
   `narration_coverage_error`, or `narration_lint_reject`.
3. A `provider_error`/transport failure does not increment the completed-model
   attempt number, does not enter `narrationAttempts`, and does not approach the
   deterministic terminal. It structurally reissues after truthful progress
   status. The outer logical narration task remains unbounded under B1/B2.
4. Unexpected narration-internal exceptions are not relabeled or recorded as
   model correction. An explicit in-memory `internal_retry` disposition keeps
   the committed receipt pending and the same narration operation truthfully
   reissues; a later healthy attempt may retain narration once. It never
   escapes as a failed player action or invokes the model-correction terminal.
   The disposition is selected by the exception boundary/type, never message
   text. Persistence/transaction faults still propagate to existing
   transaction recovery and are never swallowed.
5. Preserve `_require_current_invocation` around every completed provider call
   and every write. Re-raise `InvocationSupersededError` unchanged from the
   T097 delivery seam so the main invocation owner can quiesce deferred
   Load/Reset/quit; do not translate it into the pause-and-reenter path.
6. On a valid candidate, restore the baseline `break` exit (the candidate
   branch currently says `continue`). A first-attempt success makes exactly one
   T097 call.
7. On owner-ratified completed-invalid exhaustion, retain the approved terminal
   once under the existing delivery ID, set the existing fallback marker and
   diagnostic, and continue publication without rerunning mechanics.
8. A recovered receipt already at the ratified completed-invalid limit (the
   real 12-row save) makes zero new T097 calls and converges to that terminal.

FS-1 classification:

- the finite counter applies only to already-completed, structurally received
  invalid candidates and **CONTINUES** by retaining committed work;
- provider/transport unavailability **CONTINUES** by reissue and never consumes
  the counter;
- Load/Reset/quit **SUPERSEDES** through the existing invocation owner;
- this does not cancel an in-flight synchronous provider request. #186 remains
  the owner of that broader stall/cancellation defect, and acceptance may not
  claim it fixed.

An absent provider payload raised as shared `ProviderEmptyResponse` is provider
unavailability and reissues without counting. A completed JSON object whose
`narration` field is absent/blank is a response-contract reject and may consume
one completed-invalid attempt. The classification follows typed exception and
parsed-envelope state, never exception prose.

### C2b -- Connect the existing live-turn and combat fences

File: `utils/capture/live_provider_call.py`.

`request_live_turn_supersession` is the shared web/headless authority for
accepted quit/Load/Reset requests. When, and only when, that existing scope
accepts a supersession, also call the existing
`core.combat.invocation.supersede_invocations` with the same reason before
returning acceptance. Do this centrally rather than patching individual web or
headless commands. Save remains non-destructive and does not supersede.

This gives T097's existing `_require_current_invocation` checks real
between-attempt cancellation authority. It does not kill an in-flight
synchronous request; once that call returns, its post-call check rejects the
late result before attempt/narration persistence. Existing double-supersession
on process exit is idempotent. Development polarity covers accepted versus
conflicting/closed requests, Save non-supersession, and no late T097 write.

### C3 -- Owner resolution of the terminal/disclosure conflict

Files: `core/ai/combat_narration.py`,
`core/managers/combat_orchestrator.py`.

Current code has no safe implementation of both governing requirements:

- issue #191 preserves a deterministic committed-fact renderer; and
- current T097 facts include every event actor/action plus HP/roll details
  without enforcing `sceneFacts.disclosureGrants`, so the renderer cannot know
  whether a present hidden actor's identity is player-publishable.

TW013-D1 must therefore ratify one of these explicit authority changes before
this slice is coded:

- **D1-A -- expand disclosure scope.** Build a code-owned player-public event
  projection from existing typed participation/disclosure authority, then
  repair the existing
  `render_committed_events` and call that single renderer. It consumes only the
  resulting public projection and controller map. It covers every publishable
  event and target in order; handles attack hit/miss, non-attack/effect,
  healing, no-target, multi-target, and committed defeat/death forms; uses
  second person for the human controller; and emits no numeric bookkeeping,
  hidden identity/belief, new cause, or next-turn prompt. This widens TW-013
  beyond the current five-file narrow scope and requires a separately reviewed
  disclosure contract. Choosing D1-A sends the expanded plan back through all
  six lenses before any code; it is not authorized by this five-file plan.
- **D1-B -- narrow non-disclosing boundary (recommended for TW-013).** Owner
  explicitly supersedes/retires #191's committed-fact-renderer goal for this
  exhaustion terminal. Retain one non-diegetic statement under the delivery ID:
  `The committed combat result is safely recorded.` It names no actor/event,
  promises neither continued combat nor a player turn, and lets canonical
  initiative/recovery code decide what follows. This is the smallest safe fix.

Both options must separately ratify the bounded eligible classes: completed
parse errors, completed blank/malformed narration-object contract errors,
coverage errors, and current lint rejects. Provider/transport, shared empty
provider payloads, narration-internal faults, and transaction/persistence
faults are excluded.

The existing `_deterministic_narration` and public `narrate_committed_events`
compatibility helper are not deleted merely because this caller does not use
them. Any deletion needs its own consumer inventory and GL-1 disposition.

### C4 -- Truthful recovery status and canonical post-delivery boundary

File: `core/managers/combat_manager.py` plus C1 prompt text.

1. When `execute_agentic_turn` is resuming an already-committed pending
   delivery, do not display `Resolving combat intents...`. Use a truthful
   delivery status such as `Delivering committed combat results...`, or omit
   the redundant status if the existing narration status already covers it.
2. T097 prose never solicits input. After delivery, existing initiative logic
   recomputes the next eligible actor. In TW05-E1 Mara is unconscious, so A1
   must not prompt her; current canonical code must reach the separately owned
   `player_incapacitated` recovery boundary with no later actor mechanics.
3. A separate conscious-PC fixture proves the normal actionable prompt and
   input boundary. The queued headless `quit` check proves process exit, not a
   gameplay action consumed by combat.

### C5 -- Mandatory simplifier and verification pass

After implementation, independently inspect the diff for:

- any remaining `_TITLE_RE`/`unknown_titled_entity` use;
- any accidental typed-reference/schema/provider/persistence addition;
- duplicated renderer or error-class logic;
- the restored valid-response `break`;
- provider failures accidentally consuming correction count;
- every FS-1 terminal and supersession edge;
- caller inventory before deleting any zero-current-caller helper;
- CRLF/UTF-8/ASCII-only changed lines, obsolete imports, and unreachable code.

Remove only implementation redundancy. Do not widen to other inherited prose
lint, in-flight provider cancellation, combat defeat, or balance work.

## 7. GL-1 Behavioral Contract

| Changed branch | Origin and goal | Disposition | Proof |
|---|---|---|---|
| `_TITLE_RE` / `unknown_titled_entity` | `eb2ecd52`; reject invented titled characters | **RETIRED**: issue #191 and AP-7 prohibit phrase/title parsing as narration authority. Exact dossier input plus event coverage remain; no weaker self-attestation replaces the parser | exact TW05-E1 candidate passes; source scan proves parser absent |
| Bounded attempt range | `eb2ecd52`; prevent correction from monopolizing play | **RESTORED/PRESERVED** | real invalid-contract recovery reaches one delivery and input boundary |
| Deterministic committed-fact fallback | `eb2ecd52`; never lose committed events after narration exhaustion | **OWNER GATE D1**: either add a separately reviewed typed disclosure projection and preserve the renderer, or explicitly retire/supersede this goal for a narrow non-disclosing boundary | D1-specific disclosure/terminal proof |
| Invocation checks around T097 | candidate `4290e711`; fence Load/Reset/quit | **PRESERVED and corrected at ownership boundary**: checks remain; supersession propagates to the invocation owner instead of becoming a re-entering pause | deferred quit exits; Reset/Load cannot accept a late write |
| Live-turn supersession authority | #214 live-turn lifecycle; web/headless destructive controls supersede work | **PRESERVED/CONNECTED**: an accepted live-turn supersession now fences the existing combat invocation too; Save and rejected/closed requests do not | central bridge polarity plus web/headless quit/Load/Reset and Save controls |
| Progressive correction and durable attempts | `eb2ecd52` plus candidate `4290e711`; keep rejected prose out of history and make restart resumable | **PRESERVED for completed-invalid candidates only**; provider failures were never model corrections and are excluded | encounter receipt inspection and recovery arm |
| Non-title narration rejection gates | `eb2ecd52` and later bookkeeping hardening; reject structural/mechanical contradictions | **PRESERVED byte-for-byte** | negative-control matrix |
| Model escalation by completed-invalid attempt | existing T097 provider config | **PRESERVED**; provider reissues do not falsely advance model-correction generation | captured actual model/attempt metadata |
| Valid candidate exit | baseline `eb2ecd52`; stop after acceptance | **RESTORED** (`continue` back to `break`) | first-attempt live success makes one T097 call |
| Existing response schema/custom narrator | mainline and provider compatibility | **PRESERVED byte-for-byte** | OpenAI/Gemini schema diff and custom narrator probe |
| README AI-DM/turn-based combat promise | README Core Game Systems and Combat Example | **PRESERVED** | live combat remains narrated, initiative-owned, and player-agency safe |

No deleted behavior is UNKNOWN.

## 8. Acceptance plan

All player-facing verdicts use native Windows `C:\Python312\python.exe`,
`run_headless.py serve`/`HeadlessClient`, configured real OpenAI, complete
protocol output, API captures, authoritative files, and wall-clock evidence.
Backend contract checks are development evidence only and never presented as
gameplay acceptance. Tests remain local/ignored.

Every operation records: complete player-visible protocol transcript; encounter,
character, and conversation before/after snapshots and non-empty-to-empty diff;
actual `response.model`; token/cost record; T097 call count; wall clock; delivery
ID/receipt state; and process/orphan state. A row is one of PASS, FAIL,
NOT-REACHED, or BLOCKED. NOT-REACHED is never called PASS.

Run one operation at a time, sequentially, in a fresh isolated game copy. A4's
listed native operations are separate arms, not a parallel batch. Dedicated
backend checks use separate roots and cannot mutate a live acceptance game.

### A1 -- Exact stuck TW05-E1 recovery

On a separate copy of codex-ps's preserved game:

- boot the 12-attempt/null-narration pending delivery;
- prove no mechanics rerun and no new provider call is needed;
- one D1-ratified terminal is retained and published under the existing
  delivery ID;
- each of the four applied event IDs remains exactly once;
- HP/resources/cursor/revision do not duplicate;
- the 19x/20x status/pause pattern is absent;
- no gameplay prompt is sent to unconscious Mara Voss;
- code reaches the exact existing `phase="recovery_required"`,
  `pauseReason="player_incapacitated"` boundary; no Kira/enemy mechanics run
  after publication and no victory is invented;
- a deferred headless `quit` exits the process and no later T097 write occurs.

### A2 -- Fresh real OpenAI combat

Replay the Thornwood Bandit Stronghold opening from the preserved pre-T097
lineage or reach it naturally:

- capture the actual T097 request/response/model;
- the dossier contains exact IDs/names and the response retains the existing
  narration/coverage schema;
- a valid narration mentioning Bandit Captain Gorvek is accepted without
  `unknown_titled_entity`;
- committed facts publish once and canonical initiative continues;
- player narration uses second person, reveals no unsensed facts, contains no
  bookkeeping, chooses no player action/roll, and contains no T097-authored
  `what do you do`/next-turn handoff;
- five narration claims are checked against encounter/character disk state.

Use a separate real conscious-PC combat window to prove the normal actionable
prompt is shown and one input is accepted after delivery.

### A3 -- Real bounded-correction polarity

Use a real provider response through the native game path that completes but
violates the existing T097 parse/coverage/lint contract. Do not fabricate a
player-facing transcript. Prove:

- each completed invalid candidate is recorded and excluded from history;
- at most the configured **completed-invalid** attempts are made for that
  committed delivery;
- exhaustion retains/publishes the D1-ratified terminal and canonical combat
  continuation;
- no mechanics, rewards, event IDs, or rolls rerun;
- no pause-then-auto-reentry loop occurs.

Gate polarity is mandatory. If a naturally-invalid completed response is not
observed, A3 is NOT-REACHED and overall release acceptance is BLOCKED. A2's
valid path and backend polarity do not substitute for firing the live terminal.

### A4 -- Negative controls and compatibility

- missing/misordered `coveredEventIds`, empty narration, internal-ID leak,
  bookkeeping leak, stale condition, hostile-count mismatch, and excessive
  length retain their prior verdicts;
- valid first-attempt T097 has no fallback marker;
- reconnect replays stable narration without rerunning T097/mechanics;
- a completed provider/transport error reissues without a durable
  `narrationAttempts` row or correction-generation increment;
- an unexpected internal error is not recorded as model correction and does
  not fabricate narration; a later healthy attempt retains one narration,
  with no mechanics replay, budget increment, or failed-action message;
- transaction/persistence faults preserve their existing recovery path;
- persistent provider-empty/provider-error and `internal_retry` loops remain
  visibly live but an accepted deferred quit/Load/Reset supersedes them between
  attempts, quiesces, and permits no late narration/attempt write;
- Save queues or executes at its existing safe boundary without superseding;
- a hidden participant whose event is present but whose identity is not granted
  does not leak through the D1 terminal. Under D1-A this proves the new typed
  public projection; under D1-B the generic terminal names no participants;
- multi-target, no-target, heal/effect, miss, and defeat/death event forms have
  no omitted event, bookkeeping, or third-person-human regression;
- one pre-typed/legacy encounter remains byte/behavior compatible.
- a custom narrator using the existing return contract remains compatible.

This arm splits backend checks from native gameplay operations. Direct linter,
renderer, and exception-polarity probes are development evidence. Reconnect,
supersession, publication, and conscious-player handoff are real native runs.

### A5 -- Platform and cleanup

- changed-file `py_compile` on native Windows;
- import smoke and existing relevant deterministic checks, reported only as
  development evidence;
- full diff/EOL/ASCII/secrets scan;
- central supersession bridge regression checks for web and headless controls;
- no orphan provider/game processes;
- git status contains only the authorized production files and this plan until
  the plan artifact is handled per owner instruction.

## 9. Tracked follow-ups

- #191 remains the existing owner for broader removal/replacement of inherited
  phrase/title/number narration acceptance checks. TW-013 changes only the
  title/entity seam that caused the observed blocker.
- #184 owns unconscious/defeat recovery and the broader incorrect player-turn
  prompt. TW-013 only proves that its narration terminal does not solicit Mara.
- #186 owns in-flight synchronous provider stall/cancellation. TW-013 checks
  invocation supersession between completed attempts and makes no broader
  cancellation claim.
- TW-014 remains the separate encounter-balance finding and is explicitly out
  of scope.
- No new follow-up is created for speculative entity-reference completeness or
  other narration lint; one real observed failure is required before adding a
  mechanism (AP-5).

## 10. Resolution ledger

| ID | Finding / decision | Resolution | Status |
|---|---|---|---|
| TW013-R1 | Was the permitted list wrong or stale? | No. Captured payload and encounter contain the correct canonical names. | RESOLVED -- OBSERVED |
| TW013-R2 | What exact token failed? | Regex extracted `Captain Gorvek` from valid `Bandit Captain Gorvek`; exact set comparison rejected it. | RESOLVED -- OBSERVED + CODE-PROVEN |
| TW013-R3 | Is false rejection recent? | No; matcher is byte-present on `691b5a2f`, introduced by `eb2ecd52`. | RESOLVED -- HISTORY-PROVEN |
| TW013-R4 | Is runaway recent? | Yes; `4290e711` removed bound/fallback and added unbounded `while`; absent on `691b5a2f`. | RESOLVED -- HISTORY-PROVEN |
| TW013-R5 | Root or symptom? | Both false prose identity authority and missing terminal are independently defective and jointly causal. Receipt overflow/repeated pause are symptoms. | RESOLVED |
| TW013-R6 | Surface substring patch? | Rejected as AP-7/issue-191 violation and heuristic cascade. | RESOLVED |
| TW013-R7 | How preserve invalid-entity rejection? | Do not preserve a prohibited prose parser or add model self-attestation. Exact dossier context remains model authority; exact event coverage remains code authority. | RESOLVED -- ISSUE #191/AP-7 |
| TW013-R8 | Which failures consume correction attempts? | Completed parse/object-contract/coverage/lint rejects only. Shared provider-empty payloads and provider/transport faults reissue without counting. Narration-internal faults take typed `internal_retry`; transaction faults remain in transaction recovery. | PROPOSED -- REVIEW REQUIRED |
| TW013-R9 | What happens after valid narration? | Restore baseline `break`; runtime, not T097 prose, computes the next turn. | RESOLVED -- HISTORY/ARCHITECTURE |
| TW013-R10 | What happens on supersession? | Re-raise `InvocationSupersededError` to its owner; do not translate it into re-entering `CombatTurnPaused`. | PROPOSED -- REVIEW REQUIRED |
| TW013-R11 | What prompt boundary prevents Mara handoff prose? | T097 narrates one committed beat and never asks for input/declares next turn. | PROPOSED -- REVIEW REQUIRED |
| TW013-R12 | Can live web/headless controls actually supersede T097 retries? | Not before TW-013: live-turn scope and combat claim are separate. Bridge accepted central live-turn supersession to the existing combat fence; Save/rejected requests do not fence. | PROPOSED -- REVIEW REQUIRED |
| TW013-D1 | Ratify the exact B2-iv terminal for exhausted completed-invalid T097 responses. | D1-A preserves #191 but expands scope to a typed disclosure projection and requires a revised/re-reviewed plan. D1-B is the narrow recommendation but must explicitly supersede #191's renderer goal. In either case ratify completed parse, parsed blank/malformed object-contract, coverage, and current lint rejects; shared provider-empty, provider/transport, internal, and transaction failures are excluded. | **OPEN -- OWNER ONLY; IMPLEMENTATION BLOCKED** |
| TW013-R13 | Implementation authority | Six-lens convergence and Claude review do not authorize code. Owner D1 and explicit execution approval are required afterward. | BLOCKED UNTIL OWNER APPROVAL |
