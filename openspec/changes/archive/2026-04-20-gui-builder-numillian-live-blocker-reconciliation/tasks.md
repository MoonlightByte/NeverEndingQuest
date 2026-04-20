1. Monster Authority Reconciliation
- [x] 1.1 Reconcile validator-visible structured monster references with authority-layer NPC filtering.
- [x] 1.2 Add regression coverage proving a structured monster slug is still repair-targetable even when it also appears in NPC catalogs.

2. Monster Schema Canonical Recovery
- [x] 2.1 Add bounded canonical recovery for monster schema completion (for example singular/plural recovery).
- [x] 2.2 Preserve fail-closed behavior when canonical recovery is ambiguous or unavailable.
- [x] 2.3 Add regression coverage for canonical recovery and irreducible classification.

3. Plot Edge Repair Targeting
- [x] 3.1 Make deterministic plot prerequisite repair target the validator-identified failing conclusion edge.
- [x] 3.2 Add regression coverage for non-terminal conclusion/finale repair.

4. Area/Map Spatial Parity Reconciliation
- [x] 4.1 Add deterministic synchronization from repaired area coordinates into paired `map_*.json` artifacts when room-id parity is unambiguous.
- [x] 4.2 Recompute or normalize paired map directions when required by synchronized coordinates.
- [x] 4.3 Add regression coverage for stale-map parity repair and unchanged-contradiction debt escalation.

5. Canary And Reporting
- [x] 5.1 Re-run `The_Hidden_City_of_Numillian` as the live blocker reconciliation canary.
- [x] 5.2 Persist a new reconciliation canary artifact showing whether validator failures materially advanced.
- [x] 5.3 Classify remaining Numillian failures into repair-engine mismatch vs author/content debt.

6. Verification
- [x] 6.1 Run targeted compile and regression checks for the changed reconciliation paths.
- [x] 6.2 Validate the OpenSpec change and confirm artifact alignment.
