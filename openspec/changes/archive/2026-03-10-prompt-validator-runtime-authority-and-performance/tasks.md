## 1. Runtime Prompt Authority

- [x] 1.1 Add source-contract tests proving live narrator runtime loads `prompts/system_prompt_compressed.txt`.
- [x] 1.2 Add source-contract tests proving conversation-history prompt identity uses the compressed narrator prompt.
- [x] 1.3 Update runtime loader paths to use compressed prompt authority.

## 2. Thresholded Validation Compression

- [x] 2.1 Add tests for threshold-based validation compression routing.
- [x] 2.2 Replace unconditional validation compression with threshold-based compression in `main.py`.
- [x] 2.3 Preserve fail-open fallback if compression fails.

## 3. Low-Risk Validation Skip Routing

- [x] 3.1 Add tests for conservative validation skip/routing decisions.
- [x] 3.2 Implement routing helper that marks high-risk turns for full LLM validation.
- [x] 3.3 Skip the LLM validator only for low-risk deterministic-safe turns.

## 4. Compressed Narrator Prompt Reorder

- [x] 4.1 Add tests for compressed narrator prompt ordering and presence of `@RESOLUTION_LADDER`.
- [x] 4.2 Reorder `prompts/system_prompt_compressed.txt` so hard rules precede flavor guidance.
- [x] 4.3 Add compact `@RESOLUTION_LADDER` block and remove obviously duplicated stale guidance where safe.

## 5. Verification

- [x] 5.1 Run targeted tests for authority, compression routing, skip routing, and compressed prompt order.
- [x] 5.2 Run syntax checks and `openspec validate` for this change.
