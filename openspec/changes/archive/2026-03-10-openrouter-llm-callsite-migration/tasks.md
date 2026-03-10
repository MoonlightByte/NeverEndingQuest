## 1. Inventory and tier planning

- [ ] 1.1 Build a complete list of remaining direct/hardcoded LLM callsites and classify each as high, medium, or low risk with file targets.
- [ ] 1.2 Define per-tier migration batches and explicit acceptance checks (syntax compile, runtime smoke, fallback behavior) before implementation starts.

## 2. High-risk callsite migration

- [ ] 2.1 Migrate high-risk combat and core narration callsites to shared provider-aware routing/factory utilities without changing prompt contracts.
- [ ] 2.2 Preserve and/or standardize timeout and retry settings for migrated high-risk callsites using shared configuration utilities.
- [ ] 2.3 Add or update fallback-path logging so provider switch events include callsite role/context.
- [ ] 2.4 Verify high-risk tier with targeted smoke flows and syntax checks; document results inline in the change notes.

## 3. Medium and low-risk migration

- [ ] 3.1 Migrate medium-risk validation/summarization/update callsites to shared routing/factory usage.
- [ ] 3.2 Migrate low-risk residual callsites and remove redundant local client/model wiring that duplicates shared behavior.
- [ ] 3.3 Verify medium/low tiers with focused execution checks and confirm no regression in single-player runtime behavior.

## 4. Compatibility and safety hardening

- [ ] 4.1 Ensure any unavoidable host-file edits are minimal and marked with `# TABLETOP MODE:` for merge safety.
- [ ] 4.2 Confirm multiplayer deterministic mechanics are unaffected by routing changes (state truth-source and turn-flow invariants unchanged).
- [ ] 4.3 Validate non-retryable provider errors fail loudly with structured logs and no silent fallback.

## 5. Final validation and handoff

- [ ] 5.1 Run final repository syntax checks for all touched Python modules and fix migration fallout.
- [ ] 5.2 Produce a concise migration completion report listing migrated callsites, fallback coverage, and any deferred follow-ups.
- [ ] 5.3 Confirm OpenSpec artifacts are apply-ready and consistent across proposal, design, specs, and tasks.
