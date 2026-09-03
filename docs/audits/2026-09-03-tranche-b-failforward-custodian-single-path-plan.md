# Tranche B Fail-Forward, Custodian, and Single-Path Plan

Status: **G1-G11 IMPLEMENTED; C11/C12 ACCEPTANCE CORRECTION UNDER PART 3 REVIEW**

Date: 2026-09-03

Branch: `integration/npc-voice-episodic`

Pinned C11/C12 baseline: `2fe0b6f781cd91405d9f036acf30c8da52b274d0`

The approved non-gated Tranche B C0-C10 commits advanced both the local and remote branch from
`6fc0f8f5` to `03a8a9ab`. G1-G11 and their two reviewed corrections then advanced the isolated
local branch to `2fe0b6f7`; push remains blocked on the final acceptance gate. C11/C12 are grounded
in that actual acceptance baseline. Unrelated untracked runtime/plan artifacts remain untouched.

Authority: live GitHub issue #193 v2.9, fetched 2026-09-03 (updated
`2026-09-03T07:07:51Z`). Part 1 was read in full,
the relevant Part 2 system pages and architecture schematics were read before this plan,
Part 3 governs review, Part 4 governs the controller/reviewer rhythm and simplifier pass,
and Part 5 supplies the cited ratified rulings. If this document conflicts with live #193,
#193 controls.

## 1. Goal and player contract

Close the nine remaining ship-gate slices without adding parallel state, hidden fallbacks,
or refusal paths:

1. Load restores the requested save and never uses metadata hashes as authority.
2. Replayed save and relationship operations converge exactly once by value identity.
3. Voice work either completes, structurally reissues, or degrades for one beat with a loud,
   actor-scoped record; no future or whole batch can disappear silently.
4. Each concept has one canonical runtime representation and one renderer.
5. The first prompt is not held behind companion-memory backfill.
6. Capture fingerprinting cannot freeze play or spawn Git from a gameplay worker.
7. Reset removes live encounter state after preserving it in the durable backup.
8. Child-provider calls are visible in the same parseable acceptance record as parent calls.
9. The three prohibited branch-local design-doctrine files are removed.

The plan changes no mechanics, NPC judgment, player choice, voice prose, combat ordering, or
provider selection. It preserves `match_owned_capabilities`: current code imports and invokes
it from `core/ai/combat_agent.py`; the ledger's zero-caller claim is stale and deleting it
would remove a live contextual capability projection.

## 2. Scope boundary

### In scope

S1 through S9 below: B1-B6, B8-B9, B13-B19, B23, and B25 from the ship-gate ledger.

### Owner-ratified amendment scope

Part 5 D-VS-1..11 ratifies G1-G11 in section 5. D-VS-4 grants the temporary T045 waiver;
#282 owns retirement. D-VS-7 is explicitly interim and #284 owns redesign. D-VS-10 accepts the
current entrant list interim and #285 owns later review. No decision in this scope remains open;
implementation still waits for targeted Part 3 same-SHA convergence.

### Out of scope, tracked elsewhere

- B20 / #279: encounter creation classifies Captain Gorvek on the party side.
- B21: agentic down/death scene, queued by the owner.
- B22: minor narration overreach, retained as a prompt-quality observation.
- B24: long compressor wait has no changing player progress; retained as a pacing/liveness
  observation and not silently folded into provider or startup work here.
- #276: caps in untouched files outside the #262 bundle.
- Tranche C leanness debt.
- No T045-only repair; its runtime is governed by the owner decision D-TB-2.

## 3. Current-state proof and disposition

### 3.1 Specification pins

| Pin | Frozen value |
|---|---|
| Dynamic branch revision | C11/C12 baseline `2fe0b6f781cd91405d9f036acf30c8da52b274d0`; remote pre-gated tip `03a8a9abe631fb0d763168981e416754bc2ad44d`; `origin/main` `52990aa08f1108cdc5660c31fb862ab342871944`; main is an ancestor |
| Policy | Live #193 v2.9, updated `2026-09-03T07:07:51Z` |
| Save/Load/Reset | Part 2 page 9 plus `docs/architecture/save-load-reset-lifecycle.md` |
| NPC memory and voice | Part 2 page 7 (NPC systems) plus `companion-memory.md`, `npc-voice-ooc.md`, `npc-voice-combat.md` |
| Startup/provider | Part 2 pages 10-11 plus `startup-boot.md`, `provider-routing.md` |
| Browser/headless | Part 2 pages 10 and 13 plus `web-headless-surfaces.md` |
| Failure classes | B1/B2; Part 5 Fork-3; open D-1/D-6/D-7/D-8 are not presumed closed |
| Commit models | Save/restore: multi-file with pre-restore backup/rollback; sidecars: locked reread-copy-validate-write; Reset: durable backup before cleanup; capture: locked JSONL append |
| Lock order/end states | Lifecycle authority before campaign mutation; this tranche introduces no new provider-under-lock wait; the pre-existing module-completion drain exception is tracked separately; quiescent worker before Load/Reset; terminal future exactly once; persistent `.lock` identities never copied/unlinked |
| Provider/platform | Native Windows, real OpenAI; actual model recorded from capture, never assumed from binding |
| Player promise | README `Recent Updates -> Current Main -> Player Interfaces` plus #193 Load-never-refused, honest progress, and restart-safe gameplay |
| Persisted schemas | Existing save metadata, upgrade marker, sidecars, encounter JSON, and master JSONL; no new store |

### 3.2 Findings

| Finding | Pinned code proof | Planned disposition |
|---|---|---|
| B1 | `updates/save_game_manager.py:451-495,832-878` makes SHA/schema manifest comparison a Load gate | S1 retires manifest authority; metadata remains diagnostic |
| B2 | `updates/save_game_manager.py:946-978` cleans live companion memory even when an old save contains none | D-VS-9 selects exact precedence; S1 then neither blindly wipes nor leaks the later timeline |
| B3 | `updates/save_game_manager.py:653-661` tests `state_manifest` as a dict although the writer stores a list | S1 recognizes the actual completed-save representation |
| B4 | `core/ai/action_handler.py:3866-3876` hashes action content and history length for relationship dedup | S2 uses the accepted invocation's value identity |
| B5 | `core/npc/voice_service.py:929-944` publishes a future before `Thread.start()` and does not terminalize it when start raises | S3 resolves the future before unwinding |
| B6 | `core/npc/voice_context.py:129-258` can return from recall/pre-dispatch failure without launching remaining packets | S3 falls back to each original packet independently and records each disposition |
| B7 | OOC collection returned before all dispatched work completed | G3 completion-collects every dispatched actor under D-VS-3 |
| B8 | `core/managers/combat_orchestrator.py:101-140` accepts a second unversioned voice-map shape | S4 deletes the fallback shape |
| B9 | `core/ai/conversation_utils.py:619-655` selects a legacy renderer when the canonical store is absent/read-only | S4 retains one canonical renderer; read-only remains health, not a mode |
| B11 | T045 legacy runtime remains | D-VS-4 grants a temporary waiver; retirement remains #282 |
| B13 | `main.py:7090-7101` synchronously runs `per_run_cap=40` backfill before first input | G8 removes the cap while preserving a one-time blocking build only for missing pre-feature state |
| B14 | Three `docs/design/` files carry branch doctrine | S9 deletes them; #193 remains the sole doctrine |
| B15 | `relationship_store.assert_store_writable` has zero callers, but `match_owned_capabilities` is live at `combat_agent.py:188-193` | S4 deletes only the dead refusal helper and preserves the live matcher |
| B16 | T105 catches/skip paths are DEBUG-only or silent in voice context/main | S3 uses existing warning and `VoiceTelemetry` surfaces |
| B17 | `relationship_store.py:366-367` returns false on schema reject without store-health evidence | S3 records the existing health event before returning |
| B18 | `live_provider_call.py:872-914` structurally reissues advisory transport failures but not retryable 429/5xx | S3 admits `retryable_http` to the same existing structural reissue path |
| B19 | `multi_model_capture.py:84-137,522` lazily spawns Git from first-use worker context | S6 computes one direct-byte fingerprint on the game thread; failure yields `unknown` |
| B23 | `reset_campaign.py` backs up modules but does not clear live `modules/encounters` | S7 clears that exact runtime family after durable backup |
| B25 | `live_provider_call._child_main` bypasses the parent master capture | S8 records T105/T108/T113 in the parent after the child returns |

