# System Patterns

## Architecture Overview
The Tabletop Multiplayer system is implemented as a **Merge-Safe Plugin/Overlay**.

## Key Design Patterns

### 1. Merge-Safe Plugin Architecture
- Minimal modifications to core files (`web_interface.py`, `game_interface.html`).
- New functionality encapsulated in separate files (e.g., `tabletop_mode.js`, `tabletop_mode.css`).
- Use of clearly marked "Tabletop Mode" sections in core files for easy merging of upstream updates.

### 2. State-Driven UI
- The UI automatically activates Tabletop components when `partyMembers` in `party_tracker.json` has more than one entry.
- `party_tracker.json` is the source of truth for the party state.

### 3. PC vs NPC Separation
- **PCs**: Explicitly listed in `partyMembers`. Managed via Python functions.
- **NPCs**: Listed in `partyNPCs`. Managed via LLM or specific NPC logic.

### 3b. Role Lifecycle Continuity (NPC -> PC)
- Promotion is an in-place role transition, not a file clone.
- Character identity continuity is preserved via:
  - `character_id` (stable identity token)
  - `_tabletop_role_history` (append-only transition events)
- Role transitions normalize all role markers together (`type`, `character_type`, `character_role`).
- Party transition rule: remove from `partyNPCs`, add to `partyMembers`, keep `active_character` unchanged.
- This enables future PC -> NPC retirement without splitting character identity.

### 4. Component Relationship
- `web_interface.py`: Exposes API for PC management and character switching.
- `utils/pc_manager.py`: Logic for modifying party state and building entrance prompts.
- `party_tracker.json`: Persists party state.
- `game_interface.html`: Conditionally renders character tabs and party sidebar.
- `game.js` / `tabletop_mode.js`: Handles frontend logic for tab switching and API calls.

### 5. Automated Narrative Trigger Pattern
- Specialized logic in `web_interface.py` intercepts character addition events.
- It calls `pc_manager.get_entrance_prompt()` to build a high-quality DM instruction.
- The instruction is injected into `user_input_queue`, appearing to the engine as a high-priority narrative request.
- This pattern allows for rich, context-aware narration without modifying the core LLM processing loop.

### 5b. Non-Chat Background Repair Pattern
- Character readiness remediation runs through dedicated API endpoints (preview/apply), not chat commands.
- Repairs are safety-bounded:
  - whitelist-only narrative field updates
  - mechanical snapshot guard to block unintended stat changes
  - post-patch audit gate before persistence
- UI uses preview -> confirm so facilitator control is preserved.

### 6. Passive Multi-PC Combat Tracking Pattern
- `MultiPCCombatManager` (in `multi_pc_combat.py`) maintains a lightweight, in-memory state of the current combat.
- It provides specialized formatting methods (`format_party_turn_summary`, `format_pc_context_for_prompt`) to create context blocks for the LLM.
- **Initiative Tracker Override:** In multi-PC mode, the system bypasses the AI initiative tracker (which only recognizes ONE player) and uses `format_initiative_tracker()` to generate deterministic initiative instructions from the `turn_queue` and `pc_states`.
- `combat_manager.py` uses a synchronization loop:
    1. Reload `active_character` from `party_tracker.json` (UI-driven).
    2. Refresh `MultiPCCombatManager` with latest character file data.
    3. Inject an authoritative **Combat Phase State** block.
    4. Generate initiative tracker via `multi_pc_manager.format_initiative_tracker(encounter_data)` (multi-PC mode only).
- **Determinism Rule:** The system calculates pending enemies based on phase state (`pc_phase_complete`) rather than a volatile turn index. This ensures that switching PC tabs in the UI does not disrupt the "source of truth" for who acts during the Enemy Phase.
- This pattern allows the LLM to remain the primary narrator while ensuring it respects hard-wired, deterministic phase transitions.

