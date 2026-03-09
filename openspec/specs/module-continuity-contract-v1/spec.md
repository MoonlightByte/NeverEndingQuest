# module-continuity-contract-v1 Specification

## Purpose
TBD - created by archiving change any-order-module-continuity-normalization. Update Purpose after archive.
## Requirements
### Requirement: Continuity Contract v1 Metadata

Modules that support any-order play SHALL expose additive continuity metadata under a versioned contract.

Required continuity fields:
- `continuity_version` (string, expected value "v1")
- `entry_state_variants` (object with keys: `cold_start`, `partial_context`, `late_arc`)
- `cross_module_refs` (array of normalized cross-module reference objects)
- `standalone_fallback` (object mapping critical lore/quest elements to in-module fallback sources)

The continuity contract MUST be additive and MUST NOT remove or rename existing module IDs, area IDs, or core progression fields.

#### Scenario: Cold-start standalone run

- **GIVEN** a module is played first in campaign order with no prior cross-module state
- **WHEN** the module runtime loads the continuity metadata
- **THEN** the module provides in-module fallback clues sufficient to complete core arc
- **AND** no hard cross-module prerequisite blocks main progression
- **AND** any external references are presented as optional context, not required gates

#### Scenario: Prior-knowledge entry

- **GIVEN** a module is played after one or more linked modules
- **WHEN** the module runtime evaluates `entry_state_variants`
- **THEN** `partial_context` or `late_arc` framing is available based on prior module completion flags
- **AND** lore references can adjust flavor, NPC reactions, or rewards without creating required dead-end dependencies

### Requirement: Entry State Variants Contract

The `entry_state_variants` object SHALL define three entry modes to support any-order play.

Required structure:
```json
{
  "cold_start": {
    "description": "Party knows nothing of prior lore",
    "narrative_framing": "...",
    "available_clues": ["..."]
  },
  "partial_context": {
    "description": "Party has completed at least one linked module",
    "narrative_framing": "...",
    "prior_knowledge_flags": ["..."]
  },
  "late_arc": {
    "description": "Party has completed multiple linked modules",
    "narrative_framing": "...",
    "advantage_hints": ["..."]
  }
}
```

#### Scenario: Runtime entry state selection

- **GIVEN** campaign state indicates which prior modules are completed
- **WHEN** the module initializes
- **THEN** the appropriate entry state variant is loaded
- **AND** NPCs and narrative adjust flavor without blocking progression

### Requirement: Standalone Fallback Safety

The `standalone_fallback` object SHALL ensure the module is completable without external module dependencies.

Required structure:
```json
{
  "critical_lore_sources": {
    "first_tithe_lore": ["area_NIG001", "NPC_father_aldric"],
    "ring_purpose": ["area_NIG006", "loot_table"]
  },
  "alternative_prereqs": {
    "third_path_unlock": ["any_of", ["father_aldric_lore", "druid_artifact", "module_internal_ritual"]]
  }
}
```

#### Scenario: Standalone completion possible

- **GIVEN** a player has NOT played any linked modules
- **WHEN** they attempt an ending or unlock that would require prior knowledge in a naive design
- **THEN** in-module fallback sources are available
- **AND** the ending is achievable via standalone play

### Requirement: Normalized Cross-Module References

`cross_module_refs` entries SHALL use deterministic normalized structure with canonical identifiers.

Each entry MUST include:
- `target_module` (string, module slug like "The_Pumpkin_Kings_Curse")
- `entity_id` (string, canonical entity identifier like "red_crimson_binder")
- `relation` (string, relationship type: "ally", "antagonist", "reference", "artifact_link", etc.)
- `confidence` (string enum: "high", "medium", "low")

Each entry SHOULD include:
- `notes` (string, optional free-text context for ambiguity resolution)

Alias ambiguity MUST be handled with fail-open behavior in warn-first rollout phase and MUST NOT cause hard failures.

#### Scenario: Unambiguous canonical reference

- **GIVEN** a cross-module reference maps exactly to one canonical entity
- **WHEN** the continuity checker validates the reference
- **THEN** it is recorded with `confidence: "high"`
- **AND** no warning is emitted

#### Scenario: Ambiguous alias mapping

- **GIVEN** two or more canonical entities match a free-text alias (e.g., "Red" matches both "red_crimson_binder" and "red_wandering_merchant")
- **WHEN** the continuity checker attempts resolution
- **THEN** the reference is recorded with `confidence: "low"`
- **AND** a warning is emitted with ambiguity details
- **AND** ingest/readiness continues successfully in warn-first profile

#### Scenario: Missing required continuity key in strict mode

- **WHEN** strict continuity mode is enabled and a required key is absent
- **THEN** module readiness fails with blocking error

