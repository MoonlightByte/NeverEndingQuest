# Product Context

## Why this project exists
NeverEndingQuest is an AI-driven D&D campaign engine. The Tabletop Multiplayer feature is specifically designed for local, in-person play sessions (e.g., at a public library).

## Problems it solves
- **Single Player Limitation**: Original design was optimized for one person.
- **LLM Ambiguity**: Prompting the LLM to manage the party often leads to PCs being misidentified as NPCs.
- **Facilitation Burden**: Staff members need an efficient way to switch between multiple character sheets on one device.

## How it should work
- A facilitator runs the game on a laptop.
- Multiple PCs are added to the party.
- The UI provides tabs for each PC.
- Actions can be attributed to the "Active Character".
- Hard-wired Python functions handle PC additions to `party_tracker.json`.

## User Experience Goals
- Seamless switching between characters.
- Clear distinction between Player Characters and Non-Player Characters.
- "Staff-friendly" interface for fast-paced tabletop sessions.
