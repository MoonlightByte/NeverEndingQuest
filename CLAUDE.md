# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeverEndingQuest is an AI-powered Dungeon Master system for running SRD 5.2.1 compatible tabletop RPG campaigns. It features advanced token compression (70-90% reduction), a web interface with real-time updates, and a comprehensive module creation toolkit.

## IMPORTANT: Active Refactor Context - Read Before Any AI/Model Work

### Failed Plan Documents - DO NOT FOLLOW
The following documents in `docs/plans/` represent **failed prior attempts** at this refactor. They were
abandoned because the approach was overly complex and the models hallucinated during execution.
**Do not use them as guidance:**
- `docs/plans/2026-02-12-openai-refactor-callsite-task-matrix.md`
- `docs/plans/2026-02-12-openai-refactor-restart-plan.md`
- `docs/plans/2026-02-08-openai-model-migration-design.md`

All documents in `docs/plans/` and `docs/audit/` are historical artifacts only.

### Reference Documents (Gitignored - Local Only)
Current model documentation lives here - read these before doing any model work:
- `docs/reference/openai-models-reference.md` - GPT-5.2 family, API changes, migration mapping
- `docs/reference/gemini-models-reference.md` - Gemini 3 family, API differences, parallel call patterns
- `docs/reference/legacy-model-variable-map.md` - All 21 model variables -> legacy model strings, callsite counts, tier mapping, known bugs
- `docs/reference/capture-report-template.md` - Standardized report format for per-callsite model comparison (quality, correctness, cost, latency)
- `tests/model_validation/README.md` - Index of per-callsite model validation scripts (replay captured prompts through models, measure correctness + latency)

### API Callsite Inventory - Source of Truth
**`docs/audit/2026-02-12-openai-api-call-inventory.json`** is the authoritative list of all 95 API
callsites. Use this as the basis for tracking migration progress and designing the capture system.

Fields per entry:
- `task_id` - Unique ID (T001-T095)
- `path` + `line` - Exact file location
- `scope` - `runtime` (59, highest priority), `dev_misc` (35, low priority), `tests` (1)
- `model_expr` - The variable or literal used at call time
- `has_temperature`, `has_reasoning_effort`, `has_max_tokens` - Parameter flags
- `escalation` - E0 (compliant), E1 (non-runtime), E2 (needs reasoning_effort="none"), E3 (fix needed)

**IMPORTANT:** The `model_expr` values contain `=>gpt-5.2` / `=>gpt-5-mini` annotations (e.g.,
`"config.DM_MAIN_MODEL=>gpt-5.2"`). These are **aspirational targets from the failed plan**, NOT
the current model strings. The actual `model_config.py` still has all `gpt-4.1-2025-04-14` values.
The `=>` suffix is annotation only - do not treat it as reflecting current code state.

### Refactor Goal: Multi-Provider Model Support

**What we are doing:**
- Migrating runtime calls from `gpt-4.1-2025-04-14` to `gpt-5.2` (and mini -> `gpt-5-mini`)
- Adding parallel Gemini 3 (`gemini-3-pro-preview` / `gemini-3-flash-preview`) as an alternate provider
- Adding LM Studio support for local model execution (zero API costs, offline play)
- The existing toggle system (`USE_GPT5_MODELS` in `model_config.py`) will be extended to support
  provider selection (OpenAI vs Gemini vs LM Studio)
- gpt-4.1 is NOT being removed - it stays as a fallback. We are adding toggle options.

**Provider Options:**
1. **OpenAI GPT-4.1** - Current production (baseline)
2. **OpenAI GPT-5.2** - Next-gen cloud (testing via capture)
3. **Gemini 3** - Alternative cloud provider (testing via capture)
4. **LM Studio** - Local models (production runtime, no capture) - USE_LM_STUDIO toggle

**CRITICAL: DO NOT CHANGE PROMPTS**
The system prompts are currently perfectly tuned to gpt-4.1 outputs. We are NOT modifying any
prompts during this refactor. We are selecting comparable models, temperatures, and reasoning
settings to match the existing output quality. Prompt changes are out of scope.

