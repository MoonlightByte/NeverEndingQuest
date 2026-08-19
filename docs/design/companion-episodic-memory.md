# Companion Episodic Memory + Fragmented Compaction — Master Spec

**Status:** living spec. Phase 0 shipped; canonical data model in owner review.
**Branch:** `feature/npc-episodic-memory` (off `feature/npc-voice-redesign`).
**Companion docs:** structural map `docs/audits/2026-08-18-npc-memory-persistence-structural-map.md`;
approved plan `~/.claude/plans/reactive-cuddling-ladybug.md`; bugs issue #164.

---

## 1. Goal

NPCs become characters with **discrete episodic memory of their own journey**, so players form real
attachment. Acceptance bar (a tavern scene): the player says *"remember when we took down that wizard,
you almost died, then that clever move back in the Mountain of Chaos?"* — the NPC **genuinely recalls
it**. Hallucinating the memory OR blanking ("I don't remember") is a **FAIL**. The DM holds
general/canonical knowledge; each NPC holds a discrete, emotionally-salient slice — a fork of the
compaction system into per-character POV.

## 2. Ground truth (mapped this session; do not re-derive)

- **Fidelity is preserved.** Full per-module conversation history is archived permanently to
  `modules/campaign_archives/{module}_conversation_NNN.json`, never deleted. On **return** to a module
  the full archive is **rehydrated** (`conversation_utils.py:698-710`), not the lossy summary; on leave,
  T038 re-summarizes from full history — never summary-of-summary. → **The full-fidelity source is
  always on disk.** Episodes can be regenerated from archives, and existing campaigns can be backfilled.
- **Compaction fork point:** Layer A per-location summary (`cumulative_summary.py:235`).
- **Attribution gap:** the only structured "who was present" signal is combat `creatures[]`; roster
  history is destructively overwritten. → presence must be **stamped at write-time going forward**.
- **Reused plumbing:** `core/npc/*` voice/memory stack; sidecar `data/companion_memories/
  npc_agent_state.json`; injection via `build_companion_memory_message`. Buried substrate to revive:
  `core/memories/companion_memory.py` (max-5 core-memory crystallizer).

## 3. Owner decisions (locked)

1. **Retention:** bounded + pinned — high-salience beats never fade; routine ages out but is
   recoverable from the permanent archive.
