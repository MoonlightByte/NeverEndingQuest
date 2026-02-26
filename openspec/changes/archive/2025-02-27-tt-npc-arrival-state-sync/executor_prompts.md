## Kimi Builder Execution Prompts - tt-npc-arrival-state-sync

Use this file as the plan-to-builder handoff for deterministic NPC arrival state sync.

---

## Execution Contract

- MUST enforce narration/state coherence for off-location known NPC arrivals.
- MUST use fail-closed validation (reject and retry), not silent state mutation.
- MUST preserve existing behavior for already-present NPC references.
- MUST keep host edits additive and mark integration points with `# TABLETOP MODE:` where applicable.
- MUST avoid destructive git commands and avoid scope creep outside task sections.
- SHOULD isolate mention/action pairing logic into helper function(s) for low-risk edits.
- SHOULD keep prompt and validator wording concise to reduce retry churn.

---

## Prompt 1 - Add Validation Guard Core (tasks 1.1-1.4)

Implement tasks `1.1` through `1.4` only.

Scope:
- `main.py`
- optional new helper module only if needed for clarity

Requirements:
- Add deterministic check that inspects assistant JSON response and narration text.
- Detect non-present known NPC mentions using canonical names from current module context.
- Require same-response pairing to either:
  - `moveBackgroundNPC` with matching `npcName`, or
  - `updatePartyNPCs` add with matching NPC name.
- Return fail-closed validation reason when pairing is missing.
- Keep behavior unchanged for already-present NPC mentions.

Verification gate:
- `python3 -m py_compile main.py`

Report format:
- Files changed
- Guard entry point location
- 2 positive + 2 negative sample outcomes

---

## Prompt 2 - Prompt/Validator Alignment (tasks 2.1-2.3)

Implement tasks `2.1` through `2.3` only.

Scope:
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`

Requirements:
- Add explicit MUST rule for off-location NPC arrival claims requiring state action.
- Add validator examples for both valid and invalid forms.
- Keep wording compatible with existing action vocabulary; do not rename action IDs.

Verification gate:
- Sanity-read prompt fragments to ensure no contradictory rules.

Report format:
- Exact sections updated
- New rule text summary

---

## Prompt 3 - Party Strip Dedupe Normalization (tasks 3.1-3.2)

Implement tasks `3.1` and `3.2` only.

Scope:
- `web/extensions/tabletop_socket_handlers.py`

Requirements:
- Replace substring-based dedupe comparison with canonical equality matching.
- Preserve suppression of true duplicates while allowing distinct names.
- Keep payload shape unchanged.

Verification gate:
- `python3 -m py_compile web/extensions/tabletop_socket_handlers.py`

Report format:
- Before/after comparison logic
- Edge case demonstration (`Ansel` vs `Anselara`)

---

## Prompt 4 - Tests and Final Verification (tasks 4.x and 5.x)

Implement tasks `4.1` through `5.4`.

Scope:
- `scripts/test_npc_arrival_state_sync.py`
- verification command execution

Required checks:
- `python3 -m py_compile main.py web/extensions/tabletop_socket_handlers.py`
- `python3 -m py_compile scripts/test_npc_arrival_state_sync.py`
- `python3 scripts/test_npc_arrival_state_sync.py`
- `openspec validate tt-npc-arrival-state-sync`

Manual smoke checklist:
1. Narration mentions off-location known NPC without action -> rejected and retried.
2. Narration mentions off-location known NPC with `moveBackgroundNPC` -> accepted.
3. Narration mentions already-present NPC -> accepted without extra action.
4. Party strip dedupe keeps distinct names visible.

---

## Stop Conditions

- Stop immediately if validation guard blocks already-present NPC references.
- Stop immediately if compile/tests fail after a patch; fix before proceeding.
- Do not expand into alias-engine or broad entity-recognition redesign in this change.
