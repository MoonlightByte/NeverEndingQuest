## ADDED Requirements

### Requirement: Bonsai-routed narration SHALL fail closed during the pilot
When a narration request is explicitly routed to Bonsai during the pilot, runtime SHALL fail closed if the Bonsai API is unreachable, unhealthy, or returns a transport-level failure.

#### Scenario: local Bonsai server is unavailable
- **WHEN** the Bonsai narration pilot is enabled
- **AND** a `dm_main` narration request is routed to Bonsai
- **AND** the local Bonsai API cannot be reached successfully
- **THEN** runtime SHALL surface an explicit provider failure for that narration request
- **AND** it SHALL NOT silently fall back to OpenAI or OpenRouter

#### Scenario: Bonsai request transport failure remains local to the pilot path
- **WHEN** a Bonsai-routed narration request fails after routing has selected Bonsai
- **THEN** the failure SHALL remain explicit for that narration turn
- **AND** runtime SHALL preserve existing provider behavior for unrelated non-pilot tasks

### Requirement: The pilot SHALL assume operator-managed Bonsai server lifecycle
The Bonsai narration pilot SHALL connect only to an already-running Bonsai API server and SHALL NOT spawn or supervise the Bonsai process during this slice.

#### Scenario: Bonsai server is not running at request time
- **WHEN** the pilot attempts a Bonsai-routed narration request and no local Bonsai server is available
- **THEN** runtime SHALL report the failure explicitly
- **AND** it SHALL NOT attempt to launch `bonsai api` automatically