## 4. Authority, state, and failure contracts

### 4.1 Restore

The selected save directory and its files are restore input. `state_manifest` is optional
diagnostic metadata, never an authorization oracle. Load may warn about mismatches but may not
refuse the requested restore. It does not invent missing saved data.

For `data/companion_memories`, D-VS-9 resolves the handoff/timeline conflict. The ratified
precedence is selected-save `episode_ledger.json` schema v1 plus `npc_agent_state.json` schema
v2; else full raw `*_memories.json` forward
migration; else compressed-only migration under a ratified exact mapping; else fresh empty
canonical state. Raw plus compressed imports raw only because compressed is derived. Never
merge or preserve the pre-Load live canonical state into an older timeline. The recommended
D-TB-6 result for malformed present optional sidecar data is subordinate to D-TB-9: quarantine/
omit that family, use another validated selected-save representation or fresh empty canonical
state, emit a loud diagnostic, and complete the requested Load for all other valid state. Never
retain pre-Load knowledge as a corruption fallback. This is not a fail-open parse and requires
the owner's D-7 ruling.

An existing completed save is recognized by the actual list-shaped manifest plus its existing
completion evidence. Replaying `saveGame` returns the existing save without deleting it.

Current restore is a locked multi-file copy with a pre-restore backup and compensating rollback;
it is not an atomic directory replacement. This plan preserves and tests that real commit model.
The current five-second module-refresh and thirty-second combat-lock acquisition terminals are
not preserved as acceptable. D-VS-5 requires the accepted
Save/Load/Reset operation without an abandonment deadline, displays changing truthful progress, and
executes it once authority becomes available. The implementation is gated on the owner's D-6
ruling and must also trace `_assert_no_active_campaign_completion` before mutation.

### 4.2 Relationship event identity

The source identity is the accepted logical turn, not the text it happened to contain.
Production obtains it from `InvocationClaim.logical_invocation_id`. The claim must be current
at commit. A call without an accepted invocation identity may update no relationship lifecycle
event: it records a loud skipped disposition rather than minting a replay-unstable UUID or
falling back to prose/content hashing. Roster and other already-authoritative action effects
remain governed by their existing transaction.

### 4.3 Voice failure terminals

- A per-actor future becomes terminal exactly once even if thread construction/start raises.
- Recall enrichment failure does not delete an otherwise valid actor packet. The original
  packet continues without recalled episodes and receives actor-scoped telemetry.
- One packet's construction/dispatch failure cannot erase siblings.
- Completed-invalid T105 retains the ratified Fork-3 one-beat degradation. No fabricated
  advice enters T096.
- Retryable transport keeps the existing fresh-child structural reissue. Under D-VS-7,
  typed retryable HTTP 408/409/429/5xx enters that same existing reissue branch with its existing
  fencing and telemetry. No new loop, retry count, or backoff is added; #284 owns redesign.
  Deterministic 4xx remains a completed failure.
- Warnings/telemetry are observational and cannot themselves break play.

### 4.4 Single representations

Only `npc-voice-intents/v1` is accepted at the combat coordinator boundary. Invalid or old
unversioned maps are loudly omitted; mechanics remain playable. Canonical companion memory is
rendered by one function. Before the legacy renderer is deleted, valid
`memories_compressed.json` from authentic old saves is imported once into the canonical store
under the existing migration lock and value dedup. The renderer then reads only canonical state.
Missing/read-only storage produces an explicit health disposition and no alternate prompt
grammar. Baseline-valid legacy data may not disappear.

The production legacy-writer inventory is complete at the pinned SHA:

- `main.py:7083-7088` calls `check_and_initialize_on_startup` (origin `f01bbc8e`) to build
  legacy memory from journal history. S5's canonical T113 upgrade owns that goal, so the runtime
  call retires only after G8/T113 passes live acceptance; the module may
  remain an offline migration utility.
- `core/ai/cumulative_summary.py:749-790` calls `CompanionMemoryManager` and the compressor
  (origins `5d922597`, `fc775168`, `e2708c8c`) inside
  `update_journal_with_summary`. Its sole enclosing path has zero production callers. The nearby
  `capture_location_episode_async` path in this file is also dead. Delete this zero-production-
  caller block; the actual live canonical location-close T108 seams are `main.py:1964-1972` and
  `main.py:5355-5373`.
- `main.py`'s two `__deferred_209__` branches (origins `b7f7a863`, disabled by `4b53aace`) and
  the body after `_prepare_legacy_memory_targets`' unconditional `return []` are unreachable
  legacy writers. Delete those dead bodies while preserving the checkpoint's
  `legacy_memory.status=not_applicable` compatibility field until its own schema retirement.
- No other non-test/non-script Python caller invokes `process_journal_entry`,
  `process_journal_operation`, or `save_all_memories`. `CompanionMemoryManager` and the
  compressor remain offline migration/verification tools, not runtime writers.
- `RelationshipStore.migrate_legacy_identity` remains the single forward adapter for full raw
  `*_memories.json`, guarded by its stored migration value and exact-memory dedup. It does not
  make new legacy data. Its compressed-only extension follows D-VS-9.

### 4.5 Startup backfill

Startup performs zero memory work when canonical files and the completion marker are valid. A
genuinely history-free game creates valid empty canonical state without a model call. Only a
missing pre-feature state with history enters one uncapped blocking build, with visibly changing
popup/status until canonical files and marker are terminal. The build registers one maintenance
scope under the same lifecycle arbiter used by Save/Load/Reset/quit before publishing work. Its
authority spans T113 provider work, episode/relationship sidecar commits, and marker advancement.
No new persisted state is added; the existing upgrade marker is its crash-resume receipt. Remove
`per_run_cap=40`.

Publication order is claim -> publish worker reference -> `Thread.start`. Start failure marks the
worker terminal and clears the claim in `finally`. Provider completion alone is not quiescence;
quiescence publishes only after every sidecar write and marker advancement completes or aborts.
Every mutation revalidates the exact worker authority under the existing sidecar path locks.
Lock order is lifecycle arbiter -> release -> provider wait -> sidecar path lock(s) one at a time
-> marker writer; no lifecycle lock spans provider waits or disk writes. Save/Load/Reset/quit
seal the worker immediately, genuinely terminate/reap its provider child, wait only for any
already-entered sidecar/marker commit to become quiescent with changing progress, then mutate.
A stale worker cannot write after those operations.

The one-time build completes before gameplay context can render; if interrupted, it resumes from
the marker on the next session. Retire the cap mechanism end to end: delete
`per_run_cap`, `max_entries`, their forwarding, the cap-only `paused` branch, and related copy.
Progress uses the shared status sink but S5 must add
the missing React event contract/reconnect terminal handling: start/progress are running;
complete/disabled/error are terminal. Headless emits a changing heartbeat during any >10-second
T113 call, not only every 25 records. T113 uses the existing live-provider child primitive; no
second retry loop. Its internal result distinguishes committed, deterministic honest-no-episode,
retryable/unavailable, and completed-invalid. The marker advances only for committed or
honest-no-episode; unavailable/invalid leaves that entry current for structural reissue or the
next authorized resume. This lifecycle is justified only by observed B13/#258 and ratified by
D-VS-8; retryable HTTP obeys D-VS-7's interim structural-reissue ruling.

### 4.6 Capture fingerprint

At main-loop startup, before voice/provider workers exist, compute and cache one best-effort
fingerprint over this exact finite inclusion rule: root runtime `*.py` except private `config.py`;
all `*.py` under `core`, `utils`, `updates`, and `web`; and all regular files under `prompts` and
`schemas`. Do not scan `web/static`, node assets, tests, tools, scripts, debug/evidence, runtime
data, caches, locks, or temp files. Include `model_config.py`, `model_registry.py`, and
`config_template.py`. Sort POSIX relative paths. Hash an algorithm/version prefix followed by
an eight-byte path length, UTF-8 path bytes, eight-byte content length, and content bytes for
each entrant. No Git command and no subprocess.

