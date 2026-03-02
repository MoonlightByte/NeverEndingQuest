# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Design

## Architecture

```
Homebrew Source (.md)
    |
    v
preflight -> transform -> dry-run -> registry guard -> strict ingest
                                                    |
                                                    v
                                   media extract (warn-only)
                                                    |
                                                    v
                                  media handles manifest build
                                                    |
                                                    v
                                 portrait prewarm (NPC + monster)
                                                    |
                                                    v
                                   sidecar audit + registry verify
```

Core ingest remains authoritative and fail-closed for schema/registry contracts.
Media and prewarm stages are additive and fail-open (degraded with warnings).

## Storage Layout

- `modules/<slug>/media/environment/` -> title/hero images and generic scene images
- `modules/<slug>/media/maps/` -> extracted map images (future map-tab target)
- `modules/<slug>/media/npcs/` -> prewarmed NPC portraits
- `modules/<slug>/media/monsters/` -> prewarmed monster portraits
- `modules/<slug>/media/media_handles.json` -> canonical handle index

## Handle Manifest Contract

Each handle entry:

```json
{
  "handle_id": "map_img_3f9c...",
  "kind": "title_image|map_image|handout|npc_portrait|monster_portrait",
  "source_ref": "https://i.imgur.com/WSwArYs.jpg",
  "storage_relpath": "media/maps/WSwArYs.jpg",
  "download_status": "downloaded|missing|failed",
  "checksum_sha256": "...",
  "dimensions": {"width": 0, "height": 0},
  "linked_area_ids": [],
  "linked_location_ids": [],
  "future_use": {
    "chat_title_candidate": false,
    "map_tab_candidate": true
  }
}
```

Rules:
- `handle_id` deterministic from `(kind + source_ref + storage_relpath)`.
- Failed downloads still produce handle entries with `download_status=failed`.
- Manifest writes are atomic and idempotent.

## Media Extraction Rules

1. Parse markdown image directives and raw image URLs.
2. Accept common extensions: `.jpg`, `.jpeg`, `.png`, `.webp`.
3. Classify by nearby headings and context:
   - first hero image near title -> `title_image`
   - sections containing "map"/"DM map" -> `map_image`
4. Download policy:
   - best effort with timeout
   - no retries beyond small bounded attempt count
   - no ingest block on failure

## Portrait Prewarm Rules

- Trigger only after strict ingest success.
- Enumerate NPCs/monsters from generated module artifacts.
- Skip if target portrait files already exist.
- Use existing generator/materializer paths.
- On errors: record warnings and continue.

## Sidecar Extensions

Add non-breaking blocks:

```json
{
  "media_extraction": {
    "status": "success|degraded|none",
    "extracted_count": 0,
    "warning_count": 0,
    "warnings": []
  },
  "media_handles": {
    "status": "success|degraded",
    "manifest_path": "modules/<slug>/media/media_handles.json",
    "handle_count": 0
  },
  "portrait_prewarm": {
    "status": "success|degraded|skipped",
    "npcs": {"planned": 0, "done": 0, "failed": 0, "skipped": 0},
    "monsters": {"planned": 0, "done": 0, "failed": 0, "skipped": 0},
    "warnings": []
  }
}
```

## Orchestrator Updates (`homebrew_ingest_dev.py`)

New stage order after strict ingest success:
1. `media_extract`
2. `media_handles`
3. `portrait_prewarm`
4. `sidecar_audit`
5. `registry_verify`

Failure semantics:
- strict ingest failure -> fail closed (existing behavior)
- media/prewarm failure -> continue, mark degraded

## Skill Update Requirements

Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` to include:
- Warn-only media stage
- Handle manifest output contract
- NPC/monster prewarm default behavior
- Final report fields for extraction and prewarm
