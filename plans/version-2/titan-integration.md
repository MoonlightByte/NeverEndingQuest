# NEQ v2 Titan Integration Plan

Status: Strategic integration plan for next-version rebuild (post-v1 testing)
Date: 2026-02-26
Owner: NEQ MP TTRPG architecture (OpenRouter + EGO + world-narrative + memory + seeding)
Scope: Integration umbrella for existing plans and OpenSpec drafts

---

## 1) Purpose

This document defines the v2 integration blueprint that unifies:

1. OpenRouter model routing (including free models with thinking where available)
2. EGO background analysis loops
3. World-narrative interpreted state in `data/memory.db`
4. Runtime monster/NPC declaration and seeding pipelines
5. Module-builder continuity and long-horizon world pressure

This is an umbrella plan, not an implementation commit for v1.

---

## 2) Design intent for v2

The v2 narrative engine uses a Pantheon conceptual model to drive long-range world pressure:

- Background cycles run while the game server is active.
- Each cycle chooses one Titan identity and analyzes current relational state.
- The Titan proposes world-pressure updates (local, regional, world), not mechanical changes.
- Python remains the only authority for game mechanics and legal outcomes.

Core rule:

`Python enforces reality; Titan/EGO interprets and applies narrative pressure.`

---

## 3) Pantheon multiverse conceptual model

### 3.1 Titan families

Three Titans of Order axis:

1. Titan of Law (`L-`): draws power from lawful relationships
2. Titan of Chaos (`C-`): draws power from chaotic relationships
3. Titan of Balance (`N-order`): draws power from order-axis equilibrium

Three Titans of Morality axis:

1. Titan of Good (`-G`): draws power from good relationships
2. Titan of Evil (`-E`): draws power from evil relationships
3. Titan of Fate (`-N-fate`): draws power from pragmatic moral neutrality

### 3.2 Lore positioning

Titans are primal forces above mortal and divine planes.
They do not directly roll dice or change HP/AC/conditions.
They influence world narrative through Gods, Demons, factions, institutions, and social pressure.

### 3.3 Why this maps well to NEQ

It matches existing architecture split:

- Mechanical truth (Python): deterministic and validated
- Interpretive truth (LLM + world model): pressure, consequence, continuity

---

## 4) Non-negotiable boundaries

1. No Titan process may write mechanical state (`hitPoints`, `armorClass`, slots, conditions, initiative, encounter legality).
2. Titan process writes interpreted narrative state only.
3. Titan process is fail-open for gameplay (server continues if Titan worker fails).
4. Copyright firewall remains active:
   - local raw sources only under `/user_uploads/text/`
   - no source-identifying metadata in committable narrative outputs
5. Creation/materialization of monsters/NPCs must remain declaration-gated.

---

## 5) Runtime scheduler contract

### 5.1 Cadence

- Run one Titan cycle every 10 minutes while server is active.
- Worker starts at server boot, stops cleanly at server shutdown.
- If prior cycle is still running, skip the overlapping tick (no concurrent cycles).

### 5.2 Selection

- Random Titan selection from 6 IDs per cycle.
- Store selected Titan and cycle metadata in DB for audit and replay.
- Optional deterministic seed mode for testing (`TITAN_RANDOM_SEED`).

### 5.3 Operational guarantees

- Timeout-bounded model call.
- Max retries per cycle (small bounded count).
- Backoff after repeated failure.
- Never block `user_input` loop or combat progression.

---

## 6) OpenRouter model strategy for Titan cycles

### 6.1 Target behavior

- Use OpenRouter free model tier for Titan cycles.
- Enable thinking mode when profile/model supports it.
- Keep this worker cost-capped and isolated from main gameplay model routing.

### 6.2 Config contract (v2)

Add dedicated config keys (names can be finalized during implementation):

- `TITAN_ENABLED = True`
- `TITAN_INTERVAL_SECONDS = 600`
- `TITAN_MODEL = "<provider/model>:free"`
- `TITAN_ENABLE_THINKING = True`
- `TITAN_MAX_TOKENS = <bounded>`
- `TITAN_TIMEOUT_SECONDS = <bounded>`
- `TITAN_FALLBACK_MODE = "none|openai"`

Recommendation for v2 initial rollout:

- `TITAN_FALLBACK_MODE = "none"` so Titan cycles simply skip on provider failure (no paid surprise costs).

---

## 7) Memory DB extension for Titan integration

Use additive migration pattern in `data/memory.db`.

### 7.1 New/extended interpreted-state tables

