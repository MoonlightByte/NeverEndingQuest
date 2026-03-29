# NPC Memory Hardening Plan

## Status

- Lifecycle state: Archived (superseded/partially implemented, 2026-03-30)
- Priority: Archived reference
- Scope: Historical live-stack companion-memory hardening and relationship-edge planning
- Closure decision: Phase 1 hardening and Phase 2A file-backed relationship edges landed in runtime; remaining work moved into v2 planning
- Runtime implementation references:
  - `openspec/changes/npc-memory-parser-hardening/`
  - `openspec/changes/tt-npc-memory-relationship-edges/`
- V2 destination references:
  - `plans/version-2/memory.md`
  - `plans/version-2/v2-narrative-track.md`

Date: 2026-03-29
Project: NeverEndingQuest (Tabletop merge-safe branch)
Status: Archived reference
Related references:
- `plans/version-2/memory.md`
- `plans/version-2/v2-narrative-track.md`
- `core/memories/companion_memory.py`
- `core/memories/action_parser.py`
- `core/ai/conversation_utils.py`

## Overview

This plan defines a general hardening pass for the live NPC companion memory system.

The immediate trigger is the Blarg regression: the runtime recorded four interactions, but stored zero crystallized memories, zero emotional state, and then excluded Blarg from narrator context as "corrupted." Review of the supplied journal excerpts shows that the interaction history included multiple relationship-shaping beats that should have influenced future narration.

The fix must not be Blarg-specific. It must strengthen NPC memory behavior across varied companion NPCs, varied journal phrasing, and tabletop multi-PC play where different PCs may have different relationships with the same NPC.

## Problem Statement

The current live companion memory stack is useful but brittle.

Observed issues:

1. The live parser is regex-heavy and phrasing-sensitive.
2. Interaction counts can increase even when no meaningful action is successfully parsed.
3. The runtime stores one aggregate emotional state per NPC, not distinct NPC-to-PC relationship edges.
4. The corruption heuristic treats "interaction count without crystallized output" as broken data and suppresses the NPC from prompt context.
5. Multi-PC tabletop sessions compress several distinct social relationships into one blended NPC memory state.

Practical consequence:

- NPCs may fail to remember important coercion, trust, betrayal, rescue, loyalty, or teamwork beats.
- NPCs may feel flat, inconsistent, or reset in later narration.
- In tabletop mode, NPC attitude toward one PC can incorrectly bleed into attitude toward all PCs.

## Blarg Case Summary

The supplied Blarg files show the failure mode clearly:

- `blarg_memories.json` contains `total_interactions: 4` but no `core_memories` and all-zero emotional state.
- `memories_compressed.json` mirrors the same empty state.
- `journal.json` includes significant moments that should have created durable relationship signals:
  - Lidda steals and exposes Blarg's letters.
  - Redax confronts and pressures Blarg into aiding the party.
  - Blarg agrees to accompany the party.
  - Blarg follows the party into danger.
  - Blarg fights alongside the party in meaningful combat beats.
  - Blarg stands watch during coordinated exploration.

This indicates a real extraction failure, not a harmless warning.

## Current Baseline

### Live Runtime Path

The live runtime currently uses:

- `core/memories/companion_memory.py`
  - `ActionParser()`
  - `MemoryCrystallizer()`
- `core/ai/cumulative_summary.py`
  - writes journal entries
  - processes companion memories after summary save
- `scripts/memory_management/compress_memories.py`
  - creates `data/companion_memories/memories_compressed.json`
- `core/ai/conversation_utils.py`
  - injects compressed companion memories into narrator context
  - skips NPCs whose memory packet looks invalid

### Important Limitation

The more advanced modules under `core/memories/enhanced_action_parser.py` and `core/memories/enhanced_memory_crystallizer.py` are not the live runtime path today.

That means the current behavior is still governed by the simpler parser/crystallizer pair.

## Root Cause Analysis

### Root Cause 1: Weak semantic coverage

The current parser recognizes only a narrow set of predefined phrasings. It is weak on:

- coercion / blackmail / leverage
- exposure of secrets or hidden allegiances
- recruitment / agreement to accompany
- moral choice / being set free to choose
- following the party into danger
- guarding the rear / standing watch / holding position
- combat contribution phrased narratively rather than mechanically

### Root Cause 2: Counter semantics are misleading

`CompanionMemoryManager.process_journal_entry()` increments the interaction counter before verifying that it parsed a memory-worthy action.

This allows the system to produce:

- positive interaction count
- zero emotional state
- zero crystallized memories

That state is currently treated as corruption, even though it can also mean "NPC was mentioned, but parser coverage failed."

### Root Cause 3: Aggregate NPC memory collapses multi-PC relationships

The current design stores one emotional state and one memory set per NPC. That is too coarse for tabletop mode.