**Development approach:**
- Migrate one API callsite at a time (95 total runtime callsites, see audit inventory)
- For each callsite, run all three **cloud models** simultaneously (gpt-4.1, gpt-5.2, Gemini 3) and compare
- Record and compare outputs using the capture system (`MULTI_MODEL_CAPTURE = True`)
- **LM Studio is NOT part of capture testing** - it's a production runtime option for cost savings
- Existing A/B test data is in gitignored `development/` folders
- Balance and tune temperature/reasoning per callsite after comparing outputs
- Prefer smaller/faster models where output quality is equivalent (cost optimization)

**Model equivalence targets:**
- `gpt-4.1-2025-04-14` (full) -> `gpt-5.2` (none reasoning) OR `gemini-3-pro-preview` (low thinking)
- `gpt-4.1-mini-2025-04-14` (mini) -> `gpt-5-mini` OR `gemini-3-flash-preview`
- Temperature: OpenAI calls with temperature need `reasoning_effort="none"` for gpt-5.2; Gemini 3
  defaults to 1.0 (do not set temperature for Gemini 3 coding/reasoning tasks; measured adjustment
  is appropriate for specific non-reasoning use cases)
- Cost: Aim to match or reduce current gpt-4.1 cost per callsite

**Web UI Settings Integration (TODO - Final Phase):**
After capture testing is complete and model winners are selected, add model provider selection to the
existing web interface settings dropdown (game_interface.html lines ~4363-4400):

```html
<div class="settings-section">
    <div class="settings-section-title">AI Model Provider</div>
    <div class="settings-item">
        <label for="model-provider-select">Provider</label>
        <select class="settings-select" id="model-provider-select">
            <option value="openai-gpt41">OpenAI GPT-4.1 (Current)</option>
            <option value="openai-gpt52">OpenAI GPT-5.2 (Next-Gen)</option>
            <option value="gemini3">Google Gemini 3 (Alternative)</option>
            <option value="lmstudio">LM Studio (Local - Zero Cost)</option>
        </select>
    </div>
</div>
```

Backend SocketIO handler should update `model_config.py` or user-specific settings database.
Players can switch providers without editing code. This is the production UX after testing is complete.

**What is NOT changing:**
- System prompts and user-facing prompt content
- Response format expectations (JSON schemas, output structure)
- Game logic, validation rules, or D&D mechanics
- The compression system architecture

## Commands and Development

### Running the Game
```bash
# Main web interface (recommended)
python run_web.py          # Opens http://localhost:8357

# Module toolkit directly
python launch_toolkit.py    # Opens to module creation interface

# Terminal mode (limited features)
python main.py             # Classic text interface
```

### Testing and Validation
```bash
# Validate module schemas (run after JSON changes)
python validate_module_files.py   # Aim for 100% pass rate

# Test compression system
python test_compression.py

# Check token usage
python analyze_telemetry.py
```

### Common Development Tasks
```bash
# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp config_template.py config.py  # Add OpenAI API key

# Create new module
python -c "from core.generators.module_builder import ModuleBuilder; ModuleBuilder().build_module('Module Name', 'Description')"
```

## High-Level Architecture

### Core Design Patterns

#### 1. Module-Centric Architecture
The system uses modules as self-contained adventures with hub-and-spoke conversation management:
- Each module is completely isolated (no cross-module dependencies)
- Conversation history segments at module transitions
- AI generates travel narration for seamless transitions
- Modules stored in `modules/[module_name]/` with standardized structure

#### 2. Orchestrator-Worker Pattern (Module Generation)
**CRITICAL**: Module generation uses clear separation:
- `module_builder.py` = ORCHESTRATOR (manages workflow, calls generators)
- `module_generator.py` = WORKER (actual implementation, area connections, location IDs)
- **Always fix bugs in module_generator.py, NOT module_builder.py**

#### 3. Manager Pattern Implementation
Major subsystems use dedicated managers:
- `CampaignManager`: Hub-and-spoke campaign orchestration
- `CombatManager`: Turn-based combat with AI validation
- `StorageManager`: Atomic file operations with rollback
- `LocationManager`: Location-based features and storage
- `LevelUpManager`: Character progression in subprocess isolation

