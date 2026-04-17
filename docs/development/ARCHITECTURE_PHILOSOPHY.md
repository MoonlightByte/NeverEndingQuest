# D&D Dungeon Master System - Architecture Philosophy

NOTE: This document is retained as upstream/background philosophy context.
For current fork implementation contracts, use `AGENTS.md`, `openspec/`, and `adrs/`.

## Core Design Principles

### 1. **Modular Event-Driven Architecture**
Our system follows a clean separation of concerns with distinct layers that communicate through well-defined interfaces. Every game interaction is processed as a discrete action, enabling consistent state management and easy extensibility.

### 2. **AI-First Design with Human Safety Nets**
While AI drives the narrative and game logic, multiple validation layers ensure correctness. We embrace AI capabilities while maintaining strict data integrity through schema validation, response verification, and graceful error handling.

### 3. **Data Integrity Above All**
Every data operation is atomic, validated, and recoverable. We use JSON schemas, backup mechanisms, file locking, and multi-layer validation to ensure game state consistency even under failure conditions.

### 4. **Module-Centric Hub-and-Spoke Architecture with Timeline Preservation**
Our revolutionary module system uses geographic boundaries rather than narrative chapters. Each area network forms a self-contained module, with intelligent conversation segmentation preserving chronological adventure history. This creates a living, interconnected world where players can revisit any area while maintaining complete context through AI-generated adventure summaries and seamless timeline preservation.

### 5. **Unified Character Management**
All characters (players, NPCs, monsters) use consistent schemas and processing patterns while allowing for role-specific behavior. This simplifies maintenance and ensures consistent game mechanics.

## Architectural Patterns

### **MVC + Command Pattern + Strategy Pattern**
- **Model**: JSON-based persistent storage with schema validation
- **View**: Console interface with real-time status feedback
- **Controller**: Main game loop with centralized action processing
- **Command**: All interactions encapsulated as typed actions with parameters
- **Strategy**: Configurable AI models for different game aspects

### **Layered Architecture**
```
┌─────────────────────────────────────────┐
│  User Interface Layer (Console + Web)   │
├─────────────────────────────────────────┤
│  Action Processing Layer (Commands)     │
├─────────────────────────────────────────┤
│  AI Integration Layer (Multiple Models) │
├─────────────────────────────────────────┤
│  Game Systems Layer (Combat, Location)  │
├─────────────────────────────────────────┤
│  Data Management Layer (Files, Paths)   │
├─────────────────────────────────────────┤
│  Validation Layer (Schema, Integrity)   │
└─────────────────────────────────────────┘
```

## Data Flow Philosophy

### **Unidirectional Data Flow**
```
User Input → Action Parsing → AI Processing → Validation → State Update → Persistence
```

### **State Synchronization Strategy**
- Central game state in `party_tracker.json`
- Conversation history maintains AI context
- Real-time state updates across all game systems
- Atomic state transitions with rollback capability

## File Organization Principles

### **Module-Centric File Structure**
```
characters/             # Unified player/NPC storage (global)
├── player_character.json
├── npc_character.json
└── ...

modules/[module_name]/
├── areas/              # Location files (HH001.json, G001.json)
├── monsters/           # Module-specific creatures
├── encounters/         # Combat encounters
├── module_plot.json    # Module plot progression
├── party_tracker.json  # Current game state
└── npc_codex.json      # AI-generated NPC validation registry

modules/campaign_archives/   # Chronological conversation history
├── [Module]_conversation_001.json
├── [Module]_conversation_002.json
└── ...

modules/campaign_summaries/  # AI-generated adventure chronicles
├── [Module]_summary_001.json
├── [Module]_summary_002.json
└── ...

save_games/             # Module-aware save system
├── save_metadata.json
├── save_[timestamp].json
└── ...
```

