# Tranche B Fail-Forward, Custodian, and Single-Path Plan

Status: **DESIGN ONLY -- NO IMPLEMENTATION AUTHORIZED**

Date: 2026-09-03

Branch: `integration/npc-voice-episodic`

Pinned baseline: `6fc0f8f5db126ffd0818d2372ea69731bc1ad4d1`

The handoff expected `edf0d6ae`, but the already-approved #262 dispositions follow-up
advanced both the local and remote branch to `6fc0f8f5`. This plan is grounded in that
actual clean tracked tip. Four unrelated untracked runtime/plan artifacts remain untouched.

Authority: live GitHub issue #193 v2.7, fetched 2026-09-03. Part 1 was read in full,
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

### Owner-gated, separately sliced but represented here

- D-TB-1 / B7: OOC voices completion-collected like combat, or best-effort.
- D-TB-2 / B11: retire T045 legacy combat before merge, or grant a temporary owner waiver
  with the already-ratified retirement next.
- D-TB-3 / R4: retain or retire the top-three memory selection limit.
- D-TB-4 / R5: retain or retire the four-companion OOC dispatch limit.
- D-TB-5 / #193 D-6: replace Save/Load/Reset lock-acquisition deadlines with accepted-operation
  queue/unbounded wait plus changing progress, or grant a temporary waiver.
- D-TB-6 / #193 D-7: when a selected save contains a malformed optional companion-memory
  family, allow family-scoped loud omission while completing the rest of Load, or choose a
  different detected-corruption terminal.
- D-TB-7 / #193 D-8: extend structural reissue to advisory retryable HTTP results, with remote
  execution/cost identity explicitly accepted, or retain the present completed-failure bound.
- D-TB-8 / #193 D-1: authorize the exact lifecycle-discoverable T113 maintenance worker
  described in section 4.5, or select another explicit owner.
- D-TB-9: resolve selected-save memory precedence. The handoff says pre-feature Load must not
  wipe memory, while selected-save authority forbids retaining knowledge created after that
  save. The recommendation is selected-save canonical > raw legacy migration > an explicitly
  approved compressed-only adapter > empty canonical; never merge the pre-Load live sidecar.
- D-TB-10: confirm the Reset encounter-writer entrant set and the ordered reuse of existing
  party-transition plus per-encounter locks. If a legacy creator can evade that freeze, S7 is
  gated on D-TB-2 retirement/waiver rather than adding an unproven global lock.
- D-TB-11 / #198: authorize a Reset-visible lifecycle fence spanning every asynchronous
  companion-memory writer (T108 episode capture and T113 upgrade) through its last sidecar/marker
  commit. Without this, Reset may not clear those stores.

No owner-gated slice may be implemented from this plan until its explicit ruling is recorded.

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
| Dynamic branch revision | `6fc0f8f5db126ffd0818d2372ea69731bc1ad4d1`; `origin/main` `52990aa08f1108cdc5660c31fb862ab342871944`; main is an ancestor |
| Policy | Live #193 v2.7, updated `2026-09-02T23:28:18Z` |
| Save/Load/Reset | Part 2 page 9 plus `docs/architecture/save-load-reset-lifecycle.md` |
| NPC memory and voice | Part 2 page 7 (NPC systems) plus `companion-memory.md`, `npc-voice-ooc.md`, `npc-voice-combat.md` |
| Startup/provider | Part 2 pages 10-11 plus `startup-boot.md`, `provider-routing.md` |
| Browser/headless | Part 2 pages 10 and 13 plus `web-headless-surfaces.md` |
| Failure classes | B1/B2; Part 5 Fork-3; open D-1/D-6/D-7/D-8 are not presumed closed |
| Commit models | Save/restore: multi-file with pre-restore backup/rollback; sidecars: locked reread-copy-validate-write; Reset: durable backup before cleanup; capture: locked JSONL append |
| Lock order/end states | Lifecycle authority before campaign mutation; no lifecycle lock across provider wait/disk; quiescent worker before Load/Reset; terminal future exactly once; persistent `.lock` identities never copied/unlinked |
| Provider/platform | Native Windows, real OpenAI; actual model recorded from capture, never assumed from binding |
| Player promise | README `Recent Updates -> Current Main -> Player Interfaces` plus #193 Load-never-refused, honest progress, and restart-safe gameplay |
| Persisted schemas | Existing save metadata, upgrade marker, sidecars, encounter JSON, and master JSONL; no new store |

