# Executor Prompts: narrative-sovereignty-state-packet-foundation

## Execution Contract

MUST:
- Implement this change as a narrow gametest foundation slice, not a full architecture rewrite.
- Preserve the current JSON/action schema surface.
- Keep packet v1 limited to location/module truth, party roster, party NPC roster, and reachable topology-adjacent context.
- Keep host-file edits additive and mark required host hooks with `# TABLETOP MODE:` comments.
- Keep Python output ASCII-only.
- Use anchored, micro-edits in `main.py` and any large Python file.
- Run `python3 -m py_compile <changed_python_file>` after each touched Python file.
- Stop and report if implementation pressure expands into full world-delta reconciliation, event ledger scope, prompt-stack redesign, or broad validator rewrite.

SHOULD:
- Prefer additive helpers over moving large blocks in `main.py`.
- Keep packet consumers limited to touched DM Note and touched narrator validation assembly paths.
- Preserve existing APIs and explicit action behavior where practical.
- Keep tests focused on packet truth, parity, and no-regression behavior.

## Prompt 1 - Contract and Parity Coverage First (Tasks 1.1-1.3)

Implement focused regression/source-contract coverage before changing runtime behavior.

Scope:
- Add tests for:
  1. packet builder exposes the intended v1 fields
  2. touched DM Note consumers and touched validation assembly read overlapping truths from the same packet surface
  3. explicit action-schema turns still behave normally when packet construction is present
- Prefer small deterministic fixtures or source-contract tests over broad end-to-end setup.
- Keep coverage scoped to the packet-enabled domains only.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification gate before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run the new tests and confirm failures reflect missing packet behavior, not broken fixtures.

## Prompt 2 - Packet Helper Foundation (Task 2.1)

Create the narrow packet helper without broad runtime changes.

Scope:
- Add `utils/authoritative_state_packet.py`.
- Build a narrow packet for:
  - current module/area/location truth
  - current party roster
  - current party NPC roster
  - reachable topology context needed by touched consumers
- Keep packet shape simple and machine-readable.
- Avoid expanding into full combat/resource packet work.

Constraints:
- Do not replace the current action protocol.
- Do not introduce Titans/event-ledger semantics.
- Do not build a broad caching or orchestration layer unless absolutely necessary for this narrow slice.

Verification gate before continuing:
- `python3 -m py_compile utils/authoritative_state_packet.py`
- Run the packet-shape tests.

## Prompt 3 - Runtime Wiring in `main.py` (Tasks 2.2 and 2.4)

Wire packet construction into the touched narrator runtime and validation handoff paths.

Scope:
- Build the packet in the touched narrator runtime path in `main.py`.
- Use additive `# TABLETOP MODE:` hooks.
- Ensure packet-enabled overlapping truths in touched validation assembly come from the packet.
- Keep legacy context available for non-packet-enabled domains during migration.

Constraints:
- Do not attempt a broad rewrite of every validation context source.
- Do not alter unrelated gameplay flow.
- Do not remove legacy context unless the packet fully replaces the overlapping truth safely in the touched path.

Likely files:
- `main.py`
- `utils/authoritative_state_packet.py`

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification gate before continuing:
- `python3 -m py_compile main.py utils/authoritative_state_packet.py`
- Run packet and touched validation parity tests.

## Prompt 4 - DM Note Packet Parity (Task 2.3)

Update touched DM Note assembly to consume packet truth for overlapping fields.

Scope:
- Update only the touched DM Note rendering paths in `utils/multi_pc_dm_note.py`.
- Use packet values for overlapping location/party/party-NPC truths.
- Preserve non-targeted DM Note behavior in this slice.

Constraints:
- Do not refactor the entire DM Note system.
- Do not change unrelated combat/resource presentation unless required for overlapping packet truth.
- Preserve current compatibility for non-travel/non-NPC turns.

Verification gate before continuing:
- `python3 -m py_compile utils/multi_pc_dm_note.py`
- Run packet parity tests and any touched DM Note regressions.

## Prompt 5 - Final Verification and Builder Report (Tasks 3.1-3.4)

Run final checks and return a concise implementation report.

Required checks:
- `python3 -m py_compile main.py utils/multi_pc_dm_note.py utils/authoritative_state_packet.py <changed_test_files>`
- Run the targeted packet/parity regression tests
- Run the existing narrator/validation tests affected by the touched path
- `openspec validate narrative-sovereignty-state-packet-foundation`

Report format:
- Files changed
- Commands run
- PASS/FAIL per verification gate
- Packet fields implemented in v1
- Any remaining legacy-context dependency kept intentionally for later staged work
- Any follow-up concern for `travel-reconcile-first-autocommit`
