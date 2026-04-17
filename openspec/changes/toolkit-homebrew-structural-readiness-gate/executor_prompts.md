## Builder Prompt

Implement `toolkit-homebrew-structural-readiness-gate` from `plans/module-uploader.md` Phase 5A.

Guardrails:

1. Treat `build_completed` as raw builder success only.
2. Add a post-build readiness gate before any finisher/publication stage.
3. Reuse the canonical validator and readiness audit; do not invent an upload-only correctness model.
4. Run deterministic repair before semantic repair.
5. Fail closed on builder/runtime defects; do not paper over them with LLM repair.
6. Keep concept-builder flow unchanged.
7. Stop this change at `ready_for_finishing` or a bounded failure state.

Suggested implementation order:

1. Add job-state/reporting extensions.
2. Add readiness-gate orchestrator and persisted validation/readiness artifacts.
3. Add deterministic repair domains for the highest-confidence structural failures.
4. Add targeted semantic repair scaffolding only for remaining narrow domains.
5. Add toolkit UI progress/reporting.
6. Add regression coverage and validate the change.

Verification expectations:

1. Packet-built modules no longer jump straight from `build_completed` toward finisher/publication.
2. The uploader can distinguish builder defects from content defects.
3. A structurally repaired module reaches `ready_for_finishing`.
4. Non-converging or system-failure cases preserve artifacts and grouped fix guidance.
