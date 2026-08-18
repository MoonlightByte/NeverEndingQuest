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
- **Phase 1 — canonical ledger + presence stamping (dark).**
- **Phase 2 — POV overlays + code-derived salience/pinning.**
- **Phase 3 — default injection + grounding contract + player-claim fix.**
- **Phase 4 — agentic recall + acceptance harness (real vs fabricated tavern reference).**
- **Phase 5 — relationship depth (baseline reinforcement + anti-decay).**
- **Phase 6 — backfill existing campaigns from archives.**
- **Phase 7 — (deferred) local semantic retrieval for paraphrase-at-scale.**

## 8. Risks to watch
1. Presence accuracy at write-time (union roster + combat `creatures[]`, bias to inclusion).
2. Near-death from combat HP telemetry, not only the affinity classifier.
3. Migration transparency (Phase 0 gate asserts `read_only is False` on a real old save — DONE).

## 9. Deferred to later fine-tuning (owner)
Per-callsite model selection (voice/extraction/recall tiers), exact prompt wording, and the embedding
model choice (Phase 7).