An expected entrant that cannot be read makes the source revision `unknown`; capture and play
continue. The cached value remains provenance only, never game authority. Development evidence
records entrant count, total bytes, hash latency, first-prompt latency, and a zero-callers audit
of removed Git helpers.

### 4.7 Reset

Before any reset mutation, extend the existing backup inventory to every player-owned family
Reset deletes, including `player_storage.json`, `data/companion_memories`, and
`data/companion_memories_compressed`, plus authoritative encounter JSON/`.bak` data. Exclude
runtime `.lock` artifacts at every depth. Reset first supersedes/reaps live provider/turn workers.
It first seals/reaps every lifecycle-registered T108/T113 memory writer and waits through its
final commit boundary under D-TB-11. It then acquires the existing party-transition lock to freeze encounter creation, acquires the
sorted set of existing per-encounter `.combat.lock` authorities, re-enumerates until the entrant
set is stable, and only then acquires module-refresh/campaign locks and performs backup/cleanup.
This party -> combat locks -> module -> campaign order lets a pre-existing combat->module
completion finish before Reset takes module. D-TB-10 requires a code-proven entrant audit;
legacy/no-claim creation not covered by the party freeze gates S7 on D-TB-2. After backup durability and lifecycle quiescence,
remove authoritative live encounter data and clear memory data without unlinking/recreating
persistent lock paths. Apply the same lock exclusion/preservation rule to restore rollback
backups. Runtime locks retain path/inode identity under waiters. If backup fails, cleanup does
not start. Reset retains its existing phase ordering and restart behavior.

### 4.8 Provider capture

The parent process owns the master JSONL writer. `call_live_provider` records each primitive
child envelope immediately after correlation validation and before success return or structural
reissue. It appends through the existing locked JSONL primitive using the same master schema:
original parsed request, reconstructed response when successful, actual model, callsite,
operation/generation correlation, disposition, timing, and usage. Preserve accepted correlation
on the normalized response metadata rather than discarding it in `_reconstruct_response`.
No child writes the shared file; no new capture store or cross-process lock. Failed/reissued
generations are explicit lifecycle records; exactly one logical accepted-success record is
identified by its operation and accepted generation.

## 5. Implementation slices

Each slice is independently reviewable and committed only after its focused gates and
simplifier pass. No implementation begins before same-SHA Part 3 convergence and owner/Claude
authorization.

### C0 -- Freeze evidence and compatibility inventory

- Pin tracked diff/status and authentic save/sidecar/encounter fixtures.
- Record old save formats, relationship call consumers, current voice envelope producers,
  T113 markers, capture master schema, and Reset file families.
- Run pre-change controls proving each reachable defect. A condition that cannot be reached is
  `NOT-REACHED`, never pass.

### C1 / S1 -- Restore truth

Files: `updates/save_game_manager.py`, `utils/module_refresh_lock.py`, applicable lifecycle/
progress/UI consumers for accepted Save/Load waiting, restore schematic, focused tests.

- Demote manifest hashes/schema to diagnostic evidence.
- Correct completed-save recognition to the real list representation.
- Under D-TB-9, install the ratified selected-save precedence, including fresh empty canonical
  state when no valid saved representation exists; never preserve pre-Load live memory.
- Under D-TB-6, quarantine/omit an invalid optional companion-memory family while Load completes,
  then install D-TB-9's validated selected-save/empty result.
- Under D-TB-5, replace Save/Load/Reset module-refresh/combat busy-refusal edges with
  accepted-operation wait or queue plus changing progress; trace campaign-completion busy
  metadata as well.
- Preserve the real multi-file copy, pre-restore backup, compensating rollback, lock ordering,
  and restart semantics. Do not claim atomic directory replacement.

### C2 / S2 -- Relationship value identity

Files: `core/ai/action_handler.py`, relationship/companion-memory schematic, focused tests.

- Thread the already-existing accepted logical invocation ID to relationship lifecycle commit.
- Remove content-SHA identity creation.
- Loudly skip only the relationship event if no accepted turn identity exists.

### C3 / S3 -- Voice liveness and visibility

Files: `core/npc/voice_service.py`, `core/npc/voice_context.py`,
`core/npc/relationship_store.py`, `utils/capture/live_provider_call.py`, `main.py`, voice and
provider schematics, focused tests.

- Terminalize futures on thread-start failure.
- Isolate OOC recall/build/dispatch failures per packet and retain original packets.
- Promote silent/DEBUG failure terminals to existing warning+telemetry sinks.
- Record schema rejects through existing store-health evidence.
- After D-TB-7, route retryable HTTP failures through the existing structural reissue path;
  otherwise preserve their present completed terminal.
- G3 resolves collection policy under D-VS-3; every dispatched OOC actor completion-collects.

### C4 / S4 -- Single canonical paths

Files: `core/managers/combat_orchestrator.py`, `core/ai/conversation_utils.py`,
`core/npc/relationship_store.py`, `main.py`, `core/ai/cumulative_summary.py`, combat/memory/
startup schematics, focused tests.

- Delete the unversioned combat voice envelope fallback.
- Under D-TB-9, apply the selected-save precedence and exact approved mapping, then delete the
  legacy renderer and route all successful rendering through the canonical store path.
- After D-TB-8 and accepted C5/T113, retire the one startup runtime writer call. Delete the
  zero-production-caller cumulative-summary block and unreachable main.py writer bodies listed
  in 4.4; preserve location-memory behavior through the live main.py T108 seams.
- Retain `CompanionMemoryManager`, initializer, and compressor only as offline migration tools;
  retain `migrate_legacy_identity` as the sole runtime forward adapter for saved full raw memory.
- Preserve the transition checkpoint compatibility field as `not_applicable`; no T045 behavior
  is changed. Any newly discovered runtime consumer stops C4 and returns to D-TB-2/plan review.
- Delete zero-caller `assert_store_writable`.
- Preserve active `match_owned_capabilities` and its T096 consumer unchanged.

### C5 / S5 -- One-time blocking canonical memory build

Files: `main.py`, `core/npc/episodic_upgrade.py`, `core/npc/episode_backfill.py`,
`utils/capture/live_provider_call.py`, applicable headless/web status contracts and stores,
startup/provider/memory/web schematics, focused tests.

- Remove synchronous startup invocation and the complete `per_run_cap`/`max_entries` cap path,
  including forwarding and cap-only paused terminal.
- Under D-VS-8, start/resume the one-time missing-state build through the exact
  lifecycle-discoverable maintenance scope in 4.5; valid current state performs zero work.
- Reuse marker idempotency and provider-child reaping; add only the missing UI status consumers
  and terminal semantics required to make the existing progress surface truthful.

### C6 / S6 -- Subprocess-free source fingerprint

Files: `utils/capture/multi_model_capture.py`, startup/provider schematics, focused tests.

- Replace lazy Git subprocess probing with sorted direct-byte fingerprinting.
- Prime once on the game thread before provider workers.
- Cache `unknown` on any fingerprint failure and continue.

### C7 / S7 -- Reset live encounter cleanup

Files: `utils/reset_campaign.py`, `utils/module_refresh_lock.py`, encounter and companion-memory
lifecycle owners, applicable progress/UI consumers, save/reset schematic, focused tests.

- Extend the durable backup to every player-owned family Reset deletes, including player storage,
  both memory roots, and authoritative encounter JSON/`.bak`; exclude all runtime locks.
- Under D-TB-10/D-TB-11, freeze/reap the complete encounter and memory-writer entrant sets before
  backup; D-TB-5 supplies accepted Reset waiting/progress instead of busy refusal.
- After backup durability and lifecycle quiescence, remove authoritative data while preserving
  persistent runtime lock identities at every touched depth.
- Preserve backup contents byte-for-byte and retain current restart contract.

### C8 / S8 -- Parent-owned child-call evidence