### 3.2 Findings

| Finding | Pinned code proof | Planned disposition |
|---|---|---|
| B1 | `updates/save_game_manager.py:451-495,832-878` makes SHA/schema manifest comparison a Load gate | S1 retires manifest authority; metadata remains diagnostic |
| B2 | `updates/save_game_manager.py:946-978` cleans live companion memory even when an old save contains none | OWNER-GATED D-TB-9 selects exact precedence; S1 then neither blindly wipes nor leaks the later timeline |
| B3 | `updates/save_game_manager.py:653-661` tests `state_manifest` as a dict although the writer stores a list | S1 recognizes the actual completed-save representation |
| B4 | `core/ai/action_handler.py:3866-3876` hashes action content and history length for relationship dedup | S2 uses the accepted invocation's value identity |
| B5 | `core/npc/voice_service.py:929-944` publishes a future before `Thread.start()` and does not terminalize it when start raises | S3 resolves the future before unwinding |
| B6 | `core/npc/voice_context.py:129-258` can return from recall/pre-dispatch failure without launching remaining packets | S3 falls back to each original packet independently and records each disposition |
| B7 | OOC collection policy is an owner choice | Separate gated slice D-TB-1 |
| B8 | `core/managers/combat_orchestrator.py:101-140` accepts a second unversioned voice-map shape | S4 deletes the fallback shape |
| B9 | `core/ai/conversation_utils.py:619-655` selects a legacy renderer when the canonical store is absent/read-only | S4 retains one canonical renderer; read-only remains health, not a mode |
| B11 | T045 legacy runtime remains | Separate gated slice D-TB-2 |
| B13 | `main.py:7090-7101` synchronously runs `per_run_cap=40` backfill before first input | S5 makes backfill advisory and post-prompt, with no cap |
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

For `data/companion_memories`, D-TB-9 will resolve the handoff/timeline conflict. The recommended
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
not preserved as acceptable. The recommended D-TB-5 result queues or waits for the accepted
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
- Retryable transport keeps the existing fresh-child structural reissue. Retryable HTTP
  408/409/429/5xx is owner-gated by D-TB-7/#193 D-8 because remote execution, cost, identity,
  concurrency, and backoff are not yet ratified. The recommendation is same-logical-call fresh
  reissue with existing fencing and telemetry; until ratified, current completed-failure behavior
  remains. Deterministic 4xx remains a completed failure.
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
  call retires only after D-TB-8 is ratified and C5/T113 passes live acceptance; the module may
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
  make new legacy data. Its compressed-only extension is owner-gated by D-TB-9.

### 4.5 Startup backfill

Startup exposes the actionable prompt first. The recommended D-TB-8 design registers exactly one
process-local `EpisodeUpgradeWorker` under the same lifecycle arbiter used by Save/Load/Reset/
quit before publishing its thread. Its authority spans T113 provider work, episode/relationship
sidecar commits, and marker advancement. It is not attached to a foreground player-turn scope,
so ordinary turn closure cannot orphan or repeatedly cancel it. No new persisted state is added;
the existing upgrade marker is its crash-resume receipt. Remove `per_run_cap=40`.

Publication order is claim -> publish worker reference -> `Thread.start`. Start failure marks the
worker terminal and clears the claim in `finally`. Provider completion alone is not quiescence;
quiescence publishes only after every sidecar write and marker advancement completes or aborts.
Every mutation revalidates the exact worker authority under the existing sidecar path locks.
Lock order is lifecycle arbiter -> release -> provider wait -> sidecar path lock(s) one at a time
-> marker writer; no lifecycle lock spans provider waits or disk writes. Save/Load/Reset/quit
seal the worker immediately, genuinely terminate/reap its provider child, wait only for any
already-entered sidecar/marker commit to become quiescent with changing progress, then mutate.
A stale worker cannot write after those operations.

