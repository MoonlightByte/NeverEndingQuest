## Context

The archive zip restore change added archive rows to the Load dialog, but rendering still happens in two separate loops. This makes list order source-dependent instead of recency-dependent. Operators expect newest items first regardless of entry type.

## Goals / Non-Goals

Goals:
- Present save folders and archive zips in one merged timeline.
- Provide clear type filters with default `all`.
- Preserve current restore and delete semantics.
- Keep backend contracts additive and stable.

Non-Goals:
- No backend schema redesign.
- No new top-level restore entrypoints.
- No search or pagination changes in this pass.

## Decisions

### 1) Use a unified client-side entry model
Decision:
- Normalize both socket payloads into a shared list shape in the Load dialog renderer.

Rationale:
- Keeps backend behavior stable and localizes UX logic to one render path.

### 2) Enforce a shared sort key with deterministic fallback
Decision:
- Compute a sortable epoch per entry:
  - save folder: `save_timestamp` if present
  - archive zip: `modified_timestamp`
- Sort descending by epoch (newest first).
- Tie-break by `entry_type` then `display_name` for deterministic output.

Rationale:
- Prevents source-order bias and ensures stable rendering.

### 3) Add explicit type filters
Decision:
- Add three filter chips/buttons:
  - `all` (default)
  - `save_folders`
  - `archive_zips`

Rationale:
- Operators can quickly narrow to the asset class they need.

### 4) Preserve action compatibility
Decision:
- Restore button dispatches by selected `entry_type`.
- Delete button remains disabled unless selected entry is a save folder.

Rationale:
- Avoids behavioral regressions while changing list presentation.

## Data Flow

1. Load dialog opens.
2. Frontend requests existing save and archive payloads.
3. Frontend normalizes both payloads into one list.
4. Frontend applies active filter.
5. Frontend sorts filtered entries newest-first.
6. Frontend renders single list.
7. User action dispatches via existing route mapping.

## Risks / Mitigations

- Risk: Inconsistent timestamps across payloads.
  - Mitigation: fallback epoch handling and deterministic tie-breakers.
- Risk: Selection state mismatch after filter change.
  - Mitigation: clear selection when selected item no longer visible.
- Risk: Restore routing regression.
  - Mitigation: explicit entry-type branching and smoke checks.

## Migration Plan

1. Add unified normalization helper in load dialog JS.
2. Add filter UI and filter-state management.
3. Move to single merged render pipeline with shared sort.
4. Keep existing restore routing, mapped by entry type.
5. Keep delete restricted to save folders.
6. Run compile and interaction smoke checks.