Files: `utils/capture/live_provider_call.py`, `utils/api_logger.py` only if the existing API
cannot express the correlation metadata, provider schematic, focused tests.

- Parent logs every T105/T108/T113 child generation envelope in the current master JSONL before
  returning/reissuing and carries accepted correlation through response reconstruction.
- Confirm one parseable accepted-success per logical call and explicit failed-generation/reissue
  evidence.

### C9 / S9 -- Doctrine hygiene

Delete only:

- `docs/design/2026-08-18-episodic-upgrade-backfill-plan.md`
- `docs/design/2026-08-31-npc-voice-context-balance.md`
- `docs/design/companion-episodic-memory.md`

Update references to live #193 or the descriptive architecture schematics. Do not create a
replacement doctrine document.

### C10 -- Integrated simplifier and consumer sweep

- Remove imports/helpers made dead by C1-C9.
- No behavior expansion.
- Re-run sentinel greps, schema/sidecar scans, build/tests, and the full consumer map.

### Owner-ratified gated slices (#193 v2.9, D-VS-1..11)

These slices are now authorized. They land one at a time after targeted FULL Part 3 review.

- **G1 / D-VS-1 -- all eligible OOC companions.** Remove the `limit=4` public argument and the
  `min(4, ...)` selection clamp from `build_ooc_packets_for_turn`. Keep relevance/fairness ordering
  for deterministic packet order, but call `rank_ooc_candidates(..., limit=None)` so every
  eligible, valid roster companion receives one actor-isolated packet. Sentinel grep must prove
  no four-companion OOC runtime limit remains.
- **G2 / D-VS-2 -- relevance threshold, no fixed memory count.** In
  `core/ai/conversation_utils._companion_memory_rows`, retain the current pinned/location/
  salience/grain ordering. The current data contract has no named numeric threshold: its closest
  value boundary is schema-valid canonical POV membership plus `pinned`, current-location, and
  `salienceScore` in [0,1]. Make relevance explicit without a new score: include pinned rows,
  current-location rows, and rows whose existing `salienceScore > 0`; a zero-score, unpinned,
  elsewhere row is not relevant. Remove the fixed `limit=3` slice and slot-replacement algorithm.
  In T112 recall, keep the existing `MATCH_THRESHOLD`, exact-value inclusion, and top-two
  relevance-ranked episode selection under explicit Part 5 D-272-1 authority. The single
  `arc_seeds[:1]` goal selection at both OOC/combat packet builders remains under that same
  authority. These are the two ratified semantic selections, not unowned truncation.
  This is deliberately interim; #283 owns
  affinity-driven redesign. The authorized relevance boundary uses existing canonical values;
  it adds no new score, model call, or store.
- **G3 / D-VS-3 -- OOC completion collection.** Give `PreparedOocVoiceHandle.collect` a
  completion-required path. Every direct, enriched, and failure-fallback OOC `dispatch_batch`
  call sets `completion_required=True`. Before collecting T105, wait for the predecessor T112
  scope to finish and publish either its enriched handle or its original-packet fallback; a
  T112 thread publication/start failure terminalizes its scope/future and installs that fallback
  before unwinding. Then use the existing `VoiceBatchHandle.collect_to_completion` plus status
  sink. `inject_voice_context` completion-collects every dispatched OOC packet before T067 sees
  the immutable voice block, then seals only already-terminal scopes.
  Pending work is never pre-empted or cancelled merely because T067 is ready. Save/Load/Reset/quit
  supersession still seals and reaps the whole batch. One changing, truthful progress owner reports
  completed/total/elapsed while waiting. No deadline or third collection policy is added.
- **G4 / D-VS-4 -- legacy waiver.** Make no T045-specific change. Shared-stack improvements may
  continue to flow through existing seams, but all legacy-only findings remain owned by #282.
- **G5 / D-VS-5 -- lifecycle locks wait and reclaim.** Pass `timeout_seconds=None` through the
  existing campaign/combat/module-refresh lock stack for Save, Load, and Reset. No busy-lock result
  may become a refusal. Preserve the existing lock order. The existing OS advisory lock is released
  automatically when its process dies, and the persistent lock-path artifact is intentionally not
  ownership. First prove that behavior in code and the killed-holder native arm; add no PID
  metadata and never unlink the lock inode. No new lock family, watchdog, or give-up deadline.
  Progress remains visibly changing while an accepted lifecycle operation waits. Preserve the
  pre-existing module-completion drain and its current party/completion ordering unchanged in this
  tranche. D-VS-5 makes lifecycle waiters wait safely for that live holder without a deadline;
  provider-under-lock debt is tracked by #286, not silently normalized as ideal.
- **G6 / D-VS-6 -- repair companion memory on Load and preserve clean copies.** At the existing
  locked save/restore boundary, validate `npc_agent_state.json` and `episode_ledger.json` through
  their existing schemas/loaders. The marker has no schema: its value-valid form is exactly the
  existing `is_complete` predicate or the existing resumable in-progress fields with nonnegative
  indices; every other present value is malformed. Every successful Save already copies the full
  memory directory into the selected save, and every Load already creates the pre-mutation rollback
  backup; preserve those patterns, and ensure only schema/value-valid files are chosen as clean
  recovery inputs. Never use the pre-Load live rollback copy as selected-timeline memory.

  Load becomes a two-phase operation inside the already-held invocation-supersession barrier:
  phase 1 acquires party -> combat -> module -> campaign, validates the target, creates the rollback
  backup, and restores selected bytes; then it releases filesystem locks while retaining Load's
  lifecycle/supersession authority. Phase 2 validates the restored memory family. Prefer a valid
  selected-save file or valid backup carried inside that selected save. Missing/malformed/schema-
  incompatible files are repaired, never refused: rebuild canonical state from the now-restored
  selected save's conversation history and journal through G8's one-time uncapped T113 function.
  Only after repair reaches a terminal marker does Load end its supersession barrier and report
  success. On repair failure, keep truthful changing progress and structurally reissue healable
  provider work; malformed source rows are skipped by the existing per-entry contract, never
  converted into trusted state. The existing rollback still owns ordinary copy/write exceptions.
  Delete the live `_build_legacy_companion_memory_message` fallback branch after canonical repair
  is established: old data feeds this one canonical rebuild path, never a second renderer.
- **G7 / D-VS-7 -- retryable HTTP.** Admit only the existing typed `retryable_http` disposition
  (408/409/429/5xx) to the already-existing structural full-reap/fresh-generation reissue branch.
  Deterministic 4xx remains a completed error. Add no loop, retry count, deadline, or backoff
  constant; #284 owns replacement of the mechanism.
- **G8 / D-VS-8 -- one-time uncapped build.** Remove `per_run_cap` from the startup call and
  backfill call graph. If canonical memory files and the complete marker are valid, startup does
  zero memory work. A genuinely history-free new game creates valid empty canonical files/complete
  marker without a model call. A pre-feature game with history performs one uncapped, blocking T113
  build with visibly changing progress, writes the existing completion marker, and never recurs.
  Reuse `LiveTurnScope` plus the existing detached startup/welcome registry as the maintenance
  parent (never a second registry): register it before starting any worker, register one T113
  `AdvisoryProviderScope` before its logical backfill begins, explicitly pass that child through
  `capture_and_fanout(..., _live_selected="advisory", _detached_scope=child)`, and publish
  `quiescent` only after provider, sidecar, and marker terminals. Generalize the existing child
  opener only enough to recognize the registered detached parent. Thread/start failure finishes
  the child and records a loud terminal. Save, Load, Reset, and quit seal/reap the maintenance
  child, wait only for entered commit quiescence, and leave the marker resumable before their
  lifecycle mutation; Save never queues behind the whole uncapped build. No new coordinator or
  store.
- **G9 / D-VS-9 -- pre-feature save rebuild.** Loading a save with no memory family never retains
  the later live timeline. After selected-save restoration, run the same G6/G8 one-time uncapped
  builder against that save's restored conversation history and journal, with the same popup and
  completion marker. Canonical repair/rebuild completes before any context rendering; the runtime
  legacy companion-memory renderer is deleted. This is one function and one policy, not a second
  migration or render path.
