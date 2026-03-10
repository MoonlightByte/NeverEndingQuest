# NeverEndingQuest-TTRPG

**Version 0.3.5 (Alpha) - Fork: NeverEndingQuest-TTRPG**

This repository is the tabletop-focused fork of NeverEndingQuest for live facilitator-led multiplayer sessions and ongoing gameplay-test iteration.

An AI-powered Dungeon Master for running SRD 5.2.1 compatible tabletop RPG campaigns with infinite adventure potential. Experience the world's most popular roleplaying game with an intelligent AI that remembers every decision, adapts to your playstyle, and creates endless adventures tailored to your party.

**🚀 NEW: Advanced Token Compression System** - Play longer, pay less! Revolutionary compression technology reduces API costs by 70-90% while maintaining full game fidelity. Run the game locally with open-source models or dramatically reduce OpenAI API expenses.

---

## 🎮 Get Started | 💬 Join the Community

**Ready to play?** → [Quick Start Guide](#quick-start) | [Download Windows Installer](install_neverendingquest_windows.bat)

**Need help or want to share your adventures?** → [r/NeverEndingQuest on Reddit](https://www.reddit.com/r/NeverEndingQuest/)

**Report bugs or request features** → Use this fork's GitHub Issues tab

---

## Table of Contents

- [Quick Start](#quick-start)
- [Fork Identity](#fork-identity)
- [Key Features](#key-features)
- [Module Toolkit](#module-toolkit)
- [Installation](#installation)
- [How It Overcomes AI Limitations](#how-it-overcomes-ai-limitations)
- [Advanced Token Compression System](#advanced-token-compression-system)
- [Game Features](#game-features)
- [Technical Architecture](#technical-architecture)
- [Advanced Features](#advanced-features)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Community Module Safety](#community-module-safety)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Recent Updates](#recent-updates)

## Fork Identity

NeverEndingQuest-TTRPG keeps upstream NeverEndingQuest as the base while adding merge-safe tabletop multiplayer extensions.

- Canonical engineering guidance: `AGENTS.md`
- Active and archived implementation contracts: `openspec/`
- Long-horizon planning and v2 tracks: `plans/`
- Durable architecture decisions: `adrs/`
- Legacy upstream/background context retained: `ARCHITECTURE.md`, `ARCHITECTURE_PHILOSOPHY.md`, and historical sections in this README
- AI operator and automation workflows: `.opencode/skills/`

For contributor setup and workflow, see `CONTRIBUTING.md` and `DEV_SETUP.md`.

## Quick Start

### 🎯 One-Click Windows Installer (Recommended)

**For non-technical users on Windows:**

1. **Download the installer**:
   - Click here: [install_neverendingquest_windows.bat](https://github.com/zeug-zz/NeverEndingQuest-TTRPG/raw/main/install_neverendingquest_windows.bat)
   - **Right-click** → **"Save link as..."** → Save as `.bat` (not `.txt`)
   - Save to your Downloads folder

2. **Run the installer**:
   - Double-click the downloaded `.bat` file
   - If Windows SmartScreen appears: Click **"More info"** → **"Run anyway"**
   - Choose **Player Mode** (recommended, no Git needed) or **Developer Mode** (with Git)

3. **Install Python if needed**:
   - If prompted, install Python from **Microsoft Store**:
     - Open Microsoft Store → Search "Python 3.11" → Click "Get"
   - Or download from: https://www.python.org/downloads/
   - **Important**: Check "Add Python to PATH" during install
   - Re-run the installer after Python is installed

4. **Add your OpenAI API key**: Enter your API key in the popup dialog (get one at https://platform.openai.com/api-keys)

5. **Launch the game**: Run `launch_game.bat` in your `NeverEndingQuest-TTRPG` folder

The installer automatically:
- ✅ Checks for Python (opens Microsoft Store if missing)
- ✅ Downloads and installs the game from the fork repository
- ✅ Creates a virtual environment
- ✅ Installs all dependencies
- ✅ Sets up configuration with API key dialog
- ✅ Creates `launch_game.bat` for easy launching
- ✅ Adds desktop shortcut

**Installation location:** `%USERPROFILE%\NeverEndingQuest-TTRPG`

**To restart the game later:**
- Run `launch_game.bat` in `%USERPROFILE%\NeverEndingQuest-TTRPG`
- Or double-click the desktop shortcut

---

### 🛠️ Manual Installation

**Get playing in under 5 minutes!** The AI startup wizard handles everything automatically:

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Add your OpenAI API key**: Copy `config_template.py` to `config.py` and add your key
3. **Launch the game**: `python run_web.py` - opens the web interface at http://localhost:8357
4. **Start your adventure**: The AI will guide you through character creation and module selection

### Additional Launch Options

- **Module Toolkit**: `python launch_toolkit.py` - Opens directly to the module creation interface
- **Terminal Mode**: `python main.py` - Classic text-based interface (limited features)

> **Note**: The game is designed for the **web interface** which provides the optimal experience with real-time updates, character sheets, visual portraits, and the module toolkit.

## Key Features

### 💰 Advanced Token Compression (NEW!)
- **70-90% Cost Reduction** - Revolutionary compression cuts API expenses dramatically
- **Open-Source Model Support** - Run with Llama 3.1, Mistral, or other local models
- **Parallel Processing** - 5x faster compression with multi-threaded architecture
- **Smart Caching** - Intelligent compression cache reduces redundant processing
- **Compressed Prompts** - System prompts reduced from 101K to 8K characters (92% reduction)
- **Combat Optimization** - Special compression for verbose combat narration
- **Automatic Routing** - Intelligent model selection for optimal cost/quality balance

### Core Game Systems
- **SRD 5.2.1 Rules Engine** - Complete 5th edition compatible mechanics
- **AI Dungeon Master** - GPT-powered storytelling that adapts to your actions
- **Turn-Based Combat** - Tactical combat with initiative tracking and AI validation
- **Character Progression** - Full leveling system from 1-20 with all class features
- **Party Management** - Recruit NPCs, manage equipment, track relationships
- **Save/Load System** - Automatic progress saving with backup protection

### Web Interface Features
- **Real-Time Updates** - Live game state synchronization via SocketIO
- **Character Sheets** - Interactive character information and inventory
- **Portrait System** - Visual character portraits with hover video previews
- **Combat Visualizer** - Turn-by-turn combat display with health tracking
- **Module Browser** - View and select available adventures
- **Settings Panel** - Customize game options and preferences
- **DM Voice (Text-to-Speech)** - Listen to DM narration with multiple voice engines:
  - Browser voices (free, offline) - Uses Web Speech API with system voices
  - OpenAI TTS (paid) - High-quality AI voices (Standard and HD models)
  - Voice preview, auto-play option, and response caching to reduce API costs

### Included Adventure Modules
- **The Thornwood Watch** (Level 1-2) - Defend a ranger outpost from bandits and corruption
- **Keep of Doom** (Level 3-5) - Explore a haunted keep and establish your stronghold
- **Shadows of Kharos** (Level 4-6) - Investigate a cursed lighthouse on a storm-wracked isle
- **Plus unlimited AI-generated adventures** based on your choices and interests

## Module Toolkit

**NEW: Complete content creation suite for building custom adventures!**

Access the toolkit from the web interface or launch directly with `python launch_toolkit.py`

### Module Generator & Builder
- **Visual Module Creation** - Web-based interface for creating complete adventures
- **AI-Assisted Generation** - Describe your vision, AI creates the content
- **Area & Location Builder** - Design interconnected regions with detailed locations
- **Plot Generator** - Create main quests, side quests, and narrative hooks
- **Module Stitching** - Seamlessly connect modules for epic campaigns
- **Validation System** - Ensures all content follows SRD 5.2.1 schemas

### NPC Generator
- **Instant NPC Creation** - Generate unique NPCs with full stats and backstories
- **Portrait Integration** - Automatic portrait assignment from graphic packs
- **Personality System** - Rich personalities, goals, and motivations
- **Relationship Tracking** - NPCs remember interactions across modules
- **Party Recruitment Ready** - Any NPC can potentially join the party

### Monster Generator  
- **Custom Creature Creation** - Build unique monsters for your adventures
- **Bestiary Management** - Import/export creatures from the master compendium
- **CR Balancing** - Automatic challenge rating calculation
- **Ability Generation** - Create unique abilities and attacks
- **Visual Integration** - Assign portraits and animations from packs

### Module Media Generator
- **Batch Image Generation** - Create images for all NPCs and monsters in a module
- **Missing Asset Detection** - Automatically identifies characters without images
- **Style Consistency** - Apply consistent art styles across entire modules
- **Description Generation** - AI creates detailed visual descriptions for image generation
- **Progress Tracking** - Real-time status updates during batch generation
- **Selective Overwrite** - Choose whether to replace existing images

### Graphic Pack System
- **Reusable Asset Packs** - Share visual content across multiple modules
- **Pack Manager** - Create, import, export, and manage visual content packs
- **Module Independence** - Images stored in packs for easy module distribution
- **Style Templates** - Multiple visual styles (photorealistic, fantasy art, pixel art)
- **Thumbnail Generation** - Automatic thumbnail creation for galleries
- **Pack Merging** - Combine multiple packs into custom collections

### Style Management
- **Visual Themes** - Switch between different art styles
- **Custom Styles** - Create your own visual themes
- **Prompt Templates** - AI image generation prompts for consistency
- **Style Preview** - See how content looks in different styles

### Content Import/Export
- **Bestiary Integration** - Access the complete monster compendium
- **Module Sharing** - Export modules for community sharing
- **Pack Distribution** - Share graphic packs as ZIP files
- **Backup System** - Automatic backups of all custom content

## 📄 **Licensing**

NeverEndingQuest is licensed under the **Fair Source License 1.0** with comprehensive protection for its innovative systems:

### 🔒 **Fair Source License (5-year term)**
The entire codebase including AI prompts, conversation compression, and all game systems are protected.
- ✅ **Free for personal, educational, and non-commercial use**
- ✅ **Community contributions welcome**  
- ✅ **Modify and customize freely for your campaigns**
- ❌ **Commercial competing use prohibited for 5 years**
- ⏰ **Becomes Apache 2.0 (fully open source) after 5 years**

### 📚 **SRD Content (CC-BY 4.0)**
Game mechanics use SRD 5.2.1 content from Wizards of the Coast.
- ✅ **SRD content used with proper attribution**
- ⚠️ **This is unofficial Fan Content**
- ℹ️ **Not affiliated with Wizards of the Coast**

See [LICENSING.md](LICENSING.md) for complete details, FAQ, and legal information.

## Installation

### Prerequisites
- Python 3.9 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- 4GB+ RAM recommended
- Modern web browser (Chrome, Firefox, Edge)
- Windows, macOS, or Linux

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git
   cd NeverEndingQuest-TTRPG
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure OpenAI API**
   ```bash
   cp config_template.py config.py
   # Edit config.py and add your OpenAI API key
   ```

4. **Launch the game**
   ```bash
   # Full game with web interface (recommended)
   python run_web.py
   # Opens at http://localhost:8357
   
   # Module Toolkit directly
   python launch_toolkit.py
   # Opens at http://localhost:8357/toolkit
   
   # Terminal interface (basic)
   python main.py
   ```

### First Time Setup
- The AI wizard will guide you through character creation
- Choose from pre-built modules or generate a custom adventure
- Web interface provides tutorial tooltips for new players

## How It Overcomes AI Limitations

### The Context Window Challenge
Traditional AI systems have limited memory - typically 100-200k tokens. In a text-heavy RPG, this means:
- Conversations get truncated after a few hours of play
- NPCs "forget" your previous interactions
- Story continuity breaks between sessions
- Module transitions lose important context

### Our Solution: Intelligent Conversation Compression

NeverEndingQuest implements a sophisticated compression pipeline that maintains full contextual understanding:

#### 1. **Living Summary Generation & Chronicle System**
- Each module generates a comprehensive living summary upon exit that captures the complete adventure
- AI analyzes the entire module conversation and creates beautifully written fantasy prose summaries
- Living summaries are completely regenerated (not appended) on each visit to incorporate new experiences
- Original events preserved in elevated narrative form while reducing tokens by 85-90%
- **Chronicle Format**: Compressed histories are clearly labeled as "CHRONICLE" - these are historical records of actual gameplay, not metadata
- **Visit Evolution**: Summaries become richer and more detailed with each return visit
- **Single File System**: Always `[Module_Name]_summary_001.json` - never increments, always regenerates

#### 2. **Hub-and-Spoke Architecture with Module-Specific Conversations**
```
Module Structure:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Thornwood   │────►│   Keep of   │────►│ Silver Vein │
│   Watch     │◄────│    Doom     │◄────│  Whispers   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       └────────────────────┴────────────────────┘
                    Shared Context
                 (Character History)

Module Conversation Management:
┌─────────────────┐     ┌─────────────────┐
│ Current Module  │────►│ Module Archive  │
│ Conversation    │     │ (Auto-saved)    │
└─────────────────┘     └─────────────────┘
         ↓                       ↓
┌─────────────────┐     ┌─────────────────┐
│ New Module      │◄────│ Previous Conv.  │
│ (Fresh Start)   │     │ (Auto-restored) │
└─────────────────┘     └─────────────────┘
```

- Each module is a self-contained geographic region with its own conversation history
- **Module-Specific Conversations**: When leaving a module, conversations are archived and cleared
- **Automatic Restoration**: Returning to a module restores its specific conversation history
- **Prevents Infinite Buildup**: Each module maintains its own context bubble, preventing token explosion
- Return to any location with full memory of past events specific to that module

#### 3. **Living World Persistence with Smart Summary Management**
- **NPC Memory**: Characters remember your entire relationship history through living summaries
- **Dynamic NPC Context**: Real-time NPC discovery system provides complete context for AI interactions
- **Validation-Aware NPCs**: Automatic NPC tracking prevents hallucination and ensures consistency
- **Incremental Conversation Compression**: Intelligent compression preserves recent context while reducing token usage
- **Decision Consequences**: Past choices affect future module availability
- **World State Tracking**: Completed quests permanently change the world
- **Cross-Module Continuity**: Items, relationships, and reputation carry forward
- **Living Summary System**: Each module maintains a single, evolving summary that updates with each visit
- **Visit Tracking**: System tracks `visitCount`, `firstVisitDate`, and `lastVisitDate` for each module
- **Smart Context Injection**: Previous module summaries are injected as campaign context, excluding the current module to prevent duplication

### Benefits
- **Truly Infinite Campaigns**: Play for hundreds of hours without context loss across multiple adventures
- **Persistent Relationships**: NPCs remember you after months of real-time play through living summaries
- **Coherent Storytelling**: Every adventure builds on previous experiences with complete cross-module continuity
- **Zero Context Contamination**: Each module maintains its own conversation bubble, preventing token explosion
- **Seamless Module Returns**: Full conversation history restored when revisiting any module
- **Living World Evolution**: Summaries grow richer with each visit, tracking your expanding impact
- **Optimized Performance**: Module separation prevents infinite context growth while preserving complete history
- **Smart Context Management**: Campaign summaries provide relevant background without duplication
- **Visit Progression Tracking**: Rich metadata shows your journey across the world over time
- **Reduced API Costs**: 60-70% cost reduction through compression and intelligent model routing

## Advanced Token Compression System

### 🌟 CORE FEATURE - Now Production Ready!
The Advanced Token Compression System has graduated from experimental to **CORE FEATURE** status in v0.3.0. This revolutionary technology is now the foundation of NeverEndingQuest's AI architecture, enabling unprecedented cost savings and local model compatibility while maintaining complete game fidelity.

### Key Benefits
- **Cost Reduction**: 60-70% reduction in OpenAI API costs through compression and intelligent routing
- **Open-Source Compatibility**: Reduced context from 100K+ to under 10K tokens enables local model deployment
- **Performance**: Faster inference times with smaller contexts
- **Scalability**: Support for longer play sessions without context overflow
- **Local Deployment**: Run the game on consumer GPUs with models like Llama 3.1 (8K-128K context)

### Compression Technologies

#### 1. Parallel Conversation Compression (`core/ai/conversation_compression.py`)
The system uses advanced parallel processing to compress conversation history in real-time:

- **Parallel Processing**: ThreadPoolExecutor with up to 5 workers for concurrent compression
- **Smart Caching**: MD5 hash-based caching prevents re-compression of identical messages
- **Selective Compression**: Preserves last 2 user messages for immediate context while compressing older history
- **Token Reduction**: Achieves 76-82% reduction per message while maintaining narrative continuity
- **Configuration**: Toggle system-wide with `COMPRESSION_ENABLED` flag in `config.py`

**Performance Metrics:**
- Average compression ratio: 76-82% per message
- Processing speed: 5 messages compressed simultaneously
- Cache hit rate: ~40% in typical gameplay

#### 2. Compressed System Prompts
Revolutionary @TAG machine language format reduces prompt sizes by 87-92%:

**`system_prompt_compressed.txt`**: Main game prompt
- Original: 101,000 characters
- Compressed: 8,000 characters
- Reduction: 92%

**`validation_prompt_compressed.txt`**: Validation prompt
- Original: 48,000 characters
- Compressed: 6,500 characters
- Reduction: 87%

**Compression Methodology:**
```
@FMT: Formatting rules and output constraints
@ACTIONS: Available game actions with exact parameter contracts
@PARAMS: Precise parameter specifications
@OUTPUT_CONSTRAINTS: ASCII-only enforcement (Windows compatibility)
@EXAMPLES: Action usage examples
```

This structured notation maintains all game rules while dramatically reducing token usage.

#### 3. Module Transition Compression
Intelligent conversation archiving during module transitions:

- **Automatic Archiving**: Conversations compressed when transitioning between adventure modules
- **AI-Generated Summaries**: Beautiful prose summaries preserve adventure context
- **Chronological Timeline**: Complete adventure history maintained across all modules
- **Smart Segmentation**: Two-condition boundary detection for optimal compression points
- **Implementation**: `check_and_process_module_transitions()` in `main.py`

#### 4. Combat Message Compression
Special handling for verbose combat narration:

- **Combat Narration**: Reduces messages from 4,630 to ~850 characters (82% reduction)
- **Dice Preservation**: Maintains all dice rolls and damage calculations for validation
- **State Tracking**: Preserves `preroll_cache` and combat state for rule compliance
- **Fidelity**: Full combat mechanics preserved despite compression

Example:
```
Original: "The orc chieftain raises his massive battle-axe high above his head, muscles rippling with primal fury as he brings it down in a devastating arc toward your shoulder. The blade bites deep into your armor... [4,630 chars]"

Compressed: "Orc chieftain attacks with battle-axe. Hit: 18 vs AC 16. Damage: 2d8+5=13 slashing. You: 45->32 HP. Status: wounded, bleeding (1d4/turn)... [850 chars]"
```

#### 5. Action Prediction & Model Routing (`utils/action_predictor.py`)
Intelligent routing between AI models based on input complexity:

- **Input Analysis**: Predicts whether user input requires game actions
- **Model Selection**: Routes to appropriate model tier
  - Simple conversations → GPT-4o mini (cost-efficient)
  - Action commands → Full model (quality-critical)
- **Cost Optimization**: Significant savings for conversation-heavy gameplay
- **Seamless Experience**: Automatic routing with no user intervention

**Routing Logic:**
```python
if requires_game_action(user_input):
    model = "gpt-4o"  # Full capabilities
else:
    model = "gpt-4o-mini"  # Conversational only
```

### Configuration & Setup

#### Enable/Disable Compression
Edit `config.py` to control compression settings:

```python
# Token Compression Settings
COMPRESSION_ENABLED = True        # Master switch for compression system
COMPRESSION_CACHE_SIZE = 1000     # Number of compressed messages to cache
COMPRESSION_PARALLEL_WORKERS = 5  # Parallel compression threads
USE_COMPRESSED_PROMPTS = True     # Use compressed system prompts

# Model Routing Settings
ENABLE_ACTION_PREDICTION = True   # Enable intelligent model routing
MINI_MODEL_THRESHOLD = 0.3        # Confidence threshold for mini model
```

#### Monitoring & Telemetry
The system includes comprehensive telemetry for optimization:

- **Usage Tracking**: `openai_usage_tracker.py` logs all API calls
- **Token Analytics**: Per-endpoint token consumption statistics
- **Spike Detection**: Automatic detection of usage anomalies
- **Migration Planning**: Data for transitioning to local models
- **Log Location**: `telemetry_log.jsonl` for analysis

### Open-Source Model Compatibility

The compression system enables deployment with popular open-source models:

#### Compatible Models
- **Llama 3.1**: 8K-128K context window
- **Mistral**: 32K context window
- **Claude API Alternatives**: Various context sizes
- **Mixtral**: 32K context window
- **Solar**: 10K context window

#### Local Deployment Benefits
- **GPU Requirements**: Reduced from 48GB to 8-16GB VRAM
- **Inference Speed**: 3-5x faster with compressed contexts
- **Memory Usage**: 80% reduction in RAM requirements
- **Batch Processing**: Support for multiple concurrent games

#### Setup for Local Models
1. Install local model runtime (Ollama, llama.cpp, etc.)
2. Enable compression in `config.py`
3. Configure model endpoint in `config.py`
4. Adjust context window settings for your model
5. Run game normally - compression handles adaptation

#### 🧪 EXPERIMENTAL: LM Studio Integration

**Status**: EXPERIMENTAL - May experience issues with complex game mechanics

NeverEndingQuest now includes experimental support for running with [LM Studio](https://lmstudio.ai/) for completely local, offline gameplay with zero API costs.

**⚠️ IMPORTANT LIMITATIONS:**

This integration is **experimental** and has known limitations:

1. **Prompt Compatibility**: All system prompts and compression technology were designed and optimized exclusively for ChatGPT/GPT-4 architecture. Local models may:
   - Produce malformed JSON action structures
   - Fail to follow complex game mechanics properly
   - Generate inconsistent SRD 5.2.1 rule interpretations
   - Struggle with the compressed @TAG notation format

2. **Token Requirements**:
   - **Minimum 32K context window required** (64K+ recommended)
   - Models with smaller contexts will fail during extended gameplay
   - Parallel request handling may exceed context limits

3. **Memory & Performance**:
   - **Use quantized models** (Q4_K_M or Q5_K_M) to reduce VRAM usage
   - 7B models: Require 16GB+ system RAM
   - 13B models: Require 32GB+ system RAM
   - Parallel API requests may cause memory spikes

4. **Game Mechanics**:
   - Combat system relies on precise JSON formatting from SRD 5.2.1 licensed game content
   - Character progression uses SRD 5.2.1 rules (may not be in model training data)
   - Module transitions require exact action detection
   - NPC dialogue and quest tracking depend on GPT instruction-following

**Recommended Models** (best compatibility):
- **Mistral 7B Instruct v0.3** - 32K context, good instruction following
- **Llama 3.1 8B Instruct** - 128K context, excellent for long sessions
- **Mistral Nemo 12B** - 128K context, strong storytelling

**Quick Start** (Windows):

1. **Install LM Studio** from [lmstudio.ai](https://lmstudio.ai/)
2. **Load a model** (recommended: Mistral 7B Instruct or Llama 3.1 8B)
3. **Start LM Studio server** (click "Start Server" in Local Server tab)
4. **Verify configuration**:
   - Server address: `http://127.0.0.1:1234`
   - Model loaded and active
   - Context length set to maximum (32K+)
5. **Install proxy**: `pip install mitmproxy` (included in requirements.txt)
6. **Launch**: Double-click `launch_lmstudio_mode.bat`

**Configuration Verification**:

Make sure your LM Studio settings match:
```
API Endpoint: http://127.0.0.1:1234/v1
Model Identifier: <your-loaded-model>
Context Length: 32768 or higher
```

The proxy system in `lmstudio_forwarder.py` will automatically redirect all OpenAI API calls to your local LM Studio instance on port 1234.

**Temperature Settings Note**: The game controls temperature settings through the proxy. If you experience JSON formatting errors or poor prompt adherence, you can lower the temperature in LM Studio's server settings to improve accuracy, though this may reduce narrative creativity and storytelling immersion.

**Known Issues**:
- JSON parsing errors during complex combat
- Inconsistent action detection compared to GPT-4
- May require manual intervention for edge cases
- Slower response times on CPU-only systems
- Parallel requests may cause response delays or errors

**Documentation**:
- Complete setup guide: `LMSTUDIO_SETUP.md`
- Quick reference: `LMSTUDIO_QUICKSTART.txt`
- Configuration help: Edit `lmstudio_forwarder.py` lines 19-22

**Support**: LM Studio mode is provided as-is for experimentation. For production gameplay, we recommend using OpenAI's API with the compression system for optimal experience.

### Performance Metrics Summary

| Component | Original Size | Compressed Size | Reduction |
|-----------|--------------|-----------------|-----------|
| System Prompt | 101K chars | 8K chars | 92% |
| Validation Prompt | 48K chars | 6.5K chars | 87% |
| Combat Messages | 4.6K chars | 850 chars | 82% |
| Conversation History | 100K+ tokens | <10K tokens | 90%+ |
| Overall API Costs | Baseline | 30-40% of original | 60-70% |

### Advanced Features

#### Compression Cache System
- **MD5 Hashing**: Identifies duplicate messages instantly
- **LRU Cache**: Most recent 1000 compressions cached
- **Hit Rate**: ~40% cache hits in typical gameplay
- **Memory Usage**: <50MB for full cache

#### Adaptive Compression Levels
The system automatically adjusts compression based on content type:
- **Narrative**: Maximum compression (80-85%)
- **Combat**: Balanced compression (75-80%) preserving mechanics
- **Technical**: Minimal compression (60-70%) for rule clarity
- **Character Sheets**: No compression (data integrity)

#### Future Enhancements
- **Model-Specific Optimization**: Tailored compression for each LLM
- **Dynamic Context Windows**: Automatic adjustment based on model
- **Streaming Compression**: Real-time compression during generation
- **Multi-Language Support**: Compression for non-English gameplay

## Game Features

### SRD 5.2.1 Rules Implementation
- **Complete Character System** - All classes, races, backgrounds from SRD
- **Spell System** - Full spellcasting with components and concentration
- **Combat Mechanics** - Actions, bonus actions, reactions, opportunity attacks
- **Conditions & Effects** - All standard conditions tracked automatically
- **Equipment & Magic Items** - Complete inventory with attunement rules
- **Skill Checks & Saves** - Advantage/disadvantage, proficiency bonuses

### AI-Powered Features
- **Adaptive Storytelling** - AI responds to creative solutions and unexpected actions
- **Dynamic NPCs** - Characters with personalities that evolve based on interactions
- **Tactical Combat AI** - Intelligent enemy behavior and positioning
- **Content Generation** - Endless adventures created based on your interests
- **Natural Language** - Use plain English, no commands to memorize
- **Flexible Rules** - AI can be convinced, negotiated with, or surprised

### Module System
- **Self-Contained Adventures** - Each module is a complete experience
- **Seamless Transitions** - Travel between modules with full continuity
- **Level Progression** - Modules scale from levels 1-20
- **Geographic Regions** - Modules represent interconnected world areas
- **Plot Integration** - Main quests span multiple modules
- **Living World** - Completed modules permanently change the world state

### Party & NPC Systems
- **Party Recruitment** - Convince any NPC to join your adventures
- **Relationship Tracking** - NPCs remember all interactions and develop bonds
- **Party Combat** - NPCs fight alongside you with unique abilities
- **Character Arcs** - Party members have personal quests and growth
- **Cross-Module Memory** - Companions remember adventures across regions

### Inventory & Storage
- **Natural Language Commands** - "I store my gold in a chest here"
- **Location-Based Storage** - Create storage anywhere in the world
- **Container Types** - Chests, barrels, lockboxes with different capacities
- **Party Access** - Shared storage accessible by all party members
- **Persistent Storage** - Items remain safe across sessions and modules

### Player Housing & Hubs
- **Claim Any Location** - Transform locations into permanent bases
- **Hub Services** - Rest, storage, training, research facilities
- **Multiple Bases** - Maintain strongholds across different regions
- **Ownership Types** - Personal, party, or faction-controlled
- **Base Upgrades** - Improve facilities as you progress

## Technical Architecture

### Manager Pattern Implementation
The codebase follows a clean Manager Pattern for all major subsystems:

- **CampaignManager** - Orchestrates module transitions and world state
- **CombatManager** - Handles turn-based combat with validation
- **StorageManager** - Manages player inventory and storage systems
- **LocationManager** - Controls location features and transitions
- **LevelUpManager** - Processes character progression in isolation
- **StatusManager** - Provides real-time feedback across interfaces
- **ModulePathManager** - Abstracts file system for module data
- **IncrementalLocationCompressor** - Automatically compresses conversation history at current location
- **CompanionMemoryManager** - Tracks NPC relationships and interactions

### Module-Centric Architecture
```
modules/[module_name]/
├── areas/              # Location files (area_id.json)
├── characters/         # NPCs and party members
├── monsters/           # Module-specific creatures
├── encounters/         # Combat encounters
├── images/            # Screenshots and portraits
├── module_plot.json   # Quest progression
├── party_tracker.json # Party state
└── [name]_module.json # Module metadata
```

### Atomic Operations
All state modifications use atomic patterns:
1. Create backup of affected files
2. Perform operation with validation
3. Verify final state integrity  
4. Clean up on success OR restore on failure

### Web Interface Architecture
- **Flask Backend** - RESTful API for game operations
- **SocketIO** - Real-time bidirectional communication
- **Queue-Based Output** - Thread-safe console streaming
- **Session Management** - Synchronized state across interfaces
- **Static File Serving** - Efficient portrait and video delivery

### AI Integration Patterns
- **Specialized Models** - Different GPT models for different tasks
- **Validation Layers** - AI responses validated before application
- **Fallback Mechanisms** - Graceful degradation on AI failures
- **Subprocess Isolation** - Complex operations in separate processes
- **Token Management** - Intelligent context window optimization

### Portrait System Integration
The game features a sophisticated portrait system with video previews:

- **Dynamic Portraits** - Characters display appropriate emotional states
- **Video Previews** - Hover over portraits to see animated previews
- **Pack Integration** - Portraits sourced from active graphic packs
- **Fallback System** - Graceful degradation if media unavailable
- **Unified Popups** - Consistent behavior across all character types

## Advanced Features

### How the Campaign World Works

#### Location-Based Module System
The game uses a revolutionary **geographic boundary system** instead of traditional campaign chapters:

- **Modules as Geographic Regions**: Each adventure module represents a geographic area network (village + forest + dungeon)
- **Organic World Growth**: The world map expands naturally as you add new modules - no predetermined geography needed
- **Automatic Transitions**: When you travel to a new area, the system automatically detects if you're entering a different module
- **Living World Memory**: Every location remembers your visits and the world evolves based on accumulated decisions

#### How Modules Connect
```
Example World Evolution:
Keep_of_Doom: Harrow's Hollow (village) → Gloamwood (forest) → Shadowfall Keep (ruins)
+ Crystal_Peaks: Frostspire Village (mountain town) → Ice Caverns (frozen depths)
= AI Connection: "Mountain paths from Harrow's Hollow lead to Frostspire Village"
```

The AI analyzes area descriptions and themes to suggest natural narrative bridges between modules.

#### Adventure Continuity
- **Chronicle System**: When you leave a module, the system generates a beautiful prose summary of your adventure
- **Context Accumulation**: Return visits include full history of previous adventures in that region
- **Character Relationships**: NPCs remember you across modules and adventures continue to evolve
- **Consequence Tracking**: Major decisions affect future adventures and available story paths

### 🌍 Community Module Compatibility

**Maximum compatibility with community content!** The system is designed for seamless integration:

- **Universal Module Support**: Any properly formatted module works automatically - no configuration needed
- **Intelligent Conflict Resolution**: Automatically resolves duplicate area IDs, location conflicts, and naming collisions
- **Safety Validation**: Multi-layer content review ensures family-friendly and schema-compliant modules
- **AI Auto-Integration**: Analyzes module themes and generates natural narrative connections to your world
- **Level-Based Discovery**: New modules appear in progression based on your character's advancement
- **Plug-and-Play**: Simply drop modules in the `modules/` directory and they integrate on next startup

### Module Creation & Sharing
- **Web Module Builder**: Interactive web interface for creating complete adventure modules
- **AI-Assisted Creation**: AI helps generate cohesive module content that integrates seamlessly
- **Real-time Progress Tracking**: Visual progress bar shows module generation stages
- **Community Standards**: Built-in validation ensures your modules work perfectly for other players
- **Organic Integration**: New modules connect naturally to existing worlds without manual configuration

### Key System Features

#### Context Management System
- **Conversation Compression Pipeline** - 85-90% token reduction
- **Chronicle Generation** - Beautiful AI-generated adventure summaries
- **Hub-and-Spoke Architecture** - Isolated modules with shared context
- **Living World Memory** - Complete relationship and consequence tracking
- **Automatic Compression** - Seamless token limit management

#### Module Generation & Management
- **Web Module Builder** - Interactive creation interface
- **Context-Aware Generation** - Consistent content across modules
- **Schema Compliance** - Strict SRD 5.2.1 validation
- **Community Support** - Share and integrate player modules
- **Safety Validation** - Automatic content review
- **AI Auto-Creation** - Dynamic module generation based on play
- **Narrative Parsing** - Natural language module descriptions

#### Player Housing & Hub System
- **Establish Hubs**: Transform any location into a permanent base of operations
- **Hub Services**: Rest, storage, gathering, training, research facilities automatically available
- **Ownership Types**: Party-owned, shared arrangements, or individual strongholds
- **Hub Persistence**: Return from any adventure to your established bases
- **Multi-Hub Support**: Maintain multiple bases across different regions and modules

**Hub Types Available:**
- **Strongholds**: Fortified keeps and castles for defensive operations
- **Settlements**: Villages and towns for commerce and community building
- **Taverns**: Social hubs for information gathering and party meetings
- **Specialized Facilities**: Wizard towers, temples, guildhalls with unique services

#### Player Storage System
- **Natural Language Storage**: Use intuitive commands like "I store my gold in a chest here"
- **Location-Based Containers**: Create storage at any location using available containers
- **Persistent Storage**: Items remain safely stored across sessions and module transitions
- **Party Accessibility**: All party members can access shared storage by default
- **Automatic Inventory Management**: System handles all inventory transfers with full safety protocols

**Storage Features:**
- **Container Types**: Chests, lockboxes, barrels, crates, strongboxes
- **Smart Organization**: AI helps organize items by type and importance
- **Secure Storage**: Containers tied to specific locations for security
- **Visual Integration**: Storage automatically appears in location descriptions

#### NPC Party Recruitment System

**Build your party by recruiting NPCs you meet during your adventures!**

- **Ask Anyone**: Approach any NPC and ask them to join your party
- **AI Evaluation**: The AI considers the NPC's personality, goals, current situation, and relationship with you
- **Natural Roleplay**: Use persuasion, offer payment, complete quests, or appeal to their motivations
- **Persistent Companions**: Recruited NPCs travel with you across modules and remember shared experiences
- **Dynamic Relationships**: Party NPCs develop bonds with each other and react to your decisions
- **Full Character Sheets**: NPCs become full party members with stats, equipment, and progression

**Recruitment Examples:**
- *"Who can you spare to help us?"* → Scout volunteers and AI evaluates if they can leave their duties
- *"Mira, would you like to join us? We could use a skilled healer on our journey."* → AI considers her personality and current situation
- *"Gareth, we're heading to dangerous lands. Your sword arm would be welcome."* → AI weighs his courage against his responsibilities
- *"Can anyone help with this mission?"* → Multiple NPCs may volunteer, but only appropriate ones will actually join

**NPC Party Features:**
- **Smart Recruitment**: NPCs evaluate your requests based on their personality, duties, and relationship with you
- **Realistic Responses**: Some NPCs may decline if they can't leave their post or don't trust you yet
- **Natural Conversation**: Ask for help, and NPCs will respond in character - no special commands needed
- **Combat Participation**: NPCs fight alongside you with full AI tactical decisions
- **Skill Contributions**: NPCs use their unique abilities to solve problems and overcome challenges
- **Story Integration**: Party NPCs contribute to roleplay and have their own character arcs
- **Cross-Module Continuity**: Your companions remember adventures across different modules
- **Character Development**: NPCs grow and change based on shared experiences

#### AI-Driven Module Auto-Generation
- **Contextual Adventures**: AI analyzes party history to create personalized modules
- **Seamless Integration**: New modules connect naturally to existing world geography
- **Dynamic Scaling**: Adventures adjust to party level and accumulated experience
- **Narrative Continuity**: References previous adventures and established relationships

**Auto-Generation Triggers:**
- **Adventure Completion**: New modules generated when current adventures conclude
- **Player Interest**: AI detects story hooks and creates relevant content
- **World Events**: Major decisions trigger consequences in new regions
- **Party Progression**: Level advancement unlocks higher-tier adventure options

#### Living Campaign World Integration
- **Isolated Module Architecture**: Each module operates independently while maintaining world coherence
- **AI Travel Narration**: Seamless transitions between modules with atmospheric descriptions
- **World Registry**: Central tracking of all modules, areas, and their relationships
- **Cross-Module Consequences**: Actions in one module affect opportunities in others

## Usage Examples

### Starting Your Adventure
```bash
# Launch the web interface
python run_web.py
# Browser opens to http://localhost:8357
# Follow the AI wizard for character creation
```

### Using the Module Toolkit
```bash
# Open toolkit directly
python launch_toolkit.py
# Or navigate to http://localhost:8357/toolkit

# Create a new module:
1. Click "Create Module"
2. Enter module details and description
3. AI generates complete adventure
4. Review and customize as needed
```

### Managing Graphic Packs and Module Media
```python
# From the toolkit interface:

# Graphic Pack Management:
1. Go to "Graphic Pack Management" tab
2. Create new pack or select existing
3. Set as active pack for image storage
4. Export pack as ZIP for sharing

# Module Media Generation:
1. Go to "Module Media Generator" tab  
2. Select module and art style
3. Review NPCs/monsters without images
4. Click "Generate Selected" for batch creation
5. Images automatically saved to active pack
```

### Natural Language Storage
```
Player: "I want to store my extra weapons in a chest here"
AI: *Creates storage container and transfers items*

Player: "What do we have stored at the keep?"
AI: *Lists all containers and contents at that location*
```

### NPC Recruitment
```
Player: "Elena, would you join us on our quest?"
AI: *Elena considers your relationship and her goals*
AI: "After what you've done for this town, I'd be honored to join you."
*Elena added to party with full stats*
```

### Combat Example
```
AI: "Roll for initiative!"
Player: "I cast fireball at the grouped enemies"
AI: *Calculates damage, saves, and effects*
AI: "The explosion engulfs three goblins..."
```

## Project Structure

### Directory Organization
```
/
├── core/                    # Core game engine modules
│   ├── ai/                 # AI integration (action_handler, dm_wrapper, etc.)
│   ├── generators/         # Content generation (module_builder, npc_builder, etc.)
│   ├── managers/           # System management (combat_manager, storage_manager, etc.)
│   ├── validation/         # Data validation systems
│   └── toolkit/           # Module toolkit components
├── utils/                  # Utility functions and helpers
│   └── compression/        # Token compression scripts
├── updates/               # State update modules
├── web/                   # Web interface
├── debug/                 # Debugging and development tools
│   ├── api_captures/      # API request/response captures
│   └── logs/              # Debug and error logs
├── modules/               # Adventure modules and game data
│   ├── conversation_history/  # All conversation files
│   ├── campaign_archives/     # Archived module conversations
│   ├── campaign_summaries/    # Living AI-generated summaries
│   └── [module_name]/        # Individual adventure modules
├── graphic_packs/         # Visual content packs
├── prompts/               # AI system prompts
├── schemas/               # JSON validation schemas
└── data/                  # Game data files
```

### Core Systems
- **Entry Points**
  - `main.py` - Terminal interface game loop
  - `run_web.py` - Web interface launcher
  - `launch_toolkit.py` - Module toolkit launcher
  - `web/web_interface.py` - Flask server and routes

- **Core Modules** (`core/`)
  - `ai/` - AI integration and DM logic
  - `generators/` - Content generation systems
  - `managers/` - System orchestration
  - `validation/` - Data validation
  - `toolkit/` - Module toolkit components

- **Support Systems** (`utils/`)
  - File operations and encoding
  - Logging and debugging
  - Character progression
  - Module path management

### Module Toolkit Components
- `core/toolkit/monster_generator.py` - Creature creation
- `core/toolkit/npc_generator.py` - NPC generation
- `core/toolkit/pack_manager.py` - Graphic pack management
- `core/toolkit/style_manager.py` - Visual style templates
- `core/toolkit/video_processor.py` - Portrait video processing
- `core/toolkit/pack_integration.py` - Pack activation system

### Data Organization
- `modules/` - Adventure modules and game data
- `graphic_packs/` - Visual content packs
- `data/bestiary/` - Monster compendium
- `data/styles/` - Style templates
- `schemas/` - JSON validation schemas
- `prompts/` - AI system prompts
- `templates/` - Web interface templates

## Configuration

### OpenAI API Setup
Edit `config.py` to configure AI models:

```python
# Primary models
DM_MAIN_MODEL = "gpt-4o-mini"  # Main storytelling
DM_SUMMARIZATION_MODEL = "gpt-4o-mini"  # Compression
DM_VALIDATION_MODEL = "gpt-4o-mini"  # Rule validation

# Specialized models
DM_COMBAT_NARRATOR_MODEL = "gpt-4o-mini"  # Combat
MODULE_CREATION_MODEL = "gpt-4o-mini"  # Content generation
```

### Web Interface Settings
- **Port**: 8357 (configurable in config.py)
- **Host**: localhost (network accessible with --host 0.0.0.0)
- **Debug Mode**: Disabled by default for production

### System Requirements
- **Python**: 3.9 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB for base install, more for packs
- **Network**: Internet connection for AI API
- **Browser**: Chrome, Firefox, or Edge (latest versions)

## Community Module Safety

The module stitcher includes comprehensive safety protocols for community-created content:

### Automatic Safety Validation
- **Content Review**: AI analyzes all module content for family-friendly appropriateness
- **File Security**: Blocks executable files, oversized content, and malicious patterns
- **Schema Compliance**: Validates JSON structure against 5th edition schemas
- **ID Conflict Resolution**: Automatically resolves duplicate area/location identifiers

### How It Works
```
New module detected → Security scan → Content safety check → Schema validation → Conflict resolution → Integration
```

### For Module Creators
- Use unique area IDs to avoid conflicts
- Keep files under 10MB (JSON/text only)
- Create family-friendly content
- Follow SRD 5.2.1 schemas
- Test with validation tools
- Include module documentation

### For Players
- Download modules from trusted sources
- System provides multiple safety layers automatically
- All community modules undergo validation before integration
- Backup saves before adding new modules as good practice

## Troubleshooting

### Common Issues

#### Installation
- **Module not found**: Run `pip install -r requirements.txt`
- **OpenAI API errors**: Check API key in `config.py`
- **Python version**: Requires 3.9+ (`python --version`)

#### Startup Problems
- **No modules**: Check `modules/` directory exists
- **Web won't start**: Check port 8357 availability
- **Toolkit unavailable**: Ensure `core/toolkit/` exists

#### Performance
- **Slow responses**: Normal (10-30s for AI)
- **High memory**: Restart after long sessions
- **File issues**: Check `.backup` files

#### Platform-Specific
- **Windows encoding**: Use web interface
- **macOS permissions**: Check file access
- **Linux paths**: Use absolute paths

### Developer Debugging

#### Debug Logging
- **API Captures**: Check `debug/api_captures/` for request/response logs
- **Error Logs**: Review `debug/logs/` for detailed error traces
- **Telemetry**: Analyze `telemetry_log.jsonl` for usage patterns

#### Combat Debugging
- **Ammunition Tracking**: Enable `AMMO_DEBUG` in `combat_manager.py`
- **Combat Flow**: Monitor turn-by-turn combat logs in debug output
- **Validation Errors**: Check AI response validation in console

#### Module Transitions
- **Cross-Module Travel**: Look for "different module" error messages
- **Chronicle Generation**: Check `campaign_summaries/` for AI summaries
- **Conversation Archives**: Review `campaign_archives/` for saved histories

### Getting Help
- Check this fork's GitHub Issues tab for known problems
- Create a new issue with your error message and system information
- Include your Python version and operating system in bug reports

## Contributing

We welcome contributions to NeverEndingQuest-TTRPG. Start with `CONTRIBUTING.md` and `DEV_SETUP.md` for the current fork workflow.

### How to Contribute

#### For Developers
1. **Fork the repository** and create a feature branch
2. **Follow the code style** established in existing files
3. **Test your changes** thoroughly before submitting
4. **Update documentation** for any new features
5. **Submit a pull request** with a clear description of changes

#### For Content Creators
- **Create adventure modules** using the web module builder
- **Design graphic packs** with unique visual styles
- **Share your modules** with the community
- **Report balance issues** or suggest improvements
- **Write documentation** or tutorials

#### For Players
- **Report bugs** with detailed reproduction steps
- **Suggest features** based on your gameplay experience
- **Share feedback** on game balance and AI behavior
- **Help new players** in discussions
- **Test character classes** and abilities

### Development Setup
```bash
# Fork and clone your fork
git clone https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git
cd NeverEndingQuest-TTRPG

# Create development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8  # Add linting tools

# Run tests
python -m pytest

# Format code
black .
```

### Contribution Guidelines
- **Code Style**: Follow existing patterns and use meaningful variable names
- **Documentation**: Update README and docstrings for new features
- **Testing**: Add tests for new functionality when possible
- **Compatibility**: Ensure changes work across Windows, macOS, and Linux
- **Licensing**: All contributions will be under Fair Source License 1.0 (transitioning to Apache 2.0 after 5 years)

### Areas Needing Help
- **Module Toolkit** - Enhanced generators and templates
- **Graphic Packs** - More visual styles and content
- **Web Interface** - UI/UX improvements
- **Documentation** - Tutorials and guides
- **Testing** - Class mechanics validation
- **Performance** - Response time optimization
- **Accessibility** - Screen reader support
- **Localization** - Multi-language support

## License

NeverEndingQuest is licensed under the Fair Source License 1.0 with a 5-year transition to Apache 2.0.
See the LICENSE and LICENSING.md files for complete details.

### Fair Source License Summary
- ✅ **Free for personal, educational, and non-commercial use**
- ✅ **Modify and customize for your campaigns**
- ❌ **Cannot create competing commercial services**
- ⏰ **Becomes fully open source (Apache 2.0) after 5 years**

### SRD 5.2.1 Attribution

This game implements mechanics from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC, available at https://dnd.wizards.com/resources/systems-reference-document.

The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/legalcode

This is unofficial Fan Content and is not affiliated with, endorsed, sponsored, or approved by Wizards of the Coast LLC. NeverEndingQuest is an independent implementation compatible with 5th edition rules.

## Recent Updates

### Version 0.3.5 - DM Voice Text-to-Speech

#### DM Voice Feature
New text-to-speech system for immersive DM narration:
- **Dual Engine Support**: Choose between free browser voices or premium OpenAI TTS
- **Browser Engine (Free)**: Uses Web Speech API with system-installed voices (English/Spanish)
- **OpenAI Engine (Paid)**: High-quality AI voices with Standard and HD model options
- **Voice Selection**: Pick from multiple voices per engine with live preview
- **Auto-play Mode**: Automatically plays DM narration as messages arrive
- **Smart Caching**: OpenAI responses cached client-side to reduce API costs on replay
- **Settings Integration**: Consolidated settings dropdown with smooth animations

#### UI/UX Improvements
- **Settings Dropdown**: Consolidated AI Images, DM Voice, and Model toggles into single dropdown
- **Accordion Animation**: Smooth expand/collapse for DM Voice settings section
- **Consistent Styling**: Unified button heights and spacing across chat interface
- **Custom Tooltips**: Styled tooltips matching existing UI patterns

### Version 0.3.0 - Token Compression System (First Iteration)

#### Token Compression System
First iteration of conversation compression technology:
- **Conversation compression**: Reduces token usage by approximately 70-90% in testing
- **Compressed system prompt**: 101K tokens → 8K tokens (~93% reduction)
- **Combat message compression**: ~70-85% compression rate  
- **Validation prompt compression**: ~60-75% compression rate
- **Goal**: Enable local LLM usage in future iterations

#### Dynamic NPC Core Memory System
- **Real-time NPC Discovery**: Automatically scans all module files to build complete NPC context
- **Dynamic Context Building**: Creates comprehensive NPC presence data for AI validation
- **Location-Aware Tracking**: Knows exactly which NPCs are at each location
- **Validation Integration**: Prevents AI from hallucinating NPCs that don't exist
- **Cross-Module Consistency**: Maintains NPC continuity across different adventures

#### Bug Fixes
- Fixed debug log file growing to 3GB+ due to exponential growth bug
- Fixed level up preserving current XP (was incorrectly resetting to 0)
- Fixed atlas caching bug preventing updates from showing
- Fixed NPC healing calculations not applying correctly
- Improved file locking and save error handling

#### Performance Stats (from actual usage)
- **Main system prompt**: ~93% token reduction
- **Combat messages**: ~70-85% compression rate
- **Validation messages**: ~60-75% compression rate

This is the first iteration of the compression system designed to reduce API costs and enable future local LLM deployment.

### Version 0.2.6 - Chronicle System & Enhanced Debugging
- **Chronicle Format** - Conversation history now shows "CHRONICLE" labels for historical adventure records
- **Cross-Module Transitions** - Improved error messages guide AI when moving between modules
- **File Organization** - Better project structure with dedicated debug/ and utils/compression/ directories
- **Ammunition Tracking** - Enhanced debugging for combat ammunition management
- **Container Reconciliation** - Automatic standardization of container names and ammunition
- **Tooling Integration** - Playwright CLI smoke workflow and Context7 documentation access

### Version 0.2.5 - Advanced Token Compression System
- **Token Compression Pipeline** - 76-82% reduction per message with parallel processing
- **Compressed Prompts** - System prompts reduced by 87-92% using @TAG notation
- **Open-Source Compatibility** - Context reduced from 100K+ to <10K tokens for local models
- **Intelligent Model Routing** - Automatic selection between GPT-4o and mini models
- **Combat Compression** - Special handling for verbose combat messages (82% reduction)
- **Telemetry System** - Comprehensive usage tracking for optimization
- **Cost Reduction** - 60-70% reduction in API costs through compression and routing
- **Local Model Support** - Compatible with Llama 3.1, Mistral, and other open-source LLMs

### Version 0.2.0 - Module Toolkit Release
- **Module Toolkit** - Complete content creation suite
- **NPC Generator** - Create NPCs with portraits and backstories
- **Monster Generator** - Build custom creatures with visuals
- **Graphic Pack System** - Manage and share visual content
- **Video Processing** - Convert videos to animated portraits
- **Style Templates** - Multiple art styles supported
- **Pack Import/Export** - Share content as ZIP files
- **Bestiary Integration** - Access complete monster compendium
- **Portrait System** - Unified hover previews across all characters

### Version 0.1.5 - Core Improvements
- **Conversation Compression** - Initial compression implementation
- **Module Architecture** - Clean separation of adventures
- **Living Summaries** - Dynamic adventure chronicles
- **Atomic Operations** - Data integrity protection
- **Manager Pattern** - Clean code architecture
- **Web Interface** - Real-time updates via SocketIO
- **Party Recruitment** - Any NPC can join adventures
- **Storage System** - Natural language inventory management

### Roadmap
- **Mobile Support** - Responsive web interface
- **Voice Integration** - Speech-to-text commands
- **AI Image Generation** - Scene and character art
- **Multiplayer** - Shared campaign sessions
- **Cloud Sync** - Cross-device save games
- **Additional Rulesets** - Pathfinder, OSR support
- **Workshop Integration** - Community content hub
- **Mod Support** - Custom rules and mechanics

---

**Upstream created by MoonlightByte; tabletop fork maintained by NeverEndingQuest-TTRPG contributors.**

For support, bug reports, or contributions, use this fork's GitHub repository and Issues tab.
