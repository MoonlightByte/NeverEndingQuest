## World Narrative Profile Assignment List (Seed Build Queue)

Purpose: define ingestion-time profile mapping so meta priors and fantasy priors stay intentionally layered.

Path policy: all local source files MUST live under `/user_uploads/text/`.

## Wave A - Meta Priors (ingest first)

1. Source slot: `the_prince_public_domain`
   - Profile ID: `profile.strategy_realpolitik`
   - Profile kind: `strategy_realpolitik`
   - Priority: high
   - Expected atom emphasis: `decision_logic`, `faction_pattern`, `institution_pattern`, `arc_shape`
   - Guardrails: no direct ruler/place proper nouns in atoms

2. Source slot: `inferno_public_domain`
   - Profile ID: `profile.cosmology_layered_realms`
   - Profile kind: `cosmology_layered_realms`
   - Priority: high
   - Expected atom emphasis: `cosmology_layer`, `realm_transition_rule`, `moral_topology`, `scene_template`
   - Guardrails: no direct canonical proper nouns in atoms

3. Source slot: `lovecraft_public_domain_batch`
   - Profile ID: `profile.horror_eldritch_pressure`
   - Profile kind: `horror_eldritch_pressure`
   - Priority: high
   - Expected atom emphasis: `tone`, `threat_pattern`, `knowledge_cost`, `arc_shape`
   - Guardrails: avoid non-public-domain named entity carryover

## Wave B - Fantasy Specific Priors (ingest after Wave A)

4. Source slot: `fantasy_batch_01`
   - Profile ID: `profile.fantasy_novel_batch_01`
   - Profile kind: `fantasy_novel_batch_01`
   - Priority: medium
   - Expected atom emphasis: `motif`, `scene_template`, `faction_pattern`, `archetype`

5. Source slot: `fantasy_batch_02`
   - Profile ID: `profile.fantasy_novel_batch_02`
   - Profile kind: `fantasy_novel_batch_02`
   - Priority: medium
   - Expected atom emphasis: `motif`, `scene_template`, `faction_pattern`, `archetype`

6. Source slot: `fantasy_batch_03`
   - Profile ID: `profile.fantasy_novel_batch_03`
   - Profile kind: `fantasy_novel_batch_03`
   - Priority: medium
   - Expected atom emphasis: `motif`, `scene_template`, `faction_pattern`, `archetype`

## Operator Rules

- MUST process one source file at a time.
- MUST run strict anonymous compliance checks per ingest.
- MUST keep source-specific labels in local run logs only, not committable atom payloads.
- SHOULD ingest all Wave A sources before starting Wave B.
- SHOULD review top weighted atoms after each source for abstraction quality.