- **G10 / D-VS-10 -- accepted Reset entrant list.** Retain the already-shipped encounter cleanup
  and freeze encounter creation with the existing party-transition lock before backup through
  cleanup. Do not add a global lock. #285 owns later owner review of the accepted interim list.
- **G11 / D-VS-11 -- Reset async-writer fence.** Before Reset backs up or clears memory, seal the
  active, detached, or lifecycle-discoverable closing scope's T108/T113 advisory children and wait
  for their reapers/quiescence. Extend the existing `_scope_guard` registry, not its lock family:
  `close_live_turn_scope` moves a scope from active to a closing set before exposing the next-turn
  slot, and removes it only after every child reaches commit-terminal quiescence. Lifecycle
  supersession snapshots and seals active plus closing scopes under that same guard, then waits
  outside the guard. No provider or disk operation runs under `_scope_guard`.
  T108's current bare executor submits are first adapted to publish an `AdvisoryProviderScope`
  before `submit`; start failure finishes it, and the worker finishes it only after provider and
  sidecar commits. T113 uses G8's detached registered child. Reset uses the existing scope child
  registry plus invocation supersession; add no lock or store. A result fenced by Reset cannot
  commit afterward. Reset then backs up and clears within the existing lock order.

## 6. GL-1 behavioral contract

| Existing behavior/goal | Disposition | Proof gate |
|---|---|---|
| Load selected save | PRESERVED and strengthened: no metadata refusal | A1 |
| Manifest helps diagnose provenance | PRESERVED as non-authoritative metadata | D1/A1 |
| Malformed optional sidecar never becomes trusted input | PRESERVED; repair from a valid selected/backup copy or regenerate from restored history under D-VS-6 | D1/A1 negative control |
| Pre-feature saves remain loadable | PRESERVED | A1 |
| Save replay is idempotent | PRESERVED/fixed | A2 |
| Relationship event applies once per accepted turn | PRESERVED/fixed | A3 |
| Distinct equal-text turns remain distinct | PRESERVED/fixed | A3 |
| T105 packets are actor-isolated | PRESERVED/strengthened | A4 |
| Completed-invalid T105 degrades one beat | PRESERVED | A4 |
| Provider transport work structurally reissues | PRESERVED; typed retryable HTTP joins the same existing reissue under D-VS-7 | A4 |
| One canonical voice envelope | PRESERVED; fallback RETIRED | D4/A5 |
| Valid legacy compressed memory remains available | PRESERVED by one-time rebuild from restored history/journal; #282 owns T045 retirement | D4/A1/A5 |
| One canonical memory renderer | PRESERVED; alternate renderer RETIRED after import | D4/A5 |
| Capability candidates reach T096 | PRESERVED; live matcher retained | D4/A5 |
| `assert_store_writable` loud corrupt-store goal (origin `a4cb6174`) | PRESERVED through `_latch_read_only`, `record_store_health`, and planned schema-reject health; zero-caller helper RETIRED | D3/D4 grep + A5 |
| Legacy compressed renderer compatibility (origin `b901d68c`) | PRESERVED through D-VS-9 one-time selected-save rebuild; alternate render branch RETIRED | D4/A1/A5 |
| Unversioned combat envelope custom-caller compatibility (origin `82448d48`) | RETIRED under ratified Single-Path after all production producers are enumerated as versioned | D4/A5 |
| Startup legacy initializer (origin `f01bbc8e`): reconstruct old memories from journal | PRESERVED through canonical one-time uncapped T113 build under D-VS-8; ordinary valid startup performs zero work | D4/D5/A5/A6 |
| Dead cumulative-summary legacy memory block (origins `5d922597`/`fc775168`/`e2708c8c`): historical location-memory goal | Zero production callers; dead block RETIRED. Live goal remains owned by `main.py` T108 location-close seams | D4 call graph + A5 real boundary |
| Disabled transition legacy writers (origin `b7f7a863`, disabled `4b53aace`): recovery-compatible memory enrichment | PRESERVED by canonical async capture/backfill; unreachable bodies RETIRED while checkpoint `not_applicable` shape remains | D4/A5 legacy checkpoint replay |
| Legacy manager/compressor offline migration and verification | PRESERVED as non-runtime tools; zero production writer-call gate | D4 grep/import smoke |
| Raw legacy forward import (origin `7504a717`) | PRESERVED only where already valid; missing pre-feature memory rebuilds once under D-VS-9 | D4/A1/A5 |
| Startup produces an actionable prompt | PRESERVED/strengthened | A6 |
| Backfill resumes idempotently | PRESERVED | A6 |
| Captures carry source provenance | PRESERVED without Git/subprocess | A7 |
| Capture failure cannot block play | PRESERVED/strengthened | A7 |
| Reset retains a complete backup | PRESERVED | A8 |
| Reset removes current campaign state | PRESERVED/fixed for encounters | A8 |
| API master remains append-only parseable evidence | PRESERVED/extended | A9 |
| #193 remains sole doctrine authority | PRESERVED; branch doctrine files RETIRED | D9 |

## 7. Development and forensic gates

### D1 Restore matrix

- Authentic pre-branch save with no manifest and no companion sidecar.
- Current save with list manifest.
- Altered sidecar/hash metadata.
- Malformed present sidecar negative control: under D-VS-6, overall Load succeeds,
  unrelated saved state applies, D-TB-9's validated selected-save/empty result is installed,
  pre-Load knowledge does not survive, and omission is loud.
- Repeated `saveGame` against an existing completed folder, with before/after tree hash.
- Hold module-refresh and combat locks past their former deadlines: under D-VS-5,
  accepted Save/Load/Reset waits with changing progress then executes without resubmission.

### D2 Identity matrix

- Replay same logical turn and same payload: one lifecycle event.
- Two accepted turns with identical text: two lifecycle events.
- Same turn with correction/retry: one lifecycle event.
- Missing/stale claim: no relationship event and loud evidence.

### D3 Voice failure matrix

- `Thread.start` raises after future publication: future completes exceptionally and collection
  terminates.
- One recall failure among multiple companions: all original packets dispatch; only that actor
  lacks recall enrichment.
- Packet build/dispatch/store-schema failures: siblings survive and evidence names the actor.
- 429 and 5xx: verdict follows D-TB-7; deterministic 400 remains completed failure.
- Save/Load/Reset/quit: pending children reap and stale results cannot merge.

### D4 Single-path and consumer matrix

- Sentinel grep proves no unversioned voice-map acceptance and no legacy memory renderer.
- Current and authentic old sidecars validate unchanged; read-only health yields no alternate
  prompt grammar.
- An authentic `memories_compressed.json`-only save forward-imports once and renders the same
  grounded memories through the canonical path.
- Import/call graph proves `assert_store_writable` has zero readers before deletion.
- Import/call graph proves `match_owned_capabilities` remains imported and invoked.
- Production call graph has zero calls to legacy `process_journal_entry`,
  `process_journal_operation`, `save_all_memories`, or the memory compressor; offline scripts and
  migration tests remain callable.
- A location-close segment produces one canonical episode and no new `*_memories.json` or
  `memories_compressed.json`; T113 covers authentic historical journal state.

### D5 One-time memory-build matrix

- Valid complete, genuinely history-free, and missing pre-feature states.
- Valid complete state performs zero T113 work; history-free state creates a valid empty terminal.
- Missing pre-feature state blocks context rendering behind one uncapped build while native web
  and headless surfaces show changing truthful progress.
- Save/Load/Reset/quit seals and reaps the current child, waits for commit quiescence, then runs;
  restart/next session resumes the unchanged current marker entry without duplicate or skip.
- No per-run cap and no second local orchestrator.
- Zero grep hits for `per_run_cap`, `max_entries`, and cap-only paused copy in the T113 stack.
- A transport/unavailable or completed-invalid entry does not advance `journalNextIndex`; an
  honest-no-episode does advance exactly once.

### D6 Fingerprint matrix

- Native console, redirected headless, invalid `.git` pointer, no Git executable, unreadable
  expected source file.