The worker starts after the first actionable prompt rather than behind it, and resumes from the
marker on the next session if interrupted. Retire the cap mechanism end to end: delete
`per_run_cap`, `max_entries`, their forwarding, the cap-only `paused` branch, and related copy.
Progress uses the shared status sink but S5 must add
the missing React event contract/reconnect terminal handling: start/progress are running;
complete/disabled/error are terminal. Headless emits a changing heartbeat during any >10-second
T113 call, not only every 25 records. T113 uses the existing live-provider child primitive; no
second retry loop. Its internal result distinguishes committed, deterministic honest-no-episode,
retryable/unavailable, and completed-invalid. The marker advances only for committed or
honest-no-episode; unavailable/invalid leaves that entry current for structural reissue or the
next authorized resume. This lifecycle is justified only by observed B13/#258 and is owner-gated
by D-TB-8/D-1; retryable HTTP also obeys D-TB-7/D-8.

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
- Do not resolve D-TB-1 here: collection policy remains owner-gated.

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

### C5 / S5 -- Prompt-first resumable backfill

Files: `main.py`, `core/npc/episodic_upgrade.py`, `core/npc/episode_backfill.py`,
`utils/capture/live_provider_call.py`, applicable headless/web status contracts and stores,
startup/provider/memory/web schematics, focused tests.

- Remove synchronous startup invocation and the complete `per_run_cap`/`max_entries` cap path,
  including forwarding and cap-only paused terminal.
- After D-TB-8, start/resume through the exact lifecycle-discoverable maintenance worker in 4.5.
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

### Owner-gated slices

Only after rulings:

- G1 / D-TB-1: implement exactly the chosen OOC collection policy using the existing batch
  future set; no third policy.
- G2 / D-TB-2: either execute the separately approved T045 retirement/migration plan or record
  the precise temporary waiver. This tranche does not improvise retirement.
- G3 / D-TB-3 and G4 / D-TB-4: execute only the ratified cap dispositions.
- G5 / D-TB-5: C1 and C7 may not change Save/Load/Reset waiting until the D-6 ruling.
- G6 / D-TB-6 and G7 / D-TB-7: C1/C3 may not cross the corresponding owner-open Part 5
  authority until the ruling is recorded.
- G8 / D-TB-8: C5 must ship and pass T113 acceptance before C4 may retire the startup legacy
  initializer; neither crosses D-1 without the ruling.
- G9 / D-TB-9: C1/C4 may not alter memory restore/migration/rendering until precedence and any
  compressed-only mapping are ratified.
- G10 / D-TB-10: C7 may not clear encounter data until the writer entrant/freeze audit is
  accepted; an uncovered T045 writer routes to D-TB-2.
- G11 / D-TB-11: C7 may not clear memory state until T108/T113 and every sidecar writer are
  lifecycle-discoverable and quiescent through their final commit.

## 6. GL-1 behavioral contract

