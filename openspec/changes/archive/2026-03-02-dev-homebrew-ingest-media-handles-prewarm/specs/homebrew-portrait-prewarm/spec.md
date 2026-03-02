# homebrew_prewarm_portraits.py

## ADDED Requirements

### Requirement: NPC and Monster Portrait Prewarm
The tool SHALL prewarm NPC and monster portraits for an ingested module.

#### Scenario: Missing portraits
Given module entities with no existing portrait media
When prewarm runs
Then the tool SHALL attempt to generate/materialize portraits
And record completion counters by entity type

#### Scenario: Existing portraits
Given module entities with existing portrait media
When prewarm runs
Then the tool SHALL skip generation for those entities
And increment skipped counters

### Requirement: Fail-open generation errors
The tool SHALL not fail the ingest pipeline on provider/generation errors.

#### Scenario: Provider error
Given portrait provider returns an error for one entity
When prewarm runs
Then the tool SHALL record warning and failed counter
And continue prewarming remaining entities
And return degraded status instead of hard failure

### Requirement: Structured counters
The tool SHALL expose structured progress counters.

#### Scenario: JSON mode
Given `--json` flag
When tool completes
Then output SHALL include:
- status (`success|degraded|skipped`)
- `npcs.planned|done|failed|skipped`
- `monsters.planned|done|failed|skipped`
- warnings[]

## ADDED Interface

### CLI
```bash
python scripts/homebrew_prewarm_portraits.py \
  --slug <module_slug> \
  [--json]
```