- No `git` child in the game process tree.
- Stable same-tree fingerprint and changed-byte different fingerprint.
- `unknown` provenance still records a valid call and play continues.
- Record entrant count, scanned bytes, fingerprint latency, first-prompt latency, and prove
  `web/static` is not scanned.

### D7 Reset matrix

- Paused encounter containing `.json`, `.bak`, and held `.lock` siblings.
- Backup tree contains every player-owned family Reset will delete (including player storage and
  both memory roots), exact authoritative encounter JSON/`.bak`, and explicitly excludes locks;
  live authoritative data is empty while persistent lock identities remain stable.
- Injected backup failure leaves the live family untouched.
- Fresh restart reaches an actionable prompt and cannot inherit the old encounter.
- A held companion-memory lock survives successful Reset and forced restore rollback without
  unlink/recreate or split authority.
- Hold a legacy/no-claim/completion encounter writer while Reset begins, release it, and prove
  Reset waits then clears its committed value. Attempt a late writer after the freeze and prove it
  is rejected/blocked and cannot recreate stale encounter state.

### D8 Capture matrix

- T105, T108, and T113 each produce parseable master records with actual model/request/response.
- Reissued child generations are correlated without duplicating the accepted result.
- Concurrent records remain valid JSONL and monotonic under the existing writer lock.

### D9 Hygiene and standard gates

- `py_compile` changed Python files.
- `pyflakes` every changed Python file; no new undefined names or import defects are accepted.
- Focused tests plus `python -m pytest tests`.
- `tsc -b` and Vite build if touched paths affect the web bundle; otherwise record NOT-APPLICABLE.
- ASCII scan of additions, secret scan, schema/sidecar compatibility scan, imports, conflict markers,
  and `git diff --check`.
- No-Limits and Single-Path sentinel greps over every touched file and the branch diff.

## 8. Native Windows real-OpenAI acceptance

Every arm records the #193 v2.9 evidence block: pinned commit, actual command/surface, real
provider/model from capture, parsed request payload at its consumer, pre/post authoritative
state, player-visible stream, lifecycle/quiescence receipts, timing, and exact verdict. Synthetic
tests may support but cannot substitute.

### A1 Restore truth

Via native `run_headless.py serve`, Load an authentic pre-branch save and a copied current save
whose manifest/sidecar bytes were altered. Both requests are accepted and applied. Existing
companion memory follows D-TB-9 selected-save precedence: canonical, raw-only, compressed-only,
and no-memory fixtures receive separate disk/player-visible verdicts and never retain post-save
knowledge accidentally. A present malformed sidecar
follows D-VS-6; the overall Load succeeds, unrelated saved state
applies, the chosen validated selected-save/empty representation is installed, no pre-Load
knowledge survives, and a loud family-scoped omission is visible.
Hold both module-refresh and combat locks beyond their former acquisition budgets, then release:
under D-TB-5 the accepted Load executes without player resubmission and status keeps changing.

### A2 Save replay

Reach replay of the same accepted save operation through a real crash/restart boundary: terminate
after the durable save folder/completion evidence exists but before the action checkpoint advances,
then restart. Hash/file count/mtime before and after prove the completed folder was not removed or
rebuilt. A direct helper call may support the primitive but cannot pass this arm. If the exact
crash seam is not reached, verdict is `NOT-REACHED`.

### A3 Relationship identity

Play two real equal-intent turns and observe an internally rejected T067 candidate followed by
its automatic correction attempt under the same captured `logical_invocation_id`. Disk evidence
proves one event for each accepted turn, none for a correction attempt, and stable source IDs tied
to invocation receipts rather than text hashes. A later player clarification is a new invocation
and cannot prove this seam. If real OpenAI does not naturally reach the internal correction
boundary, that sub-arm is `NOT-REACHED` and the deterministic identity matrix remains supporting
evidence only.

### A4 OOC isolation and provider recovery

In a multi-companion real turn, create an authentic T112 failure condition without editing
state or fabricating a provider response. Every valid companion still receives its T105 packet;
telemetry names the failed enrichment. A real or controllably induced transport/429 arm proves
fresh structural reissue and no whole-batch loss. If no legal lever exists, that sub-arm is
`NOT-REACHED`, never pass. The HTTP arm follows D-TB-7. For every actor, place the parsed T105
packet/result beside the actual T067 or T096/T097 consumer payload and player-visible narration;
record successful, omitted, completed-invalid, and degraded counts.

### A5 Single-path compatibility

Load current and old sidecars and play one OOC and one typed-combat turn. Only canonical
envelopes/rendering appear. Read-only/corrupt controls produce a loud health disposition and no
legacy injection. Capability matching still supplies owned candidates to T096.
Test authentic compressed-only, raw+compressed, and canonical+legacy saves against the ratified
D-TB-9 precedence, stable identities, exact-once migration receipts, and crash/restart between
cross-sidecar writes. No episode or relationship fact may be invented from lossy shorthand.
Then perform a product-legal location/module close through the live main.py T108 seam: capture
the T108 request/result and canonical episode/relationship writes; prove no new
`*_memories.json` or `memories_compressed.json` is written; restart/revisit and demonstrate the
grounded event reaches later companion context/narration. Record player-visible transition/
history output and successful, omitted, invalid, and degraded counts.

### A6 One-time blocking memory build

Start an authentic pre-feature save with many upgrade candidates. Before context rendering, one
uncapped T113 build runs while native browser and headless surfaces show changing truthful
progress. Completed entries persist once, and restart resumes remaining work with no cap or
duplicate. A valid-current startup separately proves zero T113 work and no popup. Run a >10-second
call, an error terminal, reconnect hydration, and Save/Load/Reset/quit: status must change
truthfully, terminate cleanly, and no stale worker may write after lifecycle mutation.

### A7 No-freeze fingerprint

Launch a fresh native clone through redirected headless exactly as #278 reproduced. The first
turn completes, process inspection shows no Git child, and the capture contains a direct-byte
non-`unknown` stable fingerprint. Repeat with an invalid Git pointer and require the same useful
fingerprint to prove Git is irrelevant. A separate unreadable-expected-entrant negative control
must yield `unknown` while capture and play continue.

### A8 Reset encounter cleanup

Reset from a real paused encounter. The durable backup contains every player-owned family Reset
deletes, including player storage, both memory roots, encounter JSON and `.bak`, and excludes all
`.lock`; live authoritative data is empty while held lock identity is not split; party/reset
state is correct; restart reaches a fresh actionable prompt. Hold the refresh lock past its
former budget and prove D-TB-5 behavior without resubmission. Force restore rollback with a held
memory lock and prove its persistent identity and canonical bytes survive. On native Windows,
hold a real pre-existing encounter writer while Reset begins: Reset must wait, back up its
committed encounter, clear it, then reject/block a late writer so no stale encounter reappears.
If no product-legal writer overlap can be reached, that sub-arm is `NOT-REACHED` and D-TB-10
retains its ratified interim disposition on the deterministic entrant/lock trace; #285 owns the
later owner review. The live sub-arm is not mislabeled as pass.

### A9 Child-call evidence

Reach real T105, T108, and T113 calls. Parse the shared master JSONL and prove exact callsite,
actual model, request, response, correlation, and disposition records. Inspect for duplicate or
interleaved-invalid lines.

### A10 Integrated gameplay

One fresh multi-companion campaign covers startup, an OOC beat, typed combat, Save, Load, Reset,
and restart. No leg may be labeled pass when its mutation was not reached. Owner-gated B7/B11/
R4/R5 receive separate verdicts matching their rulings. Native Playwright additionally proves
Save/Load/Reset controls disable with an exact reason during lifecycle ownership, visible
start/changing-progress/completion messages, reconnect hydration, restored recent chat after Load,
and no technical diagnostic in the player stream. The gameplay command input/composer is also
disabled with the exact truthful reason; text entered before/after the boundary is either durably
accepted once or remains visibly unsubmitted, never silently lost.

### A11 Ratified gated-slice acceptance (supersedes stale A1/A4/A6 wording)