### Token Compression System

The system achieves 70-90% token reduction through:
- **Chunked Compression**: Process 8 transitions at a time
- **Smart Caching**: Avoid redundant compression
- **Parallel Processing**: Multi-threaded compression
- **System Prompt Compression**: 101K → 8K characters (92% reduction)

Files: `core/ai/chunked_compression.py`, `core/ai/chunked_compression_config.py`

### Real-Time Web Interface

#### SocketIO Event Architecture
25+ bidirectional events for game state synchronization:
- Queue-based threaded output management
- Cross-platform browser session handling
- Status broadcasting between console and web

Key events: `game_update`, `combat_update`, `character_update`, `module_transition`

#### Media Serving System
3-tier fallback for asset serving:
1. Current module media (`modules/[module]/media/`)
2. All modules search
3. Static fallback (`web/static/media/`)

Direct static routes for performance:
- `/graphic_packs/`: Direct file serving
- `/media/`: Smart routing with fallback

### AI Integration Architecture

#### Multi-Model Support

**Current production models** (all in `model_config.py`):
- Full model: `gpt-4.1-2025-04-14` (being sunsetted by OpenAI, redirecting to gpt-5 series)
- Mini model: `gpt-4.1-mini-2025-04-14`
- 19 config variables, 95 runtime callsites total

**Refactor targets** (see `docs/reference/` for full details):
```python
# OpenAI next-gen (toggle: USE_GPT5_MODELS)
gpt-5.2          # replaces gpt-4.1 full - use reasoning_effort="none" for temp-using calls
gpt-5-mini       # replaces gpt-4.1-mini

# Gemini 3 (new parallel provider toggle - to be added)
gemini-3-pro-preview    # parallel to gpt-5.2
gemini-3-flash-preview  # parallel to gpt-5-mini

# Intelligent routing based on action complexity
ENABLE_INTELLIGENT_ROUTING = True                  # Action-based model selection
USE_COMPRESSED_COMBAT = True                       # Compressed combat prompts
```

#### Gemini Integration

**Current role (analysis tool only - gitignored `gemini_tool.py`):**

Use Gemini for analyzing large files (>2000 lines) or entire codebases that exceed your context window.

```python
from gemini_tool import query_gemini, plan_feature

# Analyze files with specific questions
result = query_gemini("What does this code do?", files=["main.py", "utils.py"])

# Plan new features based on existing code
plan = plan_feature("Add user authentication", files=["app.py", "models/"])

# Analyze without files (general questions)
result = query_gemini("How should I structure a REST API?")
```

**When to Use (analysis):**
- User mentions "gemini" or "use gemini"
- Files are over 2000 lines
- Analyzing entire directories/projects
- Need comprehensive feature planning
- User asks to analyze files you can't fully load

**Notes:**
- `files` parameter accepts single files, lists, or directories
- Rate limited to 2 RPM (free tier) - tool handles delays automatically
- Gemini excels at analysis, you excel at implementation

**Future role (runtime parallel provider - in development):**
Gemini 3 (`gemini-3-pro-preview` / `gemini-3-flash-preview`) is being added as a parallel runtime
provider alongside OpenAI. Each API callsite will eventually have a Gemini code path behind a
provider toggle. See `docs/reference/gemini-models-reference.md` for API differences and
call pattern translation. Key note: do NOT set temperature for Gemini 3 in general - it defaults
to 1.0 and is optimized for that; measured adjustment is appropriate for specific tasks.

### Critical File Paths and Conventions

#### Conversation Management
```
modules/conversation_history/
├── conversation_history.json       # Main game conversation
├── level_up_conversation.json      # Level up subprocess
├── combat_conversation_history.json # Combat sessions
├── chat_history.json               # Lightweight UI history
└── startup_conversation.json       # Character creation history

modules/                   # Top-level module organization
├── [module_name]/         # Individual adventure modules
├── campaign_archives/     # Archived conversations by module
├── campaign_summaries/    # AI-generated module summaries
├── conversation_history/  # Active conversation files
├── campaign.json         # Active campaign metadata
├── world_registry.json   # Global world state
└── effects_tracker.json  # Active effects tracking

Root directory files:
├── party_tracker.json    # Current party location, module, and state
├── config.py            # API keys and configuration
└── model_config.py      # AI model routing configuration
```

