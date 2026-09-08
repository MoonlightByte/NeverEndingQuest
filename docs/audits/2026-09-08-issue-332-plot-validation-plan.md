# Issue 332: canonical plot evidence at semantic review

Status: proposed; independent review pending; implementation NOT authorized.
Authority: live GitHub #193 v3.1, updatedAt 2026-09-08T22:46:16Z.
Scope authority: owner selected #332 after the recommendation to investigate,
write and review a plan before implementation. No production edit, live run,
commit, push or merge is part of this planning phase.

## 1. Goal and boundary

Supply T065 with the current module's committed plot facts so it can distinguish
an existing quest from an invented one without approving unsupported progress.
Models retain interpretation and semantic adjudication; code supplies canonical
data and retains existing identity, schema, currentness and write boundaries.
No extra model, new registry, cache, store, migration, setting, timeout, heuristic
or broad context activation. No change to T067, T077, travel or plot writers.

Planning worktree: /home/loup/neq-worktrees/332-plot-validator-plan
Branch: docs/332-plot-validator-plan. Mainline evidence at investigation:
6916507c74d4bbb4795ad9529a69d33c3ce4efe0. Re-fetch and verify ancestry at gates;
this revision identifies inspected bytes, not runtime authority. WSL-created
worktree; never prune foreign-OS registrations. Native acceptance uses a separate
native-valid source export/checkout and isolated game, never the live user game.

## 2. Evidence and root cause

OBSERVED: /mnt/c/322-game-IbP7La/debug/api_captures/api_calls_master.jsonl:
- 524: T067 has PP005 in system message 4 and generated DM note 73. It proposes
  updateTime(5) and updatePlot(PP005, in progress) with new rumor claims.
- 525: T065 has PP005 only in candidate message 54. Its exact verdict is:
  "The response invents and updates plot point PP005 without any supplied
  plot-point data establishing that ID. It also presents new reports about
  strange lights, animal avoidance, and bandits as established facts without
  grounding. The five-minute updateTime action and the use of Cira, Thane, and
  Elen at the inn are otherwise valid."
- 526: correction removes updatePlot and the specific rumor claims.
- 527: T065 accepts time-only correction. The turn completes, but the ID-specific
  reason was false. This does NOT prove the original whole candidate was valid.
Selected model in these rows is gpt-5.6-luna; response.model is absent, not inferred.
Previous native verdict root: local-data/322-acceptance-oZxruI/A2-A5-continuation.

CODE-PROVEN chain on inspected main:
1. conversation_utils.py:832-835 supplies format_plot_for_ai(plot_data) to DM.
2. main.py:8984-9021 adds location and active-module plot IDs to the DM note.
3. main.py:3080-3128 intentionally selects accepted dialogue, excludes system
   context, removes generated DM notes and rejected correction history.
4. validate_ai_response at main.py:3232 builds its own location/module/NPC
   evidence; main.py:3480-3598 contains no canonical plot injection.
5. Prefix compression runs before hub evidence and exact raw-user/candidate
   assembly. The right repair is evidence supply AFTER compression, NOT undoing
   history sanitization or copying the enhanced DM note into authority.
6. ModulePathManager.get_plot_path (utils/module_path_manager.py:132-134) resolves
   modules/<module>/module_plot.json. The existing validation path_manager comes
   from the supplied party snapshot (main.py:3285). Never choose module from a
   candidate parameter, NPC name, location prose or default-module guess.
7. updates/plot_update.py:44-123 already resolves parent/main and side-quest IDs
   and permits only the requested status/impact delta. The staged travel entrant
   (action_handler.py:711) prepares before movement and applies its existing
   receipt (1140 onward); the ordinary writer owns its existing source recheck,
   schema and write. This plan changes none of those behaviors.