Examples of relationship drift this can cause:

- Lidda steals from Blarg, but Redax later earns his respect.
- Xorn heals Blarg, but Athelon distrusts him.
- The party as a whole fights together, but only one PC forms a close bond.

The existing structure cannot represent those distinctions cleanly.

### Root Cause 4: Prompt exclusion is too aggressive

The current guard in `conversation_utils.py` excludes the NPC entirely from context when memories look invalid.

That protects the narrator from obviously bad packets, but it also removes all continuity for NPCs who merely failed extraction.

## Goals

1. Generalize memory extraction so it works across many NPCs and varied journal phrasing.
2. Preserve meaningful relationship continuity for companion NPCs during live narration.
3. Support differentiated NPC feelings toward different PCs in tabletop mode.
4. Fail soft when memory extraction is sparse; do not erase an NPC from context unless data is truly malformed.
5. Keep the system merge-safe and additive where possible.

## Non-Goals

1. Full replacement of the broader `memory.db` architecture in this change.
2. A claim that every sentence in every journal entry becomes a perfect memory.
3. Broad LLM-based freeform memory extraction in the live turn loop.
4. Replacing Python mechanical authority with narrative memory state.

## Design Principles

1. Generalize before specializing.
2. Separate mention detection from meaningful interaction detection.
3. Distinguish malformed data from sparse data.
4. Preserve tabletop merge safety.
5. Keep prompt packets bounded and narrator-friendly.
6. Prefer additive migrations and clear fallback behavior.

## Desired End State

After this hardening pass:

1. Companion NPCs reliably retain meaningful social and combat continuity.
2. Tabletop mode can represent NPC relationship drift toward multiple PCs separately.
3. The narrator receives a bounded, high-signal packet instead of either stale noise or total omission.
4. "Corrupted memory" warnings represent true data breakage, not parser weakness.

## Proposed Strategy

Use a phased rollout.

### Phase 1: Stabilize the existing live stack

Objective: Make the current system trustworthy enough for live use without waiting for a full memory architecture rewrite.

#### 1.1 Parser coverage expansion

Expand the live parser to recognize generalized families of companion-relevant events.

New event families should include:

- recruitment and reluctant alliance
- blackmail, leverage, coercion, extortion, forced cooperation
- exposure of secrets, hidden allegiance, discovered letters, stolen evidence
- mercy, release, choice, freedom to decide, choosing to stay or follow
- escort, accompany, follow, bring up the rear, stand watch, hold the line
- combat teamwork, battlefield support, intimidation, savage assault, covering movement
- trust repair, suspicion, resentment, respect under pressure

Important constraint:

- Add semantic families, not hardcoded "Blarg" examples.
- Use multiple alternate phrasings for each family.
- Prefer role-aware wording such as "NPC agrees to accompany" rather than one journal sentence template.

#### 1.2 Mention count vs meaningful interaction count

Split the current counter model into explicit categories.

Recommended fields:

- `mention_count`: NPC appeared in a relevant journal entry.
- `meaningful_interaction_count`: parser found at least one relationship-meaningful action.
- `crystallized_memory_count`: durable memory objects actually created.

This allows the runtime to distinguish:

- "NPC is present in the story but parser found nothing strong"
- "NPC had meaningful actions but velocity stayed below threshold"
- "NPC data is malformed"

#### 1.3 Corruption heuristic redesign

Replace the current simple rule:

- interactions > 0 + zero emotions + zero memories = corrupted

with a more careful classification:

- `malformed`: missing required fields, wrong shapes, unreadable values
- `sparse`: valid file, no crystallized memories yet
- `degraded_extract`: meaningful-interaction count exists but zero crystallized output unexpectedly
- `healthy`: valid packet with usable state

Narrator behavior should be:

- `healthy` -> inject full packet
- `sparse` -> inject a minimal continuity stub instead of dropping the NPC
- `degraded_extract` -> inject minimal stub and log warning
- `malformed` -> exclude and log error

#### 1.4 Minimal continuity stub

When a companion NPC has story presence but weak crystallized output, inject a small fallback packet rather than total omission.

Example fields:

- NPC name
- known party role
- recent status summary such as "accompanied party recently"
- confidence marker such as `memory_quality: sparse`

This preserves basic continuity even before deeper fixes land.

### Phase 2: Tabletop relationship-edge model

Objective: Stop flattening all NPC-to-PC history into a single blended NPC state.

#### 2.1 Add relationship edges

Introduce per-PC relationship tracking for companion NPCs.

Recommended concept:

- `npc_global_state`: overall disposition, shared arc, group reputation
- `relationship_edges`: keyed by canonical PC identity

Each edge should carry:

- trust
- respect
- intimacy / closeness
- fear / caution
- resentment / betrayal pressure
- recent triggers
- last significant interaction timestamp

