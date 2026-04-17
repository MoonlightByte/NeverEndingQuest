## Context

The toolkit already supports two distinct module-creation paths:

1. concept-first upstream-style building through `ModuleBuilder`, and
2. markdown upload routed into the shared Homebrew ingest pipeline.

The second path currently assumes deterministic readiness too early. `scripts/homebrew_preflight.py` reports metadata and structure issues in a way that is appropriate for developer-oriented strict ingest, but inappropriate for the new public uploader roadmap in `plans/module-uploader.md`. Readable Homebrewery adventures are rejected before the system can preserve artifacts, classify rights/provenance, or hand off to later LLM normalization and human review stages.

This first uploader change is intentionally contract-first. It creates the stable routing, packet, and artifact substrate needed by later changes without yet implementing the LLM normalizer, the review UI, or build-from-packet execution.

## Goals / Non-Goals

**Goals:**
- Reclassify preflight as a routing decision surface, not parser authority.
- Define a canonical normalized packet contract for readable markdown sources that require later interpretation.
- Define a stable upload artifact workspace layout under `user_uploads/toolkit/homebrew_md/`.
- Extend toolkit upload/job reporting so early routing states are preserved alongside existing ingest outcomes.
- Preserve backward compatibility with the existing concept builder and deterministic-ready markdown ingest paths.

**Non-Goals:**
- Implementing the LLM normalization engine.
- Adding the human review UI or approve/reject workflow.
- Building modules from normalized packets.
- Merging this uploader lane with the source-anonymous world-narrative literary ingestion lane.
- Replacing the shared Homebrew ingest pipeline or watcher flows.

## Decisions

### Decision: Preflight MUST emit routing classes instead of collapsing readable ambiguity into failure
- Rationale: the uploader roadmap depends on a readable-but-ambiguous source being preserved for later normalization rather than rejected as unusable. The current strict preflight behavior is still valid for deterministic ingest, but it cannot remain the only interpretation path.
- Alternative considered: add more regex heuristics until most Homebrewery markdown passes deterministic preflight.
- Rejected because it keeps parser authority in the wrong layer and repeats the same failure mode whenever source shape changes.

### Decision: The first change MUST create a placeholder normalized packet contract even before the normalizer exists
- Rationale: later uploader changes need one stable artifact shape and file location. Defining the packet now prevents downstream changes from coupling directly to raw markdown or ad hoc JSON.
- Alternative considered: wait until the LLM normalizer is implemented before defining packet files.
- Rejected because it would force later phases to invent both behavior and contracts at the same time.

### Decision: Toolkit upload jobs MUST own a dedicated artifact workspace under `user_uploads/toolkit/homebrew_md/<job_id>/`
- Rationale: the uploader needs persistent source, preflight, packet, and later build artifacts for audit, retry, and rebuild. This also keeps uploader files isolated from watcher-owned `modules/ingest/` traces.
- Alternative considered: reuse watcher/archive folders or keep artifacts in memory only.
- Rejected because watcher folders imply different ownership and in-memory state would not support resume/debug workflows.

### Decision: Rights/provenance classification MUST be stored in the packet contract
- Rationale: the uploader plan now explicitly distinguishes `user_authored`, `licensed_or_project_owned`, and `third_party_copyright_restricted` sources. Storing this classification early keeps the module lane separate from the source-anonymous world-narrative lane.
- Alternative considered: leave provenance to later review/build changes.
- Rejected because later stages would then infer policy from file location or UI context, which is brittle and unauditable.

### Decision: Existing toolkit upload and job-reporting capabilities SHOULD be extended, not replaced
- Rationale: the current toolkit upload and reporting specs already define the user-facing upload surface. This change broadens those contracts so upload jobs can represent early routing states before strict ingest starts.
- Alternative considered: introduce a completely separate upload-normalization job API.
- Rejected because it would fragment the public toolkit flow and create another drift-prone reporting surface.

### Decision: This change MUST remain separate from world-narrative ingestion
- Rationale: `plans/version-2/world-narrative.md` is a source-anonymous literary ingestion lane for copyrighted novels under `/user_uploads/text/`. The uploader is a source-preserving reviewed module lane for approved adventure inputs. The plans intentionally share artifact discipline, not data policy.
- Alternative considered: define one generic source-ingestion contract for both lanes now.
- Rejected because the copyright model, commitability rules, and downstream consumers are materially different.

## Risks / Trade-offs

- [Readable uploads stop at a placeholder state and users expect a full build immediately] -> Mitigation: toolkit job reporting MUST make the routing outcome explicit and avoid generic failure wording.
- [Contract-first work adds files without immediate end-user payoff] -> Mitigation: keep the first slice small and make it the blocker-clearing substrate for the next LLM normalizer change.
- [Existing strict ingest tooling drifts from uploader routing semantics] -> Mitigation: keep preflight as the single shared classification entrypoint and add explicit routing fields rather than toolkit-only interpretation.
- [Rights classification is misapplied or ignored later] -> Mitigation: store classification inside the packet and require later uploader/build changes to consume that field explicitly.
- [World-narrative and uploader lanes drift back together] -> Mitigation: document lane separation in plan files and avoid direct code reuse that would leak source-preserving adventure data into source-anonymous narrative storage.

## Migration Plan

1. Add the normalized packet and artifact workspace contracts without changing concept-builder behavior.
2. Update preflight JSON/classification behavior so readable ambiguous markdown routes to normalization-required outcomes.
3. Extend toolkit upload job reporting to represent early routing states and workspace-backed job metadata.
4. Add regression tests for routing classification, packet/workspace creation, and toolkit job-state preservation.
5. Roll forward into the next change that implements the LLM normalizer against the packet contract.

Rollback strategy:

1. Remove packet/workspace contract usage from toolkit upload routes.
2. Revert preflight routing changes to the prior deterministic-only readiness behavior.
3. Leave existing concept builder and watcher/CLI ingest paths untouched.

## Open Questions

- Should the packet contract be enforced through a JSON schema file under `schemas/` or a Python contract helper plus regression tests in the first implementation slice?
- Should deterministic-ready uploads also write a placeholder normalized packet for parity, or only the normalization-required path in this first change?
- Should early routing states use `normalization_required` directly, or a more generic `awaiting_normalization` name that anticipates later async normalizer execution?
