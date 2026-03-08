## Execution Contract

- Complete tasks in order. Do not skip ahead.
- Keep changes additive and merge-safe; mark host-file edits with `# TABLETOP MODE:` comments.
- Preserve deterministic safety contracts unless a task explicitly narrows behavior.
- Do not commit or push.

## Prompt 1 - Input and Rule De-Duplication (Initial)

Implement Tasks 1.1-1.3 only.

### Scope

- `main.py`
- `core/ai/action_handler.py`

### Required Outcomes

1. Multi-PC path no longer appends the legacy common instruction tail in `main.py`.
2. Transition pre-validation consumes raw player utterance, not DM-note-augmented text.
3. Existing transition context (atlas/path/plot) remains intact.

### MUST Constraints

- MUST keep single-player behavior unchanged unless directly required for shared function signatures.
- MUST preserve existing transition blocking behavior (only input source changes).
- MUST avoid introducing Unicode in Python output paths.

### SHOULD Guidance

- SHOULD add a small helper/parameter to carry raw player intent clearly.
- SHOULD keep diffs surgical and localized.

### Verification Gate

- `python3 -m py_compile main.py core/ai/action_handler.py`
- Add or run focused regression checks proving transition validator receives raw intent text.

### Handoff

Return:
- files changed,
- concise rationale,
- verification outputs,
- any discovered risk for Prompt 2.

## Prompt 2 - Travel Fail-Soft NPC Arrival Guard

Implement Tasks 2.1-2.4 only.

## Prompt 3 - Retry De-Looping

Implement Tasks 3.1-3.3 only.

## Prompt 4 - Prompt Contract Slimdown + Tests

Implement Tasks 4.1-5.5.