### 7. Head-Body-Tail Prompt Architecture
To maintain high coherence and prevent LLM "amnesia" in complex scenarios (like Multi-PC combat), the prompt is structured into three functional segments:
- **The Head (Immutable/Authoritative)**: 
    - Contains the "Constitution" (system rules) and the "Authoritative State" (Python-managed JSON).
    - In Combat: Includes a consolidated JSON of ALL PCs (HP, status, initiative).
    - Never compressed or deleted; refreshed every turn to ensure the LLM has perfect ground-truth data.

### 8. Multi-PC Validation Strategy
- **Specialized Multi-PC Referee**: Uses a dedicated validation prompt (`combat_validation_prompt_multipc.txt`) that understands Multi-PC turn order and batch processing rules.
- **Python Guardrails**: Hard-wired mechanical checks in `combat_manager.py` act as a second layer of defense, specifically preventing round advancement if any PCs haven't acted.
- **Dynamic Mode Switching**: The validation layer automatically adjusts based on the presence of the `multi_pc_manager`.
- **The Body (Compressible History)**:
    - Contains the narrative flow of previous interactions.
    - Compressed into JSON summaries as it grows to save tokens while preserving plot points.
- **The Tail (Fresh Narrative)**:
    - The last 1-3 interactions kept in raw text.
    - Preserves immediate conversational flow and nuance.

### 8. Capability-Based LLM Router Pattern (PLANNED - 2026-02-07)
A centralized routing system for all LLM calls that abstracts provider selection and model configuration:

**Router Interface:**
```python
from utils.llm_router import llm

# Single interface regardless of provider or model
response = llm.call(role="narrate", messages=[...])
# Routes to Trinity Large Preview (creative), temp 0.8

result = llm.call(role="combat_validate", messages=[...])
# Routes to Gemini 2.5 Flash Lite (mechanics), temp 0.2

data = llm.call(role="extract_character", messages=[...], structured_output=CharacterSchema)
# Routes to Flash Lite with JSON mode, validates against CharacterSchema
```

**Capability-Based Model Selection:**
- **Creative Capability:** Trinity Large Preview (free) for narration, scene description, NPC dialogue (temp 0.8)
- **Mechanics Capability:** Gemini 2.5 Flash Lite for combat simulation, validation, calculations (temp 0.2)
- **Structured Capability:** Gemini 2.5 Flash Lite with JSON mode for data extraction, schema validation (temp 0.1)

**Fallback Strategy:**
- All capabilities fall back to GPT-4.1 if primary model unavailable
- User notified to update config when models change/disappear
- Hard stop on quota/billing errors (game cannot continue without LLM)

**Dual-Mode Architecture:**
- **MULTIPLAYER_MODE = False:** Original OpenAI hardwired (upstream compatible)
- **MULTIPLAYER_MODE = True:** Full OpenRouter with capability routing
- Mode detected at startup, requires restart to change
- Maintains upstream merge potential while enabling TT-only development

**Strategic Purpose:**
- Centralizes 89 LLM call sites across 39 files
- Enables fine-grained model selection (narrator vs mechanics)
- Foundation for future extraction to clean TT-only fork
- Plugin architecture allows gradual hardening toward TT-only

**Implementation:** Planned 2-3 week migration (see `/plans/version-2/openrouter_llm_router_architecture.md`)

## Data Schema Extensions
- `party_tracker.json` now includes:
  - `partyMembers`: List of character names.
  - `active_character`: The name of the currently selected character.
  - `combatInitiative`: Stored group initiative results for party vs enemies.

## Prompt File Development Workflow

### 9. Dual-Format Prompt Architecture
The system maintains two formats for LLM prompts to support both development and production:

**Uncompressed (Narrative) Format:**
- **Purpose:** Human-readable development and reference
- **Structure:** Prose-based with markdown headers (`## Section Name`)
- **Characteristics:**
  - Detailed explanations and examples
  - Conversational tone for developer understanding
  - Long-form documentation (~900-1000 lines)
