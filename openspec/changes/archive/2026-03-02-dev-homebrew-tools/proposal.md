# Developer Homebrew Ingest Tools - Proposal

## Problem Statement

Homebrew module ingestion currently works for clean, room-based markdown files. However, many community Homebrew sources use alternate formats (ACT/LOCATION structure) that fail strict deterministic validation and get quarantined.

Developers (not end-users) need a streamlined workflow to:
1. Assess Homebrew readiness
2. Transform non-conforming sources to ingestible format
3. Validate before registry write
4. Ingest with verification
5. Guard against duplicates

## Proposed Solution

Build 5 Python CLI tools that wrap the existing ingestion infrastructure:

1. **homebrew_preflight.py** - Readiness assessment
2. **homebrew_transform_to_deterministic.py** - Structural conversion  
3. **homebrew_ingest_dev.py** - Orchestrator
4. **homebrew_sidecar_audit.py** - Result validation
5. **homebrew_registry_guard.py** - Duplicate prevention

## Scope

**In Scope:**
- CLI tools for developer use
- JSON output for scripting
- Dry-run support
- Integration with existing importer/stitcher

**Out of Scope:**
- GUI/web interface (Toolkit already handles this)
- End-user features
- AI-based transformation (deterministic only)

## Success Criteria

- Developer can run single command to assess/transform/ingest/verify
- All tools have `--help` and return structured JSON
- Tools fail closed on any validation issue
- No breaking changes to existing ingestion flow

## Risks

- **Low:** Reuses existing infrastructure
- **Medium:** Transform accuracy for complex Homebrew structures
- **Mitigation:** Always require explicit confirmation before registry write
