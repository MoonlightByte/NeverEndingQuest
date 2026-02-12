## Context

NeverEndingQuest currently spreads memory across conversation history, combat history, summaries, journal artifacts, and companion-memory JSON stores. This provides continuity but does not provide a single deterministic retrieval surface with explicit ranking controls. As campaigns progress, prompt relevance risk grows faster than storage risk, so the design prioritizes bounded retrieval quality over raw storage reduction.

The repository also has known long-horizon plans (EGO/RATIO) that may later require retrieval observability, policy tuning, and safe shadow evaluation. This design keeps those surfaces additive and optional so the memory foundation is useful immediately even if controller features are never enabled.

Constraints:
- Preserve upstream compatibility patterns and TABLETOP merge safety.
- Keep single-player and multi-player behavior backward compatible.
- Maintain Python-state-truth philosophy for mechanics; memory is narrative support.
- Keep retrieval deterministic and token-bounded for live play.

## Goals / Non-Goals

**Goals:**
- Provide a canonical, additive SQLite memory foundation (`data/memory.db`) for long-term records.
- Define deterministic retrieval contracts with explicit ranking factors.
- Preserve identity across role transitions (PC <-> NPC companion, retirement, return).
- Keep God-mode historical completeness while providing strict prompt-mode filtering.
- Establish optional readiness hooks for future policy-driven retrieval tuning.

**Non-Goals:**
- Replacing current JSON memory paths in one step.
- Full narrator prompt rewiring in this change.
- Building EGO/RATIO controllers in this change.
- Introducing non-local database dependencies.

## Decisions

1. **SQLite as canonical memory store (additive-first)**
   - Decision: Use `sqlite3` with migration-managed schema under `data/memory.db`.
   - Why: Local, transactional, dependency-free, sufficient scale for campaign workloads.
   - Alternative considered: Keep JSON-only and add more compression heuristics.
   - Why not alternative: JSON-only approach lacks deterministic relational retrieval and auditable ranking.

2. **Two-plane model (God mode history vs prompt mode retrieval)**
   - Decision: Persist high-fidelity history while always returning bounded top-K context packs.
   - Why: Prevents prompt bloat while retaining full campaign traceability.
   - Alternative considered: Aggressive historical compaction/deletion.
   - Why not alternative: Loses future replay and long-arc narrative recall potential.

3. **Identity-first schema with temporal roles**
   - Decision: Model stable entities with `entity_roles` time windows, not separate PC/NPC identities.
   - Why: Required for role-transition continuity and return arcs.
   - Alternative considered: Duplicate entities per role.
   - Why not alternative: Breaks continuity and complicates retrieval semantics.

4. **Deterministic retrieval ranking in SQL baseline**
   - Decision: Start with SQL-only deterministic ranking (pinned, active-PC, importance, class, decay bucket, reinforcement).
   - Why: Stable and testable behavior for initial rollout.
   - Alternative considered: Immediate Python/LLM hybrid ranking.
   - Why not alternative: Harder to test, harder to audit, more regression risk early.

5. **Idempotent ingestion via checksums**
   - Decision: Source-type + checksum unique constraints for ingest safety.
   - Why: Prevents duplicate growth from repeated imports and startup replays.
   - Alternative considered: Time-range dedupe heuristics.
   - Why not alternative: Heuristics are ambiguous and prone to false positives/negatives.

6. **Optional EGO/RATIO readiness hooks (not activated)**
   - Decision: Reserve additive observability/policy tables and contracts (`retrieval_audit_log`, policy profiles, change logs).
   - Why: Future-proofs architecture while keeping current scope controlled.
   - Alternative considered: defer all controller-oriented schema.
   - Why not alternative: future retrofits become invasive and riskier.

## Risks / Trade-offs

- [Ranking drift from imperfect weights] -> Start with deterministic baseline weights + retrieval test matrix; tune only via explicit policy revisions.
- [Storage growth over long campaigns] -> Keep storage complete but bounded retrieval; add dedupe, optional consolidation, and maintenance jobs.
- [Schema complexity from future-proofing] -> Keep readiness surfaces optional and unused by default; no runtime dependency on controller features.
- [Runtime regression from early integration] -> Phase rollout: schema/migrations first, retrieval service second, ingest third, prompt integration last.
- [SP/MP behavior divergence] -> Keep service mode-agnostic and derive priority from existing party state only when available.

## Migration Plan

1. Add `core/memory` scaffolding and migration bootstrap.
2. Create Stage 1 schema and indexes in `data/memory.db` (idempotent migrations).
3. Implement retrieval contract `get_entity_timeline` with deterministic ranking.
4. Implement checksum-safe journal ingest path (manual or guarded startup trigger).
5. Add optional read-only inspection endpoint for retrieval verification.
6. Validate with deterministic test matrix and fallback behavior checks.

Rollback strategy:
- Disable memory DB read path via feature flag/guard and continue existing JSON/compression paths.
- Keep DB files intact for postmortem; no destructive rollback required.
- Remove or bypass optional route hooks without impacting core gameplay.

## Open Questions

- Should initial retrieval policy values be hardcoded constants or externalized immediately in policy JSON?
- Should `retrieval_snippets` be enabled in Stage 1 or deferred until real token-pressure profiling?
- What exact token cap should be default per scene type for narrator injection?
- Should summary and combat log ingestion be enabled by default or staged after journal ingestion stabilizes?