### **ID and Naming Conventions**
- **Location IDs**: Area prefix + sequential number (HH001, G001)
- **Character Files**: Lowercase with underscores (norn.json, test_guard.json)
- **Encounter IDs**: Location-encounter format (B02-E1)
- **File Locking**: .lock suffix for concurrent access protection

## AI Integration Philosophy

### **Multi-Model Strategy**
- **Primary DM**: Main narrative and game logic (GPT-4 or Claude)
- **Combat Manager**: AI-driven turn-based combat simulation with validation
- **Character Effects Validator**: AI-powered temporary effects validation system
- **Level Up Manager**: AI-guided character progression with D&D 5e rule compliance
- **Content Generators**: Specialized AI builders for NPCs, monsters, locations, and complete modules
- **NPC Codex Generator**: AI-powered NPC extraction and validation registry creation
- **Response Validator**: Separate AI model verifies narrative and mechanical accuracy
- **Summarizers**: AI-generated adventure logs and conversation compression
- **Module Builder**: AI-autonomous complete module generation with integrated validation

### **Validation Pipeline**
1. **Syntax Validation**: JSON structure and parsing
2. **Schema Validation**: D&D rule compliance
3. **AI Validation**: Separate model verifies response accuracy
4. **State Validation**: Game state consistency checks
5. **Reference Validation**: Cross-file integrity verification

## Module Transition System

### **Intelligent Conversation Segmentation**
Our module transition system preserves chronological adventure history through advanced conversation timeline management:
- **Immediate Detection**: Module transitions detected in `action_handler.py` when party tracker changes
- **Smart Boundary Detection**: Two-condition logic for optimal conversation compression
- **AI Summary Integration**: Full adventure summaries loaded from campaign_summaries folder
- **Timeline Preservation**: Chronological adventure sequence maintained across all modules

### **Two-Condition Boundary Logic**
```
Condition 1: Previous Module Transition Exists
└─ Compress conversation between the two module transitions

Condition 2: No Previous Module Transition  
└─ Compress from after last system message to current transition
```

### **Conversation Timeline Architecture**
```
[System Message] → [Module Summary] → [Module Transition] → [New Module Conversation]
```

### **Sequential Archive Strategy**
- **Immediate Archiving**: Full conversation history preserved in campaign_archives/
- **AI Chronicle Generation**: Detailed adventure summaries created in campaign_summaries/
- **Sequential Numbering**: Automatic sequence tracking for chronological timeline
- **Context Restoration**: Complete adventure context available for return visits

## AI-Powered NPC Validation System

### **Intelligent Character Registry**
Our NPC Codex system solves the critical problem of AI narrative validation by automatically generating comprehensive NPC registries for each module using GPT-4 analysis:

- **AI-Powered Extraction**: Scans plot files and area descriptions to identify all legitimate NPCs
- **Context-Aware Analysis**: Distinguishes NPCs from locations, monsters, and generic titles
- **Source Attribution**: Tracks whether NPCs come from plot, locations, or character files
- **Bulletproof Validation**: Prevents AI from inventing non-existent characters during gameplay

### **NPC Codex Architecture**
```
npc_codex.json Structure:
{
  "module_name": "Keep_of_Doom",
  "generated_timestamp": "2025-06-22T00:21:37.820175",
  "generation_method": "AI_extraction_GPT4",
  "npcs": [
    {
      "name": "Elder Mirna Harrow",
      "source": "plot_character|location_character|character_file"
    }
  ],
  "total_npcs": 23,
  "content_stats": {
    "plot_content_length": 6468,
    "area_content_length": 286135,
    "existing_character_files": 21
  }
}
```

### **Validation Integration Pipeline**
1. **Automatic Generation**: NPC codex created on-demand using AI analysis
2. **Atomic File Operations**: Concurrent-safe writing with backup and locking
3. **Module Validation**: NPCs verified against codex during AI response validation
4. **Caching Strategy**: Existing codex files reused until module content changes
5. **Error Recovery**: Graceful fallback to regeneration if codex corruption detected

