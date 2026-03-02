# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Tasks

## 1. Media Extraction Tool

- [ ] 1.1 Create `scripts/homebrew_media_extract.py` CLI skeleton
- [ ] 1.2 Parse markdown image directives and direct image URLs
- [ ] 1.3 Add classification (`title_image`, `map_image`, fallback `handout`)
- [ ] 1.4 Implement bounded download/copy with timeout and warn-only failures
- [ ] 1.5 Write extracted assets to module media folders (`environment`, `maps`)
- [ ] 1.6 Return structured JSON status with warnings
- [ ] 1.7 Add regression tests using Mangrove Keep URLs

## 2. Handle Manifest Tool

- [ ] 2.1 Create `scripts/homebrew_media_handles.py` CLI skeleton
- [ ] 2.2 Implement deterministic `handle_id` generation
- [ ] 2.3 Emit `media_handles.json` with required fields and future-use flags
- [ ] 2.4 Include entries for failed/unresolved downloads (`download_status`)
- [ ] 2.5 Add idempotent rewrite behavior and atomic write
- [ ] 2.6 Add schema-style contract tests

## 3. Portrait Prewarm Tool

- [ ] 3.1 Create `scripts/homebrew_prewarm_portraits.py` CLI skeleton
- [ ] 3.2 Discover module NPC and monster entities for prewarm planning
- [ ] 3.3 Prewarm NPC portraits with skip-if-exists behavior
- [ ] 3.4 Prewarm monster portraits with skip-if-exists behavior
- [ ] 3.5 Record planned/done/failed/skipped counters
- [ ] 3.6 Fail-open on provider errors and emit warnings
- [ ] 3.7 Add tests for skip/degraded/success contracts

## 4. Orchestrator and Audit Integration

- [ ] 4.1 Update `scripts/homebrew_ingest_dev.py` with new post-ingest stages
- [ ] 4.2 Add CLI flags: `--no-media-extract`, `--no-prewarm`, `--media-timeout`
- [ ] 4.3 Extend sidecar payload with `media_extraction`, `media_handles`, `portrait_prewarm`
- [ ] 4.4 Update `scripts/homebrew_sidecar_audit.py` to validate new sidecar sections
- [ ] 4.5 Preserve fail-closed behavior for strict ingest and fail-open behavior for media/prewarm

## 5. Skill and Documentation Updates

- [ ] 5.1 Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` workflow diagram and steps
- [ ] 5.2 Add report examples showing degraded media download with successful ingest
- [ ] 5.3 Add explicit Mangrove Keep URL examples (title + large map)
- [ ] 5.4 Update executor prompts for builder flow

## 6. Verification

- [ ] 6.1 `python3 -m py_compile` on new/updated scripts
- [ ] 6.2 Run targeted tests for extraction, handle manifest, and prewarm
- [ ] 6.3 Run full ingest on Mangrove Keep and confirm:
- [ ] 6.4 `openspec validate dev-homebrew-ingest-media-handles-prewarm`

### Expected Mangrove Keep handle coverage

- [ ] Detect `https://i.imgur.com/t50VrIo.jpg` as `title_image`
- [ ] Detect `https://i.imgur.com/WSwArYs.jpg` as `map_image`
- [ ] Detect remaining map URLs and classify as `map_image`
- [ ] Persist handles even when remote fetch is unavailable