- **Files:** `combat_sim_prompt.txt`, `combat_sim_prompt_multipc.txt`

**Compressed (Structured) Format:**
- **Purpose:** Production use by the LLM
- **Structure:** Machine-optimized @-directive blocks (`@SECTION_NAME={...}`)
- **Characteristics:**
  - Hierarchical JSON-like structure
  - Concise, token-efficient (~500 lines)
  - Added sections not in uncompressed (e.g., `@ROUND_RULES`, `@UPDATE_RULES`, `@DEATH_GATE`)
  - Controlled via `USE_COMPRESSED_PROMPTS` toggle in `combat_manager.py`
- **Files:** `combat_sim_prompt_compressed.txt`, `combat_sim_prompt_multipc_compressed.txt`

**Development Workflow:**
1. **Development:** Edit uncompressed narrative files for clarity and completeness
2. **Compression:** Convert to structured @-directive format with enhanced rules
3. **Production:** System loads compressed versions for token efficiency
4. **Synchronization:** Keep both formats in sync - compressed is the "source of truth" for production

**Key Insight:** The compressed format often contains **more** structured content than the uncompressed version because it evolved separately with additional rules and validators. When porting features between modes (single-player → multi-PC), always compare compressed files, not uncompressed.

### 10. Shared Character Audit Pipeline
- Creation, promotion, and readiness repair all route through shared server-side audit logic.
- Deterministic outcomes are used across flows:
  - `schema_error`
  - `completeness_error`
  - `success`
- This keeps UI behavior flexible while centralizing persistence correctness.

### 11. Two-Plane Memory Retrieval Pattern (2026-02-13)
- Memory architecture now separates:
  - **God mode history plane**: persistent, additive record in SQLite (`data/memory.db`)
  - **Prompt retrieval plane**: deterministic bounded top-K query outputs
- Core modules:
  - `core/memory/memory_db.py` (migrations and schema)
  - `core/memory/memory_retrieval.py` (ranking retrieval contracts)
  - `core/memory/memory_ingest.py` (idempotent ingest + backfill)
- Retrieval ranking combines pinned state, active-PC relevance, importance, persistence class, decay bucket, and reinforcement.
- Guardrails:
  - limit clamping
  - deterministic tie-break ordering
  - optional audit logging that is best-effort and non-blocking

### 12. Archive-Ready Backfill Pattern (2026-02-13)
- Backfill utility: `scripts/backfill_memory_db.py`
- Sources:
  - `journal.json`
  - `modules/conversation_history/conversation_history.json`
  - `modules/conversation_history/combat_conversation_history.json`
- Identity/linking behavior:
  - Upsert known party entities from `party_tracker.json`
  - Link events by known entity-name matches
  - Deferred-link fallback when confidence is low/no match
- Operational flags:
  - `--dry-run` for non-destructive preview on temp DB copy
  - `--include-system` to include system-channel history content

### 13. Memory Portability Package Pattern (2026-02-13)
- Portability module: `core/memory/memory_portability.py`
- Exposes explicit operators for campaign continuity workflows:
  - `export_memory_db_package()`
  - `validate_memory_package()`
  - `import_memory_db_package()`
- Export package shape:
  - `memory.db` DB artifact copy
  - `manifest.json` with schema version, row counts, migration set, campaign metadata, SHA-256 hash
- Import safety model:
  - validate-first (manifest/schema/hash)
  - non-destructive by default (no overwrite unless explicit)
  - `dry_run` mode for zero-write validation

### 14. Selective Source Ingestion Pattern (2026-02-13)
- Backfill supports deterministic source gating via `--sources`:
  - `journal`
  - `conversation`
  - `combat`
- Invalid selector values fail fast with clear allowed-value output.
- Source gating preserves idempotency guarantees because ingest dedupe remains keyed on source/checksum.

