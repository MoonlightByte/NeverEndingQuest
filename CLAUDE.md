# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeverEndingQuest is an AI-powered Dungeon Master system for running SRD 5.2.1 compatible tabletop RPG campaigns. It features advanced token compression (70-90% reduction), a web interface with real-time updates, and a comprehensive module creation toolkit.

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

#### Player-turn and travel narration authority

**One model response resolves one immediate player turn.** Travel commits the
requested movement and travel-owned bookkeeping, narrates the committed
arrival, asks what the player does next, and stops. A later clause such as
“then buy,” “then establish a hub,” “then manage a save,” or “then exit” is
deferred player intent and must not execute inside the travel transaction.
T067 interprets that semantic boundary, T065 validates it, and code reconciles
structured actions; never classify player/model prose with keywords or regexes.

Do not simplify travel narration to one call. The production chain is T013
(transition/departure layer from committed, updated location context), T063
(arrival layer from the committed target and roster), then T064 (seamless
stitch). These are three internal agent calls inside one player turn, not three
gameplay turns. The destination projection includes its player-disclosed
`adventureSummary` for continuity, but excludes DM-only encounter, trap,
instruction, and undisclosed-actor records. T064 ends by returning the choice
of the next immediate action to the player. See
`docs/plans/2026-08-23-single-turn-travel-amendment.md`.

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
```python
# Model configuration in model_config.py
DM_MAIN_MODEL = "gpt-4.1-2025-04-14"              # Main DM
DM_VALIDATION_MODEL = "gpt-4.1-2025-04-14"        # Validation
DM_MINI_MODEL = "gpt-4.1-mini-2025-04-14"         # Simple conversations
NARRATIVE_COMPRESSION_MODEL = "gpt-4.1-mini-2025-04-14"  # Compression

# Optional GPT-5 models (USE_GPT5_MODELS = True to enable)
GPT5_MINI_MODEL = "gpt-5-mini-2025-08-07"         # GPT-5 mini
GPT5_FULL_MODEL = "gpt-5-2025-08-07"              # GPT-5 full

# Intelligent routing based on action complexity
ENABLE_INTELLIGENT_ROUTING = True                  # Action-based model selection
USE_COMPRESSED_COMBAT = True                       # Compressed combat prompts
```

#### Gemini Integration

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

**When to Use:**
- User mentions "gemini" or "use gemini"
- Files are over 2000 lines
- Analyzing entire directories/projects
- Need comprehensive feature planning
- User asks to analyze files you can't fully load

**Notes:**
- `files` parameter accepts single files, lists, or directories
- Rate limited to 2 RPM (free tier) - tool handles delays automatically
- Gemini excels at analysis, you excel at implementation

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
