# NPC Memory / Relationship Persistence — Master Structural Map

**Date:** 2026-08-18
**Branch:** `feature/npc-voice-redesign` (worktree `.worktrees/npc-voice-redesign`)
**Scope:** the complete NPC memory-persistence subsystem — how it is recorded, persisted,
applied to the main DM each turn, updated from gameplay, carried across lifecycle transitions,
and saved/restored.
**Why now:** the memory layer was deliberately built **thin and lightweight** because it is fed
to the main DM model *every turn* (a decision made to reduce per-turn overhead). Now that each NPC
has its own micro-voice model call (T105), the owner wants to **expand this memory to be richer,
more detailed, and more interesting**. This document maps the system exhaustively and enumerates
every structural constraint that bears on that expansion.

## How this map was produced (convergence method)

Blind, competing agents re-mapped the system in independent waves, each citing exact `file:line`
and quoting code; findings were cross-checked and the highest-stakes claims verified by hand.
Iteration continued **until two consecutive independent rounds surfaced no new structural findings.**

| Wave | Agents | Result |
|---|---|---|
| 1 — layer mapping | 3 (storage / application / update+lifecycle) | Baseline map + ~16 findings |
| 2 — blind full remap | 2 competing generalists | +6 new (incl. the combat-commit false-negative correction) |
| 3 — convergence check | 2 (write/schema/dedup · read/inject/concurrency) | +4 (M16–M19) and +6 (M20–M25); **not clean** |
| 4 — convergence round 2 | 2 (generalist · math/identity) | +4 (M26–M29) and +1 (M30); **not clean** |
| 5 — final convergence | 2 (whole-system · reproduce-or-refute newest) | **CONVERGED** — 0 new, M29 refuted/downgraded |

Total 30 findings (M1–M30). Several candidate findings were **refuted** during the process and are
recorded below so they are not re-raised. Hand-verified by the lead: M10, M11, M16, M17, M20, M28,
and the combat-commit wiring (M4).

---

## 1. End-to-end system map

The subsystem has **three layers** plus save/restore. All NPC memory lives in **one sidecar
document per game directory**: `data/companion_memories/npc_agent_state.json`, owned exclusively by
`core/npc/relationship_store.py` and validated against `schemas/npc_agent_state_schema.json`.

### 1.1 Storage layer — `RelationshipStore` (`core/npc/relationship_store.py`)

Single JSON registry keyed by identity UUIDs (not one file per NPC). Top-level shape
(`new_state_document()` :126–136; schema `required` :7):

```
schemaVersion(const 1) · revision(int) · identities{} · profiles{} ·
relationships{} · working{} · lifecycle{} · migrations{}
```

An NPC's record is spread across five maps, all keyed by the same UUID5 (`stable_identity_id`
:101–107, derived from `kind:normalized_sheet_path`):

- **`identities[uuid]`** — `kind`(npc/player), `displayName`, `aliases[≤32]`, `sheetPath`,
  `identitySeed`, `active`, `lastModule`, `lastLocationId`.
- **`relationships["subjId|cptyId"]`** — the affinity core, **directional** (`subject|counterparty`):
  `baseline`/`current` 5-axis vector, `lastDecayDay`, `evidence[≤256]`, `appliedEventIds[≤256]`,
  `appliedEventHistory`(256-bit Bloom bitset of pruned event ids), `aggregateCounts`,
  `evidenceHashChain`. Vector axes: `trust/power/respect ∈ [-1,1]`; `intimacy/fear ∈ [0,1]`.
- **`profiles[uuid]`** — static persona: `voice{cadence,diction,taboos}`, `goals[1-3]`, `fears[≤3]`,
  `values[1-5]`, `preferences[≤5]`, `boundaries[≤5]`, `conflictStyle`, `initiativeTendency`,
  `riskTolerance`, `protectionPriorities[≤3]`, `retreatRules[≤3]`, `arcSeeds[≤2]`, `sourceHash`.
- **`working[uuid]`** — volatile single-slot scratchpad: `currentPrivateIntent[≤300]`, `sourceTurn`,
  `currentGoalReference[≤300]`, `openQuestion[≤240]`, `moodTags[≤4]`, `expiresAfterTurn`, `sceneId`.
- **`lifecycle[uuid]`** — `status`(active/inactive) + `events[≤64]` (join/depart/rejoin/module with
  recruitment/departure context).
