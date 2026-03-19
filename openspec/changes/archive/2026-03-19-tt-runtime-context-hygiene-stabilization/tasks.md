## 1. Runtime Hot Path Audit

- [x] 1.1 Identify every ordinary live-turn callsite that currently triggers module detection or integration.
- [x] 1.2 Identify all derived location-memory producers and consumers in narrator payload assembly and reconciliation flows.
- [x] 1.3 Capture the Thornwood/Gorvek failure shape as transcript-based regression input before refactoring.

## 2. Module Integration Quarantine

- [x] 2.1 Remove or gate module auto-integration from ordinary live-turn processing paths.
- [x] 2.2 Add failed-integration quarantine or debounce behavior so a rejected module does not retry every turn.
- [x] 2.3 Ensure failed module integration output is recorded in diagnostics without entering live narrator context.

## 3. Provenance Guards for Derived Location Memory

- [x] 3.1 Add explicit provenance metadata to derived location summary and chronicle emitters.
- [x] 3.2 Add helper logic that rejects derived location-memory blocks whose provenance does not match the active module and current location.
- [x] 3.3 Apply the provenance filter to live narrator payload assembly while preserving recent raw turns.

## 4. Reconciler History Hygiene

- [x] 4.1 Narrow location reconciler evidence assembly to same-location authoritative evidence only.
- [x] 4.2 Ensure mismatched or unprovenanced derived summaries do not influence hostile-state reconciliation.
- [x] 4.3 Fail safe by preserving current hostile state when same-location evidence is insufficient.

## 5. Regression Coverage

- [x] 5.1 Add a Thornwood/Gorvek continuity regression proving no false second arrival/parley at Bandit Stronghold after prior parley and departure.
- [x] 5.2 Add a regression proving `TW05` reconciliation ignores `TW02`-derived summary contamination.
- [x] 5.3 Add a regression proving failed Keep_of_Doom integration does not retry or pollute ordinary live-turn narrator context.

## 6. Verification

- [x] 6.1 Run `python3 -m py_compile` on all touched Python files.
- [x] 6.2 Run targeted transcript-based stabilization regressions.
- [x] 6.3 Re-run existing narrator hygiene, validation routing, and reconciliation-related suites affected by the change.
- [x] 6.4 Run `openspec validate tt-runtime-context-hygiene-stabilization` and confirm the change is apply-ready.
