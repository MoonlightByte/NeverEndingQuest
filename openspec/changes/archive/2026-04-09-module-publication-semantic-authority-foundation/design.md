## Context

The repository already has several prerequisites that publication work can now build on:

- continuity normalization and readiness infrastructure
- shared builder/ingest finishing parity
- spatial contract shape and tactical-grid generation
- authored-adjacency extraction and strict spatial coherence for new outputs

What is still missing is a reusable semantic-authority layer for publication-oriented gameplay semantics. Today destination phrases, room nicknames, and revealable NPC authority are still scattered across authored prose, hooks, and narrower runtime fixes. A later publication audit cannot be reliable until those semantics are gathered into one deterministic artifact.

## Goals / Non-Goals

**Goals:**
- Create one shared semantic-authority payload that later publication audits and probe harnesses can consume.
- Keep the authority extraction deterministic, bounded, and traceable back to authored module sources.
- Reuse the same enrichment contract across ingest and toolkit-finishing flows.
- Add an audit/report surface that can inspect the payload without yet becoming the repo-level `publishable` gate.

**Non-Goals:**
- Implementing the full semantic publication blocker policy.
- Implementing synthetic travel/NPC gameplay probes.
- Wiring `ready` vs `publishable` into release decisions.
- Reworking runtime travel, NPC arrival, or combat authority behavior.

## Decisions

### Decision: The semantic-authority payload MUST be a shared artifact, not a runtime-only inference path
- Rationale: publication work needs something auditable and reproducible, not a chain of heuristics buried in runtime fixes.
- Approach: introduce a shared helper that reads authored module files and emits a deterministic payload containing location aliases, destination phrases, NPC scene-authority records, and ambiguity metadata.
- Alternative considered: derive these maps ad hoc inside later readiness or runtime code.
- Rejected because it would keep publication semantics fragmented and hard to verify.

### Decision: Extraction SHOULD remain deterministic and provenance-carrying
- Rationale: publication audit failures must tell the operator exactly which authored source produced a phrase or authority record.
- Approach: each destination phrase or NPC authority record should carry source references such as file path, room id, hook section, or authored field name.
- Alternative considered: store only normalized alias -> target mappings.
- Rejected because it would make publication debugging too opaque.

### Decision: Weak or ambiguous prose MUST fail open during enrichment and fail closed only in the dedicated audit surface
- Rationale: this change is the substrate layer. It should not block ingest/toolkit finishing merely because the source is incomplete.
- Approach: enrichment records ambiguity and missing-authority diagnostics; later publication-audit changes can promote those findings into blockers.
- Alternative considered: hard-fail ingest immediately when ambiguity is detected.
- Rejected because that would conflate substrate creation with the later gate policy.

### Decision: Ingest and toolkit finishing MUST converge on the same enrichment helper and persisted contract
- Rationale: publication semantics cannot drift between import and toolkit-generated modules.
- Approach: the shared helper should be callable from both `scripts/homebrew_ingest_dev.py` and `web/extensions/toolkit_module_finisher.py`, with matching report fields.
- Alternative considered: implement parallel enrichment logic in each flow.
- Rejected because it would recreate parity drift.

## Proposed Artifact Shape

The semantic-authority payload should stay additive and auditable. A representative shape is:

```json
{
  "semantic_authority": {
    "version": 1,
    "location_aliases": {
      "priest's lodging": {
        "location_id": "NIG04",
        "sources": ["areas/NIG001.json#locations[NIG04].aliases"]
      }
    },
    "destination_phrases": {
      "lintar's place": {
        "status": "ambiguous",
        "candidate_location_ids": ["NIG04"],
        "sources": ["module_plot.json#PP..."]
      }
    },
    "npc_scene_authority": {
      "Father Aldric": {
        "visible_location_ids": ["NIG04"],
        "reveal_bindings": [],
        "sources": ["areas/NIG001.json#..."]
      }
    },
    "diagnostics": {
      "ambiguous_destination_phrases": [],
      "missing_npc_authority": []
    }
  }
}
```

The exact field names may vary, but the contract MUST preserve:
- deterministic normalized keys
- canonical target ids
- source provenance
- ambiguity/missing-authority diagnostics

## Risks / Trade-offs

- [Extraction overfits prose and creates bad aliases] -> Mitigation: keep alias extraction bounded to authored names, explicit aliases, and clear destination phrases before adding broader heuristics.
- [Ingest and toolkit reports drift] -> Mitigation: use one shared helper and one normalized result contract.
- [Operators mistake this change for full publication safety] -> Mitigation: all report surfaces and docs must explicitly say the `publishable` gate and probe harness are still out of scope.
- [Existing modules lack enough structure for clean extraction] -> Mitigation: keep enrichment fail-open and record diagnostics that later audit/probe changes can promote into blockers.

## Migration Plan

1. Add a shared semantic-authority helper and deterministic normalization rules.
2. Add coverage for alias extraction, phrase ambiguity recording, and NPC authority extraction.
3. Integrate the helper into ingest and toolkit-finishing paths with persisted report payloads.
4. Add a dedicated audit/report CLI that validates uniqueness, traceability, and ambiguity classes without yet becoming the repo-wide `publishable` gate.
5. Validate on at least one real module with known publication-semantic gaps and update `plans/module-publication.md` to reflect the new substrate.

## Open Questions

- Should the canonical persisted payload live in `module_context.json`, a sidecar artifact, or both?
- Which authored sources are in-scope for destination phrase extraction in the first pass: location titles/aliases only, or plot and hook prose as well?
- How should revealable NPC bindings represent preconditions in the first version: explicit hook/source provenance only, or a structured reveal-condition contract?