- **`migrations[key]`** — legacy `*_memories.json` import bookkeeping.

**Every write funnels through `_mutate()` (:263–299):** acquire `path_transaction_lock` (5s) →
re-read current doc inside the lock → deep-copy → run callback → bump `revision` → whole-document
schema-validate → `safe_json_dump` (unique temp file, `fsync`, atomic `os.replace`, parent-dir
fsync). No other code writes the file.

**Relationship math (`core/npc/relationship_rules.py`):** per-event deltas in `EVENT_DELTAS`
(14 event types), applied `current + delta*abs(magnitude)` then `clamp_state`; lazy exponential
decay `0.97**elapsed_days` toward `baseline`.

### 1.2 Application layer — per-turn context to the DM (T067)

**TWO distinct system blocks reach the main DM every substantive turn:**

| Block | Prefix | Built in | Source | Persistence |
|---|---|---|---|---|
| **Companion canonical context** | `=== ACTIVE COMPANION CANONICAL CONTEXT ===` | `conversation_utils.build_companion_memory_message` → `_canonical_context_row` (:398–423) | sidecar (persisted state) | baked into `conversation_history` after the system prompt, refreshed each turn |
| **NPC voice advisory** | `Private NPC intentions for the Dungeon Master only.` | `voice_context.inject_voice_context` (:1272) | live micro-model batch | injected post-compression before the last user msg; **redacted** from logs/durable history |

At the audited 2026-08-18 revision, the companion block was the lightweight persisted-
relationship summary and the voice block was the live advisory. Subsequent reviewed work retired
the documented character/cardinality loss points: current code preserves complete relevant
relationship evidence and packet text, while retaining only owner-ratified semantic selections.
The numeric vectors and private `working` map remain outside the canonical DM projection because
that is an authority boundary, not a size limit.

### 1.3 Update + lifecycle layer

**Update trigger (OOC):** `main.py:6146` (gated `NPC_VOICE_ENABLED`) → `run_ooc_voice_stage`
produces a batch (two isolated micro-calls: a thought call, and a classifier call **only if the
packet carries prior committed `relationshipEvidence`**) → after DM acceptance,
`main.py:6454 commit_accepted_ooc_voice_batch` → `store.apply_event` (if `affinity_event`) or
`store.update_working` (thought only) → `_mutate` → disk.
**Combat** is analogous and **is wired** (`combat_manager.py:4184 run_combat_voice_stage`,
`:4198`/`:4954 commit_accepted_combat_voice_batch`).

**Lifecycle:** recruit/depart via `action_handler.py:_apply_party_npc_lifecycle`
(`mark_joined`/`mark_departed` + `seed_profile_best_effort`); module transitions via
`campaign_manager.py:_update_npc_module_lifecycle_best_effort` → `mark_module_transition`
(3 call sites after `party_tracker.json` saves). A **departed NPC retains all affinity/evidence/
profile on disk** (only `working` is popped and `active` flips False); memory resumes on rejoin.

### 1.4 Save / restore

`data/companion_memories/` is an essential save artifact (copied by directory). A `state_manifest`
fingerprints the copied sidecar bytes (sha256 + byte-length + schemaVersion) and is validated
**before** any restore mutation (`save_game_manager.py:819`). `bootstrap.py` refuses to copy
private runtime (`.json/.lock/.tmp/.bak` under `data/companion_memories`) into fresh game dirs.

**Every hop from "a turn happened" to "bytes written" is best-effort / fail-open.**

---

## 2. Structural findings (M1–M30)

Severity is framed by the owner's goal (expanding memory richness) and by this codebase's
"dead-feature-behind-perfect-narration" doctrine. `[V]` = hand-verified by the lead.

### CRITICAL — expansion gate & identity integrity

**M1 — Any new schema field silently bricks all writes (THE central expansion blocker).**
`schemas/npc_agent_state_schema.json` sets `additionalProperties:false` on the root and **every**
`$def`, and `schemaVersion` is `{const:1}`. `_mutate` validates the *entire* candidate document and
skips the write (`return False`, `relationship_store.py:289–290`) on any error. Adding a field in
code without a coordinated schema + `SCHEMA_VERSION` bump makes every subsequent write a **silent
no-op forever**; a sidecar that *already contains* the new field fails the constructor's `_validate`,
`_repair_bounded_working_text` returns `None` for unknown damage, and the whole sidecar **latches
read-only** (:201) — memory silently stops persisting with only a debug log. **Expansion is not
incremental: it is a versioned migration touching the schema file, `SCHEMA_VERSION`, the relationship
math (for new axes/events), the prune cap, and the save `state_manifest` schemaVersion check in
lockstep — plus a forward-migration for existing sidecars (backward compatibility is mandatory).**

