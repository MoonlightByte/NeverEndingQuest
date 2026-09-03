# Issue #262 No-Limits Ship-Gate Remediation Plan

Status: PLAN ONLY - product edits are blocked pending Part 3 convergence, Claude
independent review, and resolution of the explicit owner gates in section 14

Date: 2026-09-02
Policy epoch: live GitHub issue #193 v2.7, updated 2026-09-02T23:28:18Z
Branch: `integration/npc-voice-episodic`
Captured HEAD and `origin/integration/npc-voice-episodic`:
`0214cbdf5d30545c9045afb471bdaed0fbcfd4c7`
Current `origin/main`: `52990aa08f1108cdc5660c31fb862ab342871944`
Issue: MoonlightByte/NeverEndingQuest#262
Primary blind inventory:
`/mnt/c/agent-room-fleet-kit/local-data/sweep-nolimits-0214cbdf.md`
No revision in this document is runtime authority.

## 1. Objective and player contract

Close the No-Limits ship gate without replacing content loss with provider failure.
Every gameplay model must receive complete selected records; every accepted model
output and player-authored clarification must survive intact; every persistent store
must accept those values. Numeric limits may remain only when they constrain mechanics,
identity, diagnostics, or an explicitly ratified semantic selection rather than model
input, model output, or injected context.

This advances the #193 Part 2 contracts for NPC systems, combat, conversation,
schemas/compatibility, web UI, provider routing, and native acceptance. It preserves:

- grounded companion memory and honest absence;
- exact player actions, clarifications, dice ownership, and committed combat facts;
- full canonical identity and state validation;
- one live runtime path and automatic compatibility for existing saves;
- real provider constraints through lossless structure, never silent truncation;
- responsive, cancellable TTS controls and truthful player-visible failure;
- no new semantic model callsite, store, recovery record, rollout switch, or hidden
  mode. Under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`, the existing T112 callsite runs whenever a present actor
  has episodes; that can increase invocations, but removes a code-authored semantic
  pre-screen rather than adding a model role. Long-TTS repair is explicitly unchanged
  here and assigned whole to #276.

README promises preserved are adaptive AI storytelling, persistent companions,
turn-based combat, browser play, and optional DM voice. Removing a cap must not turn a
previously working short-input path into a new format or different narration contract.

## 2. Authority and diagnosis

### 2.1 Governing authority

Live issue #193 v2.7 Part 1 B2 and Part 5 explicitly prohibit character, token,
length, slice, and numeric bounds on gameplay model inputs, model outputs, or injected
context. Sizing is selection and structure, not amputation. D-272-1 ratifies exactly
two semantic selections in this surface: top-2 relevance-ranked recalled episodes and
one arc-seed goal pick. No other ranked row in the combined inventory is presently a
ratified exception.

Part 2 pages consulted before planning:

- Combat: code owns bookkeeping; models receive sufficient exact scene/rule facts.
- NPC systems: grounded attributed recall or honest absence; blank/muted behavior is a
  failure.
- Conversation/chronicle: summaries cannot drop load-bearing state.
- Web/threading/assets: player controls must act and long work stays visibly live.
- Provider routing: provider/API failures are loud and gameplay remains recoverable.
- Schemas/compatibility: relax-only changes must keep every old player file valid;
  writers preserve existing non-empty values.
- Part 2 page 5 Effects and page 9 Save/Reset: generated effect state, migration receipts, completion
  epochs, locks, restored module backups, and live quest progress are runtime/player
  data, not source changes; candidate cleanup restores them exactly to `origin/main`.
- Part 2 page 12 Player Data: candidate cleanup may not migrate, normalize, or retain
  copied player state; main-tracked module assets are restored byte-for-byte.
- Acceptance: native Windows and real providers establish player-facing truth.

### 2.2 Observed/code-proven loss points

The blind sentinel found 31 CRITICAL rows, six unratified ranked selections, two
ratified selections, and 61 non-content hits. The owner then froze this ship gate to
the 72 files already touched by the voice bundle. Complete-call-path review found 19
additional in-scope semantic rows: R7-R8, C32-C33, C38-C41, C44-C50, and C51-C54. The frozen
disposition ledger has 119 rows; C23 is dispositioned whole to #276 rather than
partially changed because two mandatory consumers are outside the 72-file boundary.
The code trace confirms the critical data flow rather than relying on grep alone:

- T108 receives only `flatten_scene(...)[-16000:]`; early location events can never
  enter the episode ledger or later T105/DM recall.
- T108/T113 are explicitly instructed to return 100/600/12/120-bounded output, then
  `EpisodeStore` truncates or drops those outputs, and the episode schema rejects
  larger values. The explicit prompt bounds were missed by the prepared regex but are
  the same forbidden model-output class and are included here.
- T107 returns relaxed structured output, after which `validate_profile` and its
  fallback delete array members before the profile reaches T105.
- A completed-invalid T107 persists its deterministic fallback with the same
  `sourceCanonical` used by a validated model profile. The source-match fast path then
  returns it forever, so Fork-3's fresh-next-beat retry never occurs. Removing the
  fallback's caps also exposes the sentinel `unknown` beside real goals unless that
  sentinel becomes empty-only.
- `RelationshipStore` drops mood tags, evidence topics, evidence records, lifecycle
  events, POV rows, advisory history, red lines, obligations, and linked evidence.
  Several are persisted model-derived facts and later become T105/T107/DM context.
- T096 loses skills, proficiency entries/categories, aliases, player clarification
  history, all but eight per-actor owned-capability candidates, and all but three
  globally selected SRD references. The global rule sort leads with actor order, so
  actor one can consume every slot.
- T096 also loses feats and species traits after item 24. T105 relationship context
  loses evidence after item three on both OOC and combat packet paths. T065 validation
  loses history after four selected turns. T041 asks for at most two/250-word permanent-
  summary prose. T042 asks for 2-4 highlights and rejects outside that range. T107
  separately asks for no more than two authored arc seeds before runtime/schema caps.
- T014 instructs and validates 500-character NPC descriptions and 200-character
  location updates. T108 witness discovery takes only 500 characters when an older
  `Party NPCs:` stamp lacks its normal `Party stats:` terminator. The C15 downstream
  pending-delivery validator independently rejects the 25th narration code. T041's
  singular `story paragraph` and T042's per-highlight sentence instructions remain
  output-shape ceilings even after their explicit numeric ranges are removed.
- T097 correction context loses violation/warning codes after item 24.
- the DM sees only three module areas, three hub services, and two letters of
  alignment in multiple context builders.
- OpenAI TTS silently discards narration after character 4096. The
  [official speech endpoint](https://platform.openai.com/docs/api-reference/audio/createSpeech)
  itself accepts at most 4096 characters per request, so simply deleting the slice and
  issuing one oversized request would replace loss with a deterministic 400. The
  chosen design therefore partitions without dropping content.
- `voice_contracts.py` keeps dead `maxItems` literals and erases them at runtime. A
  copied schema can re-arm the caps, and `_remove_array_limits` does not protect future
  `maxLength` additions.
- The active T105 recall path first uses code token overlap between the raw player
  sentence and stored episode prose (`voice_context.py:165-185`). Tokens shorter than
  three characters are discarded (`episode_recall.py:56-63`), so code can prevent
  T112 from making the semantic recall decision. Two duplicate recall helpers inside
  the same 72-file surface have no runtime callers and retain the same lexical screen
  or an unratified top-three result cap; leaving them creates a dormant AP-7 path.
- Commit `cf5a89b2` accidentally tracked acceptance/runtime residue inside the merge
  candidate: four zero-byte lock files, `effects_state.json`, a completion epoch,
  five restored Keep-of-Doom area backups, and a live player-quest file. These are not
  product assets for this wave. C0 restores all twelve paths exactly to `origin/main`
  (deleting paths absent there) before any feature edit, so player-specific state and
  local backup paths cannot ship.

Lineage is mixed and does not alter the ship-gate obligation: episode/profile caps
originated in the August 18 companion-memory commits; combat caps mostly originated in
`eb2ecd52`; world-context and TTS caps predate this branch. The candidate tree is the
merge unit, so pre-existing-in-a-touched-file is not an exemption.

## 3. Full disposition contract

### 3.1 CRITICAL rows

| Rows | Current behavior | Planned disposition |
|---|---|---|
| C1 | T108 tail-only scene | RETIRE `max_chars` and send the complete flattened location scene. Do not add proactive chunk machinery; if a real provider rejects an authentic full scene, stop and return with that observed evidence before designing scene-boundary partitioning. |
| C2-C5, C31 | T108/T113 episode strings, facts, tags, witnesses are truncated/dropped; health text normalizes the witness cap | RETIRE every count/character drop and the cap-specific health event. Preserve type checks, whitespace normalization, uniqueness, UUID reconciliation, attribution, and atomic validation. |
| additional prompt rows | T108/T113 ask the model for 100/600/12/120-bounded output | RETIRE only the numeric output instructions; keep groundedness, attribution, kind, and presence rules byte-equivalent. |
| C6-C7 | T107 output and fallback arrays are sliced | RETIRE count parameters and preserve every unique non-empty value. `unknown` is emitted only when the corresponding known-value list is empty, never beside known facts. Fallback ordering and a guaranteed non-empty goal remain. T107 fallback provenance/retry is governed by D-262-T107. |
| C8 | episode ledger schema rejects larger model-derived content | RELAX ONLY: delete relevant `maxLength`/`maxItems`; retain types, required fields, UUID patterns, uniqueness, enums, and numeric game mechanics. |
| C9 | NPC sidecar schema rejects larger model-derived/context arrays | RELAX ONLY for profile, evidence topics, working/advisory history, lifecycle, red-line/obligation, and POV model-content arrays. Remove the coupled POV/evidence runtime pruning. Retain identity-alias and applied-event-ID constraints only if the consumer audit proves they are identity/dedupe state rather than model context; every retained grep hit is dispositioned explicitly. |
| C10-C14 | relationship working/evidence/lifecycle/POV persistence drops content | RETIRE the caps; keep stable dedupe, deterministic ordering, exact typed-event idempotency, existing aggregate values, and atomic writes. `_prune_evidence` becomes lossless normalization or is deleted if all callers can directly preserve evidence and applied IDs. |
| C15 | T097 correction codes stop at 24 | RETIRE both slices; keep ordering and string filtering. |
| C16-C19 | T096 skills/proficiencies/categories/aliases are sliced | RETIRE slices; keep validation, normalization, deterministic sort, and duplicate suppression. |
| C20-C21 | player clarification history is capped at 7/8 on write and render | RETIRE all three persistence slices and the render slice together; keep duplicate-current-input suppression, ordering, pending-turn ownership, and complete-chain formatting. |
| C32 | T096 feat and species-trait names stop at 24 | RETIRE `_named_entries`' count argument and break. Preserve type/whitespace normalization, source order, and canonical sheet ownership. Grade feats and species traits independently. |
| C33 | T065 validation history stops after four selected player/assistant messages | RETIRE the count argument, break, and four-item padding. Preserve role filtering, chronological order, current-turn exclusion, and exact accepted-history authority. |
| C38 | T107 prompt limits authored `arcSeeds` to two | RETIRE only the numeric output bound. Preserve source-grounding, typed structure, and advisory/non-authoritative purpose. |
| C39 | T041 permanent-combat-summary prompt limits output to 1-2 paragraphs and 150-250 words | RETIRE numeric paragraph/word bounds. Preserve factual coverage, past tense, ASCII, no-markdown, XP, aftermath, and permanent-record purpose. |
| C40-C41 | T042 prompt requests 2-4 highlights and its validator rejects outside that range | RETIRE both numeric prompt and validator bounds together. Preserve list type, non-empty meaningful presence, and every accepted highlight. |
| C44-C45 | T014 prompt and validator cap `newDescription` at 500 and `locationUpdate` at 200 characters | RETIRE each prompt/validator pair atomically. Room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c` defines optional `locationUpdate` as absent/None or string so malformed containers/scalars cannot become world prose when the shared `len` bound is removed. Preserve existing `newDescription`/`newAttitude` type/presence, canonical ownership, legal action, and exact target-location validation. |
| C46 | T108 legacy witness-stamp fallback reads only 500 characters | RETIRE the fixed slice. Parse to the normal ` Party stats:` delimiter when present; when absent, parse only to the first newline or end-of-message, whichever comes first, with no numeric cutoff. Retain existing comma/name normalization and canonical identity resolution; never admit following DM-note lines as roster text. |
| C47 | pending-delivery validation rejects more than 24 T097 violation/warning codes | RETIRE the count comparison together with C15's producer slices. Preserve list type, string type, code regex, attempt ordering/status, and receipt integrity. |
| C48 | T041 singular `story paragraph` remains a one-paragraph output instruction | Replace only that singular shape with uncapped `narrative account`; preserve story/factual/tone purpose and the other C39 contracts. |
| C49-C50 | T042 schema example and prose each require one sentence per highlight | RETIRE both sentence-count instructions. Preserve evocative, factual dramatic-moment meaning and typed/non-empty highlight validation. |
| C51 | Active T105 recall dispatch requires raw-player/stored-prose token overlap before T112 | RETIRE the lexical pre-screen under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`. The only code gate is the typed fact that a present actor has at least one episode; T112 owns whether the sentence names a past event and may return empty anchors. Preserve actor attribution, the ratified strict top-2 active selection, typed exact-value scoring eligibility, fencing, and one-beat degradation. |
| C52-C53 | Zero-caller duplicate recall helpers retain the lexical pre-screen and an unratified top-three result cap | DELETE the dead helpers, not merely their caps. Preserve the shared `parse_anchors`, `select_episodes`, tokenization used after T112, and the ratified live top-2 selection. Caller sweeps must prove zero runtime consumers before deletion. |
| C54 | T112's current system instruction presupposes that every input references a past shared event | Replace only that false premise with a neutral semantic classification: extract anchors only when the player concretely invokes a past/shared event; for present/future action or no concrete past reference, return all three arrays empty. Preserve the same typed response, grounding, lowercasing, and no-judgment contract. This is the consumer-complete half of C51, not a new model role. |
| C23 | OpenAI TTS drops narration after 4096 | ASSIGNED WHOLE to #276. D-262-TTS ratified the lossless architecture, but a correct producer-and-four-consumer change requires two React files outside the frozen 72-file bundle. Server-only or legacy-only repair is forbidden. |
| C24-C25 | DM sees only three areas/services | RETIRE slices; preserve authoritative ordering and full identifiers/names. |
| C26-C29 | alignment is reduced to two ambiguous letters | RETIRE slices and inject the complete alignment string in both shared and combat formatters. |

### 3.2 Ranked selections

| Row | Ranked datum | Planned disposition |
|---|---|---|
| R1 | relationship evidence, magnitude/recency, destructive top 256 | RETIRE. Preserve every evidence record and existing aggregate counters; no future event is folded into a count-only surrogate. |
| R2-R3 | per-NPC POV rows by salience, destructive 40/512 | RETIRE. Preserve all unique rows in deterministic pinned/salience/id order. |
| R4 | per-turn DM memory rows, pinned/location/salience/grain top 3 | OWNER GATE D-262-R4. Recommendation: retain as semantic per-turn selection only if explicitly ratified; otherwise remove the limit and inject all complete rows. In either case delete the false outer-char-budget comment. |
| R5 | OOC T105 packets, actor selection limited to four | OWNER GATE D-262-R5. Recommendation: remove the limit; it is a presence cap in the same family as D-272-1's 12-actor failure. Preserve eligibility and fairness ordering, dispatch every eligible companion. |
| R6 | T096 SRD references, global actor-first top 3 | RETIRE. Match all exact/alias/structured references per actor, preserve deterministic relevance order within each actor, and dedupe on `(actor, ruleId)` where actor availability/resources differ. Canonical spell-entry dictionaries may remain rule-keyed because their content is actor-independent; actor-specific `ruleReferences` must not collapse. Corrective references also return every exact structured match. |
| R7 | T096 owned-capability candidates, per-actor top 8 | RETIRE `max_candidates` and the final slice. Preserve matching, deterministic score/order, dedupe, canonical ownership, and ambiguity safety; every genuine match for the actor reaches `capabilityCandidates`. |
| R8 | T105 relationship evidence, relevance-ranked top 3 on both OOC and combat packet paths | RETIRE the parameter and final slice. Preserve filtering, magnitude/recency ordering, stable dedupe, and actor attribution; inject every selected evidence event in deterministic order on both paths. This follows D-272-1's complete relationship evidence/events ruling. |
| D-272-1-A | top-2 relevance-ranked episode recall | PRESERVE, ratified Part 5. |
| D-272-1-B | one arc-seed goal pick | PRESERVE, ratified Part 5. |

### 3.3 Non-content hits

Identity fragments, hash abbreviations, time display formatting, diagnostics/log
previews, bounded mechanics, cache/health rings, dedupe receipts, and ambiguity/minimum
length tests do not limit model content. They remain only after a file:line disposition
in the final sentinel paste. This plan does not turn #262 into a rewrite of IDs,
mechanical ranges, caches, retry policy, or combat retirement. T105/T107 completed-
invalid attempt policy is reviewed by Fail-Forward under Fork-3/B2-iv and escalated if
its ledger citation is insufficient; it is not silently changed as a content-cap fix.

## 4. Chosen architecture

### 4.1 Complete episode/profile persistence

Use lossless sanitizers: validate type and required meaning, strip surrounding
whitespace, retain first occurrence of exact duplicate strings, reconcile canonical
actor IDs, and preserve every surviving record. No count argument remains. Schemas are
relaxed in the same commits as their writers, so there is no intermediate state where
the writer emits a value its schema rejects.

Existing sidecars require no migration: removing `maxItems`/`maxLength` is a strict
superset of the old accepted language. The authentic-file scan is a hard gate: every
baseline-valid file must remain candidate-valid. Candidate-only validity is expected.
Any baseline-valid/candidate-invalid record stops implementation and returns to the
owner; it is not repaired or rewritten.

### 4.2 Complete combat and world projections

The plan removes storage/render caps at both ends of each chain. It does not add a
larger replacement number. T096 SRD selection remains semantic matching, but cardinality
is the number of actual matches per actor. Duplicate canonical text may be represented
once while actor availability/resource facts remain actor-keyed. Full alignment, areas,
services, skills, proficiencies, aliases, correction codes, and clarification exchanges
are copied without abbreviation.

T041/T042 prompt cadence and typed-presence rules remain qualitative, while numeric
output ranges and matching validator rejection retire together. Legacy-only T040,
T046, and T045 history/prompt/compression paths are governed by #191 retirement and
are not modified by this bounded ship gate.

### 4.3 Ratified TTS direction, deferred whole to #276

This subsection records the already-ratified direction but grants no implementation or
acceptance authority in this wave. The complete producer-and-four-consumer path moved
to #276 when the owner froze #262 to the 72 bundle-touched files.

The speech API's per-request maximum is provider topology, not authority to delete
narration. The existing `/api/tts` endpoint gains one explicit wire discriminator:

- Missing `operation`, or `operation: "speech"`, preserves the existing request
  `{text, voice, model}` and success response `200 audio/mpeg`. Empty input remains
  `400 application/json` with `{error}`; provider/internal failure remains `500` with
  `{error}`. Input above the provider maximum is rejected loudly as `413` with
  `{error}` instead of being truncated.
- `operation: "partition"` accepts `{operation, text}` and returns `200
  application/json` with `{parts: [{index, text}], sourceLength}`. Indexes are
  zero-based contiguous integers, parts are non-empty strings in source order, every
  part is provider-valid, and concatenating `parts[*].text` exactly reproduces the
  source text. Empty/malformed input is `400` with `{error}`. The operation performs
  no provider call.

The partition operation prefers paragraph, sentence, then whitespace boundaries; an
indivisible overlong token is split only as a last-resort transport partition. The
legacy narration client and React `TtsButton` first request this canonical partition,
then make the existing/default speech request once per part and play the complete
sequence. The legacy settings preview and React `SettingsMenu` preview retain their
existing short `{text, voice, model}` requests and one-part `audio/mpeg` response.
Thus all four current callers have one frozen contract: narration uses partition then
speech; preview uses the backward-compatible default speech operation. There is one
server partition owner, not duplicated split logic in two clients; one endpoint, not
a second TTS runtime; and no store or server job coordinator.

The client owns the user action and sequence. React retains its `AbortController`; the
legacy client gains the same cancellation generation and keeps its control actionable
while a part is loading. Stop aborts the client fetch, invalidates the sequence,
prevents every undispatched part, prevents caching/autoplay of the stopped result, and
returns the control to truthful idle. The synchronous Flask handler completion-collects
the already-issued provider call even if its browser fetch disconnects; it does not
spawn, abandon, or dispatch subsequent work. This is the reviewer-permitted completion
path, not a claim that the OpenAI SDK can cancel an already-issued synchronous speech
call.

No elapsed deadline, partial-success cache, or silent skipped segment is allowed. If
part N fails, prior audio may already have played, but the UI reports the failure,
returns idle, and does not claim/cache complete playback. Cache identity covers the
complete text, engine, and voice and is stored only after all part URLs exist. Short
input is a one-part instance of the same partition/sequence path. Room ruling
`91d403a3-0580-443e-818c-3dd5fa455f92` ratifies this architecture. The
provider-forced per-request partition is a Part 5 B2-iv topology boundary even though
total narration is uncapped.

### 4.4 T107 fallback is playable but not permanent

Room ruling `e01d5df3-0849-48c0-8ec5-40c90244abad` ratifies this in-wave under
Fork-3/B10. The single-path design adds one optional profile provenance enum to the
existing profile record: `fallback` or `model`. Recruitment still persists the deterministic fallback
before T107, but marks it `fallback`; only a validated T107 result is `model`. The next
eligible T105 packet build seeing `fallback` retries T107 fresh from the same immutable
source and replaces it on success. It continues using the grounded fallback for that
beat if T107 again completes invalid, with loud telemetry; gameplay never blocks.

For old profiles with no provenance, code reconstructs the deterministic fallback from
the already persisted source value and performs full typed-value equality: exact match
is classified fallback and retried, while a distinct profile is preserved as model-
authored. This is value comparison, not prose/hash authority, and requires no startup
migration. If the persisted source cannot be parsed safely, preserve the profile and
report the unclassified legacy state rather than overwrite it. The implementation must
dedupe concurrent OOC/combat attempts through existing T107 cache/voice dispatch
ownership; it may not add a lock across provider work or duplicate model calls. If that
cannot be proven with existing machinery, stop and return to the owner rather than add
a coordinator.

### 4.5 T112 owns recall meaning

Under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`, code may decide only whether there are any canonical episodes for
a present actor. When there are, the existing T112 semantic call receives the complete
current player sentence under a neutral C54 instruction and decides whether it contains
concrete past-event anchors. Present/future actions and inputs with no concrete past
reference must return all three arrays empty. Code then applies the already-ratified
strict top-2 relevance selection; exact typed-value matches affect scoring eligibility,
not cardinality. It does not compare raw player words with stored prose to decide
whether T112 may run.

