## Builder Execution Prompts - load-dialog-unified-archive-save-timeline

Use this file as staged execution guidance for `tasks.md`.

---

## Execution Contract

- MUST keep restore semantics unchanged (`save_folder` -> `restoreGame`, `archive_zip` -> `restoreArchiveZip`).
- MUST keep delete restricted to save folders.
- MUST keep existing socket payload contracts additive and unchanged.
- MUST keep host edits merge-safe and mark host hooks with `# TABLETOP MODE:` where applicable.
- MUST keep user-facing text ASCII-only.
- SHOULD keep changes concentrated in `web/templates/game_interface.html` unless backend adjustment is required.

---

## Prompt 1 - Unified Entry Model and Sort

Implement tasks 1.x and 2.x.

Scope:
- `web/templates/game_interface.html`

Requirements:
- Normalize save-folder and archive-zip payloads into one shared entry model.
- Include `entry_type`, display metadata, and shared timestamp sort key.
- Render one merged list sorted newest-first across both types.
- Keep deterministic fallback ordering for missing timestamps.

Verify before moving on:
- `node --check web/templates/game_interface.html`

---

## Prompt 2 - Filter Controls

Implement tasks 3.x.

Scope:
- `web/templates/game_interface.html`

Requirements:
- Add filter controls (`all`, `save_folders`, `archive_zips`) with default `all`.
- Apply filtering before merged render.
- Keep selection state safe when filter changes hide selected entry.

Verify before moving on:
- `node --check web/templates/game_interface.html`

Manual checks:
- Filter toggles update visible rows correctly.
- Selected item clears if filtered out.

---

## Prompt 3 - Action Compatibility

Implement tasks 4.x.

Scope:
- `web/templates/game_interface.html`
- `web/web_interface.py` (only if minimal additive routing support is needed)

Requirements:
- Preserve restore dispatch by `entry_type`.
- Preserve delete restrictions for archive entries.
- Preserve existing socket event names and payload compatibility.

Verify before moving on:
- `python3 -m py_compile web/web_interface.py`
- `node --check web/templates/game_interface.html`

---

## Prompt 4 - Final Validation Gates

Implement tasks 5.x.

Scope:
- minimal fixes in scoped files only

Required final checks:
- `python3 -m py_compile web/web_interface.py`
- `node --check web/templates/game_interface.html`

Required smoke:
1. Newest archive can appear above older save folders in `all` view.
2. `save_folders` and `archive_zips` filters each show correct subset.
3. Save-folder restore behavior remains unchanged.
4. Archive-zip restore behavior remains unchanged.
5. Delete remains disabled for archive rows.
