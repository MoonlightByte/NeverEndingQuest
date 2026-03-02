# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Executor Prompts

## Prompt 1: Media Extraction (warn-only)

**Task:** Build `scripts/homebrew_media_extract.py`.

**Scope:**
- Parse markdown image directives and direct image URLs.
- Download/copy assets into module media folders.
- Classify title vs map images.
- Emit warnings, never block ingest.

**MUST:**
- Fail-open for all media fetch/copy failures.
- Produce structured JSON report with extracted and failed counts.
- Keep deterministic naming and atomic writes.

**SHOULD:**
- Use heading context for classification.
- Prefer stable filenames derived from URL basename.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_media_extract.py
python scripts/homebrew_media_extract.py --source "Docs/modules/hombrew/The Secrets of Mangrove Keep.md" --module-slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 2: Media Handle Manifest

**Task:** Build `scripts/homebrew_media_handles.py`.

**Scope:**
- Generate `modules/<slug>/media/media_handles.json`.
- Emit deterministic handle IDs.
- Preserve entries for failed downloads.

**MUST:**
- Include future-use flags for `chat_title_candidate` and `map_tab_candidate`.
- Include source refs and storage relpaths.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_media_handles.py
python scripts/homebrew_media_handles.py --slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 3: Portrait Prewarm (NPC + Monster)

**Task:** Build `scripts/homebrew_prewarm_portraits.py`.

**Scope:**
- Discover entities in generated module.
- Prewarm missing NPC and monster portraits.
- Skip existing files.

**MUST:**
- Fail-open on provider errors.
- Emit counters: planned/done/failed/skipped for each entity type.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_prewarm_portraits.py
python scripts/homebrew_prewarm_portraits.py --slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 4: Orchestrator Integration

**Task:** Update `scripts/homebrew_ingest_dev.py` and `scripts/homebrew_sidecar_audit.py`.

**Scope:**
- Add media extraction, handle generation, and prewarm stages.
- Extend sidecar with media/prewarm blocks.
- Keep strict ingest fail-closed behavior unchanged.

**MUST:**
- Media/prewarm failures are warnings/degraded, not pipeline hard-fail.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_sidecar_audit.py
python scripts/homebrew_ingest_dev.py --source "Docs/modules/hombrew/The Secrets of Mangrove Keep.md" --strict --json
```

## Prompt 5: Skill Update

**Task:** Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` to match new pipeline.

**Scope:**
- Add media extraction and handles stages.
- Add portrait prewarm stage.
- Add report format fields for degraded media outcomes.

**Verification:**
- Confirm workflow and stop conditions match new OpenSpec tasks.

## Prompt 6: Closure + Sidecar Persistence

**Task:** Complete remaining contract gaps: sidecar persistence, targeted tests, OpenSpec closure.

**Scope:**
- Implement `_persist_media_to_sidecar()` to write media blocks into archived sidecar artifacts.
- Use atomic writes (tmp + rename) and fail-open semantics.
- Add targeted regression tests in `scripts/test_homebrew_ingest_media_pipeline.py`.
- Fix SPDX header typo in `scripts/homebrew_sidecar_audit.py`.
- Rename key to canonical `media_extraction` (was `media_extract`).
- Add backward compatibility for legacy key with deprecation warning.
- Update executor prompts and mark tasks complete.

**MUST:**
- Sidecar persistence writes canonical keys: `media_extraction`, `media_handles`, `portrait_prewarm`.
- Tests verify: canonical keys in output, sidecar persistence writes canonical keys, legacy key normalization, media degradation does not fail ingest.
- OpenSpec validation passes.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_sidecar_audit.py scripts/test_homebrew_ingest_media_pipeline.py
python3 scripts/test_homebrew_ingest_media_pipeline.py
openspec validate dev-homebrew-ingest-media-handles-prewarm
```

## Prompt 7: Download Reliability + Handle Reconciliation

**Task:** Fix Mangrove media fetch failures and stale handle reconciliation.

**Scope:**
- Harden downloader with retry/backoff and browser headers.
- Persist extraction audit log for reconciliation.
- Reconcile handles against existing local files (extension variants).

**MUST:**
- 429/503 retry with backoff.
- Accurate status logging: `downloaded|existing|failed` per URL.
- Dedupe handles to one per source URL.

**Verification:**
```bash
python3 scripts/homebrew_media_extract.py --source "Docs/modules/hombrew/The Secrets of Mangrove Keep.md" --module-slug The_Secrets_of_Mangrove_Keep --timeout-seconds 15 --json
python3 scripts/homebrew_media_handles.py --slug The_Secrets_of_Mangrove_Keep --json
# Confirm: 6 detected, 6 handles, no duplicates
```

## Prompt 8: Entity Seeding + Fallback Discovery

**Task:** Add deterministic entity extraction from adventure text.

**Scope:**
- Extract NPCs from cue patterns (`named Malliry Valderu`).
- Extract monsters from `creatures` fields and explicit encounters.
- Populate `module_context.json` and emit `npcs_seed.json`/`monsters_seed.json`.
- Add prose fallback for discovery when context is empty.

**MUST:**
- Conservative extraction (under-detect over hallucinate).
- Seed files are primary contract for prewarm planning.

**Verification:**
```bash
python3 -m py_compile core/importers/homebrewery_importer.py
python3 scripts/test_homebrew_entity_seeding.py
# Re-import transformed Mangrove and inspect seed files
```

## Prompt 9: Safety Reset + Provider Guardrails

**Task:** Stop paid generation by default; clean accidental artifacts.

**Scope:**
- Add `--allow-provider` flag (default: false) to prewarm and orchestrator.
- Without flag: plan/skip only, no provider calls.
- Restore any accidentally deleted tracked static media files.

**MUST:**
- Provider generation is opt-in only.
- No destructive cleanup of baseline assets.

**Verification:**
```bash
python3 scripts/homebrew_prewarm_portraits.py --slug The_Secrets_of_Mangrove_Keep --json
# Should return: status=skipped, warning=provider_disabled
```

## Prompt 10: Seed Contract + Quality Tightening

**Task:** Finalize seed-first discovery and tighten false-positive guard.

**Scope:**
- Seed files (`npcs_seed.json`, `monsters_seed.json`) take precedence.
- Context is secondary fallback; prose scan is last resort.
- Conservative prose scan: multi-word monster names only.
- Planned-only mode useful without provider.

**MUST:**
- If seed exists, use seed values only (don't merge with broader scans).
- Generic single-words (`bird`, `snake`) excluded from prose fallback.

**Verification:**
```bash
python3 scripts/homebrew_prewarm_portraits.py --slug <seeded_module> --json
# Confirm: planned counts from seed, skipped, no false-positive inflation
```

## Prompt 11: QA Closure + OpenSpec Hygiene

**Task:** Close remaining gaps: missing tests, docs hygiene, verification.

**Scope:**
- Add missing tests:
  - Seed precedence (seed over context).
  - False-positive guard (single-words excluded).
  - Case normalization expectations.
- Update `executor_prompts.md` with Prompts 7-11.
- Fix `tasks.md` consistency (6.4 only marked complete if validate passes).
- Run `openspec validate` and update based on real result.

**MUST:**
- All 7 entity seeding tests pass.
- Provider-safe verification path documented.
- OpenSpec docs accurate and consistent.

**Verification:**
```bash
python3 -m py_compile scripts/test_homebrew_entity_seeding.py
python3 scripts/test_homebrew_entity_seeding.py
# Expected: 7 tests OK
openspec validate dev-homebrew-ingest-media-handles-prewarm
```
