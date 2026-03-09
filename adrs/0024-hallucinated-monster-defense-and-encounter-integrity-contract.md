# ADR-0024: Hallucinated Monster Defense and Encounter Integrity Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Narrative model hallucinations could introduce invalid monsters into encounter generation.

## Decision
Apply defense in depth:
- Prompt-level constraint against invented monster types.
- Bestiary-only runtime gate in tabletop mode.
- Encounter validation that blocks combat start when enemy set is invalid.

## Consequences
- Stronger encounter integrity and reduced fabricated content.
- More explicit failure paths and quarantine behavior.
- Requires bestiary completeness for intended encounters.

## Sources
- `AGENTS.md`
- `core/generators/combat_builder.py`
- `core/ai/action_handler.py`
