# NPC Memory Recovery

This note describes the expected recovery flow after the `npc-memory-parser-hardening` change lands.

## When to Use It

Use this recovery flow when a companion NPC shows signs of degraded memory state, for example:

- recurring warnings about malformed or degraded companion memory data,
- interaction history present but zero crystallized memories,
- an NPC feels absent or reset in later narration despite recent journaled involvement.

## Source of Truth

The rebuild source for live companion memory recovery is the root `journal.json` file.

The live runtime remains file-backed in this slice:

1. `journal.json`
2. `data/companion_memories/*_memories.json`
3. `data/companion_memories/memories_compressed.json`

## Recovery Steps

1. Stop the active session or make sure no live write is happening.
2. Back up the current `data/companion_memories/` directory.
3. Rebuild companion memories from the journal:

```bash
python3 scripts/memory_management/refresh_memories.py
```

4. Regenerate compressed narrator-facing memory output if needed:

```bash
python3 scripts/memory_management/compress_memories.py
```

5. Restart the application so fresh companion memory packets are injected into narrator context.

## Expected Outcome

After a successful rebuild:

- meaningful companion interactions should be re-derived from `journal.json`,
- per-PC relationship edges should be regenerated when journal evidence clearly ties a companion beat to a specific PC,
- degraded extraction cases should either produce usable memories or bounded fallback context,
- only truly malformed packets should remain excluded from narrator context.

## Notes

- This recovery flow does not require `memory.db`.
- This recovery flow now rebuilds additive file-backed per-PC relationship edges for the live tabletop path.
- Deeper relationship retrieval, scoring, and broader memory evolution move to `plans/version-2/memory.md` after this Phase 2A slice.
- If a companion still remains degraded after rebuild, inspect the relevant journal phrasing and extend parser coverage before assuming the save data is corrupt.