This creates no new callsite, model role, store, or provider mechanism, but it can
increase T112 invocations on ordinary turns for actors with episodes. The ruling
accepts that cost because retaining the lexical screen would preserve an AP-7 semantic
bypass. Existing advisory fencing, parallel dispatch, completed-invalid
one-beat degradation, and next-beat retry remain unchanged. Delete both zero-caller
duplicate high-level recall helpers so no dormant alternate screen or top-three path
can later become a second runtime; retain their shared low-level typed scoring helpers.

### 4.6 Dead neutralizer and misleading names

Delete all `maxItems` literals from model packet/profile schemas in
`voice_contracts.py`. If the resulting schema family contains no array maxima,
delete `_remove_array_limits` and its calls; validation remains direct against the
uncapped source schema. Rename `truncate_dm_notes` and its callers to a name describing
its only behavior, legacy DM-note normalization. No logic changes in that rename.

Correct the two false documents: `voice_packets.py` has no per-field truncation, and
the context-balance record may not claim all selection/no truncation while unratified
or forbidden rows remain. Historical plans are marked as superseded at the specific
claims rather than rewritten as if they predicted this remediation.

## 5. Implementation slices and commit boundaries

No product code changes begin until all gates close. Each slice gets focused checks,
an exact diff review, and a simplifier pass before its commit.

### C0 - Freeze inventory, call graph, and compatibility corpus

- Capture branch/main ancestry, the exact 72-file bundle list, and the frozen 119-row
  disposition ledger: the sentinel inventory plus code-proven R7-R8, C32-C33,
  C38-C41, C44-C50, and C51-C54.
- Add the missed T108/T113 prompt bounds and any same-class findings from a semantic
  scan of all touched gameplay files; every hit is dispositioned before C1.
- Inventory authentic episode ledgers/NPC sidecars and their current validator result.
- Trace all `/api/tts` clients and establish one compatible complete-audio contract.
- Freeze baseline outputs for below-old-cap episode/profile/combat/world builders.
- Remove the `cf5a89b2` acceptance residue by restoring these exact paths byte-for-byte
  to `origin/main` (which means deleting those absent on main):
  `data/companion_memories/episode_ledger.json.episode-ledger.lock`,
  `data/companion_memories/npc_agent_state.json.npc-agent.lock`,
  `modules/.campaign.json.completion-epoch.json`,
  `modules/effects_migration.effects-migration.lock`,
  `modules/effects_state.json`, `modules/effects_state.json.effects.lock`,
  `modules/Keep_of_Doom/areas/G001_BU.json`, `HH001_BU.json`, `SK001_BU.json`,
  `TBM001_BU.json`, `TCD001_BU.json`, and
  `modules/Keep_of_Doom/player_quests_Keep_of_Doom.json`. Prove the five main-tracked
  files equal main and the seven main-absent files are absent; no player/runtime state is
  migrated or regenerated.
- Revert `core/headless/bootstrap.py:108-120` to main's direct `copytree` behavior.
  Commit `0993430e` added the private-runtime ignore after acceptance data was present
  in the source tree; with that residue removed, the compensating branch is unnecessary
  mechanism. Preserve every other headless fixture/bootstrap behavior byte-for-byte.
