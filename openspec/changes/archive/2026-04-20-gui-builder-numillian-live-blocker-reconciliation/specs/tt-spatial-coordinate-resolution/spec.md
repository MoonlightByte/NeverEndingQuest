## ADDED Requirements

### Requirement: Spatial remediation SHALL synchronize paired map artifacts after area repair

When deterministic spatial repair changes an area room coordinate graph and the paired `map_*.json` file is directly mappable by room id, remediation SHALL synchronize the paired map artifact before classifying residual contradictions as debt.

#### Scenario: Area repair leaves stale map coordinates

- **WHEN** an area file has been repaired to cardinal adjacency
- **AND** the paired `map_*.json` file still contains the old non-cardinal coordinates for the same room ids
- **THEN** deterministic remediation SHALL synchronize the paired map coordinates and dependent direction data when that mapping is unambiguous
- **AND** only unchanged contradictions after parity sync attempt may escalate to residual structural debt
