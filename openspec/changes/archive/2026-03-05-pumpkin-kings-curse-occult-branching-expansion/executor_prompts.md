## Kimi Builder Execution Prompts - pumpkin-kings-curse-occult-branching-expansion

Use this file for implementation-phase execution after plan approval.

---

## Execution Contract

- MUST keep edits additive in module JSON.
- MUST preserve existing PP001-PP007 progression and area IDs.
- MUST keep tone restrained (August Underground influence, implication-first).
- MUST keep all puzzle/skill gate DCs between 12 and 18.
- MUST preserve LLM DM JSON contract compatibility.
- SHOULD apply micro-edits in small batches and validate after each batch.

Edit Strategy: Apply one anchored patch at a time, then re-run validation before the next patch.

---

## Prompt A - Occult Setup and Origin Evidence

Implement the additive occult setup pass.

Scope:
- `modules/The_Pumpkin_Kings_Curse/areas/HFG001.json`
- `modules/The_Pumpkin_Kings_Curse/areas/VO001.json`
- `modules/The_Pumpkin_Kings_Curse/module_context.json`

Required:
- Add subtle omen cues in HFG001 without replacing existing quest hooks.
- Add origin evidence nodes/artifacts in VO001.
- Fill sparse context entries for major figures where needed to support branch clues.

Forbidden:
- No key removals/renames.
- No removal of existing encounters.

Accept when:
- Added content is present and coherent.
- Existing flow still functions unchanged.

Verify:
- `python core/validation/validate_module_files.py`

---

## Prompt B - Mid-Arc Clue Graph and Ritual Logic

Implement clue-distribution and reasoning gates.

Scope:
- `modules/The_Pumpkin_Kings_Curse/areas/CMS001.json`
- `modules/The_Pumpkin_Kings_Curse/areas/BOO001.json`

Required:
- Add failed-intervention evidence and child-loss clue thread in CMS001.
- Add ritual and contract-interpretation clues in BOO001.
- Ensure each major truth has at least two clue sources.
- Keep all DCs in [12, 18].

Forbidden:
- No explicit gore escalation.
- No non-schema keys.

Accept when:
- Clue graph supports reason-first progression to ending choices.

Verify:
- `python core/validation/validate_module_files.py`

---

## Prompt C - Ending Branch Integration with Parity

Implement ending branch wiring and consequence framing.

Scope:
- `modules/The_Pumpkin_Kings_Curse/module_plot.json`
- `modules/The_Pumpkin_Kings_Curse/areas/GRV001.json`
- `modules/The_Pumpkin_Kings_Curse/areas/HLF001.json`
- `modules/The_Pumpkin_Kings_Curse/player_quests_The_Pumpkin_Kings_Curse.json` (if required)

Required:
- Add four ending paths: Sacrifice, Contract Void, Kingslayer, Dark Bargain.
- Keep endpoints equal-viability with different costs/trade-offs.
- Keep the original linear backbone playable even if branch clues are missed.

Forbidden:
- No replacement of PP backbone.
- No area ID changes.

Accept when:
- All endings have clear unlock routes and distinct consequences.

Verify:
- `python core/validation/validate_module_files.py`

---

## Prompt D - Final Validation and Handoff

Run final quality and parity pass.

Scope:
- All modified files from prompts A-C.

Required:
- Confirm schema pass and no contract-breaking edits.
- Confirm DC compliance (12-18).
- Confirm restrained occult tone.
- Confirm ending parity rationale and DM runbook summary.

Final checks:
- `python core/validation/validate_module_files.py`

Output:
- File list changed
- Ending unlock summary
- Parity rationale
- Any follow-up risks