### **AI Extraction Logic**
- **Character Identification**: Distinguishes people with names from places and creatures
- **Title Preservation**: Maintains full names including titles ("Old Fenrick", "Mira the Moorwise")
- **Context Sensitivity**: Understands narrative context to identify legitimate story characters
- **Source Classification**: Categorizes NPCs by their primary source in module files

### **File Locking and Concurrency**
- **Dual Locking System**: NPC generator uses manual locks, atomic writer handles internal locking
- **Conflict Resolution**: Prevents interference between concurrent access patterns
- **Lock File Management**: Automatic cleanup with timeout mechanisms
- **Atomic Operations**: Write verification with rollback on failure

## Error Handling Philosophy

### **Defense in Depth**
- Multiple validation layers prevent cascading failures
- Graceful degradation when systems encounter errors
- Automatic retry mechanisms with intelligent backoff
- Comprehensive logging for debugging and recovery

### **Recovery Strategies**
- **File Operations**: Atomic writes with automatic backups
- **AI Responses**: Retry with feedback loops and fallback prompts
- **State Corruption**: Rollback to last known good state
- **Schema Migration**: Backward compatibility with legacy data

## Extensibility Design

### **Action-Based Extension**
New game features are added as new action types with:
- Consistent parameter validation
- Standard AI prompt patterns
- Unified error handling
- Automatic state synchronization

### **Schema-Driven Development**
All game content follows JSON schemas that:
- Ensure data consistency across the system
- Enable automatic validation and migration
- Provide clear contracts for AI generation
- Support backward compatibility

## Performance and Scalability

### **Efficient File Operations**
- Lazy loading of campaign data
- Atomic file operations prevent corruption
- Efficient path resolution through `CampaignPathManager`
- UTF-8 encoding with cross-platform compatibility

### **AI Response Optimization**
- Conversation history trimming to manage context size
- Model-specific temperature and parameter tuning
- Batch processing where possible
- Intelligent retry strategies

## Security and Privacy

### **Data Protection**
- Local file storage for campaign data privacy
- No sensitive information in logs or error messages
- Secure API key management through configuration
- File locking prevents concurrent modification issues

### **Input Validation**
- All user inputs validated against expected patterns
- JSON injection prevention through proper parsing
- Path traversal protection in file operations
- Sanitization of special characters in filenames

## Testing Philosophy

### **Automated Validation**
- Schema compliance testing for all content types
- Automated campaign generation and validation
- Combat simulation testing with edge cases
- Cross-platform compatibility verification

### **Manual Testing Support**
- Comprehensive logging for debugging
- Test campaign generation for validation
- Dummy data creation for isolated testing
- Debug modes for development workflows

## Future Evolution Guidelines

### **Maintaining Architectural Integrity**
When extending the system:
1. Follow established patterns (Command, Strategy, Factory)
2. Add validation layers for new data types
3. Maintain schema-driven development approach
4. Preserve atomic operations and error recovery
5. Keep AI integration modular and configurable

### **Backward Compatibility**
- Always provide migration paths for schema changes
- Maintain support for legacy file structures
- Preserve existing API contracts where possible
- Document breaking changes with migration guides

## Save Game Management Architecture

### **Module-Aware Save System**
Our save game system provides comprehensive campaign persistence with intelligent module context preservation:

- **Save State Capture**: Complete game state serialization including party tracker, conversation history, and module-specific data
- **Module Context Preservation**: Saves include current module information for seamless restoration across different adventure contexts
- **Save Metadata Management**: Timestamp tracking, character level snapshots, and location context for save file organization
- **Cross-Module Save Compatibility**: Save files work seamlessly when transitioning between different adventure modules

### **Save Game Architecture**
```
Save Game Structure:
{
  "metadata": {
    "save_timestamp": "ISO_timestamp",
    "current_module": "module_name",
    "party_level_range": "1-3",
    "current_location": "area_id"
  },
  "game_state": {
    "party_tracker": {...},
    "conversation_history": [...],
    "module_data": {...}
  }
}
```

