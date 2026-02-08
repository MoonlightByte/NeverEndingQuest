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

**Implementation:** Planned 2-3 week migration (see `/plans/openrouter_llm_router_architecture.md`)

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
