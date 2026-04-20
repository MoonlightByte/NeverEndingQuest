# module-publishability-reporting Specification Delta

## ADDED Requirements

### Requirement: Readiness and publishability reporting SHALL consume normalized gameplay findings
When gameplay audit output provides structured findings under a nested payload shape, readiness and publishability reporting SHALL consume those findings accurately so structural media debt summaries remain correct.

#### Scenario: Nested gameplay findings produce correct toolkit media policy summary
- **GIVEN** gameplay audit output includes structured monster-media findings under a nested `target` object
- **WHEN** readiness reporting computes toolkit media policy summary fields
- **THEN** `structural_media_debt_count` and related slug lists SHALL reflect the actual structured findings
- **AND** SHALL NOT incorrectly report zero when structural findings are present

#### Scenario: Publishability receives corrected readiness media debt metadata
- **GIVEN** readiness reporting has normalized gameplay findings correctly
- **WHEN** publishability output is emitted
- **THEN** the publishability payload SHALL preserve the corrected toolkit media policy metadata
- **AND** SHALL remain consistent with the gameplay findings that produced it
