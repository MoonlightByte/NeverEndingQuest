# Combat Narration Prose Fix -- Handoff (2026-08-24)

Branch `design/agentic-combat`, commit `ee0ba44a` (on top of Slice-1 `4290e711`).
Prompt-only change. No code, config, schema, or test changes.

## Problem (from the Slice-1 acceptance transcripts)

Combat narration read like a calculator dump instead of a DM:
- React R2: "striking Snow Rat for 5 piercing damage and reducing it to 2 hit points ... expend one arrow."
- Legacy: "dealing 9 piercing damage and killing it; her arrows decreased from 70 to 69."

Design objective (owner): the player should read *"Kira sends the arrow deep into the ghoul's
chest, brackish blood sprays the wall, she grins"* -- and the inventory/HP adjust **silently on
the backend**, never narrated.

## Root cause (prompt contradiction, not architecture)

The JSON contract already separates `narration` (prose) from `actions` (the mechanical ledger).
But the prompts fought each other:
- Generator (`combat_sim_prompt*`) only weakly said "No explicit dice math in narration".
- Validator (`combat_validation_prompt*`) DEMANDED "Immediately reflect results after each
  damaging action in narration" and "narration must consistently calculate damage". The referee
  won, so the DM recited numbers/HP/ammo in prose.

## Fix

Generator -- narration = pure cinematic prose; states NO numbers, HP totals, ammo/inventory
counts, spell slots, AC, or dice results; ALL bookkeeping lives ONLY in `actions[].changes`,
applied silently. Added GOOD/BAD examples (the ghoul/arrow example verbatim).

Validator -- verify math from `actions[]`/`plan`, NOT the prose; narration must convey the
OUTCOME in fiction (wound / kill / miss); explicitly "do NOT flag a narration invalid for
OMITTING numbers." Removed the numbers-in-narration demand. Also softened generator `v_sync`
(outcomes consistent with actions, numbers never restated in prose).

Files (compressed = ACTIVE because `USE_COMPRESSED_COMBAT=True`; uncompressed twins edited to
prevent a toggle regression):
- `prompts/combat/combat_sim_prompt_compressed.txt` (active generator)
- `prompts/combat/combat_validation_prompt_compressed.txt` (active validator)
- `prompts/combat/combat_sim_prompt.txt` + `..._uncompressed.txt` (uncompressed generator twins)
- `prompts/combat/combat_validation_prompt.txt` (uncompressed validator)

## Evidence (Claude, OpenAI/WSL arm)

Method: constructed the combat-round payload exactly as Slice-1 `combat_manager` passes it to the
model -- real (tuned) `combat_sim_prompt` via `read_prompt_from_file`, real
`filter_encounter_for_system_prompt` on the snow-rat encounter shape, faithful
`user_input_with_note` (live initiative tracker + creature states + prerolls + PLAYER ACTION),
real `api_client.create_completion(model=COMBAT_MAIN_GPT54_NONE)`. Probe is a LOCAL dev aid, not
tracked. NOT a monkeypatch, NOT a simulated player -- a real model call inspecting real output.

Result: **4/4 runs PASS** -- zero numeric/HP/ammo leakage in narration; ledger carries all HP and
ammo in `actions[].changes`; includes the ranged/ammo case that previously leaked "arrows 70 to
69"; player agency preserved (stops at the player's turn). Example narration:
"her shot punches straight through the first rat in a burst of dirty white fur. It skids across
the boards and goes still. Hard stop." -- ledger: "Snow Rat_1 takes 7 damage, HP 7 to 0, dead" +
"Expended 1 arrow."

## What Codex should do (authoritative arm)

1. Re-run the real full-game acceptance (`run_headless.py serve` + browser) with this prompt and
   confirm the narration reads as prose end-to-end through a complete combat, not just one round.
2. **Confirm on the local-model path too.** This was proven on gpt-5.4 (OpenAI). Gemma/LM Studio
   follow prompts differently; verify the same clean split holds there, since that is your
   env arm and the compressed prompt is what both use.
3. This change does NOT close the other open Slice-1 items -- crash/race, legacy/pre-typed,
   reversed-controller, recovery-conflict acceptance still remain, plus the r8 near-death /
   free-form-player-action coverage the first transcripts lacked.

## Related (pre-existing, file separately)

The ammo bookkeeping is driven by a prose/keyword word-scan in `combat_manager.py`
(`if any(word in changes.lower() for word in ["arrow","bolt","ammunition","ammo","expended"])`,
introduced `b52c0170` 2025-09-06) -- a banned prose-matching-as-authority pattern (AP-7). Not
touched here; recommend a spun-out issue since agentic combat leans on it.
