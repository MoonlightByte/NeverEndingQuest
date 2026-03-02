# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Proposal

## Why

Developer ingest currently converts Homebrew text into deterministic NEQ module artifacts, but it ignores source images that are common in Homebrewery markdown (title art, regional maps, dungeon maps, DM maps).

This creates two gaps:
- Map and title imagery cannot be indexed during ingest for future chat/map-tab features.
- NPC and monster portrait media are inconsistent at first run unless generated manually later.

## What Changes

Add a non-blocking media layer to the developer ingest pipeline, plus deterministic media handle indexing and portrait prewarm.

### 1) Warn-only media extraction
- Parse markdown for media references (including direct Imgur links).
- Copy/download resolvable assets into module media folders.
- Never block deterministic ingest on media failures; emit warnings only.

### 2) Media handle manifest
- Build `modules/<slug>/media/media_handles.json` with stable handle IDs and metadata.
- Mark candidates for future consumers:
  - chat title image
  - map tab map images

### 3) Portrait prewarm (NPC + Monster)
- After successful module ingest, prewarm NPC and monster portraits.
- Skip existing media.
- Fail open on generation/provider errors and record degraded status in sidecar.

## Non-goals

- No map-tab UI implementation in this change.
- No chat rendering changes in this change.
- No change to strict schema/registry validation behavior for core ingest artifacts.

## Capability Additions

- New script: `scripts/homebrew_media_extract.py`
- New script: `scripts/homebrew_media_handles.py`
- New script: `scripts/homebrew_prewarm_portraits.py`
- Update: `scripts/homebrew_ingest_dev.py` orchestration stages
- Update: `scripts/homebrew_sidecar_audit.py` validation of media/prewarm sections
- Update: `.opencode/skills/dev-homebrew-ingest/SKILL.md` workflow contract

## Source-backed Examples (Mangrove Keep)

From `Docs/modules/hombrew/The Secrets of Mangrove Keep.md`, extraction should detect at minimum:
- Title image: `https://i.imgur.com/t50VrIo.jpg`
- Large map image: `https://i.imgur.com/WSwArYs.jpg`
- Additional map pages: `NtCwIA4.jpg`, `LmHTSEz.jpg`, `ZS7wpZm.jpg`, `q67xQGE.png`

These must be represented as deterministic media handles even if download fails.

## Impact

- Improves module completeness for mapping workflows.
- Reduces first-run missing portrait issues.
- Preserves existing fail-closed core ingest guarantees while making media ingest fail-open.
