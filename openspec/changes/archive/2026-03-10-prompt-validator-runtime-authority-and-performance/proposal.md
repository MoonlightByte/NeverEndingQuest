## Why

The initial prompt-validator hardening slices fixed contract drift for `rest`, save-management actions, `createNewModule`, and added deterministic mechanics prechecks. The next bottleneck is architectural: live runtime still reads the uncompressed narrator prompt even though compressed prompt files are the maintained source of truth, and validation still pays unnecessary overhead on common turns.

This change moves the runtime onto compressed prompt authority, adds validation efficiency controls, and refactors the compressed narrator prompt into a clearer order that better balances speed, creativity, and mechanical truth.

## What Changes

- Make compressed prompt files canonical for live narrator and validator runtime paths.
- Add threshold-based validation compression instead of always compressing validation context.
- Add deterministic risk routing so low-risk turns can skip the LLM validator when safe.
- Reorder and slim the compressed narrator prompt, including a new `@RESOLUTION_LADDER` block.
- Keep backward-compatible fail-open behavior where low-risk skip conditions are not met.

## Covered Scope

This change explicitly covers:
- narrator runtime prompt authority
- validation prompt authority
- validation compression policy
- low-risk validator skip routing
- compressed narrator prompt ordering and slimming

Out of scope:
- structured `updateCharacterInfo.ops`
- first-class save/check contracts
- expanded deterministic guard sets beyond current mechanics precheck
- DM Note / character-summary authority cleanup beyond what is needed for low-risk routing

## Capabilities

### New Capabilities
- `tt-runtime-prompt-authority`: live narrator and validator paths MUST load the compressed prompt variants as canonical runtime sources.
- `tt-validation-efficiency-routing`: low-risk turns SHOULD avoid unnecessary compression and MAY skip the LLM validator when deterministic checks and routing rules allow.
- `tt-narrator-prompt-resolution-order`: compressed narrator prompt MUST present hard rules before flavor guidance using a stable resolution order.

## Impact

- Affected runtime:
  - `main.py`
  - `core/ai/conversation_utils.py`
  - possible shared prompt-loader helper under `utils/` if implementation chooses one
- Affected prompts:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt` (if routing metadata guidance is needed)
- Affected tests:
  - new source-contract tests for prompt authority and routing
  - updated prompt-structure tests for compressed narrator ordering

## Acceptance Criteria

- Live narrator runtime no longer loads `prompts/system_prompt.txt`; it uses `prompts/system_prompt_compressed.txt` as canonical source.
- Conversation history maintenance uses the compressed narrator prompt identity rather than the uncompressed prompt.
- Validation compression is threshold-based, not unconditional.
- Low-risk turns can bypass the LLM validator when deterministic checks and routing rules pass.
- Compressed narrator prompt includes a clear `@RESOLUTION_LADDER` and a hard-rules-first ordering.
- Targeted tests cover runtime authority, compression routing, skip routing, and compressed prompt ordering.