#### Module Structure
```
modules/[module_name]/
├── areas/                  # Location JSON files (HH001.json, G001.json)
├── media/                  # Module-specific assets
│   ├── npcs/              # JPEG compressed portraits
│   ├── monsters/          # JPEG compressed images
│   └── environment/       # Location backgrounds
├── characters/            # Player and NPC data
├── encounters/            # Combat encounter definitions
├── saved_games/           # Module-specific save states
├── [module]_module.json   # Module metadata
├── module_plot.json       # Quest progression
└── validation_report.json # Schema validation results
```

#### Data Storage
```
data/
├── bestiary/
│   ├── bestiary.json           # Monster compendium
│   └── npc_compendium.json     # 53+ centralized NPCs
├── active_pack.json            # Currently active graphic pack
├── spell_repository.json       # All spell definitions
└── style_templates.json        # AI generation styles

graphic_packs/              # Reusable style packs (root level)
├── [pack_name]/
│   ├── manifest.json     # Pack metadata
│   ├── monsters/         # Monster images and videos
│   └── npcs/            # NPC portraits

raw_images/                # Original PNGs (gitignored, root level)
├── npcs/
│   └── [module_name]/   # Original NPC PNGs by module
└── monsters/
    └── [module_name]/   # Original monster PNGs
```

## Critical Requirements

### Unicode Characters - NEVER USE
Windows console (cp1252) crashes with Unicode. Use ASCII only:
- ✓ → `[OK]` or `[PASS]`
- ✗ → `[ERROR]` or `[FAIL]`
- → → `->` or `=>`
- Any emoji → Text description

### Image Compression Standards
All generated images use JPEG compression:
- Main images: Quality 95
- Thumbnails: Quality 85
- Originals saved to `raw_images/` (gitignored)

### Location ID System
Dynamic prefix prevents conflicts:
```python
# Area 1: A01, A02, A03...
# Area 2: B01, B02, B03...
# Area 27: AA01, AA02...
```

### Atomic File Operations
All state changes use atomic pattern:
1. Create backup
2. Write new state
3. Verify integrity
4. Clean backup OR rollback on failure

## Module Toolkit Architecture

### Content Generation Pipeline
1. **Module Builder**: Orchestrates generation
2. **Module Generator**: Creates structure (fix bugs here!)
3. **Area Generator**: Builds locations
4. **NPC Builder**: AI-powered NPCs
5. **Monster Builder**: Creature creation
6. **NPC Reconciler**: Fixes name consistency

### Validation Pipeline
```bash
validate_module_files.py  # Schema compliance (80% minimum)
ModuleDebugger            # Structure validation
NpcReconciler            # Name consistency
```

## Import Patterns

```python
# Core AI
from core.ai.action_handler import process_action
from core.ai.conversation_utils import update_conversation_history

# Managers
from core.managers.combat_manager import CombatManager
from core.managers.storage_manager import StorageManager

# Generators
from core.generators.module_builder import ModuleBuilder
from core.generators.location_summarizer import LocationSummarizer

# Utilities
from utils.enhanced_logger import debug, info, warning, error
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import safe_read_json, safe_write_json
```

## Configuration System

### Model Configuration
`config.py` and `model_config.py` handle:
- OpenAI API key management
- Model routing strategy
- Compression settings
- Web port configuration

### Debug System
`debug_config.py` provides 70+ debug categories:
- Granular message filtering
- Log rotation
- Color-coded output
- Script-specific categorization

## Quality Gates

Before committing code:
- [ ] No Unicode characters in Python code
- [ ] Schema validation passes (validate_module_files.py)
- [ ] Atomic operations for state changes
- [ ] JPEG compression for new images
- [ ] Root cause addressed (not workaround)
- [ ] Import patterns match standards
- [ ] Media files in correct locations