- **Six-companion OOC:** assemble six distinct companions through the owner-authorized fixture
  procedure using six separately schema-valid character sheets and canonical party references;
  preserve a provenance manifest for every copied/built sheet. Submit one real OpenAI OOC turn.
  Capture six actor-isolated T105 requests, six terminal collections before
  T067, one DM request containing all six advisory rows, and grounded player narration. Record
  input-to-prompt wall time and voice batch wall time; expected cost is measured, never asserted.
- **Corrupt-memory Load:** alter an authentic saved `npc_agent_state.json` after Save. Load must
  apply unrelated selected-save state, visibly report repair, restore the last clean selected/
  backup copy or run the same uncapped backfill, then produce a grounded real recall. No malformed
  bytes or post-save memory survive.
- **Pre-feature Load:** load an authentic save with no companion-memory family. The restored save's
  conversation and journal feed one uncapped T113 build; native Playwright proves the progress
  popup appears, changes, survives reconnect hydration, and reaches a terminal, while headless
  protocol records the same lifecycle. The complete marker is durable, and a later real turn
  recalls a true saved event.
- **Dead-holder lock:** a separate native process acquires each relevant advisory lock and is
  killed. Load/Save/Reset then acquire the same stable lock identity without refusal or deadline;
  a living-holder control waits with changing status and proceeds once released.
- **Valid-memory startup:** launch a current game with schema-valid sidecars and a complete marker.
  The actionable prompt appears with zero T113 call, zero memory mutation, and no progress popup.
- **Retryable HTTP:** a naturally occurring real OpenAI typed 408/409/429/5xx T105 result is
  recorded, fully reaped, and reissued by the existing generation path; deterministic 400
  completes and does not reissue. If real OpenAI does not produce the retryable status during the
  approved window, record `NOT-REACHED`; typed deterministic controls remain supporting evidence.
- **Reset writer fence:** naturally reach or controllably hold existing T108/T113 child work, issue
  Reset, and prove seal -> reap/quiescence -> backup -> clear ordering with no post-Reset write. If
  the child branch cannot be reached through a legal fixture, report `NOT-REACHED`; the deterministic
  lifecycle trace remains supporting evidence rather than a false live pass.

Every arm includes the #193 v2.9 evidence block and inspects native Windows disk/protocol/master
capture. Real OpenAI is mandatory where a model call is part of the behavior. No state-edit
substitute may stand in for the final player-visible recall/narration assertion.

## 9. Simplifier questions

## 10. Acceptance-discovered corrections (#287 and G8b)

These corrections were discovered by the native authentic pre-feature Load arm after G1-G11
were implemented. They are part of completing the already-ratified D-VS-8/D-VS-9 behavior, not
a new feature wave. No other Tranche B behavior changes.

### C11 -- durable per-entry upgrade cursor (#287)

Observed failure: during a successful 133-entry backfill, canonical episodes were committed but
`episodic_upgrade.json` did not exist until the whole journal loop returned. A crash would restart
T113 at index zero. Stable episode coordinates prevent duplicate canonical episodes, but they do
not prevent repeated paid model work and do not satisfy the ratified resumable-marker contract.

Smallest correction:

- Write the initial `in_progress` marker before the first T113 call.
- A marker-write `OSError` never halts the build the player is watching. Upgrade the existing
  swallowed DEBUG-only marker-write failure to WARN plus the existing store-health telemetry, then
  continue; the next successful per-entry write re-covers the cursor. The ledger commit remains
  authoritative and idempotent, so a marker-write failure risks repeated paid work after a later
  crash, never corrupt or skipped game state. Add no retry loop, lock, store, or deadline.
- Add a callback from `backfill_from_journal` to the existing orchestrator. After each journal
  entry whose canonical EPISODE LEDGER commit returns a non-empty episode ID, persist
  `journalNextIndex` and cumulative `committed` in the existing marker. A no-episode/skip may be
  covered by a later successfully committed checkpoint or the terminal marker, but does not itself
  claim durability. A pending `BackfillCompletedInvalid`, `LiveProviderSuperseded`, provider
  failure, or canonical ledger commit/write failure never writes a cursor for that entry; a
  completed entry error returns the existing loud resumable terminal rather than letting a later
  checkpoint skip past the uncommitted entry. POV/relationship overlays retain their already
  ratified fail-open plus WARN/telemetry behavior from S3 and are not cursor authority.
- The canonical episode-ledger commit remains first; the marker is only its recovery cursor.
  `_write_marker` remains the sole marker writer and the existing stable coordinates remain the
  idempotency authority. If the episode committed but its cursor checkpoint failed, restart may
  revisit that entry and the stable coordinate converges without duplication. No new store,
  receipt, lock, timeout, or prose/hash authority is added.
- Preserve callers by making the callback optional. Preserve the final journal and summary marker
  writes as terminal reconciliation.

GL-1: valid-current zero-work, history-free empty completion, completed-invalid resumability,
malformed-row fail-open behavior, summary backfill, canonical commit idempotency, and lifecycle
supersession are PRESERVED. Only the false "cursor is durable during successful work" gap changes.

Proof: on an isolated native-Windows copy of the authentic pre-feature save, begin a real OpenAI
build, wait for at least ten journal entries, record the marker and canonical episode coordinates,
then terminate and reap the entire game/provider process tree. Prove no descendant remains and no
file changes after quiescence; only then capture the authoritative marker and canonical sidecars
before restart. The first resumed T113 journal request must start exactly at that post-death cursor
(not merely at or beyond an earlier racing sample and never at index zero); prior coordinates must
remain singletons; the build must complete and a grounded recall must reach an actionable prompt.
Capture exact marker bytes before termination, after full-tree death, and after restart.

### C12 -- React memory-upgrade progress overlay (G8b)

Observed failure: `default_progress` emits `episodic_upgrade_start/progress/complete`, but the
React event contract and socket adapter subscribe only to `compression_*`. The server already
routes these events through the existing compression-operation snapshot slot, so live clients do
not render them and reconnect cannot render their payload truthfully.

Smallest correction:

- Add the three existing `episodic_upgrade_*` payloads to the typed server-event contract and
  subscribe to them in the existing socket adapter.
- Extend the existing compression-operation Zustand state with a presentation kind and memory
  message. Map live memory events and snapshot events into that same single overlay state; do not
  create another queue, coordinator, or persistence record.
- Extend the existing `CompressionOverlay` presentation so memory upgrade shows a truthful
  "Companion Memory Recovery" title, the emitted changing message/count, and a terminal state.
  Chronicle compression behavior and payloads remain byte-for-byte compatible at their existing
  handlers.

GL-1: compression live events, reconnect hydration, completion/error display, hide delay, and
module/update operations are PRESERVED. The only new behavior is rendering the server events that
G8 already emits. The overlay remains presentational and never gates or authorizes mutation.

Proof: native Playwright loads an isolated authentic pre-feature save through the production web
path. It must observe the overlay appear, record at least two increasing progress states, disconnect
and reconnect while the build is active, observe the hydrated current state, then observe the
terminal state. A valid-current control must reach an actionable prompt with no T113 call and no
memory overlay. Run the focused frontend tests, `tsc -b`, and Vite build; inspect the browser player
stream for technical leakage.

### C13 -- remaining ratified acceptance

After C11/C12 pass, run the dead-holder/living-holder lock arm, valid-memory zero-work startup,
retryable-HTTP real-OpenAI reachability window, and Reset writer-fence arm exactly as A11 states.
Record `NOT-REACHED` honestly. The final gate package explicitly records:

- #287 as resolved only by the kill/restart cursor proof;
- legacy `*_memories.json` and `memory_config.json` writers as remaining #283-owned residue, not
  silently treated as retired by G9;
- the authentic 133-entry Load result (982.063 seconds, marker complete at 133, grounded recall)
  separately from the C11 crash-resume proof and the C12 Playwright proof.

After each slice and once integrated:

1. Did the change delete an alternate path rather than wrap it?
2. Did it reuse an existing receipt, scope, telemetry sink, lock, marker, or writer?
3. Can a helper/import/branch now be deleted?
4. Does any failure invent gameplay truth, refuse Load, or strand a future?
5. Does any test-only lever enter production?
6. Did a formerly bounded list become a new cap or hidden selection window?

