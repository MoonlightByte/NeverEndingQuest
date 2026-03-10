# Level Up System Documentation

## Overview
The level up system has been completely refactored to provide a focused, separate conversation for character advancement, similar to how combat encounters are handled. This ensures proper validation, interactive decision-making for players, and automatic optimization for NPCs.

## Architecture

### Components
1. **level_up_manager.py** - Main level up handler (subprocess)
2. **level_up_system_prompt.txt** - Specialized DM prompt for level up
3. **leveling_validation_prompt.txt** - Validation rules for 5e compliance
4. **leveling_info.txt** - 5e leveling tables and rules reference

### Flow
1. Main game detects levelUp action
2. action_handler.py launches level_up_manager.py as subprocess
3. Separate conversation handles all level up decisions
4. Validation ensures 5e rule compliance
5. Summary returned to main game when complete

## Key Features

### Player Level Up (Interactive)
- Step-by-step guidance through choices
- Hit point roll vs average decision
- Ability score improvement or feat selection
- Spell selection for casters
- Subclass choice at appropriate levels

### NPC Level Up (Automatic)
- Optimal choices made automatically
- Always takes average HP
- Class-appropriate ability score improvements
- No user interaction required

### Validation
- All choices validated against 5e rules
- leveling_validation_prompt.txt ensures accuracy
- XP thresholds, HP calculations, spell slots verified
- Proficiency bonus updates tracked

## Implementation Details

### Action Handler Integration
```python
# In action_handler.py
elif action_type == ACTION_LEVEL_UP:
    subprocess.run([
        "python", "level_up_manager.py", 
        entity_name, 
        str(current_level), 
        str(new_level)
    ], check=True, timeout=180)
```

### Summary Communication
- Level up manager writes summary to `level_up_summary.txt`
- Main game reads summary and injects into conversation
- Summary file cleaned up after reading

### Character Updates
- Uses updateCharacterInfo action for atomic updates
- Leverages existing update_character_info.py validation
- Deep merge preserves all character data

## Usage

### Triggering Level Up
When a player says "I want to level up" or similar:
1. DM recognizes intent and uses levelUp action
2. Level up manager launches automatically
3. Interactive session begins for players
4. Automatic processing for NPCs

### Example Player Interaction
```
[Level Up Manager] Starting level up for Eirik: Level 1 -> 2

DM: Beginning level up for Eirik from level 1 to level 2.

ELIGIBILITY CONFIRMED: You have 300 XP, meeting the 300 XP requirement for level 2.

HIT POINTS: As a Cleric, you gain 1d8 + CON modifier HP.
Would you like to:
1. Roll 1d8 (range: 1-8 + CON)
2. Take average (5 + CON)

Player: I'll take the average

DM: Taking average: 5 + 1 (CON) = 6 additional HP
New HP: 15 (was 9)

[continues with features, spells, etc.]
```

### Example NPC Processing
```
[Level Up Manager] Starting level up for scout_kira: Level 1 -> 2

DM: Beginning level up for scout_kira from level 1 to level 2.
As an NPC, I'll make optimal choices automatically.

- HP: Taking average (5 + 1 CON = 6), new total: 16
- New Feature: Cunning Action (Dash, Disengage, Hide as bonus action)
- Sneak Attack: Increased to 1d6
[updateCharacterInfo action applied]

Level Up Summary: Scout Kira advanced to level 2, gaining Cunning Action 
and increased Sneak Attack damage.
```

## Error Handling
- 3-minute timeout for level up process
- Validation failures prompt correction
- Failed updates logged with clear messages
- Process can be retried if needed

## Benefits
1. **Focused Experience** - No narrative distractions during level up
2. **Rule Compliance** - Automatic 5e validation
3. **Consistency** - Same pattern as combat system
4. **Flexibility** - Interactive for players, automatic for NPCs
5. **Reliability** - Atomic updates prevent partial changes

## Future Enhancements
- Multiclassing support
- Custom feat selection
- Variant rule options (rolled HP for NPCs)
- Level down handling
- Batch NPC leveling