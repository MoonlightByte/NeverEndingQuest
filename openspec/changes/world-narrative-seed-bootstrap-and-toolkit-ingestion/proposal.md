## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (OpenSpec proposal not yet extended with Titan lifecycle tables)
- Last tagged: 2026-02-26
- Retune focus: relationship-alignment schema, Titan cycle audit logs, and local/regional/world history-line proposal lifecycle

## Why

NeverEndingQuest needs a copyright-safe world-narrative ingestion foundation before implementation proceeds. The current direction is correct (PDF-only, one-book-at-a-time, source-anonymous outputs, local `/user_uploads/text/`), but Phase 1/2 must be formalized as OpenSpec builder-ready work with explicit MUST boundaries.

## What Changes

- Add runtime bootstrap contract:
  - committable baseline seed DB: `data/world_narrative_seed.db`
  - runtime mutable DB: `data/memory.db`
  - first-run copy seed -> runtime when runtime is missing.
- Add additive memory migration support for:
  - `atom_relations`
  - `atom_statistics`
  - `campaign_world_model`
  - `campaign_world_delta`
- Add source-anonymous ingestion service that accepts only sanitized atom payloads and fail-closes on banned keys/terms.
- Add toolkit world-source API flow under `/toolkit` for upload/extract/build/ingest/job-status with one-active-job locking.
- Add toolkit panel UX for world-source operations with mandatory copyright attestation and clear local-only warning.
- Add OpenSpec meta-source rubric to govern layering of strategy/cosmology/horror priors vs fantasy-specific priors.
- Add OpenSpec profile assignment list to lock initial ingest-wave ordering (meta priors first, fantasy batches second).

### MUST Contract

- MUST keep raw uploads in `/user_uploads/text/` only.
- MUST treat `/user_uploads/text/` and runtime `data/memory.db` as local-only, never committable artifacts.
- MUST keep committable outputs source-anonymous (no title/author/series/source identifiers).
- MUST keep processing one-book-at-a-time at runtime.
- MUST accept `pdf` uploads only for source ingestion in this phase.
- MUST enforce hard cutover to `/user_uploads/text/` with no legacy path fallback.
- MUST fail-closed on compliance violations.
- MUST preserve SP/MP compatibility and existing gameplay flows.

### SHOULD Guidance

- SHOULD keep host-file edits minimal and marked with `# TABLETOP MODE:`.
- SHOULD keep extraction/build as async job flow with explicit status objects.
- SHOULD keep implementation additive and extension-first.

### Non-goals

- No EPUB workflow.
- No multi-book batch ingestion.
- No direct raw-source retrieval path for narrator/module builder/EGO-RATIO.
- No commit of raw upload files or source-identifying metadata.

## Capabilities

### New Capabilities

- `world-narrative-seed-bootstrap`
- `world-narrative-source-anonymous-ingestion`
- `toolkit-world-source-jobs`

### Modified Capabilities

- None.

## Impact

- Affected code (planned):
  - `core/memory/memory_db.py`
  - `core/memory/__init__.py`
  - `core/memory/world_narrative_ingest.py` (new)
  - `web/routes/world_narrative_routes.py` (new)
  - `web/web_interface.py`
  - `web/templates/module_toolkit.html`
  - `scripts/test_world_narrative_ingestion.py` (new)
  - `scripts/test_world_narrative_routes.py` (new)
- Rollout risk: Medium (memory bootstrap + new toolkit endpoints).
- Fallback strategy:
  - If seed is missing, continue with current `init_memory_db` path.
  - If ingestion fails, block ingest only; keep toolkit and gameplay responsive.