1. `entity_alignment_state`
   - `entity_id`
   - `alignment_5e` (one of 9 alignments)
   - `order_axis` (`lawful|neutral|chaotic`)
   - `morality_axis` (`good|neutral|evil`)
   - `confidence`
   - `updated_at`

2. `relationship_alignment_edges`
   - `edge_id`
   - `entity_a`, `entity_b`
   - `relation_type` (ally, rival, patron, subject, oath, debt, etc.)
   - `strength` (numeric)
   - `order_score` (negative chaotic .. positive lawful)
   - `morality_score` (negative evil .. positive good)
   - `evidence_event_id`
   - `updated_at`

3. `titan_cycle_log`
   - `cycle_id`
   - `titan_id`
   - `model_id`
   - `status` (`success|skipped|failed`)
   - `started_at`, `finished_at`
   - `error_summary`

4. `titan_pressure_snapshots`
   - `cycle_id`
   - `titan_id`
   - axis metrics and computed "power" snapshot
   - top contributing relationships
   - summary text (bounded)

5. `world_history_lines`
   - `line_id`
   - `scope` (`local|regional|world`)
   - `proposed_text`
   - `status` (`proposed|approved|applied|rejected`)
   - `source_titan_id`
   - `source_cycle_id`
   - `created_at`, `applied_at`

### 7.2 Existing tables reused

- `campaign_world_model`
- `campaign_world_delta`
- `memory_events`
- `memory_links`

Titan cycles should primarily emit into `campaign_world_delta` and `world_history_lines`.

---

## 8) Titan output contract (strict JSON)

Each Titan cycle should produce deterministic JSON sections:

1. `alignment_snapshot`
   - current axis state relevant to Titan identity

2. `relationship_findings`
   - top relationships that increase/decrease Titan influence

3. `history_line_proposals`
   - `local`: immediate consequences (town rumors, summons, warrants, cult whispers)
   - `regional`: module-level political/military/faction reactions
   - `world`: broad shifts (alliances, theological tensions, trade disruptions)

4. `entity_pressure_suggestions`
   - suggested NPC/faction pressure tags
   - no direct spawn/mechanics instructions

5. `confidence_and_risk`
   - confidence score
   - risk tags (contradiction risk, stale-data risk)

Any output outside schema is discarded.

---

## 9) EGO integration model

In v2, Titan cycle acts as a themed EGO background process for world narrative, while preserving EGO governance principles.

### 9.1 Role of EGO in Titan mode

- Classify drift between world model and recent canon events.
- Select Titan identity.
- Generate interpreted proposals only.
- Write proposals and logs for review/apply.

### 9.2 RATIO role (later phase)

- Analyze multi-cycle trends.
- Merge/curate repeated Titan proposals.
- Propose broader world-model deltas.
- Gate medium/high-risk world shifts behind review.

---

## 10) Module builder integration

Module generation should consume approved/applicable world pressure, not raw Titan cycle logs.

### 10.1 Builder inputs

- latest `campaign_world_model`
- active `campaign_world_delta` where `applied=1`
- recent `world_history_lines` where `status in (approved, applied)`
- relevant relationship pressure near target module/region

### 10.2 Builder outputs

- module hooks reflecting Titan-influenced world pressure
- module seeds for local factions/NPCs/conflicts
- continuity links back into world model tables

---

## 11) Monsters and NPCs integration

Titan influence can suggest pressure events but cannot bypass declaration gates.

### 11.1 Declaration flow

1. Titan proposes narrative pressure (for example: royal summons, punitive expedition, cult retaliation).
2. System converts approved proposal into declaration artifacts (trusted sources).
3. Existing seeding pipelines materialize monsters/NPCs from declarations.
4. Runtime encounter creation remains fail-closed for undeclared entities.

### 11.2 Safety principle

`No declaration -> no generation.`

This preserves anti-hallucination guarantees from existing monster/NPC plans.

---

## 12) Suggested v2 build sequence (full rebuild)

### Phase A: Foundations

1. Finalize router facade and task-level model profile routing.
2. Add Titan worker framework (scheduler, lock, lifecycle hooks).
3. Add DB migrations for Titan/relationship tables.

### Phase B: Read-only Titan analytics

1. Compute alignment snapshots from existing memory graph.
2. Log cycle records with no world writes.
3. Validate cadence, stability, and cost profile.

### Phase C: Proposal writes

1. Enable writes to `campaign_world_delta` and `world_history_lines` as `proposed`.
2. Add review/approval path.
3. Keep auto-apply off initially.

### Phase D: Controlled apply

1. Enable apply rules for low-risk proposals.
2. Feed approved lines to module builder and runtime world prompts.
3. Track outcomes and rollback capability.

### Phase E: Seeding integration

