# Companion Memory

Purpose: Persist canonical shared episodes, per-NPC relationships and point of view,
then supply grounded memory to conversation and voice calls.

- Revision: `integration/npc-voice-episodic` at `8f51bef3ee39e8f86b9bff635816c2dd6a520082`
- Verified: 2026-09-01
- Doctrine: [GitHub issue #193 v2.3](https://github.com/MoonlightByte/NeverEndingQuest/issues/193)
- Visual companion: [NPC Voice Flow Map](../npc-voice-flow-map.html)

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Shared episode fact | `episode_ledger.json` coordinate-addressed episode | Idempotent canonical episode commit |
| NPC identity/profile/relationship/working state | `npc_agent_state.json` schema v2 | Revisioned `RelationshipStore` mutation |
| NPC personal memory | POV overlay linked to a canonical episode ID | Written only after canonical episode commit |
| Historical upgrade cursor | `episodic_upgrade.json` | T113 backfill marker advances after accepted entries |
| Roster/presence/raw scene | Party, character, encounter, and history files | Existing canonical game-state commits |
| Legacy `*_memories.json` | Compatibility input only | Import requires exactly one canonical identity match |
| Save copy identity | Save manifest path/hash/schema/byte count | Restore validates listed bytes before mutation |

## Flow

### Live episode capture

1. A location transition checkpoint preserves the full source segment.
2. T108 extracts a canonical summary and companion-attributed typed facts.
3. Code admits facts only for resolved present companions and assigns canonical identities.
4. `EpisodeStore` derives an episode ID from module, location, and boundary turn and commits that
   coordinate idempotently.
5. After the canonical write, code derives per-NPC POV rows and writes them to
   `npc_agent_state.json`; baseline relationship evidence may be reinforced from pinned POV.
6. Combat exit builds presence and near-death facts from authoritative roster/HP telemetry and
   submits T108 asynchronously on deep-copied inputs.
7. Module completion synchronously captures the final location segment that had no exit.

### Recall and conversation injection

1. Conversation rebuild joins each NPC POV row to its canonical ledger episode.
2. Selected `where`, `what`, `youRecall`, and `feeling` values enter companion context; canonical
   episode text remains factual authority and POV supplies personal coloring.
3. A cheap token-overlap pre-screen determines whether targeted T112 recall is needed.
4. T112 extracts typed anchors only.
5. Code selects only episodes witnessed by that exact NPC and attaches them to the exact-beat
   T105 packet; honest no-match remains valid.

### Historical T113 backfill

1. Startup detects old campaign history without a completed upgrade marker.
2. Journal entries and campaign summaries are processed against a closed companion roster.
3. T113 selects presence and parses facts; code drops unknown companions.
4. Stable `backfill-*` coordinates commit through the same canonical episode store.
5. The marker records status, journal cursor, summary completion, and commit count for resume.

### Save, restore, reset

1. Essential Save copies the complete companion-memory directory.
2. Metadata fingerprints both sidecars and the upgrade marker.
3. Restore validates manifest bytes before mutation, backs up current memory, clears live files,
   copies saved files, and restores the backup on copy failure.
4. Saves without `state_manifest` remain accepted for backward compatibility.
5. Reset deletes and recreates the companion-memory directory.

## State and atomicity

- `data/companion_memories/episode_ledger.json`: closed schema v1, path lock, revision, whole-file
  validation, and `safe_json_dump`.
- `data/companion_memories/npc_agent_state.json`: closed schema v2 with the same persistence
  discipline; corrupt/unsupported state latches read-only and emits health events.
- `data/companion_memories/episodic_upgrade.json`: atomic JSON replacement without the sidecar
  revision/path-lock protocol.
- Canonical episode commits before POV/relationship state; there is no cross-file transaction.
- Multi-NPC POV writes are independent RelationshipStore mutations.
- Save metadata verifies copied files but does not make the directory copy one atomic snapshot.

## Load-bearing seams

1. `core/npc/episode_store.py:1-12` - canonical episode authority.
2. `core/npc/episode_store.py:51-73` - coordinate-derived episode identity.
3. `core/npc/episode_store.py:189-284` - latch, lock, revision, schema, atomic write.
4. `core/npc/episode_store.py:286-378` - idempotent commit and witness retrieval.
5. `core/npc/relationship_store.py:285-377` - relationship-sidecar persistence.
6. `core/npc/relationship_store.py:422-500` - stable identity registration.
7. `core/npc/relationship_store.py:765-875` - typed relationship event application.
8. `core/npc/relationship_store.py:978-1045` - exactly-one legacy identity migration.
9. `core/npc/relationship_store.py:1413-1506` - POV storage and baseline reinforcement.
10. `core/npc/episode_extraction.py:138-201` - T108 parsing/presence reconciliation.
11. `core/npc/episode_capture.py:151-265` - location capture and POV projection.
12. `core/npc/episode_capture.py:268-412` - combat capture and async dispatch.
13. `core/npc/episode_recall.py:173-298` - T112 witnessed-only selection.
14. `core/npc/episode_backfill.py:195-254` - T113 roster-bound backfill.
15. `updates/save_game_manager.py:927-1041` - restore, cleanup, and rollback.

## Invariants

- #193 Part 1, B1/B2, AP-4, AP-7, evidence, and lineage.
- #193 Part 2, NPC systems; Save/restore/reset; Schema.
- #193 Part 5, No-Limits, Single-Path, always-live features, and Fork-3.

## Open items

- #198 - asynchronous episode capture can outlive its owning workflow.
- #200 - combat-memory persistence/save-provenance tracker remains open.
- #209 - legacy companion-memory reconciliation remains deferred in travel recovery.
- #258 - synchronous T113 backfill can delay startup after provider completion.
- #262 - remaining episodic-storage No-Limits work.
