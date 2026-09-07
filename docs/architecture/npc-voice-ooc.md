# NPC Voice Outside Combat

Purpose: Build private companion advice for one substantive player beat, inject it into
T067/T065, and commit accepted relationship working state after the DM turn is durable.

- Revision: `integration/npc-voice-episodic` through `6279ef52`
- Verified: 2026-09-03
- Doctrine: [GitHub issue #193 v2.10](https://github.com/MoonlightByte/NeverEndingQuest/issues/193)
- Visual companion: [NPC Voice Flow Map](../npc-voice-flow-map.html)

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Roster, sheets, scene, mechanics | Canonical party, character, location, and history files | Existing game-state commits before voice stage |
| Relationship and working context | `RelationshipStore` sidecar | Schema/revision-validated sidecar mutation |
| Recalled episodes | `EpisodeStore`; T112 selects grounded records | Selected records enter only the request-local packet |
| `say`, `do`, `want`, `thought` | Structurally validated T105 advisory | T067 may reconcile, edit, or omit it |
| Affinity classification | Optional T105 classification over prior committed evidence | Deterministic store applies the typed event |
| Player-facing narration and action | T067 | T065 validates the same candidate with the same advice |
| Accepted persistence | Code after accepted T067 and durable history | Per-NPC sidecar mutation; no model writes files |

### Packet context

| Layer | Packet field | Source |
|---|---|---|
| E1 | `scene.recentSceneWindow` | Recent accepted conversation scene |
| E2 | `context.presentCompanionVisibleActs` | Accepted visible acts by other present companions |
| E3 | `context.recalledEpisodes` | T112 selection from `episode_ledger.json` |
| E4 | `context.companionRelationships` | Relationship snapshot plus attributed evidence |

## Flow

### Standard beat

Local-party instruction, completion-collection and travel-publication seams checked on 2026-09-06 in the uncommitted guardian integration based on `185f8997a5055521f04fe7a55ca908a41f0d412f`. Combined-code live acceptance is pending; older anchors elsewhere are not recertified. Doctrine: live #193, D-NPC-PARTY-1, D-NPC-PARTY-6 and D-VS-3.

1. Main claims the live turn and durably appends the player's substantive input.
2. Candidate selection resolves eligible active companions from the party roster and canonical
   sheets; it does not prose-gate the player request.
3. Packet construction combines location, player/NPC identity, relationship state, prior
   accepted evidence, working context, profile, and E1/E2/E4 records.
4. If E3 recall is unnecessary, T105 dispatch starts immediately.
5. T105 workers run in parallel across selected NPCs; an optional affinity classifier runs only
   when prior committed relationship evidence exists.
6. During T067 request assembly, after compression, code completion-collects dispatched advice
   before injection immediately before the final player message; it does not pre-empt pending
   companions (`core/npc/voice_context.py:1812`, `_RecallVoiceHandle.collect` at line328).
7. T067 remains the sole player-facing DM and action author.
8. In the guardian working candidate based on the revision above, structured membership
   proposals receive T114 review before route preflight and T065. The shared owner (`main.py:9585`) keeps
   actual player input, accepted context, latest candidate and review feedback distinct.
   T065 retains the same request-local advisory batch across correction attempts.

   T067/T065 reconcile private advice against the supported local-party boundary: companion suggestions cannot authorize remote scouting, arrival or reports. Violating DM proposals return through existing semantic correction. Genuine leaving/rejoining and local scouting remain supported. No mandatory dialogue line or voice-coverage validator is added. T065 does not receive the generated common DM Note; its own prompt states the boundary. Ordinary narration remains before handler execution; this change adds no result-feedback loop.
9. Ordinary accepted T067 history is persisted under the live invocation claim.
   Travel excludes pre-processing history/sidecar publication; existing travel publishers
   own commit after exact-plan currentness checks.
10. Travel T105 working state is committed only after successful assistant processing
    while the invocation is still current. A stale/content-failed travel result does not
    commit that sidecar. Controlled caller checks are not successful-live-travel evidence.

T114 is a membership reviewer, not another voice author. Private suggestions and
rejected drafts cannot establish consent. Genuine requested membership changes and
independent departures grounded in already accepted story remain possible; the full
validator still reviews the complete candidate after guardian approval. Guardian
feedback is request-local and never committed as companion memory.

### Recall beat

1. Witnessed episode availability opens an advisory T112 scope; code does not prose-gate recall.
2. T112 classifies whether the line is a concrete past/shared reference and extracts anchors;
   code scores each NPC's full witnessed set with those anchors plus exact typed equality to
   the packet's canonical current-location ID.
3. Validated E3 rows enrich the packet.
4. T105 dispatch begins after recall; T112 is a serial predecessor, while T105 remains parallel
   across companions.
5. Superseded recall or voice work cannot merge into a later player beat.

### Privacy and failure

1. Private advice is inserted into copied request messages, never durable chat history.
2. Ordinary diagnostic exports and `api_logger` views replace the block with a redaction marker.
3. The forensic multi-model capture retains the real provider request; it is not an ordinary
   redacted diagnostic stream.
4. Missing, invalid, failed, or superseded advisory work leaves T067/T065 mechanics and player
   progress intact for that beat and records the voice failure disposition.

## State and atomicity

- Relationship state: `data/companion_memories/npc_agent_state.json`.
- Recall source: `data/companion_memories/episode_ledger.json`; this flow reads it but the
  accepted T105 commit does not write it.
- `RelationshipStore` uses `.npc-agent.lock`, rereads/copies/validates, increments revision,
  and writes with `safe_json_dump`.
- Lock contention waits in repeated acquisition intervals rather than discarding the mutation.
- Affinity plus working state is one sidecar mutation; a no-affinity result updates working
  state in one mutation.
- Multi-NPC batches commit independently, not as one cross-NPC transaction.

## Load-bearing seams

1. `main.py:8401-8416` - stage starts after durable player-input claim.
2. `core/npc/voice_context.py:373-398` - E1 scene window.
3. `core/npc/voice_context.py:401-428` - E2 visible companion acts.
4. `core/npc/voice_context.py:431-495` - E4 companion relationships.
5. `core/npc/voice_context.py:130-323` - E3/T112 witnessed selection, typed-location scoring,
   and T105 handoff.
6. `core/npc/voice_context.py:810-990` - canonical packet construction.
7. `core/npc/voice_service.py:720-917` - fenced parallel T105 workers.
8. `core/npc/voice_service.py:493-660` - response validator and affinity classification.
9. `core/npc/voice_context.py:1812` - completion-collection and private injection; `_RecallVoiceHandle.collect` at line328.
10. `main.py:6642-6671` - post-compression injection before T067.
11. `main.py:2952-2996` - same advice reaches T065 validation.
12. `main.py:8974-9007` - accepted-history and sidecar commit gate.
13. `core/npc/voice_context.py:1510-1615` - per-result sidecar commit.
14. `core/npc/relationship_store.py:339-377` - lock, revision, atomic write.
15. `core/npc/voice_context.py:1706-1726` - ordinary diagnostic redaction.

## Invariants

- #193 Part 1 B1, B2, and AP-7.
- #193 Part 2, NPC systems.
- #193 Part 2, Provider routing and startup.
- #193 Part 5, always-live functionality; No-Limits; Single-Path; Fork-3.

## Open items

- #258 - companion-memory backfill can delay startup before player control.
- #291 - lifecycle-write recovery for a roster-active but stale inactive sidecar remains open.
