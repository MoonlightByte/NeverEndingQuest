## Builder Prompt

Implement `tt-authoritative-transition-inventory-runtime-reset` as an authority-reset and fail-closed runtime hardening pass.

### MUST

- Restore deterministic Python authority for same-module `transitionLocation` validation and execution.
- Ensure failed transitions do not generate arrival narration, seamless stitched prose, or rewritten conversation history.
- Treat the LLM-based seamless transition post-processor in `main.py` as disabled/dormant in the active runtime flow.
- Restore deterministic Python authority for tracked item possession and explicit party-to-party tracked-item transfers.
- Ensure possession contradiction turns cannot bypass authoritative checks through `narration_only` skip routing.
- Fix multi-PC inventory grounding so inventory context uses the active character rather than `partyMembers[0]` fallback behavior.
- Add focused regression locks for `NIG04 -> NIG05`, failed transition history hygiene, reliquary possession queries, atomic transfer behavior, and active-character inventory context.
- Keep all host-file edits ASCII-only and mark required host changes with `# TABLETOP MODE:` comments.

### SHOULD

- Prefer a small authoritative helper/service boundary over widening ad hoc recovery patches.
- Keep graph/pathfinding support for broader travel cases, but simplify same-module local movement to fresh topology reads.
- Limit initial transactional inventory enforcement to tracked/key items if that reduces rollout risk during gametest stabilization.

### Suggested touchpoints

- `main.py`
- `core/ai/action_handler.py`
- `core/ai/inventory_context_integration.py`
- `utils/location_path_finder.py`
- a new authoritative transition helper/service if warranted
- tracked inventory runtime helper path(s)
- `AGENTS.md`
- targeted regression suites under `scripts/`

### Verification commands

```bash
python3 -m py_compile main.py core/ai/action_handler.py core/ai/inventory_context_integration.py utils/location_path_finder.py <new_or_changed_runtime_helpers> <changed_test_files>
python3 <new_or_changed_transition_test_file>
python3 <new_or_changed_inventory_authority_test_file>
python3 scripts/test_scene_location_sync.py
python3 scripts/test_validation_skip_routing.py
python3 scripts/test_validation_routing_telemetry.py
openspec validate tt-authoritative-transition-inventory-runtime-reset
```

### Acceptance bar

- Same-module move `NIG04 -> NIG05` validates from authoritative fresh topology and no longer fails because of stale runtime graph state.
- Rejected transitions do not create cinematic arrival narration or rewrite history as if the move succeeded.
- Tracked-item possession questions resolve from committed Python state rather than narration drift.
- Explicit tracked-item transfers persist atomically or fail atomically.
- Multi-PC inventory context follows the active character.
- Repository guidance clearly states the seamless transition post-processor is disabled/dormant so it does not become silent dead code.