**M28 — Alias-driven sequential identity MERGE (two distinct NPCs become one).** `[V]`
`_resolve_existing_identity` (`relationship_store.py:301–330`) tries path-match first; on a miss
(e.g. a brand-new NPC, count 0) it falls back to display-name match against `_identity_names`,
which includes **all historical aliases** (:162–170). A new same-kind NPC whose `displayName`
equals another NPC's *past alias* resolves to that NPC's UUID — its lifecycle and edges are written
onto the other identity and their histories merge. The ambiguity guard (:328) only fires on
`len>1` *simultaneous* matches, not this path-miss→name-hit route. Richer, longer-lived rosters
with renames make collisions more likely.

### HIGH — silent data loss / dead-feature risk

**M2 — ≥8 fail-open swallowed-exception hops between "turn happened" and "bytes written."**
`run_ooc_voice_stage` (`voice_context.py:1158`), main stage guard (`main.py:6158`), commit per-result
(`voice_context.py:1245`), main commit guard (`main.py:6458`), `_mutate` inner + outer
(`relationship_store.py:291`,`:297`), validation reject (:289), lock-timeout silent drop (:275).
`apply_event` returns `mutated` but callers only do `committed += int(mutated)` — **`mutated=False`
is never surfaced or checked against disk.** A persistent write failure yields perfect narration and
zero persistence. (This is exactly the class that hid the `max_tokens=400` dead-feature last session.)

**M3 — Read-only latch is per-instance + sticky; stage and commit use *separate* store instances.**
No call site passes a shared `relationship_store=`; each constructs a fresh `RelationshipStore()`
(`voice_context.py:472/656/738/1172`, `conversation_utils.py:505`, `action_handler.py:955`,
`campaign_manager.py:113`, the commit sites). A mid-turn corruption latches the fresh commit
instance read-only → silent no-op commit while the already-staged batch was narrated. Also re-reads
and full-schema-validates the whole document **every turn** — O(document) cost that grows with a
richer payload.

**M16 — Legacy migration attests success while immediately pruning the imported summaries.** `[V]`
`migrate_legacy_identity` appends legacy `core_memories` as evidence with `gameDay=None`, calls
`self._prune_evidence(edge)` immediately, and records `migratedEvidence: imported_count` (the count
*appended*, not *survived*). `_prune_evidence` ranks `gameDay=None` records at the bottom of the
recency tier, so sub-magnitude-3 legacy summaries are the first evicted while the migration reports
full success and `_mutate` returns True. **Caveat:** only bites when the edge already exceeds 256
records; `magnitude==3` legacy records sort into the top tier and survive.

**M17 — Legacy evidence is decay-invisible while the edge it seeded decays.** `[V]`
Migration seeds `baseline`/`current` from the imported emotional state and sets `lastDecayDay`, but
the imported evidence carries `applied=False`/`delta=neutral`/`gameDay=None`, so it can never
re-apply. The migrated affinity decays toward baseline one-directionally while the evidence that
would justify any deviation is inert.

**M27 — `intimacy` and `fear` are effectively dead signal (2 of 5 axes).** `[V]`
Both are floored at 0 (`relationship_rules.py` BOUNDS :13–14), and every event pushes one up and the
other down (hostile: intimacy−/fear+; friendly: intimacy+/fear−). Because neither can hold a negative
reserve, the first opposite-polarity event re-pins the inactive axis at the 0 floor via `clamp_state`.
In mixed play both axes oscillate against 0 and rarely retain accumulated signal — half the affinity
model is near-inert.