- Record exact owner rulings for D-262-R4, D-262-R5, D-262-TTS, and
  D-262-T107, plus room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`
  for T014 and recall.
- HARD STOP inside the frozen 72-file boundary: any inventory count, call graph,
  authentic-corpus result, client contract, or retained-bound classification differing
  from this plan stops before C1. Amend the plan, GL-1 table, resolution ledger, and
  allowlist; rerun every required FULL reviewer to clean same-SHA confirmation; then
  present the revised plan for Claude/owner approval. A newly found cap owned outside
  those 72 files goes to #276 by default; a legacy-only combat cap goes to #191
  retirement. If an in-scope producer cannot be corrected without an outside-bundle
  consumer change, move the complete coupled path to the applicable follow-on rather
  than ship an ineffective producer-only edit.

### C1 - Episode and profile truth, atomic with schemas

Files expected:

- `core/npc/episode_extraction.py`
- `core/npc/episode_backfill.py`
- `core/npc/episode_capture.py`
- `core/npc/episode_recall.py`
- `core/npc/episode_store.py`
- `core/npc/profile_service.py`
- `prompts/npc/npc_profile_seed_t107.txt`
- `core/npc/relationship_store.py`
- `core/npc/voice_context.py`
- `core/npc/voice_contracts.py`
- `schemas/episode_ledger_schema.json`
- `schemas/npc_agent_state_schema.json`

Remove C1-C14/C31/C38/C46/C51/C53, R1-R3/R8, dead schema limits/neutralizer, update C54, and the explicit
extraction/profile prompt bounds. Apply the D-262-R4/R5 rulings only if approved before implementation.
Apply D-262-T107 and the ratified C51 recall change in this schema-atomic slice. Delete
C53 unconditionally after zero-caller proof. Run real-sidecar validation
before and after, writer/reader round trips, and deterministic >old-boundary
preservation checks. Do not edit player files.

### C2 - Combat projection and continuation completeness

Files expected:

- `core/ai/combat_capabilities.py`
- `core/ai/srd_reference.py`
- `core/ai/combat_agent.py`
- `core/managers/combat_orchestrator.py`
- `core/managers/combat_state.py`
- `core/managers/combat_transaction.py`
- `core/managers/combat_manager.py`

Remove C15-C21, C28-C29, C32, C39-C41, C47-C50, and R6-R7 as one
consumer-complete wave. Prove every write,
render, initial selection, correction selection, and caller signature agrees. Preserve
initiative/order, action authority, exact pending-turn ownership, duplicate suppression,
and correction semantics.

### C3 - Main-DM world/context completeness and truthful naming

Files expected:

- `core/ai/conversation_utils.py`
- `core/ai/action_handler.py`
- `main.py`

Remove C24-C27 and C33; apply D-262-R4/R5 if their consumers live here. Remove
C44-C45 with the ratified coupled optional-string hardening. Delete the stale char-budget comment and the
zero-caller C52 helper, and rename `truncate_dm_notes` plus every caller. Below-boundary
outputs must be recursively identical except full alignment replaces its ambiguous
two-letter rendering.

### C4 - Reserved; not executed in this wave

C23/TTS moved whole to #276. No TTS server, legacy-client, React-client, cache, or
provider behavior changes under this plan. Its later implementation requires a fresh
#193 plan and review over the complete producer-and-four-consumer surface.

### C5 - Documentation, global sentinel, regression, simplifier

Files expected:

- `docs/architecture/companion-memory.md`
- `docs/architecture/npc-voice-ooc.md`
- `docs/audits/2026-08-18-npc-memory-persistence-structural-map.md`
- `docs/design/2026-08-31-npc-voice-context-balance.md`
- `docs/npc-voice-flow-map.html`
- any additional architecture doc whose exact contract changes are identified in C0.

Replace the token-overlap/T112 descriptions in the first two Markdown files with the
C51-C54 flow. Correct the visual map's T112/T113 episode-capture label to T108/T113 and
remove its stale-visual disclaimer rather than preserving known false architecture.
Reconcile only now-false claims, record every GL-1 disposition, run the mandatory
simplifier pass, run the whole touched-tree sentinel scan, and execute regression/live
acceptance. Commit/push only after Claude reviews the complete diff and evidence.

## 6. GL-1 behavioral contract

| Deleted/replaced behavior | Origin/goal | Disposition | Proving gate |
|---|---|---|---|
| T108 tail retention | `975f8d7a6`, constrain extraction input | RETIRED by #262; complete scene replaces it | A1 request capture includes first and last transcript anchors |
| T108/T113 concise-output numeric prompt rules | August 18 episodic work, compact memory | RETIRED by #262; factual/attribution rules preserved | prompt exact-diff plus A1/A1b quality review |
| Episode string/fact/tag/witness caps | `1736380e6`, bounded store | RETIRED by #262; validation/dedupe/attribution preserved | D1 plus A1/A2 |
| Episode schema maxima | companion episode schema, reject oversized values | RETIRED relax-only; every other constraint preserved | S1 authentic-file scan and D1 |
| T107 profile retention and fallback caps | `7504a717b`, compact profile | RETIRED; unique/non-empty and fallback ordering preserved | D2 and A2 |
| T107 source-matched fallback fast return | August 18 profile seeding, avoid repeated profile calls | PRESERVED for validated model profiles; under D-262-T107 a fallback is playable for one beat and retries fresh under Fork-3 | D2 failure polarity and A2 fresh-next-beat capture |
| NPC sidecar model-content maxima | companion state schema, bounded records | RETIRED relax-only; identity/mechanics constraints preserved | S1 and D2 |
| Relationship evidence pruning/count folding | `7504a717b` plus `b1da8f0fc`, bound storage and retain dedupe | RETIRED content loss; exact event-ID dedupe and historical aggregates preserved | D3 repeated-write/idempotency and real sidecar diff |
| POV 40/512 retention | `7817009d3`, bounded/pinned memory | RETIRED; deterministic order and keyed update preserved | D3 with 513 rows and no duplicate IDs |
| Working/profile/lifecycle/advisory count caps | August 18 NPC sidecar work, bounded store | RETIRED; exact duplicate suppression/order preserved | D3 and A2 |
| R4 top-3 DM memory selection | `0e7b1f2d3`, relevant proactive recall | OWNER-RULED disposition required | D-262-R4 plus A1 recall |
| R5 four-companion OOC selection | `b901d68cb`, bounded voice batch | OWNER-RULED disposition required | D-262-R5 plus multi-companion A3 |
| Raw-player/stored-episode lexical recall pre-screen | voice C2, avoid paying for T112 on ordinary turns | RETIRED under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`; episode existence remains the only code gate and T112 owns semantic past-reference recognition | D22 plus A2/A7 actual T112 captures |
| T112 presupposition that the player is referencing a past shared event | initial recall parser, narrow the extraction task behind the old lexical screen | RETIRED with C51; neutral classification requires empty anchors for present/future/no-past-reference input while preserving typed grounded extraction | D22 plus overlapping-term ordinary-action A2/A7 control |
| Zero-caller `_recall_by_npc` and `recall_episodes` high-level helpers | earlier recall integration, lexical/capped alternate paths | RETIRED after AST/caller proof; shared low-level anchor parsing/scoring and live ratified top-2 selection remain | D22 caller sweep plus import smoke |
| Runtime schema limit neutralizer | `e55280868`, prevent provider/schema caps | RETIRED only after source literals are deleted; direct uncapped schema preserves validation | source grep and schema equivalence minus maxima |
| Combat capability slices | `eb2ecd52`, compact T096 context | RETIRED; validation/sort/dedupe preserved | D4 plus A3 actor-keyed capture |
| Pending clarification windows | `eb2ecd52`, bounded pending state | RETIRED; ownership/order/duplicate-current-input preserved | D5 plus roll-pause replay |
| T097 correction-code slices | `eb2ecd52`, bounded correction context | RETIRED; typed status and order preserved | D6 25+ code round trip |
| Global SRD top 3 | `eb2ecd52`, compact exact references | RETIRED; exact matching, ambiguity rejection, relevance order preserved per actor | D7 plus A3 |
| Per-actor owned-capability top 8 | `eb2ecd52`, compact capability candidates | RETIRED; match safety, deterministic relevance order, dedupe, and ownership preserved | D4 plus A3/A7 |
| Feat/species-trait top 24 | combat capability projection, compact owned names | RETIRED; type/whitespace normalization, source order, and canonical ownership preserved | D4 plus A3/A7 |
| T105 relationship-event top 3 | relationship packet relevance, compact voice context | RETIRED under D-272-1; filtering/ranking become deterministic order and all selected events survive on OOC and combat paths | D3/D10 plus A2/A7 |
| T065 validation-history top 4 | transition validation, compact accepted exchange history | RETIRED; role filtering, chronology, current-turn exclusion, and accepted-history authority preserved | D11 plus A4/A7 |
| T107 authored arc-seed maximum two | compact grounded profile | RETIRED; source grounding, typed validation, and later ratified one-seed packet selection preserved | prompt exact diff, D14, A2/A7 |
| T041 1-2 paragraph / 150-250 word summary | concise permanent combat history | RETIRED numeric ceiling; factual coverage, ASCII, past tense, XP/aftermath, and no-markdown preserved | prompt exact diff, D15, A3/A7 |
| T042 2-4 highlights plus matching validator range | concise typed round summary | RETIRED numeric range at prompt and validator; list/type/non-empty meaning preserved | D16 plus A3/A7 |
| T014 500/200 prompt and validator maxima | bounded background-NPC/world prose | RETIRED atomically per field; room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c` hardens optional `locationUpdate` to absent/None-or-string because exact malformed compatibility would retain the forbidden shared numeric bound. Description/attitude typing, legal action/target, and canonical authority remain | D19 plus A4/A7 |
| T108 500-character unterminated witness-roster fallback | legacy-stamp compatibility | RETIRED; complete delimiter/same-record parsing replaces the fixed slice, with canonical identity resolution unchanged | D20 plus A1/A7 |
| pending-delivery narration-code maximum 24 | bounded combat recovery record | RETIRED with C15 producer slices; type/regex/attempt/order/receipt integrity preserved | D6/D21 plus A3/A7 |
| T041 singular `story paragraph` | engaging permanent summary | RETIRED as a one-paragraph ceiling; uncapped `narrative account` preserves purpose | D15 plus A3/A7 |
| T042 single-sentence-per-highlight instructions | concise dramatic highlights | RETIRED; evocative/factual typed non-empty meaning preserved | D16 plus A3/A7 |
| Areas/services slices and alignment abbreviation | 2025 main/world formatters, compact DM context | RETIRED; values and ordering preserved | D8/A4 |
| TTS truncation and legacy non-cancellable loading | `5702d54f`, avoid API cost/limit and one-blob playback | DEFERRED unchanged to #276 because the correct four-consumer repair crosses the frozen file boundary | #276; no in-wave acceptance claim |
| `truncate_dm_notes` symbol | legacy normalization wrapper, normalize old headers | RETIRED as a misleading name only; function body/call order unchanged | AST/caller sweep and exact A/B |
| top-2 episode relevance and one arc seed | D-272-1 semantic selections | PRESERVED exactly | sentinel citation and packet A/B |
| types, required fields, enums, uniqueness, UUIDs, attribution, canonical IDs, numeric mechanics | validation authority | PRESERVED | schema diff and negative controls |

### 6.1 Exact GL-1 site and lineage ledger

`Origin ref` names the originating commit subject and its recorded issue/plan. Where
the commit records no issue, that absence is explicit; the cited repository plan is
the nearest design record, and #262 is the owner-approved retirement authority. Sites
are grouped only when origin, goal, disposition, and proof are identical.

| Exact file/symbol/field | Origin ref | Original goal | Disposition/authority | Proof |
|---|---|---|---|---|
| `episode_extraction.flatten_scene(max_chars)` and tail slice | `975f8d7a` `feat(npc): T108 companion episode extraction service (Phase 1c)`; no issue in commit; `docs/design/companion-episodic-memory.md` | bound T108 scene input | RETIRED by #262; full scene | D1/A1 |
| T108 numeric instructions in `episode_extraction._SYSTEM` | `975f8d7a`, same subject/reference | concise grounded episode output | RETIRED numeric ceilings; grounding retained | prompt diff/A1 |
| T113 numeric instructions in `episode_backfill._SYSTEM` | `6af9804c` `feat(npc): W4 episodic backfill for existing games (T113)`; no issue in commit; `docs/design/2026-08-18-episodic-upgrade-backfill-plan.md` | concise compatible backfill | RETIRED numeric ceilings; grounding retained | prompt diff/A1b |
| `episode_store._text(limit)`, `_sanitize_facts` break, `_unique_capped`, `_witness_ids` break | `1736380e` `feat(npc): canonical episode ledger store (Phase 1a)`; no issue in commit; `docs/design/companion-episodic-memory.md` | bounded canonical ledger | RETIRED by #262; type/whitespace/dedupe/identity retained | D1/A1 |
| `episode_store` witness-cap health branch | `4797bfb9` `fix(npc): three bugs from independent feature-dev review`; no issue in commit; episodic design | make witness truncation loud | RETIRED because the truncation it reports retires; store-health reporting otherwise retained | D1/A1 |
| Episode schema `episodes.*.headline.maxLength`, `canonicalSummary.maxLength`, `salientFacts.maxItems`, `entityTags.maxItems`, `entityTags.items.maxLength`, `witnessIds.maxItems`, `salientFact.oneLine.maxLength`, and `actorRef.label.maxLength` | `1736380e`, same subject/reference | fail-closed bounded model-derived episode content | RETIRED relax-only with writer; coordinate/provenance limits on module/locationId/locationName/boundaryTurnId/promptVersion remain | S1/D1 |
| `profile_service.validate_profile.retention_counts` | `e5528086` `refactor(npc): preserve complete voice and sidecar text`; no issue in commit; `docs/design/2026-08-31-npc-voice-context-balance.md` | retain count-bounded T105 profile while removing text truncation | RETIRED; validation/dedupe retained | D2/A2 |
| `profile_service._unique(count)` signature and three count-bearing fallback callers | `82448d48` `refactor(npc): simplify the canonical voice flow`; no issue recorded; context-balance design | schema-valid compact fallback API | RETIRED count argument; deterministic non-empty fallback retained | D2/A2 |
| `profile_service._unique` loop count guard | `7504a717`, same subject/reference | stop fallback arrays at requested count | RETIRED with signature/callers; uniqueness/order retained | D2/A2 |
| T107 `arcSeeds` numeric instruction | `7504a717`, same subject/reference | compact grounded profile | RETIRED; grounding retained | D14/A2 |
| Sidecar profile maxima | `e5528086`; no issue recorded; context-balance design | schema-enforce count-bounded T105 profile after text-cap removal | RETIRED relax-only; type/required/unique retained | S1/D2 |
| Sidecar evidence `maxItems:256` | `7504a717`; no issue recorded; context-balance design | bound evidence storage | RETIRED with evidence prune; item schema retained | S1/D3 |
| Sidecar `appliedEventIds maxItems:256` | `b1da8f0f` `T3: value identity replaces content hashes across the NPC voice/episodic set`; no issue recorded; context-balance design | bound exact dedupe history | RETIRED cardinality only so 257+ exact IDs survive; string/type/unique identity retained | S1/D3 |
| Sidecar mood/linked-evidence maxima | `e5528086`; no issue recorded; context-balance design | retain count bounds while removing text truncation | RETIRED relax-only; item types/uniqueness retained | S1/D3 |
| Sidecar advisory-history maximum | `122556a5` `T6: persist accepted say/do/want advisory beats in the working sidecar (M7)`; no issue recorded; context-balance design | rolling accepted advisory history | RETIRED relax-only with writer; item schema retained | S1/D3 |
| Sidecar lifecycle maxima | `7504a717`; no issue recorded; context-balance design | bound profile/lifecycle context | RETIRED relax-only with writer; event schema retained | S1/D3 |
| Sidecar POV maxima | `7817009d` `feat(npc): per-NPC POV overlay derivation + retention (Phase 2)`; no issue recorded; episodic design | schema-enforce salient/pinned retention | RETIRED relax-only with writer; POV schema retained | S1/D3 |
| `relationship_store._prune_evidence` destructive 256 selection/folding | `b1da8f0f` `T3: value identity replaces content hashes across the NPC voice/episodic set`; no issue recorded; context-balance design | bound evidence while retaining exact dedupe | RETIRED content prune; exact event-id dedupe retained without cardinality bound | D3/A7 |
| `_set_working` moodTags `[:4]` | `7504a717`; same reference | compact current mood | RETIRED; order/dedupe retained | D3/A7 |
| advisory history `[-10:]` | `122556a5` `T6: persist accepted say/do/want advisory beats in the working sidecar (M7)`; no issue recorded; context-balance design | rolling recent advisory | RETIRED; value-idempotent ordering retained | D3/A7 |
| evidence `topicIds[:12]` | `7504a717`; same reference | compact evidence row | RETIRED; normalization/dedupe retained | D3/A7 |
| lifecycle `redLines`/`unresolvedObligations` count arguments and four `events[-64:]` sites | `7504a717`; same reference | bounded lifecycle/profile input | RETIRED; typed lifecycle order/idempotency retained | D3/A7 |
| POV non-pinned 40 and total 512 selections | `7817009d` `feat(npc): per-NPC POV overlay derivation + retention (Phase 2)`; no issue recorded; episodic design | preserve salient/pinned POV in bounded store | RETIRED destructive ceilings; deterministic ordering/keyed replacement retained | D3/A7 |
| `voice_contracts.STRUCTURED_PROFILE_SCHEMA` nine `maxItems` fields | `7504a717`; no issue recorded; context-balance design | bounded T107/T105 profile contract | RETIRED dead cardinalities; required/type/unique retained | schema equivalence/D2 |
| `voice_contracts.COMMON_PACKET_PROPERTIES` maxima for `relationship.recentEvents`, `scene.presentActors`, `scene.recentEvents`, and `working.moodTags` | `7504a717`; no issue recorded; context-balance design | bounded common T105 scene packet consumed by `packet_schema(mode)` | RETIRED dead cardinalities; presence/type/unique retained | schema equivalence/D3/D10 |
| `voice_contracts.COMBAT_CONTEXT_SCHEMA` five `maxItems` fields | `7504a717`; no issue recorded; context-balance design | bounded combat T105 context | RETIRED dead cardinalities; mechanics/type retained | schema equivalence/A3 |
| `voice_contracts.OUT_OF_COMBAT_CONTEXT_SCHEMA` utilities/items/currentGoals `maxItems` fields | `7504a717`; no issue recorded; context-balance design | bounded OOC T105 context | RETIRED dead cardinalities; typed fields retained | schema equivalence/A2 |
| `voice_contracts` `recentSceneWindow`, visible acts, recalled episodes, and companion-relationship evidence `maxItems` | `c1ede401` `feat(npc): share selective context with voice and dungeon master`; no issue recorded; context-balance design | bounded enriched T105 context | RETIRED dead cardinalities except runtime top-2 recall remains ratified separately | schema equivalence/D22 |
| `voice_contracts._remove_array_limits` and calls | `e5528086` `refactor(npc): preserve complete voice and sidecar text`; no issue recorded; context-balance design | neutralize source cardinalities at runtime | RETIRED after every source maximum is deleted; direct validation retained | schema equivalence/sentinel |
| `core/npc/voice_context.py::PreparedOocVoiceHandle._recall_candidates` lexical gate | `c1ede401`; context-balance design; room `ab60fc53` | avoid T112 cost on unlikely recall | RETIRED; episode-existence gate only | D22/A2 |
| T112 `_SYSTEM` past-reference presupposition | `713c1c6f` `feat(npc): grounded episodic recall service + acceptance PASS (Phase 4a)`; no issue recorded; episodic design | narrow anchor extraction behind old pre-screen | RETIRED premise; neutral typed classification | D22/A2 |
| zero-caller `conversation_utils._recall_by_npc` | `3fa75056` `feat(npc): grounded recall wiring + closed-world contract in live turn (Phase 4b)` plus `305c46db` pre-screen and `20963fee` exact-match repair; no issue recorded; episodic design | earlier recall orchestration/cost control | RETIRED dead alternate path; shared primitives retained | AST sweep/import smoke |
| zero-caller `episode_recall.recall_episodes(limit=3)` | `713c1c6f`, `0e7b1f2d` location retrieval, `20963fee`; no issue recorded; episodic design | earlier per-NPC recall API | RETIRED dead alternate path; shared primitives retained | AST sweep/import smoke |
| T096 skill/category/alias/candidate count guards | `eb2ecd52` `feat(combat): add contextual SRD rules engine`; `docs/design/agentic-combat-implementation-plan.md` | compact owned sheet/rule projection | RETIRED; canonical matching/order/dedupe retained | D4/A3/A7 |
| T096 proficiency-name `clean[:24]` slices | `7e8d1802` `refactor(combat): preserve complete agent and narration context`; agentic-combat plan | preserve full text per item while retaining count bound | RETIRED count; normalization/order retained | D4/A3/A7 |
| SRD `max_references`, selector/render slices, combat-agent actor-first break | `eb2ecd52`, modified `7e8d1802`; agentic-combat plan | compact exact SRD context | RETIRED; every exact actor-keyed match retained | D7/A3 |
| pending player-exchange `[-7:]/[-8:]` writes and T096 render | `eb2ecd52`, `6ac9ea44` state leases, `d67e4351` complete delivery, `fa1b27fe` #268; agentic-combat plan/#268 | bounded resumable clarification state | RETIRED windows; ownership/order/consume-once retained | D5/A3 |
| T097 violation/warning `[:24]` plus combat-state `len(codes)>24` | `eb2ecd52` and `1784461c` typed advisory persistence; agentic-combat plan | bound correction/recovery record | RETIRED atomically; type/regex/order/status retained | D6/D21/A3 |
| T041 paragraph/word/singular-paragraph instructions | `715732d5` `feat(multi-model): integrate provider-aware game runtime`; no linked issue/plan recorded | concise permanent combat record | RETIRED only output ceilings; factual/ASCII/aftermath retained | D15/A3 |
| T042 validator range and prose single-sentence instruction | `715732d5` `feat(multi-model): integrate provider-aware game runtime`; no linked issue recorded | concise typed highlights | RETIRED; typed non-empty facts retained | D16/A3 |
| T042 JSON-example numeric/single-sentence instruction | `2c472143` `Fix all import paths across reorganized codebase`; no linked issue recorded | document expected structured highlights | RETIRED output ceilings; field shape retained | D16/A3 |
| T014 500/200 prompt+validator pair and optional type ambiguity | `2c472143` import reorg over legacy movement logic; no linked issue/plan recorded; #277 + room `ab60fc53` | bound world prose | RETIRED with absent/None-or-string hardening; authority/targets retained | D19/A4 |
| T108 unterminated-roster `+500` fallback | `411e9c45` `feat(npc): wire per-location episode capture into live play (Phase 1d)`; no issue recorded; episodic design | bound malformed legacy stamp parsing | RETIRED numeric end; structural delimiter/newline/EOM retained | D20/A1 |
| T065 history `limit=4`, break, padding | `715732d5`; no linked issue/plan recorded; travel transition architecture | compact validator history | RETIRED; roles/chronology/current-turn exclusion retained | D11/A4 |
| services `[:3]` | `329496ba` `Fix module transition system and enhance hub details`; no linked issue/plan recorded | compact hub context | RETIRED; authoritative order retained | D8/A4 |
| module areas `[:3]` | `1830570b` `Fix critical combat resume hang bug`; no linked issue recorded; module lifecycle architecture | compact travel module list | RETIRED; full IDs/names retained | D8/A4 |
| shared-context player/NPC alignment `[:2]` pair | `2c472143` `Fix all import paths across reorganized codebase`; no linked issue/plan recorded | compact character display | RETIRED; complete canonical alignment retained | D8/A4 |
| combat-context player/NPC alignment `[:2]` pair | `4cd2ec12` `Implement combat conversation compression and character formatting`; no linked issue/plan recorded | compact combat character display | RETIRED; complete canonical alignment retained | D8/A3 |
| `truncate_dm_notes` definition and first caller | `932aceb0` `Complete enhanced logging migration for remaining core files`; no linked issue recorded | normalize legacy DM-note headers | RETIRED name only; body/order unchanged | AST/caller A/B |
| later `truncate_dm_notes` callers | `1f25546c` `feat(startup): #214 D - off-thread welcome lifecycle; remove the 120s kickoff abort` and `1830570b` `Fix critical combat resume hang bug`; #214/no linked issue respectively | reuse legacy DM-note normalization on startup/resume | RETIRED name only; call order unchanged | AST/caller A/B |
| 12 tracked acceptance/runtime artifacts from `cf5a89b2` `T8 fixes: DEFECT-1 first-batch self-cancel race + DEFECT-2 save-restore fail-stop`; no issue recorded; acceptance residue | incidental writes during T8 validation | RETIRED from candidate: 5 paths restored to main, 7 main-absent paths deleted; no runtime behavior intended | C0 byte/absence proof |
| `core/headless/bootstrap.prepare_game_dir` private-runtime ignore branch | `0993430e` `feat(npc): wire NPC sidecar into save/restore + headless-copy integrity`; no issue recorded; episodic design | avoid copying runtime sidecars/locks present in the source tree | RETIRED under owner room `83c05775` after source residue cleanup; main direct-copy behavior restored | C0 exact diff + headless prepare smoke |
| stale recall claims in three enumerated architecture docs | their respective voice/episodic documentation commits; current authority this plan + room `ab60fc53` | explain old lexical/capture flow | RETIRED/replaced with C51-C54 and T108/T113 truth | C5 text/visual review |

