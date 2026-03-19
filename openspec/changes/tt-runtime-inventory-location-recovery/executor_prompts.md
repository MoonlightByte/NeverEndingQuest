## Builder Prompt

Implement `tt-runtime-inventory-location-recovery` as a narrow runtime hardening pass.

### MUST

- Add deterministic runtime recovery for explicit party-to-party item transfers when the model emits a one-sided or missing action bundle.
- Add deterministic recovery for later receiver-side self-stow/item-handling turns when recent transcript evidence uniquely proves the receiver now owns the item.
- Add startup/history scene-location recovery so stale `party_tracker` location can be repaired from recent transcript evidence before UI/history rebuild.
- Ensure narration-only validator skip happens only after deterministic recovery opportunities have been evaluated.
- Preserve explicit action precedence and fail open on ambiguity.
- Add transcript-driven regressions for the reliquary handoff, receiver self-stow, and Priest's Lodging startup drift.

### SHOULD

- Keep all matching logic conservative and deterministic.
- Reuse existing reconciliation helpers where practical rather than creating a second broad parser stack.
- Keep host-file changes additive and marked with `# TABLETOP MODE:` comments.

### Suggested touchpoints

- `main.py`
- `utils/travel_state_sync_guard.py`
- existing scene-item reconciliation helper path or a new adjacent runtime helper
- startup/history refresh path in `main.py` and/or `utils/startup_wizard.py`
- targeted regression suites under `scripts/`

### Verification commands

```bash
python3 -m py_compile main.py utils/travel_state_sync_guard.py <new_or_changed_runtime_helpers> <changed_test_files>
python3 <new_or_changed_transfer_test_file>
python3 <new_or_changed_location_recovery_test_file>
python3 scripts/test_scene_location_sync.py
python3 <validation routing related test file>
openspec validate tt-runtime-inventory-location-recovery
```

### Acceptance bar

- Reliquary handoff recovers canonical ownership even if the model emits only receiver add or no action.
- Later `place the relic in my pack` turn can safely recover missing ownership when the transfer chain is unique.
- Startup no longer rehydrates `NIG01` when recent transcript evidence uniquely places the party in `NIG04 Priest's Lodging`.
- GUI/top bar/history rebuild all agree on the recovered canonical location.
- Ambiguous transfer/location evidence does not mutate canonical state.
