# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Tasks

## 1. Media Extraction Tool

- [x] 1.1 Create `scripts/homebrew_media_extract.py` CLI skeleton
- [x] 1.2 Parse markdown image directives and direct image URLs
- [x] 1.3 Add classification (`title_image`, `map_image`, fallback `handout`)
- [x] 1.4 Implement bounded download/copy with timeout and warn-only failures
- [x] 1.5 Write extracted assets to module media folders (`environment`, `maps`)
- [x] 1.6 Return structured JSON status with warnings
- [x] 1.7 Add regression tests using Mangrove Keep URLs

## 2. Handle Manifest Tool

- [x] 2.1 Create `scripts/homebrew_media_handles.py` CLI skeleton
- [x] 2.2 Implement deterministic `handle_id` generation
- [x] 2.3 Emit `media_handles.json` with required fields and future-use flags
- [x] 2.4 Include entries for failed/unresolved downloads (`download_status`)
- [x] 2.5 Add idempotent rewrite behavior and atomic write
- [x] 2.6 Add schema-style contract tests

## 3. Portrait Prewarm Tool

- [x] 3.1 Create `scripts/homebrew_prewarm_portraits.py` CLI skeleton
- [x] 3.2 Discover module NPC and monster entities for prewarm planning
- [x] 3.3 Prewarm NPC portraits with skip-if-exists behavior
- [x] 3.4 Prewarm monster portraits with skip-if-exists behavior
- [x] 3.5 Record planned/done/failed/skipped counters
- [x] 3.6 Fail-open on provider errors and emit warnings
- [x] 3.7 Add tests for skip/degraded/success contracts

## 4. Orchestrator and Audit Integration

- [x] 4.1 Update `scripts/homebrew_ingest_dev.py` with new post-ingest stages
- [x] 4.2 Add CLI flags: `--no-media-extract`, `--no-prewarm`, `--media-timeout`
- [x] 4.3 Extend sidecar payload with `media_extraction`, `media_handles`, `portrait_prewarm`
- [x] 4.4 Update `scripts/homebrew_sidecar_audit.py` to validate new sidecar sections
- [x] 4.5 Preserve fail-closed behavior for strict ingest and fail-open behavior for media/prewarm

## 5. Skill and Documentation Updates

- [x] 5.1 Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` workflow diagram and steps
- [x] 5.2 Add report examples showing degraded media download with successful ingest
- [x] 5.3 Add explicit Mangrove Keep URL examples (title + large map)
- [x] 5.4 Update executor prompts for builder flow

## 6. Verification

- [x] 6.1 `python3 -m py_compile` on new/updated scripts
- [x] 6.2 Run targeted tests for extraction, handle manifest, and prewarm
- [x] 6.3 Run full ingest on Mangrove Keep and confirm:
  - Detected URLs: 6 (all Mangrove Keep image URLs found)
  - Downloaded: 6 (all images successfully fetched with retry/backoff)
  - Handle count: 6 (no duplicates - dedup working correctly)
  - Extraction log shows accurate statuses: `downloaded` with `attempts=1`
- [x] 6.4 `openspec validate dev-homebrew-ingest-media-handles-prewarm`
  - **Result:** Change is valid

### Expected Mangrove Keep handle coverage

- [x] Detect `https://i.imgur.com/t50VrIo.jpg` as `title_image`
- [x] Detect `https://i.imgur.com/WSwArYs.jpg` as `map_image`
- [x] Detect remaining map URLs and classify as `map_image`
- [x] Persist handles even when remote fetch is unavailable
