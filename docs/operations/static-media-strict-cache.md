# Static Media Strict-Cache

`modules/<module>/media/{npcs,monsters}` is authoritative and publishable.
`web/static/media/{npcs,monsters}` is runtime fallback cache only.

## Audit (review before delete)

- Endpoint: `GET /api/toolkit/static-cache/audit`
- Reports, per target folder:
  - `live_files`: files currently in `web/static/media/{npcs,monsters}`
  - `active_pack_files`: pack-sourced files by active pack
  - `orphaned_files`: live files not present in active packs
  - `collisions`: same filename provided by multiple active packs

## Rebuild (clear then repopulate)

- Endpoint: `POST /api/toolkit/static-cache/rebuild`
- Payload fields:
  - `dry_run` (default `true`)
  - `create_backup` (default `true`)
  - `active_packs` (optional list override)
- Behavior:
  1. Optional backup snapshot pack (`graphic_packs/live_backup_*`)
  2. Clear `web/static/media/npcs` and `web/static/media/monsters`
  3. Repopulate from active packs only

Out-of-scope sibling folders such as `web/static/media/videos` are untouched.