Lineage: history filtering is present in 715732d5 (provider-aware game runtime);
be4df1cb (#262) preserves complete history. addf3809 supplies only canonical hubs.
Do not blame #322 for introducing the older missing-plot evidence boundary.
The DM formatter (utils/plot_formatting.py) has existed since older mainline:
it omits side-quest IDs and omits some stored fields/status representations.
That makes it unsuitable as a lossless validator identity source; no formatter
rewrite is needed to fix #332, and its DM presentation remains unchanged.

## 3. Spec pin and architectural contract

#193 Part 2 p8 NEQ-WORLD-03/04: module bubbles and progression consequences.
p12 NEQ-SCHEMA-01/02: frozen schemas, preserve player data.
p11 NEQ-PROVIDER-01/02: unchanged calls/routing, measure added input tokens.
p10 NEQ-WEB-01/03: no new thread/lock/wait; acknowledge input and preserve status.
p13 NEQ-ACCEPT-01..03, NEQ-TEST-02: real provider-backed serial acceptance.
Schematics read: docs/architecture/module-lifecycle.md and progression-leveling.md.
Their historic pins are orientation, not present-code proof. The new evidence
seam will be documented as a narrow delta in module-lifecycle.md; historical
acceptance statements are not silently relabeled. README introduction promises
remembered decisions and adaptive adventures; this fixes unjustified rejection
without making authored future events completed or player-known.

| Datum | Authority and boundary |
| --- | --- |
| Module scope | supplied canonical party snapshot, same as existing review |
| Plot IDs, statuses, side quests, authored descriptions | that module's live module_plot.json |
| Player intent | exact raw user turn, not generated DM note |
| Candidate | proposal only; never canonical evidence |
| Semantic verdict | existing T065, with existing correction path |
| Mutation | existing T077 target/delta/schema/source checks and commit |
| Cancellation | existing invocation/LiveTurnScope checks; no new owner |

## 4. Smallest proposed implementation

Production allowlist: main.py only. Documentation: this plan, review/execution
records, and docs/architecture/module-lifecycle.md. No tracked test edits.

Inside validate_ai_response, after existing prefix compression and hub evidence,
before review_feedback/_assemble_validation_messages:
1. Use the existing nonempty module_name and path_manager.get_plot_path(). If
   module identity is absent, do not use ModulePathManager's default fallback.
2. Read UTF-8 JSON directly without a manager constructor/recovery pass. For a
   dictionary with list-valued plotPoints, serialize the COMPLETE object with
   json.dumps(ensure_ascii=True); no recency/length/status/location filters.
   Do not run a new schema admission gate or normalize nested data. Existing
   schemas and writers stay the authority; raw stored values are evidence.
3. Append one system message with the module identity and JSON, under this
   exact proposed instruction:
   "Canonical plot data for the current module follows. Use its recorded IDs,
   statuses and plot impacts when reviewing this candidate. Authored descriptions,
   objectives and future outcomes are scenario context, not proof that an event
   occurred, a quest completed, or the party learned a hidden fact. Judge the
   proposed change against the player's immediate action and established events;
   the existence of an ID alone does not authorize a progression update."
4. Missing file/identity, unreadable UTF-8/JSON, nonobject root or nonlist/missing
   plotPoints yields a failure-class WARN and one evidence note:
   "Canonical plot information is unavailable for this review. Missing evidence
   does not establish that a proposed plot ID is invented, nor authorize a plot
   update. Review against the remaining supplied facts."
   Catch only OSError/UnicodeError/JSONDecodeError for the read. Do not catch
   supersession or other control exceptions. No repair, creation, retry counter,
   rejection, forced approval or state write in this read. An empty plotPoints
   list is valid evidence and must be distinguished from unavailable evidence.
5. Existing raw-user/candidate adjacency, local template tail, NPC voice context,
   SRD evidence, currentness checks and correction-history isolation unchanged.
   Each fresh review rebuilds evidence; no reuse across Load/module transitions.

Why raw JSON: the existing pretty formatter is lossy for SQ identity. JSON
serialization reuses the existing library, adds no public helper or secondary
runtime, and keeps original field values available to the reviewing agent.
No hardcoded PP005, title matching, prose parsing or digest authority.

## 5. Slices and review gates

C0: verify live policy epoch/ancestry; recover full sent validation system prompt
and all attempt payloads from rows 524-527 into local evidence; freeze production
and fixture prompt hashes, provider binding and EOL inventory. Read the current
gameplay guidelines. No implementation until review and owner presentation/go.
C1: one main.py additive evidence block as section 4; no unrelated cleanup.
C2: pure JSON/file/assembly primitive checks, py_compile and pyflakes undefined
name gate; independent simplifier; document the seam; review actual diff and
both sentinel scans. New failure handling triggers FULL review (not LITE).
C3: serial real native OpenAI acceptance below; stop/report defects without
repairing unrelated issues. Independent PX reviews transcript against disk.
C4: post-implementation five-verdict audit (#193 NEQ-REVIEW-15); owner presents
acceptance/limits before any publication or merge. No automatic issue closure.

FULL seats: Custodian, Fail-Forward, Acceptance, Consumer/Compat (entry point),
PX (review prompt), Leanness (new evidence admission branches), No-Limits,
Single-Path. Legacy-Contract conditional: no deletion/replacement proposed;
escalate if implementation alters an existing branch. Schema-Freeze: no schema
changes, verify diff; Platform/Provider and Hygiene mandatory. Reviewers read
same plan and full ledger independently; controller single writer. Three runtime
slots mean seats are dispatched in independent concurrent waves, not combined.
No gameplay probes in parallel. Current review status: PENDING, not a pass.

## 6. Behavioral preservation / FS-1

| Existing behavior | Lineage | Disposition and proof |
| --- | --- | --- |
| Sanitized dialogue, generated-note exclusion | 715732d5, be4df1cb | PRESERVED: raw-pair/history comparison A1/A3 |
| Current hub evidence | addf3809 | PRESERVED: bytes retained, A1 request capture |
| T065 reject/correct before publication | existing validate_ai_response/process pipeline | PRESERVED: A3 |
| Plot target/delta/schema/source guards | updates/plot_update.py | PRESERVED byte-identical, A2/A3 |
| Provider scopes/Load cancellation/travel staging | existing main/action_handler | PRESERVED byte-identical, A4 |

No existing branch is retired; obtain exact blame for any proposed replacement
before implementing it. FS-1: no numeric bound, timer, wait, provider call or
lock is added. Unavailable evidence continues through existing adjudication;
the new block does not own or suppress any mutation verdict. Measure raw diff
and touched-file sentinel hits; inherited unrelated hits remain separate, never
silently remove them to produce a clean grep. Schemas remain byte-identical.

## 7. Acceptance, specified before code

Authentic fixture: copied official Keep_of_Doom + The_Thornwood_Watch campaign
from #322 acceptance, before the Cira greeting. Preserve original. Native-valid
code export and refreshed prompt files from candidate; OpenAI configured and
recorded from actual bindings, no model substitutions. Use run_headless.py serve
with its existing client/relay, one command then read/decide. No synthetic model
output, fabricated captures, save edits, batched player commands or new harness.
Record response.model as absent when absent. Hashes are evidence only.

A1: real Cira greeting on fresh copy, same immediate command as row 524. At T065
capture parse new evidence JSON and compare entire object to pre-turn module
file, including PP005 and nested SQ IDs. Raw intent/candidate exact and adjacent;
hub map still present. No false ID-absence objection. If DM emits no updatePlot,
context-supply may PASS but positive update gate is NOT-REACHED, not PASS.
A2: continue naturally to an evidenced quest-progress action (main and SQ as
reachable). Capture T067/T065/T077 and disk before/after. Only requested target
status/impact changes; siblings, authored facts, characters and memories retained.
An unvisited SQ mutation is NOT-REACHED; its inclusion in evidence is separately
checked. No forced completion, reward or quest ID supplied as test instruction.
A3: real player asks to claim an unearned quest reward/completion without doing
the objective, clearly as immediate player intent. Read actual answer and disk.
T067 refusal can PASS player safety but T065 rejection is NOT-REACHED unless an
actual candidate reaches and fires it. Natural rejected-candidate correction
must retain canonical evidence and publish only accepted content. Fake-ID and
unavailable/malformed evidence variants use pure backend JSON/I/O checks only;
never label these as real gameplay proof. Do not inject synthetic candidates.
A4: Save, one quiet turn, Load, restart and one next turn; prove restored module
plot evidence rather than stale other-module history; normal action and prompt
continue. A natural cross-module travel leg if needed to reach the scope-change
boundary must retain T013/T063/T064 and select the new module, not both bubbles.
Cancellation during validation only if naturally reached; otherwise NOT-REACHED.

Backend checks: missing/nonobject/nonlist/empty plotPoints; non-ASCII/long fields;
all main/SQ statuses and nested values survive serialize/parse; unknown ID never
inserted; no writes in evidence read; no default-module read; prefix/candidate
separation; old plot files validate unchanged. Deterministic tests local/untracked.
Do not import provider/game engines as a fake-player test.

Every arm reports PASSED/FAILED/BLOCKED/NOT-REACHED per boundary; per-call capture
rows, actual payloads, input-relative timings and prompt hashes, verbatim player
text, before/after disk, fallback/omission counts, orderly shutdown/orphan receipt.
Report added context bytes/tokens and latency, not merely a successful turn.
The report cannot promise all semantic judgments correct or all branches reached.

## Tracked follow-ups

- #331: hub readiness narration, unrelated; preserve its existing failure record.
- #326: naming/attribution, no new identity mechanism here.
- #329: XP validation context, separate; do not generalize this into an all-state
  reviewer framework or progression rewrite.
- #317/#318: module history fidelity and retention, no compression redesign here.

## Resolution ledger

| ID | Finding/decision | Resolution |
| --- | --- | --- |
| F1 | Real PP005 absent from reviewer authority | task-C1 |
| F2 | Pretty formatter omits SQ identities | task-C1: lossless raw canonical JSON, no formatter change |
| F3 | Original candidate also has unsupported reports | task-C3: retain rejection and separate factual verdicts |
| F4 | Candidate/system notes cannot become authority | task-C1: independent disk evidence after compression |
| D332-1 | Execution after reviewed-plan presentation | escalate:@owner; pending, blocks code |

No authority waiver requested. Findings outside scope are reported separately;
no product repair or public issue mutation is authorized by this planning step.
