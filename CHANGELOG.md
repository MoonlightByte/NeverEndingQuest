# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased - NeverEndingQuest-TTRPG Fork]

### Changed

- Rebranded repository documentation to NeverEndingQuest-TTRPG for the tabletop multiplayer fork.
- Updated README quick-start/runtime references to current default web port `8357`.
- Clarified fork collaboration contract and source-of-truth hierarchy (`AGENTS.md`, `openspec/`, `plans/`, `adrs/`).
- Archived stale OpenSpec planning changes while retaining them for collaborator visibility under `openspec/changes/archive/`.

### Added

- Added `CONTRIBUTING.md` with fork-specific PR workflow and guardrails.
- Added `DEV_SETUP.md` for contributor install/run/verification workflow.
- Added `.github/PULL_REQUEST_TEMPLATE.md` for consistent collaboration metadata and verification reporting.

### Notes

- Playwright test MCP server is disabled for this fork; use Playwright CLI workflows.

## [0.2.0] - 2025-08-11

### Major UI and Media Update

This release brings significant improvements to the user interface, combat experience, and visual feedback systems.

#### Added
- **Combat Initiative Tracker**: Visual real-time combat tracker with animated portraits
  - Hover-activated video previews for monsters and NPCs
  - Dynamic HP display with color-coded health status
  - Automatic round tracking
  - Support for 30+ monster animations

- **Party Display System**: Persistent party member display outside combat
  - Real-time HP tracking for all party members
  - Character portraits with class-based defaults
  - NPC companion tracking

- **Time-of-Day System**: Dynamic environment visualization
  - Four time periods (sunrise, midday, sunset, nightfall)
  - Automatic image updates based on in-game time
  - Clean 60x60 adventure box display

- **Media Assets**: Comprehensive animation library
  - 30+ compressed monster video animations
  - NPC character animations
  - Thumbnail generation for all creatures
  - Class-based portrait defaults

- **Token Usage Tracking**: OpenAI API monitoring
  - Real-time tokens per minute (TPM) display
  - Requests per minute (RPM) tracking
  - Total token consumption monitoring

#### Changed
- **Skill System Refactor**: Improved skill handling with backward compatibility
  - Skills now stored as arrays for better AI interaction
  - Automatic proficiency bonus calculations
  - Support for both legacy and new formats

- **Combat Flow**: Fixed turn fragmentation issues
  - Improved prompt system for seamless multi-turn processing
  - Better handling of NPC and monster turns
  - Clearer player turn prompts

#### Fixed
- Video reset issues during 5-second refresh cycles
- Vertical scrollbar problems in initiative tracker
- Portrait upload and positioning system
- Combat conversation compression for character formatting
- Saving throws layout optimization

#### Technical
- Added comprehensive video compression utility
- Improved .gitignore for proper media tracking
- GPT-5 model integration with reasoning effort levels
- Enhanced file organization and import patterns

## [0.1.0] - 2025-01-20

### Initial Alpha Release

This is the first public alpha release of NeverEndingQuest, an AI-powered Dungeon Master for tabletop roleplaying using the world's most popular 5th edition system.

#### Features
- **Core Gameplay**
  - Complete 5th edition rules implementation with automated combat
  - Character creation wizard with class, race, and background selection
  - Persistent character progression with XP and leveling
  - Inventory management and equipment tracking
  - Spell slot tracking and magical effects
  - SRD 5.2.1 compliant content under CC BY 4.0

- **AI Dungeon Master**
  - Natural language processing for player actions
  - Dynamic narration and scene descriptions
  - NPC dialogue and personality management
  - Quest and plot progression tracking
  - Intelligent combat encounter management
  - Validation system to ensure consistent gameplay

- **Module System**
  - Two starter modules included:
    - The Thornwood Watch (Level 1-3): Stop a sorcerer corrupting the wilderness
    - Keep of Doom (Level 3-5): Lift the curse from an ancient keep
  - Hub-and-spoke architecture for infinite adventures
  - Module transition with context preservation
  - Dynamic area and location management
  - AI can create new modules when adventures complete

- **Innovation: Context Management**
  - Conversation compression to overcome AI memory limits
  - Persistent world state across sessions
  - NPC memory and relationship tracking
  - Adventure chronicle generation