## 10. Part 3 review protocol

Freeze this file and SHA-256, then dispatch blind independent reviewers against the same bytes:

- Architecture Custodian: cross-file atomicity, state owners, worker lifecycle, source fingerprint.
- Fail-Forward Reviewer: B1/B2/B3, all futures/children terminal, Load-never-refused, no hidden
  deadlines, lock/wait traces.
- Acceptance Strategist: real reachability, native-Windows/OpenAI evidence, honest NOT-REACHED.
- No-Limits Sentinel: caps/windows/budgets in touched files and diff.
- Single-Path Sentinel: restore, memory renderer, voice envelope, provider and capture paths.
- Consumer/Compatibility DA: old saves/sidecars, every changed field/function reader/writer,
  UI/history/capture consumers.
- Player-Experience Reviewer: blocking work is visibly truthful, errors are player-safe, and no
  mechanical drift occurs.
- Leanness Reviewer: reject new stores/ledgers/adapters/retry loops and challenge S5/S6 machinery.
- Schema/Platform Reviewer: JSON representations, cp1252/ASCII, Windows file replacement/locks.
- Legacy-Contract Reviewer: T045 boundary, forward compatibility, no unapproved legacy-only fix.

The controller alone edits this plan. Every finding gets one explicit resolution in the ledger
below. Re-dispatch affected and confirmation seats until one clean same-SHA pass. Implementation
remains blocked until convergence plus Claude/owner gate.

## 11. Decision and resolution ledger

| ID | Status | Decision / required evidence |
|---|---|---|
| D-TB-1 / D-VS-3 | RATIFIED | OOC completion-collects every dispatched companion with progress; no pre-emption |
| D-TB-2 / D-VS-4 | RATIFIED-WAIVER | T045 stays unchanged; retirement remains #282 |
| D-TB-3 / D-VS-2 | RATIFIED | Keep relevance ordering/threshold and remove fixed memory count; #283 owns redesign |
| D-TB-4 / D-VS-1 | RATIFIED | Remove OOC companion count limit; every eligible companion gets a packet |
| D-TB-5 / D-VS-5 | RATIFIED | Save/Load/Reset lock waits have no give-up deadline and reclaim dead holders |
| D-TB-6 / D-VS-6 | RATIFIED | Repair malformed/missing memory from clean copy, else existing history/journal backfill |
| D-TB-7 / D-VS-7 | RATIFIED-INTERIM | Typed retryable HTTP uses existing structural reissue only; #284 owns redesign |
| D-TB-8 / D-VS-8 | RATIFIED | One-time uncapped blocking memory build with progress; never ordinary-startup work |
| D-TB-9 / D-VS-9 | RATIFIED | Pre-feature save rebuilds once from its restored history/journal; never keep/wipe |
| D-TB-10 / D-VS-10 | RATIFIED-INTERIM | Existing Reset encounter entrant/freeze list accepted; owner review #285 |
| D-TB-11 / D-VS-11 | RATIFIED | Reset seals/reaps existing async memory child scopes; no global lock |
| R-TB-1 | RESOLVED | Preserve live `match_owned_capabilities`; ledger zero-caller claim disproven by code |
| R-TB-2 | RESOLVED | Exact one-time blocking G8/T113 lifecycle ratified by D-VS-8 |
| R-TB-3 | RESOLVED | Exact direct-byte fingerprint entrants/framing and latency evidence specified |
| R-TB-4 | RESOLVED | Parent observes every primitive envelope before reissue; existing JSONL writer/metadata |
| R-TB-5 | RESOLVED | B24 remains explicitly out of scope; no implementation here |
| R-TB-6 | RESOLVED | Persistent lock files excluded from backup and preserved live; authoritative encounter data clears |
| R-TB-7 | RESOLVED | Legacy compressed memory forward-import required before renderer deletion |
| R-TB-8 | RESOLVED | Restore described as multi-file backup/rollback, not atomic directory replacement |
| R-TB-9 | RESOLVED | Entire T113 cap path retires; failed entries do not advance marker |
| R-TB-10 | RESOLVED | S7 inventory expanded to all data Reset deletes; locks excluded/preserved globally |
| R-TB-11 | RESOLVED | GL-1 origin/goal/proof added for all S4 deletions |
| R-TB-12 | RESOLVED | Save seals/reaps advisory T113 before snapshot; it never waits on an unbounded maintenance call |
| R-TB-13 | RESOLVED | Normal fingerprint must be useful; `unknown` accepted only on unreadable-input negative control |
| R-TB-14 | RESOLVED | Full legacy producer/consumer inventory complete; startup retirement gates on accepted C5, cumulative block is zero-production-caller, live T108 seams pinned |
| R-TB-15 | RESOLVED | Save seals/reaps T113 immediately; no queue behind an unbounded maintenance worker |
| R-TB-16 | RESOLVED | A3 uses an internal same-invocation correction, never a later player clarification |
| R-TB-17 | RESOLVED | Native A8 may honestly mark writer overlap NOT-REACHED while D-VS-10 remains ratified interim and #285 owns later review |
| R-G-1 | RESOLVED | G3 completion-required covers direct/enriched/fallback OOC dispatch; T112 start failure terminalizes before fallback publication |
| R-G-2 | RESOLVED | G11 explicitly scopes T108 before executor submit and T113 before detached work; terminal includes sidecar/marker commit |
| R-G-3 | RESOLVED | G5 reuses OS-released advisory locks; no PID metadata, unlink, watchdog, or new lock identity |
| R-G-4 | RESOLVED | Load repair is two-phase under one supersession authority; provider work occurs after filesystem-lock release |
| R-G-5 | RESOLVED | Marker validity is value-defined; repair sources belong only to the selected save timeline |
| R-G-6 | RESOLVED | Schema-incompatible authentic memory repairs through canonical G8 rather than blocking Load |
| R-G-7 | RESOLVED | Runtime legacy memory rendering is deleted after canonical repair; D-VS-4 waives T045 only |
| R-G-8 | RESOLVED | G2 removes the proactive fixed-three slice; D-272-1 retains top-two targeted recall and one arc-seed pick |
| R-G-9 | RESOLVED | Acceptance requires distinct schema-valid companion provenance, Playwright popup truth, and honest live-HTTP NOT-REACHED |
| R-G-10 | RESOLVED | Stale prompt-first and v2.7 language retired throughout; the current v2.9 blocking-build contract remains |
| R-G-11 | RESOLVED-OWNER-B | Preserve the pre-existing completion drain; D-VS-5 waiters do not refuse, and provider-under-lock debt is #286 |
| R-G-12 | RESOLVED | Closing T108 scopes remain discoverable under the existing scope guard until child commit quiescence |

## 12. Tracked follow-ups

| Item | Disposition |
|---|---|
| #276 / #262-b | No-Limits caps in untouched files; separate follow-on |
| #278 | Closed only after S6 real no-Git-child proof |
| #279 | Encounter faction/identity owner; excluded from voice tranche |
| #280 | Closed only after S7 native Reset proof |
| #286 | Pre-existing Save/module-completion provider-under-lock debt; separate planned change |
| #258 | S5 startup-backfill evidence source and closure target if fully resolved |
| #198 | Async episode-writer lifetime; D-TB-11 makes it an explicit Reset prerequisite |
| B21 | Owner-queued agentic death/down scene; no mechanics work here |
| B22 | Prompt-quality observation; no narration tuning here |
| B24 | Compressor progress observation; no pacing repair here |
| T045 retirement | D-VS-4 temporary waiver and separate #282 retirement plan |

## 13. Stop conditions

Stop and return to owner/Claude before code if:

- any owner-open decision is required by an otherwise-authorized slice;
- an authentic old save/sidecar is baseline-valid but candidate-invalid;
- S5 needs a new persisted coordinator, deadline, or parallel retry engine;
- S6 cannot provide useful provenance without a Git subprocess and no ratified waiver exists;
- any slice changes combat mechanics, voice prose, player intent, or T045-only behavior;
- a new defect appears: capture evidence and file it separately before proceeding.