Any deletion not present in this table is a blocking UNKNOWN until added with origin,
goal, disposition, and proof.

## 7. Development checks (not gameplay acceptance)

All checks are local/ignored and do not modify tracked tests.

- D1: episode store accepts and returns strings, 9+ facts, 13+ tags, 17+ witnesses,
  preserving exact values/order; invalid type/UUID/kind still rejects or sanitizes as
  before; repeated commit stays idempotent.
- D2: T107 validation and fallback preserve arrays above 3/5/2 with uniqueness and
  required-goal guarantees; four known goals contain no `unknown`, while an empty
  known set produces only that honest sentinel. The packet sees the complete profile.
  Under D-262-T107, completed-invalid persists a playable fallback, the next eligible
  beat retries fresh, and a later valid result replaces it without duplicate calls or
  blocking T105.
- D3: relationship store preserves 257+ evidence rows, 513+ POV rows, 65+ lifecycle
  events, and 11+ advisory beats. Independently cross every nested old boundary: 5+
  working `moodTags`, 13+ `topicIds` on one evidence row, 6+ `redLines`, 6+
  `unresolvedObligations`, and 9+ `linkedEvidenceIds` on one POV row. Prove each value
  through writer, schema, disk, and every actual downstream reader; if C0 confirms a
  field has no reader, record that fact rather than inventing consumption. Existing
  aggregate counts and applied-event dedupe remain stable.
