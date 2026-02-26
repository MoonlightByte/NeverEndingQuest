# Technical Context

## Core Technologies
- **Backend**: Python (Flask)
- **Frontend**: HTML, CSS, JavaScript (Jinja2 templates)
- **State Management**: JSON-based files (`party_tracker.json`, character JSONs)
- **AI**: Integration with OpenAI/Gemini/LM Studio for DM capabilities.

## Development Setup
- **OS**: macOS
- **Shell**: /bin/zsh
- **Python Environment**: `.venv` (**CRITICAL**: All python commands must be run from within the virtual environment)
- **VCS**: Git (Main repo tracking `MoonlightByte/NeverEndingQuest`)

## Technical Constraints
- **Merge Compatibility**: Must avoid breaking single-player or creating massive merge conflicts with upstream.
- **File System Authority**: State must be persisted to the file system to ensure continuity.
- **Concurrency**: Basic file locking is in place for state-sensitive files.

## Key Dependencies
- `flask`: Web server.
- `openai` / `google-generativeai`: AI integrations.
- `json`: Data persistence.
- `sqlite3` (stdlib): Long-term memory persistence (`data/memory.db`).

## Tabletop Mode Additions
- `utils/pc_manager.py`: Centralized PC/Party management logic.
- `prompts/tabletop/entrance_narration.txt`: Template for cinematic character introductions.
- `web/static/js/tabletop_mode.js`: Client-side logic for multiplayer UI.
- `web/static/css/tabletop_mode.css`: Styles for multiplayer-specific components.

## Portrait UX Locking (2026-02-19)
Frontend-only state management to prevent duplicate portrait operations and provide clear async UX feedback.

**State Variables:**
- `portraitOperationInFlight` (boolean): Shared lock for Upload/Create operations
- `portraitOperationMessage` (string): Current operation message for placeholder
- `backendIsProcessing` (boolean): Backend processing state for coordination
- `backendStatusMessage` (string): Backend status message

**Core Functions:**
- `setPortraitButtonsDisabled(disabled)`: Disables/enables all `.portrait-action-btn` elements
- `syncInputAndPortraitUiState()`: Central coordinator for all UI state
  - Disables input/send when: `!connected || !gameStarted || backendIsProcessing || portraitOperationInFlight`
  - Sets placeholder priority: portrait message → backend message → default
  - Updates portrait button states (disabled during portrait operations only)

**Integration Points:**
- `socket.on('status_update')` and `socket.on('status_response')`: Store backend state, call sync function
- `window.uploadPortrait()`: Early return if lock active, set lock/message before fetch, clear in `.finally()`
- `window.submitPortraitProfile()`: Same lock pattern for Create flow
- `displayCharacterStats()`: Reapplies button disabled state after DOM refresh

**CSS:**
- `.portrait-action-btn:disabled`: `opacity: 0.4`, `cursor: not-allowed`
- `.portrait-action-btn:disabled:hover`: No hover effect (prevents visual confusion)

**Key Design Decisions:**
- Portrait lock takes precedence over backend status for UX (shows portrait-specific message)
- Input stays disabled until BOTH portrait operation AND backend processing complete
- Portrait buttons only disabled during portrait operations (backend processing doesn't block them)
- Removed redundant `createPortraitInFlight` variable in favor of shared state

**File Modified:** `web/templates/game_interface.html`

## Memory Foundation Stack (2026-02-13)
- `core/memory/memory_db.py`
  - Idempotent migration bootstrap and additive schema tables
  - Optional readiness tables for future EGO/RATIO policy/audit hooks
- `core/memory/memory_retrieval.py`
  - `get_entity_timeline(...)`
  - `get_context_memories(...)`
  - `get_retirement_return_memories(...)`
- `core/memory/memory_ingest.py`
  - `ingest_journal_entry(...)` dedupe via source/checksum
  - `ingest_journal_file(...)`
  - `backfill_memory_db_from_histories(...)`
- `web/routes/memory_routes.py`
  - `GET /api/memory/entity/<entity_id>?limit=25` (read-only, safe fallback)
- `scripts/backfill_memory_db.py`
  - `--dry-run` for temp-copy, no-persist preview
  - `--include-system` to include system-channel history records
  - `--sources` for selective source ingest (`journal`, `conversation`, `combat`)

## Memory Portability Stack (2026-02-13)
- `core/memory/memory_portability.py`
  - `export_memory_db_package(source_db_path, output_dir, overwrite=False)`
  - `validate_memory_package(package_dir)`
  - `import_memory_db_package(package_dir, target_db_path, overwrite=False, dry_run=False)`
- CLI integration in `scripts/backfill_memory_db.py`:
  - `--export-package <dir>`
  - `--import-package <dir>`
  - `--overwrite`
  - `--dry-run` (import validation-only)

## World Observer Telemetry DB (Current State)
- `core/managers/world_observer.py` uses `data/world_surveillance.db` as a write-only telemetry ledger for event/surveillance logs.
- Current gameplay does not depend on reading this DB; it is non-critical and regenerable.
- The DB file can be safely deleted when needed; it will be recreated automatically when `get_world_observer()` is invoked.
- This remains aligned with future EGO/RATIO observability plans, but is not a hard runtime dependency today.

## LLM Router Architecture (PLANNED)
**Status:** Architecture plan complete, implementation pending
**Location:** `/plans/version-2/openrouter_llm_router_architecture.md`

**Core Components:**
- `utils/llm_router.py` - Centralized LLM router with capability-based routing
  - Trinity Large Preview (free) for creative tasks
  - Gemini 2.5 Flash Lite for mechanics/structured tasks
  - GPT-4.1 universal fallback
- `model_config.py` - Capability configurations (ROLE_CAPABILITIES, CAPABILITY_MODELS, CAPABILITY_TEMPERATURES)

**Technical Approach:**
- Single interface: `llm.call(role="...", messages=[...])`
- Automatic model selection based on role capability
- JSON mode for structured output with Pydantic validation
- Cost tracking (total + by model/capability/role)
- Hard stop error handling (quota/billing)
- Dual-mode: MULTIPLAYER_MODE toggle for upstream compatibility

**Migration Scope:**
- 89 LLM call sites across 39 files
- 3-phase implementation (2-3 weeks total)
- Gradual hardening strategy (Path A): maintain upstream merge potential

**Strategic Decision:**
- Path A: Gradual Hardening with dual-mode support
- Keep SP code as merge insurance policy
- All new features are TT-only
- Eventually extract to clean TT-only fork when value exceeds merge potential
