## ADDED Requirements

### Requirement: Resumed Combat SHALL Not Reapply Already-Committed Enemy State
When resumed combat processing receives an enemy-state update whose authoritative post-update state is already present in the encounter, runtime SHALL treat that update as a replay and SHALL NOT apply the enemy HP/status mutation a second time.

#### Scenario: Resumed enemy damage result is already reflected in encounter state
- **WHEN** resumed combat processing handles an enemy update whose prose mirror indicates `HP old->new`
- **AND** the authoritative encounter already shows that enemy at the same final HP and non-living/living status implied by the update
- **THEN** runtime SHALL skip reapplying the enemy mutation
- **AND** runtime SHALL preserve the existing authoritative enemy HP/status unchanged

#### Scenario: Resumed enemy update is not yet reflected in encounter state
- **WHEN** resumed combat processing handles an enemy update whose authoritative final HP/status is not yet present in the encounter
- **THEN** runtime SHALL apply the update normally
- **AND** later defeat checks SHALL use the newly persisted authoritative enemy state

### Requirement: Resumed Replay Guards SHALL Prevent False Combat Auto-Exit
Resumed combat replay protection SHALL prevent auto-exit from concluding combat while a hostile still has positive authoritative HP.

#### Scenario: Positive-HP enemy survives resumed player damage replay attempt
- **WHEN** a resumed player damage action targets an enemy that already has positive post-hit HP recorded in the authoritative encounter
- **THEN** runtime SHALL not reduce that enemy a second time from the stale replay payload
- **AND** combat auto-exit SHALL NOT fire while that enemy remains alive with positive HP

### Requirement: Resumed Combat Summary Handoff SHALL Be Historical-Only
When resumed combat ends, the combat summary appended to main conversation history SHALL be explicitly marked as historical record and SHALL forbid replay of XP, treasure, or combat-state rewards.

#### Scenario: Resumed combat summary is appended to main history
- **WHEN** resumed combat completes and main history receives the encounter summary
- **THEN** the appended summary SHALL use the historical-record marker contract
- **AND** the appended summary SHALL explicitly state that rewards and combat bookkeeping were already distributed by the combat system

#### Scenario: Main loop processes resumed combat summary history
- **WHEN** the main loop later reads a resumed combat summary from history
- **THEN** it SHALL treat the summary as historical context only
- **AND** it SHALL NOT emit fresh reward or combat-state update actions solely from that summary

### Requirement: Resume Replay Guards SHALL Preserve Non-Resume Compatibility
The replay guard fix SHALL preserve existing non-resume combat behavior and single-player compatibility.

#### Scenario: Normal combat applies a new enemy HP update
- **WHEN** combat is not in a resumed replay condition
- **THEN** enemy updates SHALL continue to apply normally
- **AND** non-resume reward and summary flow SHALL remain unchanged except for any shared historical-summary wrapper unification
