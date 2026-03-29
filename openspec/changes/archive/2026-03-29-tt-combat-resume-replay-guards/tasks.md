## 1. Resume Summary Guard

- [x] 1.1 Unify resumed combat summary handoff in `main.py` with the historical-record wrapper used by the normal combat-complete path.
- [x] 1.2 Add a targeted regression covering resumed combat summary history so XP/reward actions are not regenerated from historical combat text.

## 2. Enemy Replay Idempotency

- [x] 2.1 Add a deterministic replay guard in encounter update handling so resumed enemy HP/status updates are skipped when authoritative encounter state already matches the summarized final state.
- [x] 2.2 Ensure combat auto-exit only triggers after replay-guarded encounter state still shows all enemies defeated.

## 3. Verification

- [x] 3.1 Add or update targeted regression tests for resumed duplicate enemy damage, positive-HP enemy no false auto-exit, and normal non-resume compatibility.
- [x] 3.2 Run the targeted regression commands and any required compile checks, then record the results in the final report.
