# tt-transition-failure-history-hygiene Specification

## Purpose
TBD - created by archiving change tt-authoritative-transition-inventory-runtime-reset. Update Purpose after archive.
## Requirements
### Requirement: Failed transition actions SHALL not generate synthetic arrival narration
If `transitionLocation` fails, runtime SHALL fail closed and SHALL NOT generate arrival narration, seamless stitched narration, or other synthetic destination prose for that turn.

#### Scenario: Transition execution error blocks arrival generation
- **WHEN** a `transitionLocation` action returns an execution error
- **THEN** runtime SHALL stop transition post-processing for that turn
- **AND** runtime SHALL NOT invoke arrival or stitching narration helpers

#### Scenario: Transition validation rejection blocks destination narration
- **WHEN** a `transitionLocation` action is rejected by authoritative transition validation
- **THEN** runtime SHALL not narrate the destination as reached

### Requirement: Failed transitions SHALL not rewrite conversation history as if movement succeeded
A failed transition SHALL NOT replace or rewrite conversation history with polished movement prose that implies the party arrived.

#### Scenario: History remains aligned to failed movement outcome
- **WHEN** a transition attempt fails after the assistant proposed movement
- **THEN** conversation history SHALL preserve the failed outcome
- **AND** conversation history SHALL NOT be rewritten to a successful arrival narrative

### Requirement: Dormant transition beautifier helpers SHALL not be active runtime dependencies
The seamless transition post-processor MAY remain in the codebase temporarily, but active runtime movement correctness SHALL NOT depend on it.

#### Scenario: Dormant helper bypassed in active runtime path
- **WHEN** runtime handles a `transitionLocation` turn
- **THEN** correctness of transition commit and failure handling SHALL be determined before any dormant beautifier helper could run