- D4: independently cross all four capability losses: 25+ skills reach T096; 25+
  proficiency names within one category reach T096; 13+ proficiency categories reach
  T096; and an authentic alias at position 13+ drives its exact owned-capability/SRD
  match into T096 while at least eight higher-ranked genuine matches coexist. Also
  prove 9+ genuine owned-capability matches for one actor all reach
  `capabilityCandidates`, 25+ feats reach T096, and 25+ species traits reach T096.
  Grade all paths independently. Ordinary sheets remain recursively identical.
- D5: nine or more real-shaped pending exchanges survive append/request/write/render
  in order; duplicate current answer remains consume-once.
- D6: 25+ T097 violations/warnings persist completely; narration receipt behavior is
  unchanged.
- D7: two actors with four distinct exact rules each receive all actor-keyed matches;
  ambiguous names still fail closed and unmatched prose adds nothing.
- D8: four+ module areas/services and full alignments render completely; empty/missing
  values retain prior fallbacks.
- D10: a relationship packet with four or more genuine relevant evidence events
  preserves all events and deterministic ranking on both OOC and combat T105 paths.
- D11: five or more accepted historical player/assistant messages reach T065 in
  chronological order while the current turn remains excluded; short/empty history is
  recursively identical and no padding record is invented.
- D14: the T107 prompt has no numeric arc-seed maximum, keeps every grounding rule,
  and a real-shaped valid response with 3+ arc seeds survives validation/persistence;
  the later D-272-1 one-seed packet selection remains exactly unchanged.
- D15: T041 prompt exact diff removes only paragraph/word counts; independently prove
  a 251+ word valid summary and a 3+ paragraph valid summary persist completely as the
  permanent encounter summary.
- D16: T042 prompt/validator accept 5+ typed non-empty highlights and preserve them;
  independently accept one typed non-empty highlight; wrong type/empty required meaning
  still fails exactly as the retained contract says. Independently preserve a typed
  non-empty highlight containing 2+ sentences through validator, storage, and render.
- D19: T014 accepts typed `newDescription` above 500 characters and `locationUpdate`
  above 200 independently, then applies the complete value through the existing legal
  action/canonical target path. Missing/wrong-type description, invalid action, and
  invalid location controls retain their prior rejection. Under room ruling
  `ab60fc53-9e8d-4211-90de-54ea55218c5c`,
  absent/None location update stays optional, strings remain accepted without a length
  ceiling, and truthy/falsy non-string values reject before mutation.
- D20: an engine-authored legacy roster stamp with no ` Party stats:` delimiter and a
  resolvable companion token beginning after character 500 preserves that companion
  through witness parsing and canonical ID resolution. The fallback stops at newline
  or end-of-message. A delimiter-terminated roster above 500, ordinary short roster,
  and no-companion record are no-change controls; following-line prose and malformed
  names do not become identities merely because the cutoff is gone.
- D21: a pending delivery with 25+ valid narration codes passes C15 through the
  downstream combat-state validator and round-trips intact. Non-list, non-string,
  malformed-code, bad-attempt-order, and invalid-status controls still reject.
- D22: with at least one canonical episode for a present actor, both a short concrete
  player reference whose distinguishing token is under three characters and a
  lexically divergent paraphrase reach the existing T112 call. Concrete anchors feed
  the unchanged strict top-2 typed selector. A genuine present-tense action deliberately
  sharing a stored episode term receives empty anchors, injects no recalled episode,
  and proceeds through normal T105 dispatch without retrospective narration. With no
  episodes, T112 is not called.
  Provider failure retains the existing loud one-beat degradation/fresh-next-beat
  behavior. AST/import/caller sweeps prove `_recall_by_npc` and high-level
  `recall_episodes` have zero consumers before deletion, while `parse_anchors`,
  `select_episodes`, `_tokens`, and the live selection path remain available.
- S1: validate every authentic episode ledger and NPC sidecar with baseline and
  candidate schemas; baseline-valid/candidate-invalid target zero. Then round-trip a
  copied sidecar with above-old-bound values and diff every non-empty-to-empty path.
- Run `py_compile` on every changed Python file, TypeScript build, Vite build, and the
  focused import smoke.
- Run the NPC suite before/after against `0214cbdf`; accepted target is the same 27
  documented stale failures or fewer, with no new failure.

## 8. Mandatory sentinel and consumer evidence

The No-Limits reviewer and execution gate paste raw scans, not a prose assertion:

```text
git diff --unified=0 0214cbdf -- <all touched files>
git diff --unified=0 0214cbdf -- <all touched files> | grep -nE '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat|\[:[0-9]+\]'
grep -nE '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat|\[:[0-9]+\]' <every touched Python/JSON-schema file>
git diff --unified=0 0214cbdf -- <all touched files> | grep -nE 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback'
grep -nE 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback' <every touched Python/JSON-schema file>
```

Every remaining hit gets a file:line disposition. The only model-content selections
that may remain without a new owner ruling are D-272-1 top-2 recall and one arc seed.
TTS is dispositioned whole to #276 with D-262-TTS authority; this diff leaves it
unchanged. The semantic scan also searches prompt prose (`<=`, `at most`,
`first/last/top N`, `bounded`) so prompt-only caps cannot evade the mandatory regex.

Consumer/compat evidence includes symbol-family sweeps for every changed helper,
validator, schema, pending exchange, SRD payload, world formatter, TTS endpoint, legacy
template client, and React client. No cap is removed only at a producer while its
writer, schema, renderer, or downstream consumer retains the same loss.

## 9. Native-Windows real-OpenAI acceptance

One operation at a time, fresh copied fixtures, no synthetic/monkeypatched content,
no state edits to manufacture model outputs, and honest PASSED/FAILED/BLOCKED/
NOT-REACHED verdicts. Captures include actual callsite/model, full request/response,
latency, player transcript, on-disk before/after, and quiescence receipt.

### A1 - Long-location episode and early recall

Play a real official-module location long enough that the authentic flattened segment
exceeds 16,000 characters and contains distinguishable grounded facts near both ends.
Leave the location normally so T108 runs. Prove its captured request includes both
anchors and equals the complete flattened source. Inspect the episode ledger. Later ask
the witnessed companion about the early event through ordinary play; the response must
ground recall in that early fact or honestly lack an extracted fact. Passing the cap
boundary requires the early fact to have survived T108/store/schema; model choosing not
to mention it is reported separately, never papered over.

For each retired T108 output boundary (headline >100, summary >600, 13+ tags, 9+
facts, oneLine >120, and 17+ witnesses), record PASSED only when an authentic model
response crosses it and the exact value persists; otherwise record that boundary
NOT-REACHED.

Separately reach an authentic engine-authored legacy `Party NPCs:` stamp with no
` Party stats:` delimiter and a resolvable companion token beginning after character
500 where possible. PASSED requires that companion to appear as a canonical witness
and following-line prose to remain outside the roster; otherwise record NOT-REACHED.
A delimiter-terminated roster above 500 and a normal short roster are no-change controls.

### A1b - Authentic existing-game T113 backfill

Load a copied authentic pre-episode save through the ordinary one-time episodic-upgrade
seam and capture the real T113 request/response. Prove the full source passage reaches
T113 and the committed episode/POV rows preserve its accepted output. Grade the same
headline/summary/tag/fact/oneLine/witness boundaries individually as PASSED or NOT-
REACHED. The copied save is not edited to manufacture values; D1/S1 remain development
and schema evidence, never substitutes for a boundary the real T113 response did not
reach.

### A2 - Rich profile and sidecar persistence

Through real recruitment/profile construction, capture a T107 response naturally
exceeding at least one old 3/5/2 profile boundary. If no authentic response does, this
sub-boundary is NOT-REACHED, not passed. When reached, every returned unique value must
persist and reach the next T105 packet. Exercise a later lifecycle/evidence write and
prove zero non-empty-to-empty transitions. Existing sidecar load is the negative control.
Under D-262-T107, a completed-invalid T107 branch is PASSED only if authentically
reached through the real provider path; otherwise it is NOT-REACHED in acceptance and
deterministic evidence cannot be relabeled live. When reached, gameplay uses the
fallback for that beat, telemetry is loud, and the next eligible beat makes a fresh
real T107 call whose valid result replaces the fallback.

