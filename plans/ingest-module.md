# Homebrew Module Ingest Plan (Tester Wave 1)

## Status

- Planned
- Priority: High (tester validation)
- Scope: First Homebrew markdown ingest (Birble adventure), then generalize to similar markdown modules, then begin PDF ingest foundation

## Objective

Build a deterministic, NEQ-native ingest path for:

1. `Docs/CLONE - Adventure - Birble Tinkertop's Tinkertop Adventuring Academy.txt`
2. Similar Homebrewery/GMBinder markdown exports
3. Initial PDF parsing groundwork (after markdown path is proven in play)

Primary goal for this tester version:

- Ingest the Birble module into valid NEQ module artifacts using sequential NEQ IDs and pass schema validation.
- Enable an always-on watch folder workflow so facilitators can drop files into `modules/ingest/` and let the server ingest automatically.

## Ingest Watch Folder Contract (Locked)

- Watch folder: `modules/ingest/`
- Archive folder: `modules/ingest/archive/`
- Behavior:
  - User saves supported source files (`.md`, `.markdown`, `.txt`) into `modules/ingest/`
  - Server watcher detects stable files, ingests to module artifacts, then moves processed source to archive
  - Every archived source gets sidecar result JSON (`*.result.json`) with status, errors, and generated artifact list
- Publish policy:
  - Strict validation enabled by default
  - Validation failures are archived as `quarantined` (not auto-published/stiched)

## Why This Source Is a Good MVP

Compared to the Drakkenheim encounter supplement, this file is a traditional adventure with:

- Clear chapter + room progression (`Room 1` to `Room 22`, `Room 100` finale)
- Per-room puzzle/combat mechanics and DM instructions
- Ending/epilogue section
- Appendix content (`Magic Items`, `Monster Manual`)

This structure maps directly to NEQ module scaffolding with minimal guesswork.

## Non-Negotiable Constraints

1. **NEQ sequential IDs only**
   - Do not use literal source room numbers for location IDs.
   - Preserve source room numbers in display names/metadata only.
   - Example: `Room 100: Birble Battle Bot 9001` can map to `locationId: BTA23`.

2. **Python deterministic first, LLM optional second**
   - Deterministically parse headings, room blocks, tables, and known subsections.
   - Use LLM only for bounded enrichment where source is sparse.

3. **Strict validation gate**
   - Must pass `python core/validation/validate_module_files.py`.
   - If validation fails: quarantine output, do not auto-publish/stitch.

4. **Fail-open batch behavior, fail-closed publish behavior**
   - One bad file should not crash batch runs.
   - But invalid modules must not be published.

5. **Merge-safe architecture**
   - Add importer in dedicated files (`core/importers/`, `scripts/`) with minimal core coupling.

## Deliverables (Wave 1)

1. New importer module:
   - `core/importers/homebrewery_importer.py`
2. New ingest CLI:
   - `scripts/import_homebrewery_module.py`
3. Tests:
   - Parser unit tests
   - Emission + schema tests
   - End-to-end Birble ingest test
4. New generated module output (in tester workspace):
   - `modules/<module_slug>/...`
5. Validation + smoke report notes (command outputs captured in implementation PR notes)
6. Watch worker integration:
   - Startup hook in `web/web_interface.py`
   - Worker implementation in `web/extensions/module_ingest_watch.py`
   - Config toggles in `model_config.py`

## Target Output Shape (Wave 1)

For module slug (example): `Birble_Tinkertop_Adventuring_Academy`

- `modules/Birble_Tinkertop_Adventuring_Academy/module_context.json`
- `modules/Birble_Tinkertop_Adventuring_Academy/module_plot.json`
- `modules/Birble_Tinkertop_Adventuring_Academy/map_BTA001.json`
- `modules/Birble_Tinkertop_Adventuring_Academy/areas/BTA001.json`
- Optional future expansion:
  - `modules/Birble_Tinkertop_Adventuring_Academy/monsters/*.json`
  - `modules/Birble_Tinkertop_Adventuring_Academy/characters/*.json`

Where:

- Area ID: `BTA001`
- Location IDs: `BTA01`, `BTA02`, ..., sequential
- Source room label retained in location `name` and metadata field

## High-Level Pipeline

1. **Load and sanitize source**
2. **Extract semantic markdown** (ignore presentation markup)
3. **Parse room chain and subsections**
4. **Parse deterministic tables**
5. **Normalize to intermediate schema**
6. **Emit NEQ scaffold JSONs**
7. **Optional bounded LLM enrichment**
8. **Validate + quarantine/publish decision**

## Intermediate Data Contract (Importer Internal)

