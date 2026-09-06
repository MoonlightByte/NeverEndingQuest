# Travel and Transitions

Purpose: Convert one accepted travel intent into a canonical destination commit,
recoverable departure effects, and one destination-grounded narrated arrival.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Authority table

| Datum | Single source of truth | Commit or acceptance point |
|---|---|---|
| Immediate intent and action family | Accepted T067 `actions[]` | T065 and route approval precede processing |
| One-beat semantic boundary | T065 exact verdict | Invalid candidate returns to T067 correction with no mutation |
| Route and topology | Request-bound `ApprovedTransitionPlan` from active-module disk | Identity reverified under transition lock before movement |
| Current location | `party_tracker.json.worldConditions` | Atomic destination write occurs before departure effects/prose |
| Recovery progress | `pending_location_transition.json` v2 checkpoint | Receipt advances after each durable step; removed after completion |
| Origin departure | Checkpoint preimages plus canonical origin area/journal | Receipt-based reconcile after movement |
| Player-facing travel prose | Committed destination/roster and retained narration identity | T013/T063/T064 retained, projection-checked, then published |
| Conversation atlas | Fresh rendering of current module area files | Advisory T067 context only; not movement authorization |
| Cross-module target | Canonical target-module projection | Root checkpoint then party-module transition publication |

## Flow

### Within-module travel

1. T067 returns the structured response.
2. Normalize the supported action envelope, retaining nonmovement tracker fields.
3. The shared current-module snapshot supplies identity labels and route preflight;
   T021 is used only for the existing ambiguous intermediate-encounter class.
4. T065 validates semantic intent and the single-beat boundary against those
   provisional route facts. Every corrected candidate passes these checks again.
5. The existing transition publisher stages its v2 checkpoint. The draft is not
   independently published as accepted history before movement freshness succeeds.
6. Travel-owned sibling receipts are prepared outside the mutation lock.
7. Under the lock, code rederives plan identity and commits `party_tracker.json` to the
   destination first.
8. Origin area/journal departure effects reconcile from checkpoint preimages.
9. T013 builds departure/transition from committed updated context.
10. T063 builds arrival from the exact committed target, roster, and T013 layer.
11. T064 stitches both into one player-facing turn and asks for the next immediate action.
12. Code rechecks destination projection, retains/publishes narration, applies only staged
    travel siblings, and removes the correlated checkpoint.

### Single-turn boundary

1. `transitionLocation` must be unique and action index zero.
2. Only movement and approved travel-owned `updateTime`/`updatePlot` siblings belong to the beat.
3. Shopping, resting, saving, exiting, and other future clauses remain deferred player intent.
4. Cross-module travel is the exact pair `updatePartyTracker` then one intrinsic `updateTime`.
5. T013/T063/T064 remain one complete narration chain inside that single player turn.

### Crash/restart

1. Recovery compares the checkpoint with canonical party location.
2. Origin plus planned state retires/replans; committed destination resumes existing receipts.
3. Resume completes origin reconciliation, T013/T063/T064, history compaction, staged siblings,
   final context, and stable publication in checkpoint order.
4. Operation-ID correlation prevents an unrelated transition from clearing the checkpoint.

### Atlas and gate

- `build_active_module_snapshot` supplies detached source records to the atlas,
  validator and route preflight. `areas/*.json` retains structurally valid non-regex
  filenames; existing legacy-root precedence remains. Backup-only labels are
  separately marked reference-only and never enter live routes.
- Ordinary DM request preparation replaces the atlas even when no module completion
  was drained. The resulting request-local snapshot is shared with T065/preflight.
  Compression retains this separate system block; actual payload acceptance is required.
- The same preparation renders installed foreign-module identity references once
  for both T067 and T065. Registry module keys nominate candidates; canonical area
  files supply module-qualified labels and source diagnostics, never foreign edges
  in the local route graph. Missing references do not establish global absence.
  Actual cross-module movement still requires target lookup and commit checks.
- Area descriptions and eligible NPC-name lists are not truncated. Source diagnostics
  stay visible to the model; the atlas itself never grants movement or disclosure.
- `build_active_module_snapshot` keeps duplicate and dangling-link problems explicit and gives
  each source an identity.
- Path finding and encounter analysis derive the route plan from that snapshot.
- `pre_validate_transition` deliberately does not build a second legacy global atlas.
- The plan is rederived and identity-compared immediately before mutation.
- Both default and explicit cross-module targets must match actual live records;
  a cached starting pair is a proposal, not authority. Starting-location inference
  itself is unchanged (separate #308).
- Precommit travel freshness rejection returns to the same detached correction loop,
  retaining semantic constraints and revising the latest candidate. It does not use
  the bounded generic regeneration shortcut or retain rejected narration/voice effects.
- Temporary read contention waits outside the party lock and remains cancellable.
  D-303-2 permits only an unverified move to be refused for permanent unreadability:
  preserve files/position, explain truthfully without a fictional obstacle, and
  return control for another action or Load. Committed travel still resumes its
  existing receipts; no new crash store or movement replay is introduced.

These #303/#307 changes are an implementation-worktree description, not a native
acceptance verdict. The verification pin above describes the historical baseline.

## State and atomicity

- Stores: `party_tracker.json`, transition checkpoint, origin area JSON, `journal.json`, main
  conversation history, and optional staged episode/chronicle/handoff records.
- `safe_json_dump` publishes each JSON by same-directory temp, fsync, and `os.replace`.
- The workflow is multi-file, not one rename; the checkpoint carries preimages, phases, stable
  message IDs, deferred cursor/operation IDs, and before/after projections for convergence.
- No provider call runs under the party/module mutation lock.
- T063/T064 run unlocked; canonical destination is locked and rechecked before display/save.

## Load-bearing seams

1. `main.py:6665` - physical T067 call.
2. `main.py:3350-3373` - T065 verdict and reissue boundary.
3. `main.py:8754-8877` - semantic acceptance before route authority.
4. `core/ai/action_handler.py:1871-2124` - route prevalidation and immutable plan.
5. `utils/path_encounter_analyzer.py:160-235` - active-module disk snapshot.
6. `core/ai/action_handler.py:2140-2206` - plan identity revalidation.
7. `core/ai/action_handler.py:3467-3611` - checkpoint, proposals, locked movement receipt.
8. `core/managers/location_manager.py:486-546` - destination-first commit.
9. `main.py:4981-5050` - movement execution and suffix staging.
10. `main.py:5232-5283` - committed-context chain and supersession recheck.
11. `main.py:1263-1310` - T013 departure layer.
12. `main.py:1341-1412` - T063 arrival layer.
13. `main.py:1462-1515` - T064 stitch and handback.
14. `main.py:1829-2224` - v2 resume and checkpoint completion.
15. `core/ai/conversation_utils.py:609-636` - fresh advisory atlas injection.

## Invariants

- #193 Part 1, Prime Directive, B1/B2, AP-1..AP-7, evidence, and lineage.
- #193 Part 2, World registry; Module generation; Conversation; Save/restore/reset;
  Provider routing; Schema; Acceptance.
- #193 Part 5, D-TRAVEL-2 and No-Limits.

## Open items

- #187/#194/#195 - world-state loss, atlas gate, and intermediate-stop correction.
- #196/#197/#237/#238 - post-commit summary, deferred action, and departure recovery.
- #198/#209 - episode capture overlap and travel/voice reintegration.
- #199/#211/#248 - startup recovery before or across first control.
- #247/#249 - T091 receipt overwrite and non-fail-forward terminals.
- #264 - typed combat flee into previously visited travel space.