1. Connect approved world declarations to monster/NPC seeding.
2. Verify declaration-gate invariants still hold.

---

## 13) Governance, safety, and rollback

1. Every Titan cycle must be auditable (`titan_cycle_log`).
2. Every applied narrative line must preserve provenance (`source_titan_id`, `source_cycle_id`).
3. Interpretation revisions are allowed; canonical mechanics are not rewritten.
4. Global kill switch: disable Titan worker without impacting gameplay.
5. Rollback path:
   - mark pending proposals rejected
   - revert unapplied deltas
   - keep historical logs immutable

---

## 14) Verification checklist for v2

### Automated

1. Scheduler cadence and non-overlap tests.
2. Output schema validation tests.
3. DB migration idempotency tests.
4. No-mechanics-write invariant tests.
5. Proposal/apply/rollback flow tests.
6. Declaration-gate regression tests for monsters/NPCs.

### Manual

1. Run server for >= 1 hour, confirm 10-min cycle logs and no loop blocking.
2. Confirm random Titan distribution appears reasonable.
3. Inspect generated local/regional/world line proposals for coherence.
4. Confirm module build reflects approved pressure lines.
5. Confirm undeclared creature requests still fail closed.

---

## 15) Alpha go/no-go gate (auto-apply enablement)

Use this gate before enabling any Titan auto-apply behavior in v2 alpha.

All items must be green:

1. `Boundary Safety`: Titan paths cannot write mechanics (`HP/AC/conditions/initiative/encounter legality`).
2. `Schema Enforcement`: Titan output is strict JSON schema validated; invalid payloads are rejected.
3. `Fail-Open Runtime`: Titan failures do not block chat/combat/server loop.
4. `Non-Overlap Scheduler`: 10-minute cadence uses lock/skip behavior for long-running cycles.
5. `Provenance Completeness`: every proposal/applied line stores `source_titan_id`, `source_cycle_id`, model, and timestamps.
6. `Proposal Lifecycle Gate`: state transitions enforce `proposed -> approved -> applied -> rejected` with no bypass.
7. `Declaration Integrity`: Titan proposal alone cannot seed monsters/NPCs; approval + declaration required.
8. `Drift Controls`: damping and budget rules exist (max applies per cycle/day, reinforcement thresholds).
9. `Observability`: metrics split Titan vs gameplay calls (latency, failure, usage/cost, applied counts).
10. `Rollback Readiness`: global Titan kill switch and rollback path are tested.

Decision rule:

- If any item is red -> remain in proposal-only mode.
- Enable auto-apply only when all 10 are green.

---

## 16) Cross-link map for current plans

Use this index to retool existing plan docs under one v2 umbrella.

| Plan | Role in v2 | Required retune focus |
|---|---|---|
| `plans/version-2/CNS build/EGO.md` | Titan cycle controller contract | Scheduler + Titan identity + interpreted-only writes |
| `plans/version-2/world-narrative.md` | Canon + interpreted world state | Alignment relationship model + history-line lifecycle |
| `plans/version-2/toolkit/monsters.md` | Runtime materialization safety | Titan proposals -> declarations -> seeding bridge |
| `plans/version-2/openrouter_llm_router_architecture.md` | Model routing and fallback | Dedicated Titan task route to free-thinking profile |
| `plans/version-2/world-mapping.md` | Visualization/DM observability | Titan pressure overlays and world graph read models |
| `plans/version-2/memory.md` | Retrieval and provenance baseline | Relationship edge scoring and Titan audit traceability |
| `plans/version-2/toolkit/module-builder-enhancements.md` | Content build continuity | Consume approved Titan pressure in module seeds |

---

## 17) Retune checklists by sub-proposal

### 16.1 `plans/version-2/CNS build/EGO.md`

- [ ] Add explicit `TitanCycleWorker` contract (10-min cadence, non-overlap lock, lifecycle hooks).
- [ ] Add Titan identity randomization policy (6 IDs) and deterministic test seed mode.
- [ ] Add strict write boundary: no mechanical writes, interpreted state only.
- [ ] Add cycle output schema requirement (JSON-only, discard invalid payloads).
- [ ] Add failure semantics: fail-open gameplay, bounded retries, backoff, audit log.
- [ ] Add review/apply gate between Titan proposals and active world deltas.

### 16.2 `plans/version-2/world-narrative.md`