- **Web Interface**
  - Real-time character sheet display
  - Interactive command interface
  - Combat tracker with initiative order
  - Visual dice rolling
  - Auto-scrolling adventure log
  - Tabbed character data viewer

#### Known Limitations
- Alpha release - expect bugs and rough edges
- Limited to two modules currently (AI can generate more)
- Requires OpenAI API key (Claude support coming)
- Web interface required for optimal experience
- Some combat edge cases may need refinement

#### Requirements
- Python 3.8+
- OpenAI API key with GPT-4 access
- Modern web browser
- ~100MB disk space

#### Legal
- Uses content from SRD 5.2.1 under Creative Commons Attribution 4.0
- Fair Source License for codebase
- No affiliation with Wizards of the Coast

## [Historical Unreleased (Upstream Snapshot)] - 2025-01-20

### Changed
- **Major Codebase Reorganization** for better maintainability:
  - All Python modules organized into logical directories:
    - `core/` - Core game engine (ai, generators, managers, validation)
    - `utils/` - Utility functions and helpers
    - `updates/` - State update modules
    - `web/` - Web interface
  - Module builder moved to `core/generators/module_builder.py`
  - Conversation history files moved to `modules/conversation_history/`
  - Updated all import paths throughout the codebase (100% import success)
  - Fixed 47+ import issues across 22 files
  - Added comprehensive import testing tools

### Added
- AI Autonomous Module Creation system:
  - AI DM can create new modules when current adventures are complete
  - Narrative-driven module generation from rich text descriptions
  - AI parsing of embedded parameters (areas, locations, level ranges)
  - Fully agentic system - AI controls all aspects of module creation
  - Conditional prompt injection only when module completion detected
- New `createNewModule` action for AI DM
- Enhanced `module_builder.py` with `ai_driven_module_creation` function
- AI narrative parser for extracting module parameters from prose
- Module creation prompt that guides contextual adventure generation
- Interactive tabs in the web interface for viewing player data:
  - Inventory tab showing equipment, weapons, and currency
  - Character Stats tab displaying basic info, combat stats, and abilities
  - NPCs tab listing party NPCs with their current status
- Auto-refresh of tab data every 5 seconds
- Socket.IO handlers for fetching character data from JSON files
- Responsive styling for tabbed interface with dark theme

### Fixed
- Web interface output routing to properly separate game narration and debug information
- Only "Dungeon Master:" messages appear in the game output panel
- All other output (DEBUG, ERROR, system messages, etc.) now goes to the debug panel
- Fixed issue where DM dialogue containing quotes or colons was incorrectly split between panels
- Improved detection of player status lines vs. DM content to prevent incorrect panel routing

## [0.1.0] - 2025-01-17

### Added
- New `generate_prerolls.py` module that pre-generates dice rolls for all combat actions, preventing the LLM from deciding roll outcomes
- Explicit character type labeling in combat (PLAYER, NPC, ENEMY) for clearer differentiation
- Import for `generate_prerolls` function in `combat_manager.py`
- Preroll text generation before each combat round with:
  - Attack rolls
  - Damage rolls (using proper damage dice from creature stats)
  - Saving throw rolls
  - Ability check rolls
  - Clear labeling of creature types and relationships
- Web-based interface for the game with Flask and SocketIO:
  - Separate panels for game output and debug information
  - Real-time updates using WebSockets
  - Automatic browser launch when starting the game
  - Professional dark theme UI
  - Input handling through web interface
- `web_interface.py` - Flask server with SocketIO for real-time communication
- `templates/game_interface.html` - Modern web UI with split panel design
- `run_web.py` - Simple launcher script that starts the web interface

### Changed
- Combat AI no longer determines dice roll outcomes - all rolls are pre-generated
- Enhanced creature type identification with explicit labels:
  - PLAYER CHARACTER: Controlled by the human player
  - NPC: Friendly non-player character allied with the player
  - ENEMY: Hostile monster fighting against the player
- Updated combat prompts to include pre-generated rolls for each round
- Updated `requirements.txt` to include Flask and SocketIO dependencies

### Improved
- Fairness of combat by removing AI bias in dice rolling
- Transparency of combat mechanics with explicit pre-rolled values
- Clarity of character roles and allegiances in combat encounters
- User experience with a modern web interface instead of terminal-only output

### Fixed
- Previously fixed XP calculation path issue for monster files
- Previously fixed .gitignore to exclude runtime and debug files