Grade an authentic T107 response with 3+ source-grounded arc seeds separately. PASSED
requires every seed to persist in the profile; a later T105 packet may still select the
single ratified arc seed. If the real response stays at two or fewer, report NOT-
REACHED rather than treating the prompt diff as live proof.

On both an OOC companion beat and a typed-combat companion beat, capture T105 with four
or more genuine relevant relationship events for one actor and prove every event is
present in deterministic ranking order. Each path receives its own PASSED or NOT-
REACHED verdict.

Under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c`, use ordinary play with a companion who has grounded episodes to
exercise three independent T112 polarities: a short concrete reference whose key token
is shorter than three characters, a lexically divergent paraphrase of a stored event,
and an ordinary present-tense action. Capture the real T112 request/response each time.
The two references must be semantically evaluated rather than code-skipped; the
ordinary action must deliberately overlap a stored episode term, return honest empty
anchors, inject no recalled episode, proceed through normal T105, and produce no
retrospective narration. A
no-episode companion is the negative control and must not trigger T112. These rows are
PASSED only from authentic traffic; otherwise each is NOT-REACHED.

### A3 - Multi-actor combat context

Enter a real typed combat with at least two actors in the adjudicated window and a
player action/scene that produces distinct exact SRD matches for more than three
actor-rule pairs. Capture T096 and prove every matched actor receives its reference,
capabilities are complete, and no actor receives a rule that was not matched. Continue
through one player-roll pause to prove the full clarification chain and immutable voice
envelope replay. Where authentic sheets cross them, independently capture 25+ feats,
25+ species traits, and 9+ owned-capability candidates for one actor. Each unreached
boundary is NOT-REACHED. Where the ordinary shared combat-summary seams are reached,
grade T042 one-highlight and 5+-highlight outputs independently, and grade T041 251+
words and 3+ paragraphs independently. Also grade a T042 highlight containing 2+
sentences independently through stored/rendered output. A typed-combat call that never reaches one of
those shared seams records it NOT-REACHED; no legacy-only fixture is required or fixed
by this ship gate. Narration/HP/action authority remain truthful.

### A4 - World context

Use legally installed official modules and an authentic hub exposing more than three
areas/services where reachable. Capture the DM request and prove all values plus full
alignment strings are present. If the authentic content lacks a >3 boundary, report
that exact arm NOT-REACHED while the deterministic consumer proof remains development
evidence only.

During an authentic transition-validation turn with five or more prior accepted
player/assistant history messages, capture T065 and prove the complete filtered history
arrives in chronological order with the current turn excluded. If ordinary play never
reaches that boundary, record it NOT-REACHED and keep D11 as development evidence.

Reach real T014 background-NPC status/location updates and independently grade an
accepted `newDescription` above 500 characters and `locationUpdate` above 200. PASSED
requires the complete value to persist through the canonical world mutation; otherwise
each boundary is NOT-REACHED. Normal short updates and invalid target/action are the
negative controls.

### A5 - TTS explicitly outside this wave

No TTS acceptance verdict is produced by #262. The unchanged baseline is recorded only
as scope proof; #276 owns the later complete producer-and-four-consumer implementation
and its native browser acceptance.

### A6 - Integrated regression

Run a fresh non-combat voice beat and a full typed combat beat. Inspect player-visible
transcript for second-person address, no hidden facts, no invented player action/roll,
grounded companion voice, exact committed mechanics, prompt acknowledgment, and no
technical limit/retry text. Run the NPC suite A/B and global scans. Any player-facing
quality regression is FAILED even when files validate.

### A7 - Per-boundary live-verdict matrix

Development checks D3-D6 prove deterministic preservation but are never relabeled as
live acceptance. The final report must record each row below independently as PASSED
only when authentic product traffic crosses the old boundary and disk/capture evidence
shows every value survives; otherwise it records NOT-REACHED with the development
evidence path. One reached row cannot stand in for another.

| Changed family | Authentic live boundary |
|---|---|
| relationship evidence | 257 or more genuine evidence rows survive a later product write |
| relationship POV | 513 or more genuine POV rows survive a later product write |
| relationship lifecycle | 65 or more genuine lifecycle rows survive a later product write |
| relationship advisory | 11 or more genuine advisory rows survive a later product write |
| working mood tags | 5 or more genuine tags survive write, schema validation, disk, and every actual reader |
| evidence topic IDs | 13 or more genuine IDs on one evidence row survive write, schema validation, disk, and every actual reader |
| lifecycle red lines | 6 or more genuine values survive write, schema validation, disk, and every actual reader |
| lifecycle unresolved obligations | 6 or more genuine values survive write, schema validation, disk, and every actual reader |
| POV linked evidence IDs | 9 or more genuine IDs on one POV row survive write, schema validation, disk, and every actual reader |
| T096 skills | 25 or more real owned skills reach the captured request |
| T096 proficiency names | 25 or more real names within one proficiency category reach the captured request |
| T096 proficiency categories | 13 or more real categories reach the captured request |
| T096 capability aliases | an authentic alias at position 13 or later drives its exact owned-capability/SRD match into the captured request |
| T096 owned-capability candidates | 9 or more genuine matches for one actor all reach `capabilityCandidates`; the alias row coexists with at least eight higher-ranked matches |
| T096 feats | 25 or more real owned feat names reach the captured request |
| T096 species traits | 25 or more real owned species-trait names reach the captured request |
| T107 authored arc seeds | 3 or more source-grounded seeds persist from one authentic response |
| T105 OOC relationship events | 4 or more genuine relevant events for one actor all reach the OOC packet |
| T105 combat relationship events | 4 or more genuine relevant events for one actor all reach the combat packet |
| T112 short/divergent recall | a real short-token reference and a lexically divergent paraphrase each reach T112 and receive its semantic disposition rather than a code lexical skip |
| T112 ordinary/no-episode controls | an ordinary action deliberately overlapping a stored episode term reaches T112, yields empty anchors/no injected recall, proceeds through normal T105, and produces no retrospective narration; no episodes means no T112 call |
| T065 validation history | 5 or more genuine filtered historical messages reach the request in order, excluding the current turn |
| T042 lower range | one authentic typed non-empty highlight is accepted and preserved |
| T042 upper range | 5 or more authentic typed highlights are accepted and preserved |
| T042 highlight sentence shape | one authentic highlight containing 2+ sentences survives validation, storage, and render |
| T041 word ceiling | one authentic valid summary of 251+ words persists completely |
| T041 paragraph ceiling | one authentic valid summary of 3+ paragraphs persists completely |
| T014 NPC description | one authentic accepted value above 500 characters persists completely |
| T014 location update | one authentic accepted value above 200 characters persists completely |
| T108 legacy witness roster | one authentic unterminated roster has a resolvable companion token beginning after character 500; it becomes a canonical witness while following-line prose remains excluded |
| pending clarification chain | 9 or more genuine player exchanges persist/render in order |
| T097 correction codes | 25 or more genuine codes survive producer, committed narration receipt, downstream combat-state validation, and replay |

A1 covers the T108 witness roster; A2 is the natural reachability path for every
profile/relationship/T105 row; A3 is the natural path for typed capability,
clarification, T041/T042, and T097 rows; A4 covers T065 and T014. If ordinary play does not cross a row,
the required verdict is NOT-REACHED, not a scenario manufactured by editing state. If
C0 proves an advisory or nested field has no downstream reader, its live row still
grades persistence PASSED/NOT-REACHED and separately records `NO-READER-CONFIRMED`;
disk retention may not be mislabeled as downstream model-context delivery.

## 10. Review protocol

This is FULL: it changes play-path schemas, deletes/replaces working code, touches
provider/model surfaces, and exceeds the large-change file
threshold. Reviewers are blind and receive the same frozen SHA:

1. Architecture Custodian - AP-1..AP-7, mechanism/call-path budget, wrong boundary,
   schema/profile architecture, and no bypassed producer/consumer.
2. Fail-Forward DA - B1/B2 verbatim, FS-1, T105/T107 completed-invalid policy,
   T014/T105/T107 completed-invalid handling, no busy refusal, and every terminal state.
3. Acceptance DA - real boundary reachability, native artifacts, gate polarity, and
   NOT-REACHED discipline.
4. Consumer/Compat DA - schema relax-only authentic-file scan, every helper/caller,
   pending-turn, episode/profile/relationship, combat, and world-action compatibility.
5. Legacy-Contract DA - full GL-1 table, git-blame origins, behavior-preserving A/B,
   and no loss hidden by deletion.
6. Player-Experience DA - transcript truth, pacing, agency, world consequences, and recall.
7. Leanness DA - challenge T107 provenance/retry and any new helper; no new store,
   mode, cache, or proactive scene-chunk mechanism.
8. No-Limits Sentinel - mandatory raw diff+touched-file scan plus semantic prompt scan;
   every hit dispositioned.
9. Single-Path Sentinel - mandatory raw scan; no legacy/new or single/multipart runtime
   fork implementing the same behavior twice.
10. Schema-Freeze and Platform/Provider reviewers - relax-only proof, native Windows,
    real OpenAI calls, ASCII, no secrets/config/tracked tests.
11. Pre-merge large-change Custodian sweep against every touched Part 2 page.

Convergence requires one clean same-SHA pass. The controller alone edits the plan
between rounds. Reviewer convergence authorizes nothing; Claude review and owner gates
still control execution.

## 11. Prohibited shortcuts

- No larger replacement cap, `max_tokens`, tail/head slice, silent summary, or
  provider-error-as-success.
- No new persistence store, migration sweep, feature flag, legacy runtime, or hidden
  rollout path.
- No prose/hash authority, model-output parsing outside existing typed schemas, or
  code-authored semantic memory.
- No tracked test edits, `git add -f`, config changes, synthetic acceptance, or model
  substitution.
- No broad refactor or opportunistic repair of out-of-scope ID/cache/retry mechanics.
- No partial TTS repair in this wave; #276 owns the complete four-consumer path.

## 12. Tracked follow-ups

- GitHub #276 (`#262-b`) owns any newly discovered non-legacy gameplay model/content
  cap whose owner is outside the frozen 72-file voice bundle. It has no implementation
  authority from this plan. It also owns C23/TTS whole because the correct repair
  requires the two out-of-bundle React consumers; D-262-TTS records the direction but
  no partial server/legacy repair lands here.
