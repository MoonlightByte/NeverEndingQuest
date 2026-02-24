## Purpose

Ensure Character Sheet stats rendering remains resilient during startup timing races so temporary null payloads do not freeze UI and later valid payloads recover automatically.

## Requirements

### Requirement: Character Sheet stats rendering SHALL be null-safe during startup races

Character sheet stats rendering SHALL handle temporary null payloads without throwing and SHALL recover when valid data arrives.

#### Scenario: Null stats payload does not throw
- **WHEN** `player_data_response` for `stats` carries `data: null`
- **THEN** character sheet renderer completes without JS exception and displays deterministic waiting/error state

#### Scenario: Late valid payload renders without reload
- **WHEN** a later `player_data_response` contains valid stats payload
- **THEN** character sheet renders full stats without requiring manual page reload

#### Scenario: Backend error is surfaced
- **WHEN** stats response includes `error` text with null payload
- **THEN** the stats panel displays concise error context while keeping retry path active

### SHOULD Guidance
- SHOULD preserve existing polling cadence as recovery mechanism.
- SHOULD avoid broad layout/UI changes while implementing null-safety.