**M30 — Combat voice lens is all-or-nothing; one over-budget combatant zeroes the whole window.**
`[V]` `build_combat_packets_for_window` (`voice_context.py:794–939`) has **no per-actor try/except**
(the OOC builder wraps each candidate in `try/except: continue`, :663–676), and `_fit_packet` /
`_shrink_longest` (`voice_packets.py:120–158`) can shrink only profile prose — **never** combat
`threats`/`capabilities`/`allies` (~7.8K un-reducible vs a 4800-char budget). A busy fight raises
`ThoughtContractError`, unwinds the loop, and `run_combat_voice_stage` returns `_empty_combat_stage()`
— silently losing say/do/want/thought **and affinity capture for every NPC in the window**.
*Fix parity:* give the combat loop the OOC per-actor guard and/or let threats/capabilities/allies
participate in `_fit_packet` reduction.

### MEDIUM — dedup / concurrency / integrity

**M4 — Combat rarely moves the affinity vector.** `[V]` Commit fires an affinity delta only when
`result.affinity_event is not None`, which requires the packet to carry prior committed
`relationshipEvidence`. Combat sets that only from a *previously committed* player-on-NPC fact, so
affinity lags one turn and the deciding turn (NPC saves the player, then combat ends) is often never
revisited — the highest-affect content persists to `working` only, not the vector. (Refinement: the
combat commit *is* wired — an earlier "unwired" suspicion was a false negative; dedup is per-edge so
the shared combat `beat_id` does not cross-block NPCs.)

**M5 — Bloom-filter dedup false-positives grow with history; content-blind event id caps granularity.**
`appliedEventHistory` is a 256-bit Bloom set keyed `int(event_id[:8],16)%256` (:172–181); once ~256
events age in, genuinely new events collide and are dropped as "duplicate." `_event_id` (:501–517)
hashes `[source_turn_id, subject, counterparty, prompt_version]` — **not** event content — so at most
one affinity delta persists per NPC/turn/pair. (Refinement: `source_turn_id` for OOC is a SHA over
the full conversation prefix+input, so identical phrasings on *different* turns do **not** collide —
the ceiling is per-turn only, not cross-turn.)

**M6 — Lock-timeout silent drop; no optimistic-concurrency; ambiguity swallowed.** On 5s lock-timeout
`_mutate` returns `(False,None)` and drops the write with no re-queue (:275). The `revision` counter
is monotonic-in-lock but there is **no CAS** — concurrent same-turn edits are last-writer-wins.
`ensure_identity`'s `ValueError("ambiguous stable identity")` (:329) is swallowed by the per-candidate
`except` in `build_ooc_packet_for_turn` → the NPC is silently dropped from the batch.

**M18 — Exact dedup channel shrinks to feed the lossy Bloom for long edges.** `_prune_evidence`
rebuilds `appliedEventIds` from the kept list only (:557–593), so once an edge crosses 256 records
the exact `event_id in appliedEventIds` test can no longer see evicted events — dedup authority
migrates from the exact array to the collision-prone Bloom (M5) as the *designed steady state* for
any long-lived relationship.

**M19 — Relationship-key schema pattern is looser than the identity-key pattern.** The relationship
key regex `^[0-9a-f-]{36}\|[0-9a-f-]{36}$` (schema :29) accepts any 36-char hex/dash blob, while
identity keys require a strict UUIDv5. `get_relationship`'s read path returns the edge with **no**
endpoint-registration check (that lives only in `_ensure_edge` on the write path), so a corrupt or
hand-edited orphan edge validates and is served to the packet composer.

**M20 — Flag-OFF is NOT byte-identical to `main`.** `[V]` The flag-off legacy block wraps its NPC list
in `filter_active_companion_memories` (`conversation_utils.py:347`), a function that **does not exist
on `main`** (verified: `main` iterates `for npc in memories['npcs']` with no roster filter). So with
`NPC_VOICE_ENABLED=False` the branch silently drops non-roster / departed NPCs that `main` would
inject. *This falsifies the "flag-off byte-identical" claim recorded during the redesign — corrected
in project memory.*

**M22 — Restore copies the whole save tree but the manifest validates only one listed path.**
`_validate_state_manifest` only checks entries whose path is the single hardcoded sidecar
(`save_game_manager.py:449–456`); restore `copy2`s every file under `data/companion_memories/`.
Unlisted injected files restore unchecked — the integrity gate is bypassable by omission.

**M23 — A save with no `state_manifest` key is accepted, skipping all sidecar integrity checks.**
`_validate_state_manifest` returns `True` when `manifest is None` (:445–446) — backward-compat for
pre-manifest saves, but combined with M22 any save that simply omits the key restores an arbitrary
sidecar with zero validation (low threat for single-player self-hosted; real for shared saves).