### Additional Gates for Model Refactor Work
- [ ] NO prompt text was modified (prompts are frozen - gpt-4.1 tuned)
- [ ] Response format/JSON schema is unchanged at the callsite
- [ ] New model call is behind a toggle (does not replace, adds alongside)
- [ ] gpt-4.1 path still functional as fallback
- [ ] Temperature/reasoning parameters are comparable equivalents, not arbitrary choices
- [ ] Capture system records output for comparison before merging

### Capture Quality Review Tool
**`tools/capture_quality_reviewer.py`** is the primary tool for evaluating capture data. It sends
captured input+outputs to GPT and Gemini as independent qualitative reviewers, scoring each variant
on 6 criteria (1-5) and producing a final ranking. This is the preferred method -- uses frontier
models as judges without burning Claude tokens.

**CRITICAL: The reviewer model must be `gpt-5.4` with `reasoning_effort="medium"`.**
The tool currently defaults to `gpt-4.1-2025-04-14` at line 278 which is a WEAK judge --
it scored 5/12 correct on T065 validation while gpt-5.4 medium scored much more accurately.
gpt-4.1 misses game logic errors that stronger models catch. Update the tool before using it.

**CRITICAL: Always run reviews on ALL entries for a callsite, not just a subset.**
The denominator in correctness scores (X/Y) must always be the total number of test runs.
Never report X/5 when you ran 12 entries. The full count is required for accurate comparison.

```bash
python tools/capture_quality_reviewer.py T067                    # Review latest entry (both reviewers)
python tools/capture_quality_reviewer.py T067 --reviewer gpt     # GPT reviewer only
python tools/capture_quality_reviewer.py T067 --reviewer gemini  # Gemini reviewer only
python tools/capture_quality_reviewer.py T067 --entry 0          # Review first entry instead of latest
python tools/capture_quality_reviewer.py T067 --variants "gpt-5.2|effort=none,gemini-3-pro|thinking=low"
```

Other analysis tools:
- `tools/analyze_captures.py` - Deterministic validation with per-task validators, generates HTML/JSON reports
- `tools/analyze_capture_results.py` - Summary statistics across all captures (pass/fail/error counts)

### Capture Output Manual Analysis Requirements
When manually analyzing model captures in `model_captures/*.json` (without the review tool), you MUST:
1. **Read only the LAST entry** - files contain many old captures, only analyze the most recent
2. **Show actual field values** - not summaries like "Excellent" or "matches"
3. **Create detailed comparison tables** with these columns:
   - Latency (seconds)
   - Tokens (input/output)
   - Cost (USD)
   - JSON Valid (Yes/No)
   - Each field from baseline schema with ACTUAL values (e.g., `stat: ""` vs `stat: "other"`)
   - Extra Fields (list any fields not in baseline)
   - Missing Fields (list any baseline fields not present)
   - For narration: word count, same scene described, character names match
   - For actions: count, types match, parameters match, extra/missing actions
4. **Note specific differences** - e.g., "baseline uses 'Removed' vs variant uses 'Decrease'"
5. **DO NOT use Python scripts** - read JSON directly with Read tool

### PROHIBITION: No Automated Search-and-Replace for API Callsites
**NEVER use automated Python scripts (or any scripting) to search-and-replace API callsite code.**
This approach was attempted previously and broke the codebase because callsites are not uniform -
they have different parameters (temperature, reasoning_effort, response_format, kwargs).

**Required process for API callsite changes:**
1. Each of the 95 callsites must be individually visited and understood
2. Changes are applied one at a time by a subagent (or by hand)
3. A separate validation agent must verify each change is correct and complete
4. The callsite must reference `model_config.py` variables for its model (no hardcoded strings)

This is non-negotiable. No exceptions. No "just this once." No bulk operations.

### Callsite Migration Pattern (Per-Provider Model Selection)

**HARD RULE: Every callsite must be manually coded to specify its exact model configuration
per provider. No blanket mechanisms, no automatic parameter injection, no escalation ladders.
The callsite owns its model selection and parameters. This is non-negotiable.**

