## ADDED Requirements

### Requirement: Toolkit packet-built modules SHALL use a shared monster hydration pipeline
Packet-built toolkit modules SHALL resolve authored monster references through the same authoritative hydration contract used by readiness repair, post-build finishing, and runtime-authorized hydration.

#### Scenario: Readiness routes authored monster repair through shared hydration
- **WHEN** a packet-built module fails `reference_integrity` because an authored monster file is missing
- **THEN** readiness repair SHALL invoke the shared monster hydration pipeline for that monster reference
- **AND** SHALL NOT route the repair through a separate legacy closure path with different precedence rules

#### Scenario: Finishing reuses the same hydration contract
- **WHEN** toolkit post-build finishing runs monster materialization for a packet-built module
- **THEN** finishing SHALL use the same shared monster hydration contract and structured result model as readiness repair
- **AND** finishing MUST NOT maintain a toolkit-only parallel monster materializer

### Requirement: Packet-built modules SHALL authorize monster hydration from authored module assets even without seed artifacts
The toolkit SHALL treat authored module assets as sufficient hydration inputs when `monsters_seed.json` is absent or incomplete.

#### Scenario: Packet-built module has area monster refs but no seed file
- **WHEN** a packet-built module contains authored monster references in its generated area files
- **AND** `monsters_seed.json` is missing or empty
- **THEN** the shared hydration pipeline SHALL discover the authored monster identities from module-owned assets
- **AND** SHALL continue hydration using those discovered references

#### Scenario: Seed artifacts remain usable when present
- **WHEN** a packet-built or ingest-built module already has `monsters_seed.json`
- **THEN** the shared hydration pipeline SHALL accept that file as a hydration input source
- **AND** SHALL preserve backward compatibility with existing ingest workflows

### Requirement: Authorized non-bestiary monsters SHALL support controlled AI generation
The toolkit SHALL support creation of module-local monster files for authored monsters that are not present in deterministic reusable sources or the shipped bestiary.

#### Scenario: Authored bespoke monster misses deterministic sources
- **WHEN** a monster is authorized by authored module content
- **AND** no existing module-local file, reusable trusted file, or bestiary-backed source can satisfy it
- **THEN** the shared hydration pipeline SHALL allow controlled AI generation for that monster
- **AND** the generated output SHALL be written as a schema-valid module-local monster JSON before hydration is considered successful

#### Scenario: Unauthorized monster does not trigger AI generation
- **WHEN** a missing monster reference is not authorized by authored module content
- **THEN** the shared hydration pipeline SHALL reject the reference as unauthorized
- **AND** SHALL NOT invoke controlled AI generation

### Requirement: Hydration blockers SHALL remain structured and readiness-blocking
Hydration failures SHALL stay visible, structured, and blocking until the missing monster file exists locally.

#### Scenario: Controlled AI generation fails for an authorized monster
- **WHEN** an authorized monster reaches the controlled AI generation step and generation does not produce a valid local monster file
- **THEN** the hydration pipeline SHALL return a structured blocking outcome with a stable blocker class
- **AND** toolkit readiness SHALL continue to fail on `reference_integrity`

#### Scenario: Hydration outcome exposes precedence mode
- **WHEN** the shared monster hydration pipeline resolves or fails a monster reference
- **THEN** the result SHALL include the winning or failing hydration mode such as `existing`, `reuse`, `bestiary`, `generated`, `unauthorized`, or `failed`
- **AND** toolkit reporting SHALL be able to surface that mode without parsing freeform stderr text