**M24 — The read path mutates under the same lossy lock; `snapshot()` is lock-free.** `get_working`
does read-then-`_mutate(clear)` on scene change/expiry (:766–792) — a **write on the read path**;
on lock contention the clear is silently dropped and a stale working slot feeds the next turn. Because
`snapshot()` takes no lock, the context builder and the voice stage (separate store instances) can
observe different revisions of the sidecar within one turn.

**M26 — Evidence records the *unclamped* delta while state is clamped (audit-vs-state divergence).**
`[V]` `event_delta` (`relationship_rules.py:75–85`) computes `raw*abs(magnitude)` with no reference
to bounds, while `apply_event_delta` clamps the actual change. Near a bound (e.g. `fear=0.05`, `heal`
mag 3) the state moves −0.05 but evidence stores `delta.fear=−0.06`. Anything reconstructing state by
summing evidence deltas drifts.

### LOW — thinness caps, minor bugs, fragilities

**M7 — `say`/`do`/`want` are never persisted.** They live only on the in-memory `NpcVoiceResult` and
are injected transiently; the commit persists only `thought`→`currentPrivateIntent`. The `workingState`
schema has no slot for them. Any "remember what the NPC said/wanted last turn" needs new schema fields.

**M8 — `working` is a single self-erasing slot, not a history.** One dict per NPC, erased on scene
change/turn-expiry, depart, module transition, and rejoin. No rolling window of prior intents exists.

**M9 — Lossy caps discard episodic detail.** Evidence hard-capped 256/edge; `_prune_evidence` folds
overflow into `aggregateCounts` + hash chain, **discarding the `summary` text**; `retrieve_evidence`
hard-clamps to 3 rows regardless of caller `limit` (:832); profiles are terse and array-capped.

**M10 — `retrieve_evidence` game-day tiebreak inversion.** `[V]` `-(game_day if isinstance(game_day,int)
else -1)` (:826): real days → large negatives (sort first), but `gameDay=None` → `+1`, sorting all
legacy/migrated evidence to the bottom of the 3-row window.

**M11 — Unwitnessed events consume the dedup slot without moving the vector.** `[V]` `witnessed=False`
returns the state unchanged but still appends a full record and consumes the `event_id`/`sourceTurnId`
slot (:706/721–722), so a later witnessed event on the same turn/pair is dropped as duplicate. Latent
today (one event per packet).

**M12 — `mark_joined` prior_status inference is order-dependent (rejoin/join mislabel).** Cosmetic;
requires `active` to be flipped True before the pre-mutation snapshot. Continuity-label only.

**M13 — Decay never runs without a full calendar date.** `game_day_ordinal` returns `None` unless
`worldConditions` has exact year/month/day, so an edge whose calendar is incomplete never decays.

**M14 — Save/restore hardcodes the single sidecar path + exact 4-key manifest shape.** Growing to
multiple files (per-NPC sidecars, an evidence log) silently won't be carried, and the manifest
validator rejects any added shape.

**M15 — Module transition wipes all `working` continuity for active NPCs.** Intentional scoping, but
it blocks cross-module continuity of intent.

**M21 — The always-on canonical context block emits the full profile unredacted into durable history.**
`_canonical_context_row` emits `profile` verbatim (fears/boundaries/retreatRules/arcSeeds), and
`redact_voice_context` only strips the *voice* prefix, so this block lands in `conversation_history.json`
and the diagnostics dump. *Mitigated:* it is removed-and-reinjected each turn (does not accumulate) and
`conversation_history.json` is API-side, not player-facing — DM-facing context, arguably intended.

**M25 — `messages_for_diagnostics` ordering is safe-by-luck.** Currently the pre-injection binding
protects the diagnostics dump if `redact_voice_context` throws, but a future line reorder would write
the private block to disk. Fragility, not a live defect.

**M29 — `ensure_identity` double-resolves (benign TOCTOU, no id divergence).** `[V, REFUTED as a defect]`
The resolve runs once against an unlocked `snapshot()` and again inside the locked `update()`, so a
TOCTOU *window* exists — but the write uses and returns the **locked** resolution, and when `_mutate`
fails nothing is written, so the returned UUID and the written UUID never diverge. Recorded as a
no-op observation, not a persistence defect.

