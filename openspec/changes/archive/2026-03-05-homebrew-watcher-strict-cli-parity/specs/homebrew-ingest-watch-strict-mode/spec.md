## ADDED Requirements

### Requirement: Strict Ingest-Ready Gate For Watcher

The ingest watcher MUST accept only ingest-ready markdown files and MUST reject/quarantine non-ready files without attempting ingest.

#### Scenario: Ready markdown passes gate
- WHEN a file in `modules/ingest/` is preflight-ready (`ready=true`) with deterministic ingest structure and required metadata
- THEN the watcher proceeds to ingest pipeline execution
- AND the archived sidecar records that strict gate passed.

#### Scenario: Non-ready markdown is quarantined
- WHEN a file in `modules/ingest/` fails readiness checks (unknown structure, missing metadata, or title hygiene failure)
- THEN the watcher MUST NOT run ingest
- AND MUST archive/quarantine the source with explicit rejection reason
- AND MUST write a `.result.json` sidecar containing a strict rejection status and reason code.

#### Scenario: No auto-transform in strict mode
- WHEN strict watcher mode is active
- THEN watcher MUST NOT auto-transform source markdown
- AND MUST instruct operators to prepare/validate markdown through the dev skill workflow first.