This lets the game represent cases like:

- Blarg distrusts Lidda after theft
- Blarg respects Redax after direct leadership
- Blarg values Xorn's support in combat

#### 2.2 Canonical PC identity

Edge keys must use canonical character identity, not display-name accidents.

Use stable routing via existing tabletop identity patterns where possible:

- normalized party member names
- future-safe `character_id` where available

#### 2.3 Bounded prompt projection

Do not dump every relationship edge into narrator context.

Project only:

- active PC edge
- 1-2 strongest non-active edge summaries when relevant
- recent group memory if it affects current scene

This keeps multi-PC continuity while avoiding token explosion.

### Phase 3: Upgrade live extraction path

Objective: Move the live runtime closer to the enhanced parser/crystallizer model already present in the repo.

#### 3.1 Evaluate migration path

Review whether the existing enhanced modules can be promoted safely into runtime usage.

Questions to answer:

- Are they complete enough for live use?
- Do they preserve deterministic enough behavior?
- Can they run without introducing fragile dependencies?
- Can they be adapted to tabletop per-PC edges without major rewrite?

Preferred direction:

- Reuse enhanced modules if they meaningfully reduce implementation cost.
- Avoid running two divergent memory stacks long term.

#### 3.2 If enhanced path is not ready

If direct adoption is too risky, backport the most valuable concepts into the current live path:

- richer attribution tags
- context tags
- climactic moment lowering of threshold
- relationship-phase awareness
- reinforcement tracking

### Phase 4: Recovery and migration tools

Objective: Repair existing saves with degraded NPC memory state.

#### 4.1 Companion memory rebuild tool

Provide a deterministic rebuild path that:

- reprocesses `journal.json`
- rebuilds companion memory files
- rebuilds compressed memories
- preserves backups of prior files

#### 4.2 Diagnosis report mode

Add a report mode that identifies NPCs in these buckets:

- healthy
- sparse but valid
- degraded extraction
- malformed

This should help operators identify whether a save needs intervention.

#### 4.3 Optional targeted rebuild

Allow rebuilding one NPC from journal history without forcing a full party refresh.

Useful for live recovery when one companion is affected.

## Data Model Proposal

This section proposes an additive JSON evolution, not a full DB migration.

### Current per-NPC file shape

Current live shape is roughly:

```json
{
  "npc_name": "Blarg",
  "core_memories": [],
  "current_emotional_state": {
    "trust": 0.0,
    "power": 0.0,
    "intimacy": 0.0,
    "fear": 0.0,
    "respect": 0.0
  },
  "behavioral_model": {},
  "total_interactions": 4
}
```

### Proposed additive shape

```json
{
  "npc_name": "Blarg",
  "mention_count": 6,
  "meaningful_interaction_count": 4,
  "crystallized_memory_count": 3,
  "memory_quality": "healthy",
  "npc_global_state": {
    "trust": 0.1,
    "power": 0.0,
    "intimacy": 0.0,
    "fear": 0.2,
    "respect": 0.3,
    "resentment": 0.2
  },
  "relationship_edges": {
    "redax": {
      "trust": 0.2,
      "respect": 0.4,
      "fear": 0.1,
      "resentment": 0.0,
      "last_significant_interaction": "1492 Springmonth 2 10:16:00"
    },
    "lidda_underbough": {
      "trust": -0.3,
      "respect": 0.0,
      "fear": 0.2,
      "resentment": 0.5,
      "last_significant_interaction": "1492 Springmonth 2 10:16:00"
    }
  },
  "core_memories": [],
  "behavioral_model": {}
}
```

Notes:

- This keeps backward-compatible top-level memory concepts.
- Existing readers can still use a top-level NPC-global state.
- New readers can use relationship edges when in tabletop mode.

## Prompt Contract Proposal

The narrator should not receive raw full memory files.

It should receive a bounded projection with:

1. NPC identity and role.
2. Memory quality marker.
3. Top 1-3 group memories.
4. Active-PC relationship edge.
5. Optional one-line note for strongest tension or alliance with another PC.

Example prompt projection:

```text
NPC: Blarg
Memory quality: healthy
Group continuity: accompanied party into cathedral; fought alongside party against cultists; stood watch during crypt entry
Active PC edge (Redax): wary respect after confrontation; follows Redax's lead under pressure
Other tension: distrusts Lidda after theft and exposure of hidden letters
```

This is both more useful and more compact than the current empty-or-drop behavior.

## Implementation Workstreams

### Workstream A: Extraction Coverage

Files likely touched:

- `core/memories/action_parser.py`
- possibly `core/memories/enhanced_action_parser.py`
- tests under `scripts/`

Deliverables:

- generalized pattern families
- broader narrative combat phrasing support
- recruitment/coercion/trust-betrayal coverage