- GitHub #191 typed-combat retirement owns the legacy-only T040/T046/T045/compression
  findings: T040 two-stage 12-message windows plus source compression; T046 six-message
  windows in `combat_manager.py` and `initiative_tracker_ai.py`; T045 eight-word prompt,
  keep-three/AP-7 DM-note pruning, T017 25-word compression output/validator, and
  `strip_combat_setup_messages` code-authored replacement. They are not repaired,
  accepted, or partially edited here; the retired A3b legacy arm is NOT-REACHED for
  this ship gate by owner rulings `16269e31-54c2-4f07-a87b-d2298b22ceaa` and
  `df3ebe6c-b1e4-450d-bf01-b559e69f464d`.
- GitHub #277 records the pre-existing T014 optional `locationUpdate` type-contract
  gap. Room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c` folds its minimal coupled
  hardening into the cap removal; #277 closes on the same proof rather than becoming a
  second implementation.

## 13. Review resolution ledger

| Finding | Disposition in this revision |
|---|---|
| R1 - the original server-owned multi-call TTS design could continue issuing calls after client cancellation | RESOLVED architecturally in section 4.3 and ratified by room ruling `91d403a3-0580-443e-818c-3dd5fa455f92`, then deferred whole to #276 by the later file-scope ruling. No TTS code lands here. |
| R2 - C0 could silently expand the implementation scope | RESOLVED by C0's hard stop: any changed inventory, call graph, corpus, client contract, classification, or touched-file set requires a plan/GL-1/ledger/allowlist amendment and a new full same-SHA review. |
| R3 - T107 completed-invalid fallback becomes permanently authoritative | RESOLVED by the section 4.4 design and ratified under Fork-3/B10 by room ruling `e01d5df3-0849-48c0-8ec5-40c90244abad`. Fallback provenance permits play now and a fresh next-eligible-beat retry without treating failure as success. |
| R4 - fallback injects `unknown` beside known goals or values | RESOLVED in C6-C7 and D2. The sentinel is legal only when the corresponding known-value list is empty. |
| R5 - episode backfill was mislabeled T111 and lacked an authentic upgrade-path acceptance | RESOLVED. The callsite is T113 throughout, and A1b requires the real one-time upgrade plus a real T113 capture and separate old-boundary verdicts. |
| R6 - a later-part provider-failure acceptance could be manufactured | RESOLVED. A5 calls it live evidence only if authentically reached; deterministic injection is development evidence and the live arm is otherwise NOT-REACHED. |
| R7 - the dual-purpose TTS endpoint lacked a frozen discriminator and could break one of four current blob callers | RESOLVED in the ratified #276 direction: missing/`speech` remains backward-compatible `audio/mpeg`; `partition` has an exact JSON contract; both narration callers opt in and both preview callers remain default. This plan neither implements nor accepts it. |
| R8 - live acceptance could silently omit above-old-boundary verdicts covered only by development checks D3-D6 | RESOLVED by A7. Every relationship, capability, clarification, and T097 boundary gets its own authentic PASSED or honest NOT-REACHED verdict. |
| R9 - A7 used `more than 25/13` even though the old capability caps were 24/12 | RESOLVED. The authentic thresholds are 25+ and 13+, matching D4 and the retired slices. |
| R10 - aggregate relationship-row counts did not cross nested array caps | RESOLVED in D3 and A7. Mood tags, evidence topics, red lines, obligations, and linked evidence each receive an independent deterministic proof and authentic PASSED/NOT-REACHED verdict, with dead readers identified honestly. |
| R11 - D4/A7 combined four independent capability losses and used the wrong alias oracle | RESOLVED. Skills, names within one proficiency category, proficiency categories, and 13th+ alias matching now receive separate proofs and live verdicts; aliases prove the resulting exact SRD match rather than raw alias packet output. |
| R12 - complete-call-path review found an unplanned per-actor `max_candidates=8` loss before T096 | RESOLVED in R7, C2, GL-1, D4, and A7. The cap and final slice retire while matching/order/dedupe/ownership remain, and authentic 9+ matching is graded independently. |
| R13 - semantic scan found T096 feat/species top 24, T105 relationship-event top 3, T065 history top 4, and T046 history top 6 at two layers | SPLIT by owner scope. In-scope C32-C33/R8 have consumer-complete slices, GL-1, D4/D10-D11, and live verdicts. Legacy-only T046 is assigned whole to #191; no ineffective producer-only edit lands here. |
| R14 - exhaustive scan found T040 history 12, T107 prompt arc seeds 2, T041 summary counts, T042 highlight numeric range, T045 eight-word cadence, and legacy T045 keep-three/AP-7 pruning | SPLIT by owner scope. In-scope C38-C41 have exact scope, GL-1, D14-D16, and live verdicts. Legacy-only T040/T045 paths are assigned whole to #191. |
| R15 - T040 source compression remained; T042 lacked the changed one-highlight polarity; T041 live oracle falsely treated two paragraphs as above-boundary | SPLIT/RESOLVED. T040 source compression is #191 retirement work. D16/A3/A7 independently grade one and 5+ highlights. T041 independently requires 251+ words and 3+ paragraphs. |
| R16 - T017 25-word prompt/validator and code-authored combat-setup replacement were outside the plan | ASSIGNED to #191 because their current production consumers are the retirement-bound legacy combat pipeline; no legacy-only repair lands in #262. |
| R17 - unbounded repository scanning made the ship-gate inventory grow outside its merge surface | RESOLVED by owner rulings `16269e31-54c2-4f07-a87b-d2298b22ceaa` and `df3ebe6c-b1e4-450d-bf01-b559e69f464d`: this plan is frozen to the bundle plus its 72 touched files; later outside-bundle non-legacy findings route to #276. |
| R18 - the frozen 72-file scan found T014 500/200 prompt-validator pairs, T108 500-character witness fallback, downstream C15 code-count rejection, T041 singular paragraph, and T042 sentence-shape instructions | RESOLVED as C44-C50 with producer/consumer-complete slices, GL-1, D19-D21 plus corrected D15-D16, and independent authentic A1/A3/A4/A7 verdicts. |
| R19 - the TTS producer/legacy files were in the 72-file set but both mandatory React consumers were outside it | RESOLVED by moving C23/C4 whole to #276. D-262-TTS remains the ratified direction, but this wave performs no partial server/client edit and claims no TTS acceptance. |
| R20 - C0 count was stale, T014 overstated current type rejection, C46 could false-pass on the normal delimiter path, and C49-C50 lacked a multi-sentence oracle | RESOLVED. C0 freezes 119 rows; room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c` authorizes coupled optional-string hardening with C44-C45; C46/D20/A1/A7 require an unterminated stamp with a post-500 resolvable token and structural line end; D16/A3/A7 independently grade a 2+-sentence highlight. |
| R21 - active recall used raw-player/stored-prose token overlap before T112, while two zero-caller helpers retained duplicate lexical/top-three paths | RESOLVED under room ruling `ab60fc53-9e8d-4211-90de-54ea55218c5c` in C51-C53, section 4.5, C1/C3, GL-1, D22, and A2/A7. Code gates only on typed episode existence, T112 owns meaning, the ratified strict top-2 active selection remains, and dead alternate helpers are deleted unconditionally after zero-caller proof. |
| R22 - removing the lexical screen exposed T112's false presupposition that every input references past shared history, and the plan overstated active exact-match cardinality | RESOLVED in C54/section 4.5/GL-1/D22/A2/A7. T112 neutrally distinguishes past reference from present/future action, the overlapping-term negative control forbids fabricated recall, and the active selector is documented and preserved as strict top-2 with exact typed values affecting score only. |
| R23 - the 72-file merge unit contained undispositioned runtime/player-state artifacts from acceptance | RESOLVED in diagnosis, Part 2 pages 5/9/12, C0, and the exact GL-1 site ledger. Five main-tracked module backups restore byte-for-byte; seven main-absent locks/effects/epoch/quest paths are deleted; owner room `83c05775-df69-44f1-8563-a7487e835a15` also retires the compensating headless bootstrap ignore; no player state ships. |
| R24 - C5 did not enumerate stale T112 architecture docs and the visual mislabeled capture as T112/T113 | RESOLVED by enumerating `companion-memory.md`, `npc-voice-ooc.md`, and `npc-voice-flow-map.html`; C5 replaces exact stale claims with C51-C54 and T108/T113 truth and removes the stale-visual disclaimer. |

## 14. Owner gates and stopping conditions

- D-262-R4: ratify the existing top-3 per-turn DM memory selection, or remove it.
- D-262-R5: ratify the four-companion OOC selection, or remove it. Recommendation:
  remove.
- D-262-T014: CLOSED by room ruling
  `ab60fc53-9e8d-4211-90de-54ea55218c5c`. The minimal coupled optional-string contract
  lands with C44-C45: absent/None or string is valid; any other present type rejects
  before mutation.
- D-262-Recall: CLOSED by room ruling
  `ab60fc53-9e8d-4211-90de-54ea55218c5c`. Remove the active raw-player/stored-prose
  lexical pre-screen and both zero-caller high-level duplicates. Episode existence is
  the sole code gate; neutral T112 decides recall and can return empty anchors. The
  accepted cost is increased T112 calls on ordinary turns when present actors have
  episodes; no AP-7 cost optimization remains.
- D-262-TTS: CLOSED by room ruling `91d403a3-0580-443e-818c-3dd5fa455f92`.
  Lossless provider-capacity partition, complete ordered playback, and client-owned
  cancellation are the ratified direction, now deferred whole to #276 by the later
  72-file scope rulings; they do not land in this wave.
- D-262-T107: CLOSED by room ruling `e01d5df3-0849-48c0-8ec5-40c90244abad`.
  The optional provenance field and next-eligible-beat fresh retry land in-wave under
  Fork-3/B10, with no new store and no schema-version bump.
- If a real full T108 input exceeds the provider/model context and fails, stop with
  evidence; do not invent a chunk threshold or drop content.
- If any authentic baseline-valid sidecar becomes candidate-invalid, stop and return
  with the exact record; do not migrate or rewrite under this plan.
- If a supposedly non-content retained bound inside the frozen 72 files is proven to
  reach model input/output or injected context, reclassify it CRITICAL and amend/review
  this plan before implementation. Outside-bundle findings route to #276; legacy-only
  findings route to #191 retirement.

Implementation and acceptance are not authorized by this document.