- [ ] Add Titan-specific additive tables (`entity_alignment_state`, `relationship_alignment_edges`, `titan_cycle_log`, `titan_pressure_snapshots`, `world_history_lines`).
- [ ] Add relationship-axis scoring model (`order_score`, `morality_score`) with confidence and evidence links.
- [ ] Add local/regional/world proposal lifecycle (`proposed -> approved -> applied -> rejected`).
- [ ] Add world-model merge rules for repeated Titan proposals (dedupe, reinforce, supersede).
- [ ] Add provenance requirement for all applied lines (`source_titan_id`, `source_cycle_id`).
- [ ] Add retrieval contract for Titan pressure packs (bounded size, stable ordering).

### 16.3 `plans/version-2/toolkit/monsters.md`

- [ ] Add declaration source type for approved Titan world-pressure outputs.
- [ ] Keep hard gate: undeclared entities remain blocked.
- [ ] Add conversion step from approved narrative line -> trusted declaration artifact.
- [ ] Add resolver logging dimension for declaration provenance (module vs Titan-derived).
- [ ] Add regression case: Titan proposal exists but not approved -> no seeding allowed.
- [ ] Add regression case: approved declaration seeds normally through existing pipeline.

### 16.4 `plans/version-2/openrouter_llm_router_architecture.md`

- [ ] Add dedicated task id (`ego_world_narrative` or `titan_world_cycle`).
- [ ] Add task-level profile override to `:free` model with thinking capability where supported.
- [ ] Add Titan-only budget/timeout settings, isolated from narrator/combat tasks.
- [ ] Add explicit fallback policy (`none` recommended first; optional OpenAI fallback later).
- [ ] Add usage reporting split for Titan cycles vs gameplay calls.
- [ ] Add guardrail: Titan call failure must not propagate to gameplay hard-stop.

### 16.5 `plans/version-2/world-mapping.md`

- [ ] Add optional Titan pressure overlay layer for `World` map scope.
- [ ] Add read-only legend mapping Titan IDs to pressure markers.
- [ ] Add DB query contract for recent approved pressure lines by region/module.
- [ ] Add DM debug viewer filters: by Titan, by scope, by status.
- [ ] Keep renderer fail-open if no Titan data exists.

### 16.6 `plans/version-2/memory.md`

- [ ] Add Titan-relevant retrieval features for relationship pair timelines.
- [ ] Add ranking boosts for high-confidence alignment edges.
- [ ] Add audit trace link from retrieved item -> Titan cycle that proposed/applied it.
- [ ] Add data hygiene jobs for stale/unverified relationship edges.

### 16.7 `plans/version-2/toolkit/module-builder-enhancements.md`

- [ ] Add module seed input for approved Titan world-pressure lines.
- [ ] Add deterministic mapping of pressure lines into module hooks (faction, ruler, summons, sanctions, omens).
- [ ] Add bounded inheritance rules so one Titan cycle cannot dominate full module structure.
- [ ] Add writeback contract to record which module seeds came from Titan pressure.

---

## 18) OpenSpec draft retune checklist

### 17.1 `openspec/changes/world-narrative-seed-bootstrap-and-toolkit-ingestion`

- [ ] Extend capability docs with Titan lifecycle tables and proposal statuses.
- [ ] Add requirements for alignment relationship edges and provenance fields.
- [ ] Add ingestion constraints for Titan-generated lines (source-anonymous and schema-bound).
- [ ] Add tests for Titan-line storage compliance and fail-closed validation.

### 17.2 `openspec/changes/openrouter-llm-router-facade`

- [ ] Add explicit Titan task profile requirements.
- [ ] Add free-tier routing and fallback behavior scenarios.
- [ ] Add timeout/cost budget acceptance criteria for background cycles.

### 17.3 `openspec/changes/openrouter-llm-callsite-migration`

- [ ] Reserve migration slot for Titan worker call site(s).
- [ ] Add non-blocking error handling contract for background calls.
- [ ] Add usage-stats segmentation acceptance criteria (Titan vs gameplay).

---

## 19) OpenSpec packaging recommendation for v2

When implementation starts, split into focused changes (do not bundle all into one):

1. `titan-worker-foundation`
2. `titan-alignment-relationship-schema`
3. `titan-world-delta-proposals`
4. `titan-module-builder-pressure-integration`
5. `titan-declaration-seeding-bridge`

Each change should include:

- strict non-goals
- rollback triggers
- verification gates
- explicit boundary tests (no mechanics writes)

---

## 20) Final architectural statement

NEQ v2 should treat Titan cycles as a structured, auditable narrative-pressure controller:

- thematic enough to feel mythic and alive,
- bounded enough to stay safe and testable,
- integrated enough to unify OpenRouter, EGO, world narrative, module continuity, and declaration-gated seeding,
- and disciplined enough to preserve the core truth hierarchy:

`mechanics in Python, meaning in narrative.`