### 15. Dormant Streaming Foundation Pattern (2026-02-14)
- When streaming UX regresses player experience, keep backend lifecycle scaffolding but disable runtime execution.
- **Keep:**
  - `web/extensions/streaming_events.py` (event lifecycle helper)
  - `model_config.py` stream flags with defaults OFF
  - minimal host transport + template flag pass-through in `web/web_interface.py`
- **Revert:**
  - runtime generation integrations (`main.py`, `combat_manager.py`)
  - frontend draft rendering and stream sentence TTS (`game_interface.html`, `tts_queue_manager.js`)
- Preserve baseline canonical narration path (`WebOutputCapture` -> `game_output`) with no stream suppression coupling.
- This pattern keeps merge-safe future runway while eliminating immediate UX/token-cost risk.

### 16. Structured-to-Prose Portrait Prompt Pattern (2026-02-19)
- Portrait generation quality improves when structured profile fields are translated into one natural-language visual brief before style instructions.
- Prompt assembly order:
  - visual brief paragraph (identity + appearance + personality cues)
  - composition instructions (head-and-shoulders, face focal)
  - strict negatives (no text/UI/sheet/document overlays)
- Avoid positive terms that imply documents/cards (for example, passport/card/profile sheet wording).
- Use defensive parsing for optional appearance fields (`age`, `height`, `weight`) so non-numeric values do not break prompt composition.
- Normalize leading personality/bond phrasing (`believes that`, `loyal to`, `sometimes`, `can be`) before connector composition to prevent duplicated phrase artifacts.
- Add punctuation guards after composition (`....` -> `...`) for bounded free-text truncation paths.

### 17. Fast-Lane Combat Initiation Pattern (2026-02-26)
- Skip redundant LLM narration when the main DM response already described the encounter context.
- **Guard Condition:** `multi_pc_manager is not None and encounter_data.get("awaitingPcGroupRoll", False) is True`
- **Fast-Lane Behavior:**
  - Skip initial-scene LLM generation block entirely
  - Print immediate system prompt: `[SYSTEM] Combat initiated. Initiative pending. Enter /init <1-20> to begin combat.`
  - Flush stdout immediately after print
- **Non-Fast-Lane Behavior:** Perform full initial scene LLM generation (single-player, resumed combat, non-Phase-1)
- **Cost/UX Impact:** Saves ~2-5 seconds + ~$0.01-0.03 per combat initiation by eliminating duplicate narration
- **Regression Safety:** All existing `/init` validation and combat loop behavior preserved; only adds conditional branch at combat handoff

### 18. Session State Poisoning Prevention Pattern (2026-02-26)
- Accumulated system messages with restrictive constraints (e.g., "do NOT emit gameplay actions") can poison LLM context and block core functionality.
- **Detection:** Filter messages containing known constraint markers: `"SESSION RESUME RECAP ONLY"`
- **Cleanup Strategy:**
  - Filter at session boundary (before injecting fresh recap)
  - Log removal count for observability: `STATE_CHANGE: Removed N stale recap messages`
  - Provide manual cleanup utility for active poisoned sessions
- **Prevention:** Never allow identical constraint messages to accumulate; always dedupe/filter before context injection

### 19. Deferred Reveal Auto-Scroll Pattern (2026-02-26)
- Text reveal synchronization (word-by-word TTS) can break container auto-scroll if content height changes after initial append.
- **Problem:** Pre-initializing reveal mode with `display: none` on unrevealed text causes collapsed height at append time.
- **Solution:**
  1. Let message append at full height (no pre-init reveal)
  2. Initialize reveal only when playback actually starts
  3. Re-pin scroll after reveal completion using `requestAnimationFrame(() => scrollToBottom(container))`
- **Fallback Safety:** If boundary events don't arrive (1s watchdog), reveal full text immediately then re-pin scroll
- **End-State Safety:** Always call scroll pin in `finalizeReveal()` to catch stop/error paths