2. **Existing saves:** backfill from archives (one-time agentic pass).
3. **Relationship depth:** include now (episodes reinforce intimacy/fear baseline + soften decay).
4. **Extraction timing: BOTH** — per-location extraction during play (live, growing memory inside a
   module) AND a module-leave consolidation over the full module archive (the authoritative "full
   profile" guarantee: reconcile/finalize/de-dupe each companion's salient facts).
5. **Persona and lived memory stay SEPARATE layers.** Persona (voice/goals/fears, recruit-seeded via
   T107) is never overwritten by memory. Lived memory (salient facts / episodes) accumulates
   separately. A companion's "full profile" = persona + pinned core memories + relationship state,
   presented together. Salient facts *nudge* relationship tendencies (via the affinity layer) but do
   not rewrite seeded persona fields.

### Empirical validation (2026-08-18, real Keep_of_Doom/Thornwood archives)
- The production T018 location summary **drops attachment beats and their attribution** on real data:
  Kira's "Trouble Magnet" lean and Thane's reassuring-hand-on-shoulder + "that's what Kira would want"
  were absent/flattened; and shipped `campaign_summaries` already **scramble attribution** ("Trouble
  Magnet" drifts Eirik→Elen; nickname collisions) — T038's "Enrich and Extrapolate" reattributing.
- A **per-character extraction on the same raw scene with the SAME model** recovered those beats with
  correct attribution. So the fix is the **lens/prompt against full-fidelity text**, not model power
  or a duplicated pipeline. The present-companions guard held on real data (Elen, only mentioned,
  correctly got no memory).
- **Model designated: `luna|low`** (`gpt-5.6-luna`, reasoning_effort=low) for the extraction callsite —
  sampled none/low/medium on the real scene; all correct, quality climbs with effort; low is the
  cost/quality balance for an infrequent per-location call. Final effort to get a blind 3-reviewer eval
  in the fine-tuning pass (cf. T026). Harness: `scratchpad/luna_extract_probe.py`.

## 4. Architecture (two-tier, agentic-first / reconcile-by-code)

- **Canonical shared episode ledger** — NEW file `data/companion_memories/episode_ledger.json`, NEW
  `core/npc/episode_store.py`, NEW `schemas/episode_ledger_schema.json`. One row = one real event, the
  **shared truth**; all NPCs reference it, so they can never contradict each other or the DM. Separate
  file keeps the sidecar's version transition off the canonical path.
- **Per-NPC POV overlay** — additive `episodes[]` on the relationship edge in the sidecar (schema v2
  container already shipped in Phase 0b). A cheap **delta**, not a re-summary: emotional tag + salience
  **derived by code** from already-classified affinity events + combat telemetry, plus one generated
  first-person line.
- **Presence stamping (forward):** per-turn accumulator (active `partyNPCs` at the OOC voice stage +
  authoritative combat `creatures[]`) keyed by `(module, locationId)`, flushed at the Layer A boundary.
- **Extraction pass (the specific-memory capture — replaces the dead `companion_memory.py` verb-list
  crystallizer):** ONE structured `luna|low` call per boundary — covering ALL present companions at
  once (not one call per companion) — reading the **full-fidelity encounter text**, NOT the lossy T018
  output. Emits attributed atoms (`Kira → dropped 5g in wishing well "for luck"`). Runs at TWO seams:
  (a) **per-location close** (Layer A boundary, raw turns present) for live memory; (b) **module-leave
  consolidation** over the full module archive (T038 seam) for the authoritative full profile. Plus
  combat HP telemetry for near-death. Present-companions guard + reconcile-by-code against stamped
  `witnessIds` (a companion merely *mentioned* by another gets no memory). Deep recall of anything not
  pre-captured is backed by RAG over the archived full history.
- **Retrieval (grounded; model parses, code selects):** default = inject each NPC's top-K pinned/
  high-salience episodes (0 calls); recall = a micro-call parses the player line into anchors, **code**
  selects matching `episodeId`s from the NPC's fixed index (can't invent one). Embeddings deferred.
- **Grounding contract:** closed-world — NPC states as memory ONLY what is injected; vivid → recall,
  partial → hedge the rest, absent → in-character uncertainty, never fabricate. DM won't attribute a
  shared memory unless it's in that NPC's recall block. Player claims are marked *unverified*, never fed
  as scene truth.
- **Relationship depth:** high-salience episodes reinforce the relationship **baseline** + soften decay.

---

## 5. Data model (PROPOSED — decisions Dn flagged for owner sign-off)

### 5.1 Canonical episode ledger — `data/companion_memories/episode_ledger.json`

```
{
  "schemaVersion": 1,
  "revision": <int>,
  "ordinalCounter": <int>,            # monotonic; source of `ordinal`
  "episodes": { "<episodeId>": <CanonicalEpisode>, ... }   # keyed by episodeId
}
```

**CanonicalEpisode**

| field | type | purpose / notes |
|---|---|---|
| `episodeId` | string | **[D1]** deterministic id from STABLE COORDINATES `uuid5(module\|locationId\|boundaryTurnId)` — NOT content. Stable across re-summarization; idempotent for backfill. (Respects "no content-hash as identity.") |
| `ordinal` | int | monotonic write order → stable chronological sort even when `gameDay` is null (fixes the M10 null-day sort bug). |
| `module` | string ≤160 | where. |
| `locationId` | string ≤120 | area id (e.g. `RO01`). |
| `locationName` | string ≤160 | human place name — a retrieval anchor ("Mountain of Chaos"). |
| `gameDay` | int \| null | in-world day ordinal (null if calendar incomplete). |
| `boundaryTurnId` | string ≤120 | the transition/turn that closed the segment (ordering + id seed). |
| `headline` | string ≤100 | short label ("Defeated the sorcerer Vheshk"). |
| `canonicalSummary` | string **[D2] ≤600** | the shared-truth prose, derived from the Layer A summary. The ONLY factual authority at recall time. |
| `salientFacts[]` | array ≤8 of SalientFact | structured emotional/event atoms (the recall hooks). |
| `entityTags[]` | array ≤12 string ≤60 | normalized retrieval anchors ("wizard", "boss:vheshk"). |
| `witnessIds[]` | array of identity-UUID | who was present/party — scopes per-NPC POV. |
| `intensity` | number 0..1 | intrinsic event weight (seeds POV salience). |
| `derivedFrom` | enum | `location_summary` \| `combat_telemetry` \| `backfill`. |
| `sourceHash` | string(64) | change-detection of the source window (re-extract if it changed). Provenance aid, NOT gameplay authority. |
| `promptVersion` | string ≤40 | extraction prompt version. |

**SalientFact** — **[D3]** the emotional/event vocabulary:

| field | type | purpose |
|---|---|---|
| `kind` | enum | Two families. **EVENTS** (what happened): `defeat`, `near_death`, `rescue`, `protect`, `sacrifice`, `loss`, `discovery`, `vow`, `betrayal`, `victory`, `defeat_suffered`, `first_meeting`, `reunion`. **TEXTURE** (who they are / the bond — validated on real data): `bond`, `tender`, `joke`, `fear`, `vulnerability`, `habit`, `gift`, `confession`. The real luna run emitted exactly the texture kinds — they carry the attachment, and T018 drops them. |
| `subject` | `{id?: uuid, label: str≤80}` | who acted (identity id if a tracked character, else a free label like "the sorcerer Vheshk"). |
| `object` | `{id?: uuid, label: str≤80}` | to/for whom (nullable). |
| `oneLine` | string ≤120 | the atom in words ("Kira dropped the chandelier on the sorcerer"). |

### 5.2 Per-NPC POV overlay — sidecar `episodes[<npcId>] = [PovEpisode, ...]`

**PovEpisode** (the cheap delta; strict item schema tightens the Phase-0b container)

| field | type | purpose |
|---|---|---|
| `episodeId` | string | FK into the canonical ledger. |
| `povTag` | enum | **[D4]** how THIS NPC holds it: `proud`, `triumphant`, `traumatic`, `tender`, `guilty`, `grieving`, `resentful`, `afraid`, `grateful`, `protective`, `amused`, plus romance set `smitten`, `longing`, `heartbroken`. Code-derived from linked affinity events + telemetry. |
| `salienceScore` | number 0..1 | code-derived personal weight (drives pinning + recall ranking). |
| `pinned` | bool | high-salience → never pruned (bounded+pinned retention). |
| `personalLine` | string ≤160 | ONE generated first-person fragment ("I put myself between her and the blast"). The only generative per-NPC product. |
| `linkedEvidenceIds[]` | array ≤8 | FK to affinity `evidence.eventId` that occurred in this segment. |

**Consistency guarantee:** a PovEpisode NEVER restates canonical facts — at injection it is rendered
*against* its `canonicalSummary`. An NPC can feel differently but cannot invent a different outcome.

---

## 6. Decisions — LOCKED (2026-08-18)

- **[D1] episodeId = stable coordinates** `uuid5(module|locationId|boundaryTurnId)`, not content →
  idempotent on revisit + safe backfill. LOCKED.
- **[D2] canonicalSummary ≤600 chars.** LOCKED (adjustable knob).
- **[D3] SalientFact `kind`** = the two-family vocabulary in §5.1 (Events + Texture). Texture kinds
  validated on real data. LOCKED (redline the enum anytime).
- **[D4] POV `povTag`** = the set in §5.2 incl. the romance extension. LOCKED (redline anytime).
- **Granularity:** one episode per LOCATION segment; combat near-death is a `salientFact` inside it.
  LOCKED.

## 7. Phases (sequence-only; each headless-validated on-disk)

- **Phase 0 — DONE.** Fail-loud persistence + v1→v2 migration framework + M28 identity fix. Commits
  `fea16428`, `a4cb6174`. 107/107 npc suite.
- **Phase 1 — DONE.** Canonical ledger + extraction + LIVE capture wiring.
  - 1a store (`1736380e`), 1b T108 callsite luna|low (`e0be8fbb`), 1c extraction service (`975f8d7a`).
  - 1d live per-location capture (`411e9c45`) + position-based boundary (`1e554d45`) + module-leave
    final-location consolidation (`b164fc31`) + ledger save-manifest (`8f16d7b7`). 124/124 npc suite;
    validated end-to-end on real archives through the real luna model.
  - **Deferred (documented):** the startup-backfill hook (`check_and_compact_missing_summaries`
    summarizes *arriving* locations — needs arrival-vs-leaving position reconciliation to avoid a
    coordinate mismatch with live capture; edge case: mid-location save/reload). And Phase-6 backfill
    of pre-stamp archives (no `Party NPCs:` presence stamp before that engine change).
- **Phase 2 — DONE** (`pov_overlay.py`, `7817009d`). POV overlays + code-derived povTag/salience/
  pinning + bounded+pinned retention. *Simplification vs R7:* salience is the 2-term form
  (`w_intensity*intensity + w_kind*kindWeight`); the affinity-delta term and `linkedEvidenceIds`
  population are deferred to Phase 5. `personalLine` is the fact's line verbatim (third-person), not a
  generated first-person line — a deliberate no-model-call choice.
- **Phase 3 — DONE, default injection only** (`conversation_utils.py`, `7f37d097`). Top pinned/salient
  memories injected into the companion context each turn. The closed-world **grounding contract** (R9
  prompt) and the **player-claim fix** are NOT yet in the prompt surface — they land in Phase 4b.
- **Phase 4a — DONE** (`episode_recall.py`, `713c1c6f`). T112 recall service; real-luna acceptance
  harness passes (real recalled / fabricated absent / presence-negative not leaked).
- **Phase 4b — DONE** (`conversation_utils.py`, `<this commit>`). Closed-world grounding contract
  prepended to the memory-carrying companion block; targeted recall wired (one T112 anchor-parse/turn,
  skipped when no present NPC has episodes, code-selected per NPC as a `recalled` field). Validated
  through the REAL DM model: real reference recalled + grounded; fabricated reference hedged, no
  confabulation. The contract also serves as the player-claim defense at the authoritative DM layer.
  *Residual (defense-in-depth, low priority):* mark the raw player claim `unverified` inside the voice
  packet (`voice_context` beat.summary/scene.stakes) too — the DM layer is already grounded.
- **DEFERRED (explicitly, so it is not silently missing): R8 near-death combat telemetry + combat-path
  episode capture.** Episodes are captured at location-close + module-leave only; combat beats are
  captured only if they fall inside a location segment. The `combat_telemetry` `derivedFrom` value +
  `near_death` kind exist but have no producer yet. Near-death currently depends on the T108 extraction
  noticing it in prose. Build in a later phase or keep deferred.
- **Phase 5 — DONE** (`relationship_rules.py`/`relationship_store.py`/`episode_capture.py`). Pinned
  memories reinforce the NPC→player baseline (`baseline_from_pinned` + `reinforce_baseline_from_pov`),
  so decay settles the bond at a memory-justified level — the M27 dead-axes fix. Pure/idempotent; only
  pinned peaks move it. Validated: store test + real-luna end-to-end (a pinned near-death elevates
  intimacy/fear baseline). *Deferred within P5:* the `linkedEvidenceIds`↔affinity-evidence linkage +
  R7's affinity-delta salience term (traceability nicety; baseline works without it). Anti-decay
  softening (0.99 vs 0.97) not needed — an elevated non-zero baseline already makes bonds stick.
- **Phase 6 — backfill existing campaigns from archives.**
- **Phase 7 — (deferred) local semantic retrieval for paraphrase-at-scale.**

## 7b. Blind-review resolutions — closing the plan before live wiring (2026-08-18)

Three blind reviewers (correctness / completeness / integration-seam) validated the work + plan.
One CRITICAL code bug was fixed (`commit_episode` reported success on failed writes — now a 3-state
outcome, commit `5fdc2567`). The remaining gaps are DESIGN, resolved here so 1d is buildable:

**R1 — Identity resolution BEFORE extraction (the #1 integration landmine).** `witnessIds` requires
strict identity UUIDs; `partyNPCs` entries are display names. So the wiring MUST, at the boundary,
resolve each present companion name→UUID via `RelationshipStore.ensure_identity(kind="npc",
display_name=…, sheet_path=…)` (the canonical system the voice feature already uses) and pass
`present_companions=[{name,id}]` with resolved ids. A companion whose id can't be resolved is SKIPPED
(never passed with a null id). **Fail-loud:** if present companions exist but the resolved witness set
is empty, emit `record_store_health("episode_no_witnesses", …)` — never commit a witness-less episode
silently (that is the blank-recall failure mode).

**R2 — `boundaryTurnId` = the close-time world clock, not a content hash.** There is no turn id in the
transition marker. Use the `worldConditions` game-day+time scalar captured at location close
(`scalar_from_calendar` / the value behind `game_day_ordinal`) as `boundaryTurnId`. It is stable within
a visit (idempotent re-summarization → same episodeId) and advances across revisits (distinct
episodeId), so `uuid5(module|locationId|boundaryTurnId)` no longer collides on revisit. If the clock is
unavailable, fall back to the transition's position index in history (still coordinate-derived).

**R3 — Presence union by scanning the segment, not reading the boundary.** `partyNPCs` at close ≠ the
visit union, and combat `creatures[]` is unreachable at close. Reuse the existing per-turn engine stamp
`Party NPCs: {…}` written into every DM note (`main.py:6076/6085`) and already parsed by
`voice_context._source_turn_witnessed` (`voice_context.py:88`): the witness union = the union of
`Party NPCs` across the segment's user messages (covers combat turns too, since they carry the stamp).
No new per-turn write state.

**R4 — Hot-path is engineered, not assumed.** The location-close seam (`main.py:2316-2336`, between
`generate_enhanced_adventure_summary` at :2318 and `compress_conversation_history_on_transition` at
:2333) is synchronous and player-blocking with no async harness. The extraction call runs BEST-EFFORT
and OFFLOADED (background thread/queue), inside the outer try (`main.py:2316`), MUST NOT mutate
`conversation_history`/`compressed_history`, and never gates the summary return. It reads the raw
segment (still present before :2333). A throw or slow call can never affect the summary or the turn.

**R5 — Cover both close paths + safe module-leave placement.** Wire BOTH `check_and_process_location_
transitions` (live) and `check_and_compact_missing_summaries` (startup backfill of un-summarized
transitions), or startup-closed locations get no episode. The module-leave consolidation runs at the
T038 seam (`campaign_manager._generate_module_summary`, full archive available at :3184-3191) but ONLY
after the T038 summary is committed and OUTSIDE the archive/checkpoint critical section (a throw there
aborts module completion), wrapped fail-open.

**R6 — Ledger integrity manifest (before Phase 6 backfill).** `episode_ledger.json` is saved/restored
as a `data/companion_memories/` directory file, but `state_manifest` only allow-lists
`npc_agent_state.json` and rejects a second path (`save_game_manager.py:449-456`). Add
`episode_ledger.json` to the allow-list + fingerprint it, so the shared-truth ledger is integrity-checked
on restore. Small, required before backfill ships ledgers users save.

**R7 — POV/salience derivation (Phase 2) is a concrete formula, not a hand-wave.**
- `povTag` ← a fixed map from the linked affinity `eventType` + telemetry to the tag set (e.g.
  protect/rescue→`protective`; the actor's own near_death→`traumatic`; heal/give→`grateful`;
  betray/abandon→`resentful`; share/trust bonding→`tender`; victory/defeat→`proud`/`triumphant`).
- `salienceScore` ∈ 0..1 = clamp( `w_intensity*canonical.intensity` + `w_evt*max(|affinity delta|)` +
  `w_kind*kindWeight(salientFact.kind)` ). `pinned` = `salienceScore >= PIN_THRESHOLD` (e.g. 0.6) OR
  `kind ∈ {near_death, sacrifice, betrayal, confession, first_meeting}` (always-pin peaks).
- All code-derived from already-classified events → idempotent, no model authorship.

**R8 — Near-death telemetry has a concrete producer.** `combat_manager` observes a party/NPC HP crossing
a near-zero threshold (e.g. ≤ max(1, 10% max HP)) during a fight and stamps a `combat_telemetry`
salient fact (`kind:near_death`, subject = that NPC id) into the presence/segment accumulator, so the
location-close extraction folds it into the episode independent of whether the classifier fired. This is
what makes "you almost died" recall real.

**R9 — Retrieval + injection + grounding contract (Phases 3-4), specified.**
- *Default (0 calls):* extend `_build_canonical_companion_context_message` (`conversation_utils.py:426`)
  to append each active NPC's top-K episodes by `(pinned desc, salienceScore desc, ordinal desc)` from
  `episodes_for_witness(npcId)`, rendered as `episodeId + headline + the NPC's personalLine`, under a
  per-turn char budget shared with the existing companion block.
- *Recall (bounded call):* a NEW callsite (propose **T112**, luna|low, gated) parses the player's line
  into anchors (entities/place/outcome) as structured JSON; CODE selects matching `episodeId`s from that
  NPC's fixed index via lexical match over `entityTags` + `locationName` + `salientFacts.oneLine` (no
  embeddings in v1; Phase 7 adds them). Only the NPC's own `episodes_for_witness` set is searchable.
- *Grounding contract (an actual prompt fragment, not prose):* "You may state as memory ONLY facts in
  the RECALLED EPISODES block below. Vivid if present; hedge the unmatched part; if empty, stay
  in-character uncertain ('remind me…') and NEVER invent a shared past." Paired DM-side rule: the DM
  won't attribute a shared memory to an NPC unless it's in that NPC's recalled block. Player claims are
  marked *unverified*, never fed as scene truth.

**R10 — Module consolidation behavior = idempotent re-emit.** The module-leave pass re-runs the SAME
per-location extraction over the full archive and re-commits with the SAME coordinate episodeIds
(update-in-place, ordinal preserved) — it reconciles/completes, it does not mint a separate module-level
row. The "full profile" is an ASSEMBLER (persona ⊕ pinned POV memories ⊕ relationship state) rendered
together; persona fields are never overwritten by memory.

**R11 — Retention.** The canonical ledger is NOT pruned (it is the shared truth, small, archive-backed).
Boundedness lives in the per-turn INJECTION (top-K) and the per-NPC POV overlay (bounded+pinned): pinned
peaks never drop, routine POV rows age out under a cap, recoverable by re-deriving from the archive.

## 8. Risks to watch
1. Presence accuracy at write-time (union roster + combat `creatures[]`, bias to inclusion).
2. Near-death from combat HP telemetry, not only the affinity classifier.
3. Migration transparency (Phase 0 gate asserts `read_only is False` on a real old save — DONE).

## 9. Deferred to later fine-tuning (owner)
Per-callsite model selection (voice/extraction/recall tiers), exact prompt wording, and the embedding
model choice (Phase 7).
