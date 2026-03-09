# ADR-0026: Capability-Based LLM Router Facade (`llm.call`)

- Date: 2026-03-10
- Status: Planned
- Supersedes: ADR-0025 (upon acceptance)
- Superseded by: None

## Context
LLM behavior is currently spread over many task-specific call sites with mixed models and parameters.

## Decision
Introduce a central router facade (`llm.call`) that maps capabilities and roles to provider/model/temperature/structured-output contracts.

## Consequences
- Fewer per-callsite inconsistencies.
- Better observability and governance for cost/latency/quality.
- Migration work remains substantial and must preserve existing gameplay contracts.

## Sources
- `plans/version-2/openrouter_llm_router_architecture.md`
- `AGENTS.md`
- `openspec/changes/openrouter-llm-router-facade/`
