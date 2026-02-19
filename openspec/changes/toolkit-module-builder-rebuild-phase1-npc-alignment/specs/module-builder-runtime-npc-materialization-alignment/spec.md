## ADDED Requirements

### Requirement: Runtime NPC materialization SHALL consume module seed context when available

Runtime NPC materialization paths SHALL read module-local NPC seed context and pass it into NPC generation/materialization logic.

Primary callsites:
- enlist path (`updatePartyNPCs` add flow)
- combat fallback NPC creation path

#### Scenario: Seed file available for target module
- **WHEN** runtime materialization is requested for an NPC in a module with a seed artifact
- **THEN** generation input includes matching seed context
- **AND** materialized NPC data reflects seed-informed profile hints when provided

#### Scenario: Seed file unavailable
- **WHEN** runtime materialization is requested and no seed artifact exists
- **THEN** existing generation path still executes
- **AND** gameplay flow remains functional

### Requirement: Generated NPC records SHALL be role-normalized and profile-key complete

Materialized NPC records SHALL be normalized for role fields and include appearance profile keys required by downstream portrait/promotion workflows.

Role normalization contract:
- `type = "npc"`
- `character_type = "npc"`
- `character_role = "npc"`

Appearance key presence contract:
- `age`, `height`, `weight`, `eyes`, `skin`, `hair` keys present (values may be empty)

#### Scenario: LLM omits role markers or appearance fields
- **WHEN** upstream model output is missing some role/profile keys
- **THEN** deterministic postprocessing fills required keys
- **AND** final saved character record remains schema-valid

### Requirement: Add Existing candidate listing SHALL not classify explicit NPC records as players

Candidate listing for Add Existing SHALL exclude records explicitly marked as NPC by any role marker field.

#### Scenario: Character file has explicit NPC role marker
- **WHEN** candidate listing scans character files
- **THEN** files with `type="npc"` OR `character_type="npc"` OR `character_role="npc"` are excluded from player candidate list

### SHOULD Guidance

- Runtime generation SHOULD fail closed on schema-critical corruption and fail open for non-critical optional enrichment.