### Workstream B: Counter and Quality Semantics

Files likely touched:

- `core/memories/companion_memory.py`
- `scripts/memory_management/compress_memories.py`
- `core/ai/conversation_utils.py`

Deliverables:

- mention vs meaningful-interaction distinction
- memory quality classification
- soft fallback packet instead of total omission

### Workstream C: Tabletop Per-PC Relationship Edges

Files likely touched:

- `core/memories/companion_memory.py`
- `scripts/memory_management/compress_memories.py`
- `core/ai/conversation_utils.py`
- possible schema docs / migration helpers

Deliverables:

- per-PC edge storage
- active-PC prompt projection
- bounded non-active edge projection

### Workstream D: Recovery Tooling

Files likely touched:

- `scripts/memory_management/refresh_memories.py`
- new diagnosis / repair scripts

Deliverables:

- diagnosis mode
- targeted rebuild mode
- operator-safe recovery flow for live saves

## Regression Strategy

This work needs source-contract and behavior tests built from real examples, not synthetic toy phrasing only.

### Required test families

1. **Recruitment / coercion extraction**
   - letters discovered
   - blackmail or leverage applied
   - NPC agrees to accompany

2. **Choice / release extraction**
   - party frees NPC to choose
   - NPC chooses to continue with group

3. **Combat teamwork extraction**
   - NPC fights alongside party
   - narrative phrasing, not only mechanical verbs

4. **Guard / escort / watch extraction**
   - NPC stands watch
   - NPC guards rear or entry point

5. **Quality classification tests**
   - sparse but valid packets
   - degraded extraction packets
   - truly malformed packets

6. **Tabletop per-PC edge tests**
   - one NPC develops different responses to different PCs
   - active-PC prompt packet changes appropriately

7. **Migration / rebuild tests**
   - rebuild recovers degraded companion state from journal
   - compressed output matches rebuilt raw state

### Test fixture guidance

Use real excerpt-driven fixtures inspired by Blarg and similar companion cases.
Do not rely only on idealized short phrases.

## Rollout Plan

### Stage 1: Safe hardening MVP

Deliver:

- broader parser coverage
- counter split
- quality classification
- soft fallback packet
- rebuild script improvements

Expected impact:

- immediate reduction in false "corrupted memory" suppressions
- live companion continuity improves without redesigning the full system

### Stage 2: Tabletop relationship edges

Deliver:

- per-PC relationship state
- active-PC prompt projection
- compact multi-PC continuity rules

Expected impact:

- NPC feelings become meaningfully different per PC in tabletop mode

### Stage 3: Runtime unification with enhanced path

Deliver:

- adoption or selective merge of enhanced parser/crystallizer features
- reduced divergence between planned and live memory stacks

Expected impact:

- longer-term maintainability and better continuity fidelity

## Risks

1. **Overmatching**
   - Broad regex patterns may create false positives.
   - Mitigation: require context windows, attribution checks, and regression fixtures.

2. **Prompt bloat**
   - Per-PC edges can explode prompt size in multi-PC mode.
   - Mitigation: project only active-PC edge and strongest relevant side notes.

3. **Backwards compatibility drift**
   - New JSON fields may confuse old tools.
   - Mitigation: additive fields only; preserve top-level fallback state.

4. **Narrative overconfidence**
   - Sparse memory may still be interpreted too strongly.
   - Mitigation: include explicit memory-quality markers in prompt projection.

5. **Tooling complexity**
   - Dual support for current and enhanced paths can increase maintenance cost.
   - Mitigation: treat runtime path unification as an explicit later stage.

## Open Questions

1. Should resentment be modeled as its own axis, or derived from negative trust/respect?
2. Should per-PC relationship edges exist only in tabletop mode, or universally?
3. How much of the enhanced parser/crystallizer can be safely promoted now?
4. Should minimal fallback packets be derived from journal snippets, or from structured counters only?
5. Should rebuild tooling also backfill prior NPCs already marked sparse, or only future entries?

## Recommended Review Focus

For review, the most important decisions are:

1. Whether Stage 1 should remain heuristic-only or immediately adopt parts of the enhanced parser path.
2. Whether per-PC relationship edges are mandatory for the first tabletop-facing fix or a second-stage extension.
3. Whether the corruption heuristic should ever exclude sparse memory NPCs from prompt context, or only truly malformed data.
4. Whether resentment / betrayal pressure should be an explicit relationship field.

## Recommended Next Action

After review, convert this plan into an OpenSpec change focused on a bounded first slice:

- parser generalization
- sparse-vs-malformed quality classification
- soft prompt fallback
- regression coverage using the Blarg excerpts

That is the highest-value first step and directly addresses the live failure mode without waiting for the full relationship-edge redesign.
