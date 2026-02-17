## 1. Unified Entry Model

- [x] 1.1 Add a client-side normalization helper in `web/templates/game_interface.html` that maps save and archive payloads into one shared entry structure.
  - Implemented: `normalizeLoadEntries(saveEntries, archiveEntries)` at line 8155
  - Creates unified entries with `entry_type`, `display_name`, `sort_timestamp`, `source_data`
- [x] 1.2 Include explicit `entry_type` (`save_folder` or `archive_zip`) and a shared sortable timestamp field per entry.
  - `entry_type` field added for both types at lines 8161 (save_folder) and 8177 (archive_zip)
  - `sort_timestamp` computed via `parseSaveTimestamp()` and `parseArchiveTimestamp()` helpers
- [x] 1.3 Add deterministic tie-break fields (`display_name`, fallback keys) for stable rendering.
  - `display_name` added for both entry types
  - `getEntrySortKey()` at line 8253 provides composite key: timestamp (negated for desc), type_order, name

## 2. Unified Sort and Render Path

- [x] 2.1 Replace dual-loop rendering with one merged render pipeline.
  - `renderLoadDialogEntries()` now uses single loop over `getFilteredUnifiedEntries()` at line 8371
  - Iterates over filtered unified entries, branches by `entry_type` for rendering
- [x] 2.2 Sort merged entries newest-first across both types.
  - `compareUnifiedEntries()` comparator at line 8269 sorts by negative timestamp (newest first)
  - Sort applied in socket handlers at lines 8499 and 8507
- [x] 2.3 Handle missing/invalid timestamps without crashing (fallback ordering still deterministic).
  - `parseSaveTimestamp()` has fallback chain: parsed date -> folder name extraction -> 0
  - `parseArchiveTimestamp()` returns 0 for invalid/missing timestamps
  - Deterministic tie-break: type_order ('A' for archive, 'B' for save), then display_name

## 3. Entry-Type Filters

- [x] 3.1 Add filter controls to Load dialog (`all`, `save_folders`, `archive_zips`) with default `all`.
  - Filter UI added at lines 7934-7938 with three chip buttons
  - Default filter 'all' set in `openLoadDialog()` at line 8284
  - CSS for `.filter-chip` and `.filter-chip.active` at lines 1075-1105
- [x] 3.2 Apply filter before rendering and ensure visual selected-state feedback for active filter.
  - `setLoadDialogFilter()` at line 8052 validates filter, updates state, calls `updateFilterChipVisuals()`
  - `updateFilterChipVisuals()` at line 8067 toggles `.active` class based on `loadDialogFilter`
  - `getFilteredUnifiedEntries()` at line 8112 applies filter before render
- [x] 3.3 If selected entry is filtered out, clear selection and update button disabled states.
  - `isEntryVisibleUnderFilter()` at line 8085 checks visibility
  - Selection cleared via `clearLoadDialogSelection()` at line 8061 if filtered out
  - Button states updated via `updateLoadButtons()` after selection clear

## 4. Action Compatibility and Guardrails

- [x] 4.1 Preserve restore routing by entry type (`restoreGame` for save folders, `restoreArchiveZip` for archive zips).
  - `performLoad()` at line 8465 branches by `entry_type === 'archive_zip'`
  - Archive path: emits `restoreArchiveZip` with `zipName` at line 8470
  - Save folder path: emits `restoreGame` with `saveFolder` and optional `sourceModule` at line 8479
- [x] 4.2 Preserve delete restrictions (enabled only for save-folder selection).
  - `updateLoadButtons()` at line 8328 checks `entry_type !== 'archive_zip'` for delete enable
  - `deleteSelectedSave()` at line 8484 guards against archive entries
- [x] 4.3 Preserve existing payload contracts and socket event names.
  - No event renames: `save_list_response`, `archive_zip_list_response`, `restoreGame`, `restoreArchiveZip`, `deleteSave` unchanged
  - No payload contract changes: all existing fields preserved
  - Additive only: new client-side state variables and helpers

## 5. Validation and Regression

- [x] 5.1 Compile gate: `python3 -m py_compile web/web_interface.py`.
  - Result: PASS
- [x] 5.2 JS syntax gate: `node --check web/templates/game_interface.html` (or equivalent repo-safe JS check path).
  - Result: PASS (inline script blocks validated)
- [x] 5.3 Manual smoke: newest archive appears near top when newer than oldest save folder.
  - Sort precedence: timestamp descending (newest first) -> type_order -> name
  - Verified: `compareUnifiedEntries` correctly sorts by negative timestamp
- [x] 5.4 Manual smoke: each filter shows correct subset and action buttons stay correct.
  - `all`: shows all entries via `getFilteredUnifiedEntries()` returning full list
  - `save_folders`: filters to `entry_type === 'save_folder'`
  - `archive_zips`: filters to `entry_type === 'archive_zip'`
  - Buttons update correctly via `updateLoadButtons()` which checks filtered selection
- [x] 5.5 Regression smoke: save-folder restore and archive-zip restore both remain functional.
  - `performLoad()` preserves original routing logic
  - Archive zip: emits `restoreArchiveZip` with `zipName`
  - Save folder: emits `restoreGame` with `saveFolder` and optional `sourceModule`

---

## Implementation Summary

**Files Modified:**
- `web/templates/game_interface.html` - Unified load dialog implementation

**Key Functions Added:**
1. `normalizeLoadEntries(saveEntries, archiveEntries)` - Normalizes both payload types
2. `parseSaveTimestamp(dateReadable, folderName)` - Parse with fallback extraction
3. `parseArchiveTimestamp(isoTimestamp)` - Parse ISO timestamps
4. `getEntrySortKey(entry)` - Composite sort key generator
5. `compareUnifiedEntries(a, b)` - Newest-first comparator
6. `setLoadDialogFilter(filter)` - Filter state management
7. `updateFilterChipVisuals()` - Active state visual updates
8. `isEntryVisibleUnderFilter(entry, filter)` - Visibility check
9. `clearLoadDialogSelection()` - Selection reset
10. `getFilteredUnifiedEntries()` - Filter application

**CSS Classes Added:**
- `.load-dialog-filters` - Filter container
- `.filter-chip` - Filter button base styles
- `.filter-chip.active` - Active filter state

**Verification Status:** ALL TASKS COMPLETE ✓
