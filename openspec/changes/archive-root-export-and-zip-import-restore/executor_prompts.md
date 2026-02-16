## Kimi Builder Execution Prompts - archive-root-export-and-zip-import-restore

Use this file as staged execution guidance for `tasks.md`.

---

## Execution Contract

- MUST implement in task-group order (1 -> 7).
- MUST preserve existing folder restore path and semantics.
- MUST keep essential save behavior unchanged.
- MUST fail closed for invalid zip restore attempts.
- MUST keep host edits merge-safe and mark host hooks with `# TABLETOP MODE:`.
- MUST keep user-facing strings ASCII-only.
- SHOULD keep changes additive and avoid broad rewrites.

---

## Prompt 1 - Root Export Foundation

Implement tasks 1.x.

Scope:
- `updates/save_game_manager.py`

Requirements:
- Add root export folder path helper.
- Switch full-save archive output to `archive_exports/`.
- Implement deterministic archive naming with module/timestamp/save folder context.

Verify before moving on:
- `python3 -m py_compile updates/save_game_manager.py`

---

## Prompt 2 - Payload and Archive Catalog

Implement tasks 2.x.

Scope:
- `updates/save_game_manager.py`
- `web/web_interface.py`

Requirements:
- Full save payload path reflects root export location.
- Essential payload remains legacy content-only.
- Add zip catalog listing support for `archive_exports/*.zip`.

Verify before moving on:
- `python3 -m py_compile updates/save_game_manager.py web/web_interface.py`

---

## Prompt 3 - Zip Validation and Secure Extraction

Implement tasks 3.x.

Scope:
- `updates/save_game_manager.py`

Requirements:
- Add preflight validation for zip archive structure and metadata.
- Add traversal/absolute-path rejection.
- Add extract-to-temp staging with cleanup.

Verify before moving on:
- `python3 -m py_compile updates/save_game_manager.py`

---

## Prompt 4 - Zip Restore Pipeline

Implement tasks 4.x.

Scope:
- `updates/save_game_manager.py`

Requirements:
- Add restore-from-zip entrypoint.
- Stage extracted save into canonical module save path.
- Delegate to existing folder restore flow.

Verify before moving on:
- `python3 -m py_compile updates/save_game_manager.py`

---

## Prompt 5 - Web and Load Dialog Integration

Implement tasks 5.x and 6.x.

Scope:
- `web/web_interface.py`
- `web/templates/game_interface.html`

Requirements:
- Add archive zip list action and restore action.
- Extend load dialog with archive rows (name/size/modified).
- Preserve existing folder restore controls.

Verify before moving on:
- `python3 -m py_compile web/web_interface.py`

Manual checks:
- Load dialog shows both folder saves and archive zips.
- Zip restore triggers restore_complete on success.

---

## Prompt 6 - Final Validation Gates

Implement tasks 7.x.

Scope:
- test scripts under `scripts/`
- any minimal fixes required in scoped files

Required final commands:
- `python3 -m py_compile updates/save_game_manager.py web/web_interface.py utils/reset_campaign.py`
- new/updated zip restore smoke tests

Required smoke:
1. Full save creates zip under `archive_exports/`.
2. Reset then restore from valid zip succeeds.
3. Invalid zip fails with explicit error.
4. Essential save and folder restore regressions pass.
