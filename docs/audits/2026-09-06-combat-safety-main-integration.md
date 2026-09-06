# Combat safety and main integration - 2026-09-06

Owner authorized main integration and explicitly selected the safety empty-response
policy after reviewing its conflict with #284. First integration commit: 4c10b8d8,
combining safety aab1200 with main 3df32fa5. Main subsequently advanced to d11b348a
(Ember); the final integration includes that update without replacing its UI.

## Resolution

- Preserve #284 transport recovery, changing status, deterministic-error handling,
  and usable turn-loop cleanup; empty responses in the shared non-wizard required
  path do not terminate at six. Genuine cancellation still wins. This is not a
  bounded-latency/cost guarantee or removal of caller-specific ratified policies.
- Preserve both authority_check and startup retry_message_repair callbacks,
  envelope correlation checks and diagnostic generation logging.
- Preserve startup interview/selection changes and safety restore handling.
  An absent startup transcript is included in both cleanup and verification.
- Preserve Ember confirmations and recovery guards. Delete is disabled during
  recovery and rechecks recovery state on confirmation; Load remains available.

## Validation

| Check | Result |
| --- | --- |
| Native Windows compilation of resolved backend files | PASS |
| Native pytest frontend-launch/provider-settings suite | 14 PASS, including rerun after Ember integration |
| Retry arithmetic/required-call inventory and cancellation/restore source contracts | PASS; source-level only |
| Mocked provider-loop negative controls | PASS: seven empty replies then useful eighth; cancellation after seven; deterministic error immediate; HTTP recovery; identity stable and reap before reissue |
| TypeScript and production Vite build after Ember integration | PASS |
| Full frontend unit suite | 344 PASS, 2 outdated expectation failures; not an all-green suite |
| Recovery/delete confirmation integration checks | PASS |
| Real OpenAI native Windows Load | PASS: 37 files, selected_applied, clean restart to retained round-7 damage request |
| Real OpenAI resumed combat completion and post-combat T082 Quit | PASS: completion closed, 100 XP once, Quit 0.175 seconds after accepted_deferred, no late narration or prompt |
| Cancellation persisted-state comparison | PASS: all 15 pre-control snapshot files unchanged after exit |
| Clean subsequent restart | PASS: HP 13/16, XP 400, no active combat, ordinary prompt and clean Quit |

The live run exercised the resumed-combat handoff (_main_game_loop ->
get_ai_response -> predict_actions_required), not the separate non-resumed
process_ai_response handoff. The latter was live-validated on aab1200 earlier.
Ember added no changes to main.py, live_provider_call.py, the headless session or
save manager relative to 4c10b8d8; these live witnesses therefore cover the final
unchanged backend paths. This is not a new full browser campaign acceptance.

Two HeaderBar.test.tsx assertions (lines 43 and 57) still demand enabled Start
while disconnected. Safety already disabled that control before either merge;
the click handler also refuses offline dispatch. These are recorded as stale
expectations, not silently skipped or repaired by weakening the product guard.
Tracked tests were left unchanged under the existing local-test instruction.

## Local evidence (intentionally untracked)

Under the combat-persistence-safety worktree validation_evidence directory:

- safety_combined_merge_live.jsonl: Load result seq 18, clean restart seq 20.
- safety_combined_merge_combat.jsonl: combat narration seq 8; observed native
  stack and committed receipt; Quit acceptance seq 13, exit seq 16; relay exit 0.
- safety_combined_merge_restart.jsonl: state seq 11, HP/XP/combat; clean Quit.
- safety_merge_empty_policy_checks.py: executable mocked loop negative controls.
- safety_transport_checks.py and safety_*source_checks.py: focused contracts.
- safety_p3_owner_final_verdict.md: earlier non-resumed handoff witness.
- web/frontend/validation_evidence/merge-recovery.test.tsx: component controls.

The state hash comparison initially encountered Windows path separators under
WSL; normalizing separators made all 15 comparisons pass. No game data was edited.
The first final-UI compile caught a mistaken state-property spelling introduced
during conflict resolution; it was corrected before the successful build.
CRLF-aware git diff checking passes; no broad line-ending rewrite was performed.