### **Atomic Save Operations**
- **Backup Creation**: Automatic backup of existing saves before overwriting
- **Write Verification**: Save integrity validation after write operations
- **Rollback Capability**: Automatic restore of backup on save corruption detection
- **Concurrent Access Protection**: File locking during save operations

### **Save Discovery and Management**
- **Automatic Save Detection**: Dynamic discovery of available save files
- **Metadata-Driven Organization**: Save list presentation with contextual information
- **Save Validation**: Schema compliance checking for save file integrity
- **Legacy Save Migration**: Backward compatibility with older save formats

## Player Storage System Architecture

### **Location-Tied Storage Model**
Our player storage system transforms game locations into persistent player bases with comprehensive inventory management:

- **Location Storage Binding**: Any location can become a permanent storage facility through player interaction
- **Storage Schema Integration**: Locations gain storage capabilities through dynamic schema extension
- **Multi-Container Support**: Different storage container types (chests, barrels, rooms) with distinct capacity limits
- **Persistent Storage State**: Storage contents preserved across game sessions and module transitions

### **Storage System Components**
```
Storage Integration Pipeline:
Location Detection → Storage Initialization → Schema Validation → Atomic Operations → State Persistence
```

### **Storage Manager Architecture**
- **Atomic Storage Operations**: All storage modifications use backup/restore patterns for data integrity
- **Concurrent Access Protection**: File locking prevents storage corruption during simultaneous access
- **Schema-Driven Validation**: Storage operations validated against location and item schemas
- **Cross-Module Storage Access**: Storage contents accessible when revisiting locations across different modules

### **Storage Operation Patterns**
```python
# Storage operation with atomic protection:
# 1. Create backup of current location state
# 2. Modify location storage data
# 3. Validate modified data against schema
# 4. Write changes with integrity verification
# 5. Clean up backup on successful operation
```

## Level Up Management Architecture

### **AI-Driven Character Progression**
Our level up system provides interactive, AI-guided character advancement with complete D&D 5e rule compliance:

- **Isolated Subprocess Execution**: Level up operations run in separate process to prevent game state corruption
- **AI-Guided Decision Making**: GPT-4 provides intelligent recommendations for character advancement choices
- **Interactive Progression Interface**: Step-by-step guidance through ability score improvements, feat selection, and spell choices
- **Rule Compliance Validation**: Automatic verification of all character advancement against D&D 5e rules

### **Level Up Process Architecture**
```
Level Up Pipeline:
XP Validation → Backup Creation → Subprocess Launch → AI Interaction → Rule Validation → Character Update → State Restoration
```

### **Character Advancement Components**
- **Experience Point Validation**: Prevents duplicate XP awards and validates level progression thresholds
- **Ability Score Management**: Guided ability score improvements with racial bonus calculations
- **Feat Integration**: AI-assisted feat selection with prerequisite validation
- **Spell Management**: Class-appropriate spell selection with spell slot calculation
- **Equipment Integration**: Automatic equipment updates for class-specific gear

### **Fault-Tolerant Design**
- **Process Isolation**: Level up failures don't affect main game state
- **Automatic Backup/Restore**: Character state protected through atomic operations
- **Validation Layers**: Multiple validation passes ensure character sheet integrity
- **Graceful Error Recovery**: Comprehensive error handling with rollback capabilities

## Web Interface Architecture

### **Real-Time Web Interface System**
Our web interface provides a modern browser-based interface with real-time game state synchronization:

- **Flask + SocketIO Integration**: Real-time bidirectional communication between web interface and game engine
- **Tabbed Interface Design**: Organized character data presentation with dynamic tab management
- **Queue-Based Output Management**: Threaded output processing for responsive user experience
- **Cross-Platform Compatibility**: Browser-based interface works across different operating systems

### **Web Interface Components**
```
Web Architecture Stack:
Frontend (HTML/CSS/JS) → SocketIO Bridge → Flask Application → Game Engine Integration → File System
```