| Existing behavior/goal | Disposition | Proof gate |
|---|---|---|
| Load selected save | PRESERVED and strengthened: no metadata refusal | A1 |
| Manifest helps diagnose provenance | PRESERVED as non-authoritative metadata | D1/A1 |
| Malformed optional sidecar never becomes trusted input | PRESERVED; recommended family-scoped loud omission is OWNER-GATED | D1/A1 negative control |
| Pre-feature saves remain loadable | PRESERVED | A1 |
| Save replay is idempotent | PRESERVED/fixed | A2 |
| Relationship event applies once per accepted turn | PRESERVED/fixed | A3 |
| Distinct equal-text turns remain distinct | PRESERVED/fixed | A3 |
| T105 packets are actor-isolated | PRESERVED/strengthened | A4 |
| Completed-invalid T105 degrades one beat | PRESERVED | A4 |
| Provider transport work structurally reissues | PRESERVED; HTTP extension OWNER-GATED | A4 |
| One canonical voice envelope | PRESERVED; fallback RETIRED | D4/A5 |
| Valid legacy compressed memory remains available | PRESERVED by forward import before renderer retirement | D4/A5 |
| One canonical memory renderer | PRESERVED; alternate renderer RETIRED after import | D4/A5 |
| Capability candidates reach T096 | PRESERVED; live matcher retained | D4/A5 |
| `assert_store_writable` loud corrupt-store goal (origin `a4cb6174`) | PRESERVED through `_latch_read_only`, `record_store_health`, and planned schema-reject health; zero-caller helper RETIRED | D3/D4 grep + A5 |
| Legacy compressed renderer compatibility (origin `b901d68c`) | PRESERVED through D-TB-9 selected-save forward adaptation; alternate render branch RETIRED | D4/A1/A5 |
| Unversioned combat envelope custom-caller compatibility (origin `82448d48`) | RETIRED under ratified Single-Path after all production producers are enumerated as versioned | D4/A5 |
| Startup legacy initializer (origin `f01bbc8e`): reconstruct old memories from journal | PRESERVED through canonical T113 backfill; runtime call RETIRED only after D-TB-8 plus C5 live acceptance, offline utility retained | D4/D5/A5/A6 |
| Dead cumulative-summary legacy memory block (origins `5d922597`/`fc775168`/`e2708c8c`): historical location-memory goal | Zero production callers; dead block RETIRED. Live goal remains owned by `main.py` T108 location-close seams | D4 call graph + A5 real boundary |
| Disabled transition legacy writers (origin `b7f7a863`, disabled `4b53aace`): recovery-compatible memory enrichment | PRESERVED by canonical async capture/backfill; unreachable bodies RETIRED while checkpoint `not_applicable` shape remains | D4/A5 legacy checkpoint replay |
| Legacy manager/compressor offline migration and verification | PRESERVED as non-runtime tools; zero production writer-call gate | D4 grep/import smoke |
| Raw legacy forward import (origin `7504a717`) | PRESERVED as the sole idempotent runtime migration adapter; compressed extension OWNER-GATED D-TB-9 | D4/A1/A5 |
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
- Malformed present sidecar negative control: under recommended D-TB-6, overall Load succeeds,
  unrelated saved state applies, D-TB-9's validated selected-save/empty result is installed,
  pre-Load knowledge does not survive, and omission is loud.
- Repeated `saveGame` against an existing completed folder, with before/after tree hash.
- Hold module-refresh and combat locks past their former deadlines: under recommended D-TB-5,
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

### D5 Startup/backfill matrix

- Zero, one, and many candidate markers.
- Prompt marker precedes any T113 call.
- Concurrent accepted input remains playable while backfill progresses.
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
- Focused tests plus `python -m pytest tests`.
- `tsc -b` and Vite build if touched paths affect the web bundle; otherwise record NOT-APPLICABLE.
- ASCII scan of additions, secret scan, schema/sidecar compatibility scan, imports, conflict markers,
  and `git diff --check`.
- No-Limits and Single-Path sentinel greps over every touched file and the branch diff.

## 8. Native Windows real-OpenAI acceptance

Every arm records the #193 v2.7 evidence block: pinned commit, actual command/surface, real
provider/model from capture, parsed request payload at its consumer, pre/post authoritative
state, player-visible stream, lifecycle/quiescence receipts, timing, and exact verdict. Synthetic
tests may support but cannot substitute.

### A1 Restore truth

Via native `run_headless.py serve`, Load an authentic pre-branch save and a copied current save
whose manifest/sidecar bytes were altered. Both requests are accepted and applied. Existing
companion memory follows D-TB-9 selected-save precedence: canonical, raw-only, compressed-only,
and no-memory fixtures receive separate disk/player-visible verdicts and never retain post-save
knowledge accidentally. A present malformed sidecar
follows D-TB-6; under the recommended ruling, the overall Load succeeds, unrelated saved state
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

### A6 Prompt-first backfill

