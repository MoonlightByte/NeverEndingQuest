# Developer Homebrew Ingest Tools - Design

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Developer CLI Tools (NEW)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ preflight    │  │ transform    │  │ orchestrator     │  │
│  │ - assess     │  │ - convert    │  │ - full pipeline  │  │
│  │ - classify   │  │ - normalize  │  │ - one command    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                 │                    │             │
│         └─────────────────┴────────────────────┘             │
│                          │                                   │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ sidecar      │  │ registry     │                         │
│  │ audit        │  │ guard        │                         │
│  │ - verify     │  │ - prevent    │                         │
│  │ - validate   │  │ - duplicates │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Existing Infrastructure (REUSED)                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ homebrewery_importer.py - deterministic ingest       │  │
│  │ import_homebrewery_module.py - CLI runner            │  │
│  │ module_stitcher.py - registry integration            │  │
│  │ module_ingest_watch.py - optional watcher            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Tool Specifications

### 1. homebrew_preflight.py

**Purpose:** Assess Homebrew source readiness

**Input:** Source markdown file path
**Output:** JSON readiness report

**CLI:**
```bash
python scripts/homebrew_preflight.py \
  --source Docs/modules/hombrew/Mangrove.md \
  --json
```

**Output:**
```json
{
  "ready": false,
  "issues": [
    {
      "type": "title_hygiene",
      "severity": "fixable",
      "current": "CLONE - ADVENTURE: ...",
      "recommended": "..."
    }
  ],
  "structure_class": "act_location",
  "can_auto_transform": true
}
```

### 2. homebrew_transform_to_deterministic.py

**Purpose:** Convert non-conforming sources to room-block format

**Input:** Source markdown file path
**Output:** Prepared markdown file

**CLI:**
```bash
python scripts/homebrew_transform_to_deterministic.py \
  --source Docs/modules/hombrew/Mangrove.md \
  --output /tmp/prepared_Mangrove.md
```

**Transform Rules:**
- Strip title prefixes
- Ensure metadata block
- ACT/LOCATION → ## Room N: blocks
- Infer exits from descriptions
- Add empty encounters if missing

### 3. homebrew_ingest_dev.py

**Purpose:** Full orchestration pipeline

**Input:** Source markdown file path
**Output:** Ingest result report

**CLI:**
```bash
python scripts/homebrew_ingest_dev.py \
  --source Docs/modules/hombrew/Mangrove.md \
  --strict \
  --json
```

**Pipeline:**
1. Preflight
2. Transform (if needed)
3. Dry-run validation
4. Registry guard check
5. Strict ingest
6. Sidecar audit
7. Registry verification

### 4. homebrew_sidecar_audit.py

**Purpose:** Verify ingest sidecar results

**Input:** Module slug
**Output:** Validation report

**CLI:**
```bash
python scripts/homebrew_sidecar_audit.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --require-success \
  --json
```

### 5. homebrew_registry_guard.py

**Purpose:** Prevent duplicates and verify registry state

**CLI:**
```bash
# Check for conflicts
python scripts/homebrew_registry_guard.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --check-duplicate \
  --json

# Verify presence
python scripts/homebrew_registry_guard.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --verify-present \
  --json

# Remove (cleanup)
python scripts/homebrew_registry_guard.py \
  --slug "Bad_Module" \
  --remove
```

## Dependencies

All tools depend on:
- `core/importers/homebrewery_importer.py`
- `core/generators/module_stitcher.py`
- `utils/file_operations.py`
- `config.py`

## Error Handling

All tools:
- Return non-zero exit code on failure
- Write structured JSON to stdout (with `--json`)
- Write human-readable errors to stderr
- Fail closed (safe defaults)

## Testing Strategy

- Unit tests for each tool
- Integration tests with sample Homebrew files
- End-to-end test with full pipeline