```python
{
  "source": {
    "path": str,
    "title": str,
    "description": str,
    "hash": str,
    "format": "homebrewery_md"
  },
  "module_seed": {
    "module_name": str,
    "module_description": str,
    "level_min": int,
    "level_max": int,
    "module_type": str
  },
  "chapters": [
    {
      "title": str,
      "summary": str,
      "rooms": [
        {
          "source_room_number": int,
          "source_room_title": str,
          "name": str,
          "description": str,
          "puzzle": str,
          "solution": str,
          "creatures": [str],
          "tables": [
            {
              "name": str,
              "dice": str,
              "rows": [{"range": str, "result": str}]
            }
          ],
          "dc_hints": [str],
          "reward_hints": [str],
          "exit_comment": str
        }
      ]
    }
  ],
  "appendix": {
    "magic_items": [str],
    "stat_blocks": [str]
  }
}
```

## Proposed Public Function Signature

```python
def import_homebrewery_adventure_to_module(
    source_path: str,
    module_slug: str | None = None,
    output_root: str = "modules",
    strict: bool = True,
    llm_enrich: bool = True,
    parse_appendix_stats: bool = True,
) -> dict:
    """Parse Homebrewery markdown export into NEQ module artifacts."""
```

Expected return payload:

```python
{
  "status": "success" | "quarantined" | "error",
  "module_slug": str,
  "artifacts": [str],
  "validation": {"passed": bool, "errors": [str]},
  "quarantine_reason": str | None
}
```

## Detailed Implementation Plan

### Phase 1 - Single-Module MVP (Birble)

#### 1.1 Importer module scaffold

Create `core/importers/homebrewery_importer.py` with:

- `load_source_text(source_path: str) -> str`
- `extract_metadata_block(text: str) -> dict`
- `strip_presentation_blocks(text: str) -> str`
  - remove fenced `css` blocks
  - remove `<style>...</style>`
  - drop known Homebrewery layout macros (`{{frontCover...}}`, logos, page numbers, TOC wrappers)
- `normalize_markdown(text: str) -> str`
  - normalize whitespace, keep headings/tables/list text

#### 1.2 Semantic parser

Add parser functions:

- `extract_heading_tree(markdown_text: str) -> list[dict]`
- `extract_room_blocks(markdown_text: str) -> list[dict]`
  - detect `## Room <num>: <title>` blocks
  - capture until next `## Room` or next `#` major heading
- `extract_room_subsections(room_text: str) -> dict`
  - capture `### The Puzzle`, `### Solution`, `#### Creatures`, `### Burble's Exit Comment`, etc.
- `extract_markdown_tables(block_text: str) -> list[dict]`
  - parse markdown table headers and rows
  - retain dice column labels and row ranges verbatim

#### 1.3 Intermediate normalization

Add:

- `build_intermediate_from_birble(parsed: dict) -> dict`

Rules:

- Set module seed from title + intro
- Build one primary area (`BTA001`) for challenge room chain
- Preserve source room numbers in per-room metadata field:
  - `"sourceRoom": 100`
- Keep location IDs sequential regardless of source numbering

#### 1.4 Deterministic NEQ emission

Add:

- `emit_module_scaffold(intermediate: dict, module_slug: str, output_root: str) -> dict`

Emission rules:

- `module_context.json`: include area/location/NPC references and parse notes
- `module_plot.json`: deterministic minimal plot spine:
  - Hook
  - Enter academy
  - Progress challenge rooms
  - Final encounter (`Room 100` source label)
  - Return to office / resolution
- `areas/BTA001.json`:
  - `areaName`, `areaId`, `locations[]`
  - each location includes room name, description, puzzle/solution in DM notes, optional creatures seeds
- `map_BTA001.json`:
  - room graph in deterministic progression order
  - default linear connections unless explicit room-order table indicates branching

#### 1.5 Bounded LLM enrichment (optional)

Add:

- `enrich_scaffold_with_llm(scaffold: dict, intermediate: dict) -> dict`

LLM allowed scope:

- improve `moduleDescription`
- flesh out `timelineEvents`
- add 1-3 coherent `factions` if missing
- enrich plot point descriptions

LLM prohibited scope:

- changing IDs
- changing parsed room ordering
- inventing off-source core mechanics that conflict with extracted text

#### 1.6 Validation and quarantine

Add:

- `validate_emitted_module(module_slug: str) -> dict`
- `quarantine_invalid_module(module_slug: str, errors: list[str]) -> dict`

Validation command:

- `python core/validation/validate_module_files.py`

Behavior:

- strict mode: return `quarantined` on any validation failure
- non-strict mode: still report errors, but keep artifacts for manual repair

#### 1.7 CLI entrypoint

Create `scripts/import_homebrewery_module.py`:

- Required args:
  - `--source`
- Optional args:
  - `--module-slug`
  - `--strict`
  - `--no-llm`
  - `--dry-run` (parse + preview, no writes)

Example:

```bash
python scripts/import_homebrewery_module.py \
  --source "Docs/CLONE - Adventure - Birble Tinkertop's Tinkertop Adventuring Academy.txt" \
  --module-slug "Birble_Tinkertop_Adventuring_Academy" \
  --strict
```

