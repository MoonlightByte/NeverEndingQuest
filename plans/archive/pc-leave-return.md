# PC Leave/Return World Memory Plan (Kimi Builder)

Status: In Progress (openspec-plan-to-builder)
Owner: Tabletop Mode
Date: 2026-02-16

## Builder Orchestration Contract (openspec-plan-to-builder)

This plan uses strict phased execution with approval gates per the openspec-plan-to-builder skill.

### Workflow Loop

```
Plan emits step prompt → Builder executes ONE step → Plan verifies → Plan emits next step prompt
```

### Phase Gates

After each phase, **STOP and wait for user approval** before proceeding.

### Default Verbosity

- **lite** (6-line capsule) - default unless user requests otherwise
- Use standard/full only on explicit request

### Verification Gates (per step)

1. **Compile/Syntax** - `python3 -m py_compile [files]`
2. **Behavior Smoke** - expected functionality works
3. **Compatibility** - no breaking changes to existing callers
4. **Scope Compliance** - only allowed files modified

### Verdict Flow

- **PASS** → proceed to next step
- **FAIL** → retry step with corrections
- **NEEDS_FIX** → specific fix instruction

---

## Objective

Implement graceful PC leave and return flow where:

1. Clicking the tab `x` retires a PC from `party_tracker.json` without deleting world/NPC memory.
2. The LLM narrates the departure (explicit farewell text if provided, mysterious departure if not).
3. Retirement is stored as high-priority long-term memory in `data/memory.db`.
4. Re-adding that PC through Manage Party -> Add Existing triggers return narration and NPC recall based on prior memories.

## Key Decision

Use `data/memory.db` as the authoritative long-term memory source for leave/return lifecycle.

- JSON remains compatibility and audit mirror during migration.
- No memory purge on retirement.
- Role transitions become first-class world events in DB.

## Scope (MVP)

In scope:

- Retirement flow (`/api/party/remove_character`) with optional player farewell text.
- Return flow (`/api/party/add_character`) with memory-aware re-entry narration.
- DB writes for `role_transition` events and links.
- Character lifecycle trace in `_tabletop_role_history`.
- Route-level failure isolation (memory failure must not hard-fail party management).

Out of scope (follow-up):

- Full replacement of legacy companion memory stack.
- Automatic per-NPC emotional vector synthesis from DB events.
- UI timeline for retired PCs.

## Files to Add

1. `core/memory/party_transition_memory.py`
   - New service for retirement/return memory writes and retrieval packs.
2. `prompts/tabletop/retirement_narration.txt`
   - Departure narration prompt template.
3. `prompts/tabletop/return_narration.txt`
   - Re-entry narration prompt template.
4. `scripts/test_party_retirement_memory.py`
   - Focused integration test script for lifecycle memory behavior.

## Files to Modify

1. `web/routes/tabletop_party_routes.py`
   - Extend remove/add endpoints for memory + narration orchestration.
2. `web/static/js/tabletop_mode.js`
   - Capture optional farewell text on retire action.
3. `utils/pc_manager.py`
   - Add helper(s) for role-history append on retire/return.
4. `core/memory/__init__.py`
   - Export new transition-memory service API.
5. `core/ai/cumulative_summary.py` (optional mirror)
   - Optionally mirror retirement/return summary entry to journal pipeline.

## Data Contract

### API: Retire Character

Endpoint: `POST /api/party/remove_character`

Request body:

```json
{
  "character": "Acheron",
  "departure_text": "I stay in this Keep as its Lord. See you lot later!"
}
```

`departure_text` is optional. Blank means mysterious departure style.

Response additions:

```json
{
  "success": true,
  "partyMembers": ["..."],
  "retirement_event_id": "evt_...",
  "narration_queued": true
}
```

### API: Return Character

Endpoint remains `POST /api/party/add_character`.

Response additions:

```json
{
  "success": true,
  "partyMembers": ["..."],
  "return_event_id": "evt_...",
  "narration_queued": true
}
```

## DB Write Rules (Authoritative)

For retirement event:

- `memory_events.event_type = "role_transition"`
- `summary` includes clear retirement sentence
- `importance = 95`
- `persistence_class = "identity_core"`
- `decay_profile = "none"`
- `priority_active_pc = 1`
- `pinned = 1`

Links:

- Departing PC linked as `actor`.
- Active party NPCs and remaining PCs linked as `witness`.

Entity state:

- `entities.is_retired = 1` on leave.
- `entities.is_retired = 0` on return.
- Close prior active `entity_roles` rows and open new role row (`retired_player` on leave, `player` on return).

## Step-by-Step Execution (Kimi Builder)

### Step 0 - Preflight and Non-Breaking Guardrails

1. Add strict guard in route: block retirement if combat is active (`worldConditions.activeCombatEncounter` non-empty).
2. Block retiring the last remaining party member.
3. Keep failure-isolated behavior: if memory write fails, party removal/add still succeeds with warning logs.

Acceptance:

- Existing remove/add still work without DB.
- No crash paths if memory DB unavailable.

### Step 1 - Build Transition Memory Service

Create `core/memory/party_transition_memory.py` with functions:

1. `record_pc_retirement(character_name, party_tracker, departure_text="") -> Dict[str, Any]`
2. `record_pc_return(character_name, party_tracker) -> Dict[str, Any]`
3. `build_return_memory_pack(character_name, party_tracker, limit=8) -> Dict[str, Any]`

Implementation notes:

- Use `create_memory_event` and `create_memory_link` from `core/memory/memory_db.py`.
- Generate deterministic event IDs with normalized name + timestamp hash.
- Add robust `try/except` with categorized logging (`memory_ingest`, `tabletop_mode`).

Acceptance:

- Returns event IDs and status dicts.
- Handles missing DB gracefully (no exception escape).

### Step 2 - Route Hook: Retirement

Modify `web/routes/tabletop_party_routes.py` (`remove_party_character`):

1. Parse optional `departure_text` from request JSON.
2. Load pre-removal party context (for witness linking and narrative context).
3. Call `record_pc_retirement(...)` before or immediately after `pc_manager.remove_pc(...)`.
4. Append `_tabletop_role_history` event in character file (`retired_from_party`).
5. Build retirement narration prompt from new template and enqueue via `user_input_queue`.

Acceptance:

- `x` action retires PC, queues narration, and writes memory event.
- Blank `departure_text` yields mysterious departure narration.

### Step 3 - UI Hook: Optional Farewell Text

Modify `web/static/js/tabletop_mode.js` (`retireCharacter`):

1. Keep existing confirmation.
2. Add prompt input for optional farewell line.
3. Send `{ character, departure_text }` payload.
4. Preserve existing reload behavior on success.

Acceptance:

- User can submit explicit farewell or empty text.
- Existing retire UX remains simple and fast.

### Step 4 - Prompt Templates

Add `prompts/tabletop/retirement_narration.txt`:

- Inputs: character name, location/area, departure text, remaining party, key memory hints.
- Instruction to include party NPC emotional reactions consistent with known relationships.

Add `prompts/tabletop/return_narration.txt`:

- Inputs: returning PC, retirement/return milestones, social memory snippets, current location.
- Instruction to narrate recognition and continuity.

Acceptance:

- Prompts produce narration-only output.
- Works with and without rich memory pack.

### Step 5 - Route Hook: Return/Rejoin

Modify `web/routes/tabletop_party_routes.py` (`add_party_character`):

1. After successful `pc_manager.add_pc(...)`, call `record_pc_return(...)`.
2. Fetch memory context using `build_return_memory_pack(...)`.
3. Generate return narration prompt and enqueue into `user_input_queue`.
4. Append `_tabletop_role_history` event (`returned_to_party`).

Acceptance:

- Re-added character triggers memory-aware return narration.
- NPCs can reference prior relationship moments.

### Step 6 - Optional Journal Mirror (Compatibility)

Optional but recommended:

1. Mirror concise leave/return summary into `journal.json` as campaign milestone.
2. Keep mirror best-effort only; DB remains authority.

Acceptance:

- Journal drift does not affect retrieval correctness.
- No duplicate journal spam on repeated retries.

### Step 7 - Test Coverage

Add `scripts/test_party_retirement_memory.py` covering:

1. Retirement writes `role_transition` with `identity_core` and `pinned=1`.
2. Return writes second `role_transition` and clears `is_retired`.
3. Prior events remain queryable via `get_retirement_return_memories`.
4. No memory purge side-effects in DB tables.
5. Route flow continues when DB missing/unavailable.

Also run existing memory regressions:

- `python3 scripts/test_memory_regression_coverage.py`

### Step 8 - Manual Smoke Checklist

1. Start game with 2+ PCs and known party NPCs.
2. Retire one PC with explicit farewell text.
3. Confirm narration includes departure and NPC reaction.
4. Re-add same PC via Add Existing.
5. Confirm return narration references prior relationship context.
6. Verify DB rows exist and are linked to relevant entities.

## Validation Commands

```bash
python3 -m py_compile web/routes/tabletop_party_routes.py web/static/js/tabletop_mode.js core/memory/party_transition_memory.py
python3 scripts/test_party_retirement_memory.py
python3 scripts/test_memory_regression_coverage.py
```

## Logging and Diagnostics

Add structured logs:

- `TABLETOP_RETIRE action=apply character=<name> event_id=<id> status=<ok|degraded>`
- `TABLETOP_RETURN action=apply character=<name> event_id=<id> status=<ok|degraded>`

This supports quick diagnosis in `debug/logs/live_chat_monitor.json` and standard log flow.

## Rollback Plan

If issues appear:

1. Disable memory write calls in route layer (keep party add/remove behavior).
2. Keep narration prompt queueing active with fallback generic prompt.
3. Preserve DB rows already written (no destructive cleanup required).

## Suggested Commit Sequence

1. `feat(memory): add party transition memory service for PC retirement and return`
2. `feat(tabletop): wire retire and rejoin routes to memory and narration hooks`
3. `feat(ui): add optional farewell text input to retire character action`
4. `test(memory): add retirement return lifecycle integration coverage`

## Definition of Done

1. PC retirement does not purge NPC/world memory.
2. Departure and return both narrate through LLM with context.
3. Retirement/return transitions are persisted in `memory.db` and retrievable.
4. Rejoining PC triggers NPC recall continuity in narration.
5. All new paths are failure-isolated and backward compatible.