Start an authentic save with many upgrade candidates. The actionable prompt appears before
T113. Submit a turn while visible progress changes. Play remains responsive, completed entries
persist once, and restart resumes remaining work with no cap or duplicate. Run a >10-second call,
an error terminal, reconnect hydration, and Save/Load/Reset/quit: browser and headless status must
change truthfully, terminate cleanly, and no stale worker may write after lifecycle mutation.

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
remains blocked rather than passing on the deterministic control.

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

## 9. Simplifier questions

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
- Player-Experience Reviewer: prompt-first, visible truthful progress/errors, no mechanical drift.
- Leanness Reviewer: reject new stores/ledgers/adapters/retry loops and challenge S5/S6 machinery.
- Schema/Platform Reviewer: JSON representations, cp1252/ASCII, Windows file replacement/locks.
- Legacy-Contract Reviewer: T045 boundary, forward compatibility, no unapproved legacy-only fix.

The controller alone edits this plan. Every finding gets one explicit resolution in the ledger
below. Re-dispatch affected and confirmation seats until one clean same-SHA pass. Implementation
remains blocked until convergence plus Claude/owner gate.

## 11. Decision and resolution ledger

| ID | Status | Decision / required evidence |
|---|---|---|
| D-TB-1 | OWNER-OPEN | OOC completion-collected vs best-effort |
| D-TB-2 | OWNER-OPEN | T045 retirement before merge vs temporary waiver |
| D-TB-3 | OWNER-OPEN | Top-three memory selection |
| D-TB-4 | OWNER-OPEN | Four-companion OOC selection |
| D-TB-5 | OWNER-OPEN | D-6: replace Save/Load/Reset lock deadlines with wait/queue + progress or waive |
| D-TB-6 | OWNER-OPEN | D-7: recommended malformed optional sidecar family-scoped loud omission |
| D-TB-7 | OWNER-OPEN | D-8: advisory retryable-HTTP structural reissue authority |
| D-TB-8 | OWNER-OPEN | D-1: lifecycle-discoverable T113 maintenance worker |
| D-TB-9 | OWNER-OPEN | Selected-save memory precedence and compressed-only compatibility mapping; recommendation in 4.1 |
| D-TB-10 | OWNER-OPEN | Accept complete Reset encounter-writer entrant/freeze proof; uncovered legacy writer routes to D-TB-2 |
| D-TB-11 | OWNER-OPEN | #198: lifecycle fence for every async T108/T113 companion-memory writer before Reset |
| R-TB-1 | RESOLVED | Preserve live `match_owned_capabilities`; ledger zero-caller claim disproven by code |
| R-TB-2 | RESOLVED-PROPOSED | Exact S5 worker lifecycle specified; owner D-TB-8 remains required |
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
| R-TB-17 | RESOLVED | Native A8 includes held/late encounter writer overlap and keeps D-TB-10 blocked if NOT-REACHED |

## 12. Tracked follow-ups

| Item | Disposition |
|---|---|
| #276 / #262-b | No-Limits caps in untouched files; separate follow-on |
| #278 | Closed only after S6 real no-Git-child proof |
| #279 | Encounter faction/identity owner; excluded from voice tranche |
| #280 | Closed only after S7 native Reset proof |
| #258 | S5 startup-backfill evidence source and closure target if fully resolved |
| #198 | Async episode-writer lifetime; D-TB-11 makes it an explicit Reset prerequisite |
| B21 | Owner-queued agentic death/down scene; no mechanics work here |
| B22 | Prompt-quality observation; no narration tuning here |
| B24 | Compressor progress observation; no pacing repair here |
| T045 retirement | D-TB-2 owner gate and separate approved retirement plan |

## 13. Stop conditions

Stop and return to owner/Claude before code if:

- any owner-open decision is required by an otherwise-authorized slice;
- an authentic old save/sidecar is baseline-valid but candidate-invalid;
- S5 needs a new persisted coordinator, deadline, or parallel retry engine;
- S6 cannot provide useful provenance without a Git subprocess and no ratified waiver exists;
- any slice changes combat mechanics, voice prose, player intent, or T045-only behavior;
- a new defect appears: capture evidence and file it separately before proceeding.
