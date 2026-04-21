# module-publishable-gate Specification

## ADDED Requirements

### Requirement: Publishability SHALL NOT treat shared static fallback media as module-local fulfillment

Shared runtime fallback media under `web/static/media/{npcs,monsters}` MUST NOT satisfy module-local media requirements for publication readiness.

#### Scenario: Shared fallback exists but module-local media is missing
- **GIVEN** a module is missing required media under `modules/<module>/media`
- **AND** a matching asset exists under `web/static/media/npcs` or `web/static/media/monsters`
- **WHEN** publishability is evaluated
- **THEN** the module SHALL remain blocked for missing module-local media
- **AND** the shared static fallback asset SHALL NOT be treated as resolving that debt