#### 1.8 Watch worker integration (server-driven ingest)

Create `web/extensions/module_ingest_watch.py`:

- Polling worker (daemon thread) with idempotent start behavior
- File stability guard (require unchanged size/mtime over one poll cycle)
- Allowed extension filtering
- Ingest call path to importer function
- Archive move on completion to `modules/ingest/archive/`
- Sidecar result JSON write per file
- Runtime stats counters and structured logging

Wire startup in `web/web_interface.py`:

- Start watcher at server boot when enabled
- Fail-open startup (warn only, never crash web server)

Config block in `model_config.py`:

- `ENABLE_MODULE_INGEST_WATCH`
- `MODULE_INGEST_WATCH_DIR`
- `MODULE_INGEST_ARCHIVE_DIR`
- `MODULE_INGEST_POLL_INTERVAL_SECONDS`
- `MODULE_INGEST_ALLOWED_EXTENSIONS`
- `MODULE_INGEST_STRICT_VALIDATION`

### Phase 2 - Tester Verification for Birble

#### 2.1 Parser verification checks

- Room count extracted matches source room headings
- Room title mapping correct
- `Room 100` preserved as source label but sequential NEQ ID assigned
- Section extraction coverage (puzzle/solution/creatures) reported

#### 2.2 Module validation checks

- Schema validator passes for emitted files
- No malformed IDs
- No missing required fields in module/map/area/plot JSON

#### 2.3 Gameplay smoke checks

- Start module from web UI
- Traverse several rooms
- Confirm room descriptions and puzzle prompts surface correctly
- Confirm final room accessible in map progression

#### 2.4 Fix loop

- Record issues from tester run
- Patch importer transforms (not manual one-off module edits where possible)
- Re-ingest to prove deterministic reproducibility

### Phase 3 - Generalize to Similar Markdown Modules

After Birble works in play:

#### 3.1 General parser profile system

Introduce parser profiles:

- `homebrewery_adventure_rooms_v1` (Birble-like)
- future profiles for chapter/scene styles without room numbering

#### 3.2 Generalized section mapping

- Robust heading pattern support (`Room`, `Scene`, `Act`, `Chapter`)
- Multiple area segmentation if source has separate location clusters

#### 3.3 Batch ingest script

Add batch mode support:

- scan `Docs/` for candidate md/txt exports
- per-file status outputs
- skip unchanged files by hash

#### 3.4 Shared quality gates

- same strict validation/quarantine contract
- per-source parse quality metrics (coverage percentages)

### Phase 4 - Start PDF Parsing Foundation

Only after markdown ingest is stable:

#### 4.1 PDF extractor baseline

- Add `core/importers/pdf_extractor.py`
- extract text by page spans
- normalize into paragraph/heading candidates

#### 4.2 Unified intermediate contract

- PDF extractor should emit same intermediate shape as markdown parser
- keep downstream emitter unchanged

#### 4.3 Reliability policy

- if PDF extraction confidence is low, quarantine automatically
- no silent auto-publish from weak OCR/text extraction

## Test Plan

## Unit tests

- markdown cleaning tests (style/macro stripping)
- room block extraction tests
- subsection extraction tests
- table parsing tests (dice ranges and row integrity)
- sequential ID assignment tests

## Integration tests

- Birble source ingest end-to-end with strict mode
- schema validation pass checks
- dry-run output stability test

## Regression tests

- ensure importer changes do not alter IDs for same source hash
- ensure known room titles remain mapped identically

## Operational Commands (Planned)

```bash
# Single-source ingest (strict)
python scripts/import_homebrewery_module.py --source "Docs/CLONE - Adventure - Birble Tinkertop's Tinkertop Adventuring Academy.txt" --module-slug "Birble_Tinkertop_Adventuring_Academy" --strict

# Validation gate
python core/validation/validate_module_files.py

# Optional smoke checks
python run_web.py
```

## Risks and Mitigations

1. **Interleaved layout markup corrupts parse**
   - Mitigation: strict content-mode stripping + parser profile tests

2. **Room parsing misses uncommon headings**
   - Mitigation: fallback subsection capture + coverage metrics warnings

3. **Stat block appendix variability**
   - Mitigation: treat appendix parsing as optional in Wave 1; rely on deterministic room ingest first

4. **Schema drift or missing required fields**
   - Mitigation: emit from explicit templates + mandatory validator gate

## Definition of Done (Wave 1)

1. Birble source ingests via one command into NEQ module artifacts.
2. IDs are NEQ-sequential and deterministic across reruns.
3. Output passes module validation in strict mode.
4. Tester can play through initial rooms and reach finale path.
5. Plan for Phase 3 generalization and Phase 4 PDF foundation remains unchanged and actionable.

## Next Steps After Wave 1

1. Run tester playthrough and capture friction points.
2. Implement parser profile abstraction for same-family markdown modules.
3. Start PDF extractor with shared intermediate schema and quarantine-first policy.