---

## 3. Areas verified CLEAN (do not re-raise)

- **Delta signs / magnitude math** — all `EVENT_DELTAS` signs correct; max coefficient 0.18×3 cannot
  destructively overflow `[-1,1]` before the clamp.
- **Decay math** — `0.97**elapsed` is monotonic, non-oscillating, strict convex interpolation toward
  baseline; **backwards game-time is safely absorbed** (the `<=` guard no-ops, no corruption).
- **Directional keying** — `subject|counterparty` is always NPC-first; player→NPC is never created or
  read; no double-count.
- **`store_profile` is wired** (not dead code) in `seed_profile_best_effort`; `sourceHash` gating
  neither thrashes per-turn nor stale-locks after a sheet change; it does not mint identities.
- **Atomicity** — temp-file + `fsync` + `os.replace` + parent-dir fsync is correct; readers see
  whole-old-or-whole-new.
- **Telemetry** — `VoiceTelemetry` hashes all identifiers, carries no packet/thought/name/error text,
  and is best-effort by design; no leak.
- **Cache key / generation token** — `_cache_key` covers packet + prompt/schema versions + model
  config + provider + nested state digest; late results are correctly rejected; no stale-voice serve.
- **`apply_event` decay+event ordering** — decay applied before the fresh delta, same-day re-entry
  no-ops; distinct same-day events have distinct ids and each appends. No same-day event loss.
- **`voice_selection` ranking** — mention/evidence/least-recently-merged tiers with stable-id
  tiebreak; the name regex uses `re.escape` and selects *who speaks*, not game state (not a
  load-bearing prose-authority gate).

---

## 4. What this means for the expansion (owner's goal)

The memory infrastructure is **robust in mechanism** (atomic, locked, revisioned, hash-validated
across save/restore) but **every payload dimension is intentionally capped for lightness**. Making
memory richer is therefore not a data-volume tweak — it is a coordinated migration. The findings
sort into four workstreams for expansion:

1. **Unlock the schema safely (M1).** Bump `SCHEMA_VERSION` (`const:1`→`2`), add the new fields to
   `schemas/npc_agent_state_schema.json` *and* the save `state_manifest` schemaVersion check *and*
   the relationship math in the same change, and ship a **forward-migration** for existing sidecars
   (backward compatibility is mandatory — never render a live sidecar unusable). Without this, any new
   field silently bricks persistence.

2. **Add the substrate the new voices produce (M7, M8, M15).** `say/do/want` and a rolling
   intent/goal history have **nowhere to persist** today. Expansion needs new `working` (or a new
   dedicated) array field, plus a policy on whether it survives scene/module transitions.

3. **Raise the richness ceilings deliberately, and surface silent drops (M2, M9, M5/M18, M27, M30).**
   The 256-evidence prune discards summary text; retrieval is clamped to 3; two of five affinity axes
   are near-dead; the Bloom dedup degrades as history grows; combat loses the whole window on one
   over-budget packet. Each is a concrete cap to raise or redesign. **Critically, before shipping any
   richer feature, add a non-silent signal on the write path** — the pervasive fail-open (M2) means a
   richer feature can look perfect in narration while persisting nothing (the `max_tokens` lesson).

4. **The cheap seam for richer per-turn context (M20, M21, M24).** The single function
   `_canonical_context_row` (`conversation_utils.py:398–423`) is the whitelist that holds the per-turn
   companion context thin — the numeric vectors and `working` map are already assembled in the packet
   and merely un-projected. Because the voice micro-call now carries per-turn interiority, the historical
   reason for that thinness (per-turn overhead) is relaxed: richer standing context is additive edits at
   that one projection plus three numeric caps (`limit=4` :454, `recentEvents≥3` :204, `16000` :332).
   Fix M20 (flag-off roster-filter regression) and decide the M21 profile-in-durable-history policy as
   part of that work.

**Identity integrity (M28) and the migration seam (M16/M17) should be fixed regardless of expansion** —
they cause silent, hard-to-diagnose corruption of exactly the long-lived, rename-heavy, legacy-carrying
companions that a richer memory system is meant to serve.

---

*Produced by blind competing-agent iteration to convergence (5 waves, 11 agent-runs, two consecutive
clean rounds). Every finding cites `file:line`; the highest-severity claims were hand-verified.*
