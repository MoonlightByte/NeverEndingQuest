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

## Tabletop Mode Additions
- `utils/pc_manager.py`: Centralized PC/Party management logic.
- `prompts/tabletop/entrance_narration.txt`: Template for cinematic character introductions.
- `web/static/js/tabletop_mode.js`: Client-side logic for multiplayer UI.
- `web/static/css/tabletop_mode.css`: Styles for multiplayer-specific components.

## LLM Router Architecture (PLANNED)
**Status:** Architecture plan complete, implementation pending
**Location:** `/plans/openrouter_llm_router_architecture.md`

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