### **Real-Time Communication Patterns**
- **Event-Driven Updates**: Game state changes broadcast immediately to connected clients
- **Queue-Based Processing**: Output messages queued and processed asynchronously
- **Session State Management**: Web sessions linked to game state for consistent experience
- **Concurrent User Support**: Multiple browser sessions can monitor same game state

### **Status Management System**

### **Observer Pattern Status Tracking**
Our status management system provides comprehensive real-time feedback across all game operations:

- **Multi-Channel Status Updates**: Different status types (info, warning, error, success) with appropriate visual presentation
- **Thread-Safe Status Queue**: Status updates processed safely across multiple threads
- **Component-Specific Status**: Different game systems provide contextual status information
- **Real-Time Status Broadcasting**: Status updates immediately visible in both console and web interfaces

### **Status System Architecture**
```python
# Status update flow:
# Game Component → Status Manager → Queue Processing → Interface Updates (Console + Web)
```

### **Status Categories and Integration**
- **Combat Status**: Turn progression, damage calculations, and combat resolution updates
- **Character Status**: Level progression, equipment changes, and ability modifications
- **Module Status**: Location transitions, plot progression, and module loading information
- **System Status**: File operations, AI processing, and validation results

## Session Management Architecture

### **Cross-System Session State**
Our session management architecture maintains consistent state across all game systems and operations:

- **Session Isolation**: Each major operation (save/load, level-up, storage management) maintains isolated session context
- **State Synchronization**: Session state synchronized across console interface, web interface, and file system
- **Session Recovery**: Robust session recovery mechanisms for interrupted operations
- **Cross-Module Session Continuity**: Session state preserved during module transitions and adventure progression

### **Session State Components**
```
Session Architecture:
Game State ↔ Session Manager ↔ Operation Contexts (Save, Level-Up, Storage, Combat)
                    ↕
            Status Broadcasting System
                    ↕
        Interface Layers (Console + Web)
```

### **Session Lifecycle Management**
- **Session Initialization**: Automatic session setup when game operations begin
- **Context Preservation**: Operation-specific contexts maintained throughout complex workflows
- **Session Cleanup**: Automatic cleanup of temporary session data and locks
- **Session Migration**: Session state transferred seamlessly during module transitions

## Atomic Operations Architecture

### **Universal Backup/Restore Pattern**
Our atomic operations architecture ensures data integrity across all game systems through comprehensive backup and restoration mechanisms:

- **Pre-Operation Backups**: Automatic backup creation before any state-modifying operation
- **Operation Validation**: Post-operation validation with automatic rollback on failure
- **Multi-File Atomic Operations**: Coordinated atomic operations across multiple related files
- **Nested Operation Support**: Atomic operations within atomic operations with proper cleanup

### **Atomic Operation Patterns**
```python
# Universal atomic operation pattern:
# 1. Create backup of all affected files
# 2. Perform operation with validation at each step
# 3. Verify final state integrity
# 4. Clean up backups on success OR restore from backups on failure
```

### **Atomic Operation Integration**
- **Character Operations**: All character modifications use atomic patterns (level-up, equipment, effects)
- **Location Operations**: Location storage and modification operations with full backup protection
- **Save Game Operations**: Save creation and loading with integrity verification
- **Module Transitions**: Module changes coordinated across multiple file systems atomically
- **Combat Operations**: Combat state changes with rollback capability for invalid states

### **Fault Tolerance Design**
- **Operation Logging**: Comprehensive logging of all atomic operations for debugging and recovery
- **Automatic Recovery**: Failed operations automatically restored to pre-operation state
- **Corruption Detection**: Automatic detection of file corruption with restoration from backups
- **Graceful Degradation**: System continues operating even when some atomic operations fail

This architecture philosophy ensures our D&D system remains maintainable, extensible, and reliable while embracing the power of AI-driven game management.
