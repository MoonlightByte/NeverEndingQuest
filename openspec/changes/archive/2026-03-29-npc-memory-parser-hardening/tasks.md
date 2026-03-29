## 1. Parser Coverage Hardening

- [x] 1.1 Audit the current live companion parser in `core/memories/action_parser.py` and map missing generalized event families from the Blarg-style journal excerpts.
- [x] 1.2 Add generalized extraction patterns for coercion/leverage, exposed secrets, recruitment/agreement to accompany, watch/escort duties, and narrative combat teamwork in `core/memories/action_parser.py`.
- [x] 1.3 Verify the updated parser still avoids obvious overmatching by adding focused parser-level regression coverage for positive and negative examples.

## 2. Memory Accounting and Quality Classification

- [x] 2.1 Update `core/memories/companion_memory.py` to distinguish NPC story presence from meaningful interaction accounting without breaking the existing file-backed save flow.
- [x] 2.2 Add companion memory quality classification semantics in `core/memories/companion_memory.py` and/or the compressed projection path so healthy, sparse, degraded-extract, and malformed states are distinguishable.
- [x] 2.3 Update `scripts/memory_management/compress_memories.py` to preserve any new quality or accounting fields needed by narrator consumers while keeping backward-compatible compressed output.

## 3. Narrator Fallback Integration

- [x] 3.1 Update `core/ai/conversation_utils.py` so truly malformed companion memory packets remain excluded, but sparse and degraded-extract packets use bounded fallback handling.
- [x] 3.2 Implement a compact soft-fallback companion context projection that preserves continuity signals without inlining large journal excerpts or unsupported emotional claims.
- [x] 3.3 Verify that healthy companion packets still use the normal injection path and that fallback handling does not widen prompt payloads excessively.

## 4. Regression and Recovery Verification

- [x] 4.1 Add regression fixtures and tests covering the known Blarg-style recruitment/leverage, follow-into-danger, watch-duty, and narrative combat contribution cases.
- [x] 4.2 Add classification tests covering healthy, sparse, degraded-extract, and malformed packet outcomes.
- [x] 4.3 Run targeted verification for the touched files, including Python compile checks and the new companion-memory regression suite.
- [x] 4.4 Document the expected rebuild/recovery flow for affected saves so degraded companion memories can be regenerated after the parser hardening lands.