Each callsite migration follows this process:

1. Run capture testing to collect quality + cost data across model variants
2. Run `tools/capture_quality_reviewer.py` to get GPT-scored quality rankings
3. Select the winning model+params combo per provider from the results
4. Add named config variables to `model_config.py` for each model+params combo
5. Update the callsite to reference the correct config variable per provider
6. Route through `api_client.create_completion()` instead of raw OpenAI client

See `docs/reference/legacy-model-variable-map.md` for the full variable inventory.

**Step 1: Define model configs in `model_config.py`**

Each tested model+params combination gets its own named config variable. The variable
bundles the model string with its required provider-specific params (reasoning_effort,
thinking_level, etc.). Temperature is NOT included -- it stays at the callsite.

```python
# model_config.py -- per-callsite model selections from capture testing

# OpenAI models
DM_FULL_MODEL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
DM_MINI_MODEL_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini models
DM_FULL_MODEL_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
DM_MINI_MODEL_GEMINI_FLASH_MINIMAL = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "minimal"}

# Legacy models (no extra params needed)
DM_FULL_MODEL_LEGACY = {"model": "gpt-4.1-2025-04-14"}
DM_MINI_MODEL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
```

**Step 2: Wire the callsite to select the right config per provider**

The callsite checks `MODEL_PROVIDER` and references the specific config variable
by name. No magic lookup -- the callsite explicitly names which tested configuration
it uses for each provider.

```python
# Example: T067 Main DM Loop (uses full + mini models with intelligent routing)
from model_config import MODEL_PROVIDER

if MODEL_PROVIDER == "openai":
    full_config = config.DM_FULL_MODEL_GPT52_NONE
    mini_config = config.DM_MINI_MODEL_GPT5MINI_LOW
elif MODEL_PROVIDER == "gemini":
    full_config = config.DM_FULL_MODEL_GEMINI_PRO_LOW
    mini_config = config.DM_MINI_MODEL_GEMINI_FLASH_MINIMAL
elif MODEL_PROVIDER == "lmstudio":
    full_config = config.DM_FULL_MODEL_LMSTUDIO
    mini_config = config.DM_MINI_MODEL_LMSTUDIO
else:  # legacy
    full_config = config.DM_FULL_MODEL_LEGACY
    mini_config = config.DM_MINI_MODEL_LEGACY

selected = full_config if prediction["requires_actions"] else mini_config

response = capture_and_fanout("T067", api_client.create_completion,
    messages=messages_to_send,
    model=selected["model"],
    temperature=TEMPERATURE,     # callsite owns temperature
    **{k: v for k, v in selected.items() if k != "model"})
```

**Key rules:**
- Temperature stays at the callsite (not in the config dict)
- The config dict contains ONLY model string + provider-specific params
- Each provider branch explicitly names the config variable (no inference)
- `create_completion()` is a thin router -- it does NOT inject params
- New models require new config variables (e.g., `DM_FULL_MODEL_GPT54_LOW`)

## SRD 5.2.1 Compliance

When implementing game mechanics:
- Use "5th edition" or "5e" instead of "D&D"
- Add attribution: `"_srd_attribution": "Portions derived from SRD 5.2.1, CC BY 4.0"`
- Reference only generic fantasy settings
- Follow official SRD rules for mechanics

## Module Transition System

Module transitions preserve conversation timeline:
1. Detection in `action_handler.py` when party changes module
2. Marker insertion at exact transition point
3. AI summary loaded from `modules/campaign_summaries/`
4. Conversation compression between module boundaries
5. Archive stored in `modules/campaign_archives/`

## Performance Optimizations

### Thumbnail Loading
- Direct `/graphic_packs/` static serving
- Cache busting only on explicit refresh
- Lazy loading with intersection observer

### Token Optimization
- Chunked compression (8 transitions)
- Parallel processing (5 workers)
- Smart caching system
- Combat narration compression

### API Cost Reduction
- Model routing by task type
- Compression before API calls
- Cached responses where appropriate
- Batch operations when possible