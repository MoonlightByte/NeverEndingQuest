# Builder Prompts - tt-narrator-arrival-deadlock-fix

## GPT-5.3 Codex Execution Prompt

Implement OpenSpec change `tt-narrator-arrival-deadlock-fix` end-to-end.

MUST:
- Fix narrator retry deadlock caused by arrival-sync validation + `moveBackgroundNPC` name normalization mismatch.
- Ensure outbound narrator payload contains exactly one canonical main system prompt.
- Keep retry correction notes transient (not persisted to history).
- Preserve fail-closed behavior for true explicit-arrival violations and ambiguous state mutations.
- Preserve single-player compatibility and TABLETOP MODE merge-safety markers.

SHOULD:
- Keep edits minimal and semantic-only for prompt files.
- Add deterministic logs for prompt dedupe and resolver path.

Primary files:
- `main.py`
- `utils/npc_arrival_validator.py`
- prompt files under `prompts/system_prompt*` and `prompts/validation/validation_prompt*`
- tests under `scripts/test_*` narrator/arrival suites

Execution sequence:
1. Add failing regression assertions first.
2. Implement prompt singularity guard in runtime assembly.
3. Align arrival validation to explicit-arrival semantics.
4. Split `moveBackgroundNPC` normalization to module-canonical scope.
5. Harden retry correction guidance text to avoid impossible loops.
6. Run compile + regression suite + `openspec validate tt-narrator-arrival-deadlock-fix`.

Required verification commands:
```bash
python3 -m py_compile main.py utils/npc_arrival_validator.py core/ai/action_handler.py
python3 scripts/test_npc_arrival_state_sync.py
python3 scripts/test_npc_arrival_party_exemption.py
python3 scripts/test_retry_de_looping.py
python3 scripts/test_narrator_prompt_validation_refactor.py
python3 scripts/test_validation_payload_hygiene.py
openspec validate tt-narrator-arrival-deadlock-fix
```

Deliverable summary format:
- Files changed
- Behavior changes (before -> after)
- Test results
- Any deferred follow-ups
