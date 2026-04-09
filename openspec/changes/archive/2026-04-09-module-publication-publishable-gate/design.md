## Context

The publication plan's last missing piece is the actual gate:

- readiness already checks gameplay, sidecar, schema, and continuity
- semantic audit now classifies publication blockers
- live-play probes now provide deterministic proof of authored interaction semantics

But the repo still lacks one canonical surface that says both:

- `ready`: the module passes structural/gameplay/readiness requirements
- `publishable`: the module is also semantically safe for release

That distinction matters because current and legacy modules may be structurally valid while still failing the stricter publication semantics. The final slice should preserve readiness compatibility while exposing the stricter release decision explicitly.

## Goals / Non-Goals

**Goals:**
- Add a distinct publishability audit layered over readiness.
- Reuse existing semantic publication audit and probe harness outputs.
- Expose `ready` vs `publishable` clearly in CLI and toolkit reporting.
- Allow legacy modules to fail publishability without redefining readiness.

**Non-Goals:**
- Fixing all existing modules to become publishable.
- Reworking semantic-authority/probe logic beyond narrow integration needs.
- Altering runtime game behavior.

## Decisions

### Decision: Publishability MUST layer on top of readiness, not replace it
- Rationale: structural readiness and semantic publishability are distinct concepts.
- Approach: keep readiness semantics intact and compute publishability as `ready && semantic_audit && semantic_probes`.
- Alternative considered: replace readiness with publishability everywhere.
- Rejected because it would erase a useful intermediate state and break existing expectations.

### Decision: A standalone publishability CLI SHOULD be the canonical release-facing gate
- Rationale: the repo needs one stable entrypoint for release decisions.
- Approach: add a standalone publishability audit script that calls or composes the existing readiness audit, semantic audit, and probe harness.
- Alternative considered: overload `audit_module_readiness.py` as both readiness and publishability gate.
- Rejected because it would blur the distinction the final phase is trying to create.

### Decision: Toolkit reporting MUST show both statuses explicitly
- Rationale: toolkit-generated modules should surface whether they are merely structurally ready or actually publishable.
- Approach: extend toolkit finisher output/report with `ready_status` and `publishable_status` fields.
- Alternative considered: keep publishability hidden in raw nested stage data.
- Rejected because that would not satisfy the plan's reporting goal.

### Decision: Publishability exit code MUST follow publishability, not readiness
- Rationale: the final gate is release-facing.
- Approach: standalone publishability audit returns success only when the module is publishable.
- Alternative considered: return success when ready but not publishable.
- Rejected because that would weaken the final gate.

## Proposed Surface

Representative publishability output:

```json
{
  "module": "Night_of_the_Restless_Dead",
  "ready_status": "pass",
  "publishable_status": "fail",
  "readiness": { ... },
  "publication_gates": {
    "semantic_audit": { "status": "fail" },
    "semantic_probes": { "status": "fail" }
  },
  "blocking_errors": [...],
  "fix_list": [...],
  "exit_code": 1
}
```

## Risks / Trade-offs

- [Legacy modules all fail publishability immediately] -> Mitigation: preserve readiness separately and keep the failure informative, not ambiguous.
- [Reporting drift between CLI and toolkit] -> Mitigation: reuse one standalone publishability audit surface and mirror its statuses in toolkit reporting.
- [Too much duplication of existing readiness output] -> Mitigation: wrap or embed existing readiness data rather than reimplementing it.

## Migration Plan

1. Add standalone publishability audit surface.
2. Reuse readiness + semantic audit + semantic probe outputs.
3. Extend toolkit finisher report to show `ready` vs `publishable`.
4. Add focused regression coverage for layered status behavior.
5. Validate on real modules, then archive the full publication plan.

## Open Questions

- Should bulk validation eventually default to publishability after this phase, or remain a separate readiness-oriented bulk view?
- Is a dedicated `publishable` field enough for toolkit consumers, or should stage labels also be added in the module toolkit UI later?
