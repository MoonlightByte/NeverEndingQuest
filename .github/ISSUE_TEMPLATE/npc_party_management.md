---
name: NPC Party Management Enhancement
about: Improve automatic NPC party joining functionality
title: "[ENHANCEMENT] AI should automatically add NPCs to party when they volunteer or are recruited"
labels: enhancement, AI behavior, party management
assignees: ''

---

## Issue Description
When NPCs volunteer to help or are recruited by the player, the AI should automatically add them to the party using the correct action, but currently this doesn't happen consistently.

## Current Behavior
- Player asks for help: "Who can you spare?"
- NPC volunteers: "I can spare Scout Kira"
- AI uses `updateCharacterInfo` to indicate joining but doesn't actually add to party tracker
- Party tracker remains unchanged (`"partyNPCs": []`)

## Expected Behavior
When an NPC explicitly joins the party, the AI should:
1. Use `updateCharacterInfo` to document the character change
2. Also trigger party tracker update to add NPC to `partyNPCs` array
3. Ensure party composition is properly tracked for gameplay mechanics

## Examples from Chat History
```
Player: "Who can you spare?"
AI Response: "I can spare Scout Kira"
Result: Kira mentioned as joining but not added to party tracker
```

## Validation Enhancement Needed
The validation prompt should include explicit instructions about:
- When NPCs join the party (volunteering, recruitment, etc.)
- How to properly update party composition
- Requirements for party tracker consistency

## Files to Update
- Validation prompt in AI response handler
- README.md gameplay section
- Party management documentation

## Priority
Medium - Affects gameplay mechanics and party management consistency

## Additional Context
This issue was discovered during active gameplay where Scout Kira volunteered to help with scouting but wasn't properly added to the party, requiring manual intervention.