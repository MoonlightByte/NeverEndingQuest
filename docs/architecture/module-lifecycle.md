# Module Lifecycle

## Issue 332 canonical plot review evidence (2026-09-08; scoped acceptance passed)

The existing T065 semantic review reads the supplied party snapshot's module
plot through ModulePathManager after prefix compression. It receives complete
stored JSON, including main and side-quest IDs, not the lossy DM presentation.
Authored objectives/future outcomes do not establish occurred events or earned
rewards; the reviewing model still adjudicates the immediate player action.
Missing/unreadable/invalid outer evidence is explicitly unavailable with a WARN,
never repaired, defaulted to another module, or turned into a forced verdict.
The raw player/candidate boundary, hub evidence, currentness and T077 writers
remain unchanged. This is an evidence-read seam, not a progression rules engine.
Native OpenAI acceptance and explicit unvisited branches are recorded in
../audits/2026-09-08-issue-332-execution.md. No all-model or all-prose guarantee.

## Issues 322/328 implementation delta (2026-09-08; acceptance pending)

The existing T039 call is instructed to emit the five established container
types and source-supported hub fields. Its structural validator is unchanged.
At the existing campaign importer, effective supplied fields overlay the latest
committed hub record; omission/null/blank/empty-object does not erase prior
facts, while explicit false/zero/lists (including empty services) remain updates.
Historical non-object hub facts use the existing details field losslessly when
an effective update occurs; reads do not migrate stored data.

Three live hub-context readers (conversation_utils world-state context, main
DM note, and semantic validator evidence) use format_campaign_hubs from
campaign_manager: complete stored JSON, no invented party ownership/type/services.
The validator reads campaign.json directly after prefix compression, before
the unchanged exact player/candidate pair. It does not construct CampaignManager
or run recovery. Absent data adds nothing; unreadable/non-object campaign data
adds an explicit unavailable-evidence note and WARN, never a manufactured verdict.
Other categories and availability
keep their existing pathways; get_campaign_context is not activated. T038,
archives, visit identity, T108, locking and summary publication are unchanged.
This supersedes only the export/import/hub-reader description, not historical
acceptance claims. Real acceptance is recorded separately; code alone is not PASS.

## Issue 311 implementation delta (2026-09-07; live acceptance pending)

The undefined-snapshot final-memory block is removed from the locked commit
helper. `complete_module` now captures the final origin episode after
`_complete_module_once` returns and releases all commit locks, before resolving
the leader flight. Ready-intent replay takes that same path; canonical-existing
memory completes its deterministic POV projection without another T108 call.
The child finishes before staged-intent cleanup or an accepted Save returns.
Final memory identity uses the returned committed visit count, including receipt
replay, rather than counting history markers; later visits cannot reuse the prior
visit's final episode. Existing old-coordinate records remain untouched.
Unavailable epoch observations at the six synchronous memory checks wait
interruptibly outside locks/provider requests; typed supersession still unwinds.
Regeneration remains summary-only; no historical-location facts are inferred
from the live destination. This supersedes only the #311 missing-input description
below, not the historical acceptance receipts or broader lifecycle contracts.

## #248 implementation candidate (2026-09-06; acceptance pending)

For startup with pending travel, the existing ordered completion drain runs under travel recovery authority. Structured failed work requests lifecycle choice; blocked/transient work continues waiting. Typed cancellation bypasses module-final advisory catches before outcome-marker completion/removal; already committed module data is not rolled back. Existing final-episode missing-input defect #311 prevents that T108 call on this baseline and remains a separate repair, not an acceptance PASS.

These statements describe the working implementation, not verified live acceptance.

Purpose: build and validate a complete hidden module, publish it through one directory rename, and finish cross-module campaign history through restartable archive and summary receipts.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

## Safety worktree delta (2026-09-05; live acceptance partial)

The approved combat/persistence safety implementation changes completion, not
module authorship or publication. `complete_module` and regeneration register an
attempt in the existing flight registry and stamp the existing work record with
producer identity and lifecycle epoch. Preparation and commit take short locks;
T038/T039 generation runs outside party/completion/campaign locks. Checkpoints,
commit and cleanup revalidate the exact work identity. A live or unobservable
producer is followed, never declared dead because its filesystem lock is free.

Regeneration reads the original archive without owning/removing it or incrementing
visits. Save settles work outside snapshot locks and rechecks at the snapshot.
Load/Reset reconcile canonical pending commits before replacing the epoch. Lost
unfinished work is allowed; no new crash snapshot or replay store is introduced.
Source and primitive checks are recorded in the execution ledger. Native live
completion has reached T038/T039, preserved the existing invalid-export fallback,
committed one archive/chronicle, and resumed at the destination. This is not a
successful structured-export verdict. Clean-save recovery after process loss is
also observed. Direct startup reclaimed the same interrupted T039 work/epoch,
reused stored T038, and committed once. A deliberate native same-campaign
competitor followed the live producer without another provider child or commit.
Native primitive tests separately cover unknown/mismatched/relinquished owners;
these are not claimed as live gameplay variants. The local
`validation_evidence/safety_acceptance_remaining.md` records exact S5-S7 limits.

T013/T063/T064 retain their successful departure/arrival/combined narration chain
and genuine-error fallback. Typed cancellation now unwinds instead of publishing
fallback travel prose after Quit. Actual T013 Quit and clean three-call resume
are recorded in `validation_evidence/safety_transition_cancellation_verdict.md`.

Creation narration borrows the existing turn or welcome authority. Its accepted
history and refreshed context are persisted under short checked party-lock
phases; completion draining and the shared DM request run outside the response
and party fences. Final history publication rechecks that same authority.
This does not add a provider call, change the request mode, or own a new scope.

## Authority table

| Datum | Source of truth | Acceptance or commit point |
|---|---|---|
| Requested module | Validated `ModuleCreationSpec` from explicit inputs plus optional T030 inference | Explicit validated values override inferred fields |
| Candidate contents | `ModuleBuilder` rooted at the publisher-assigned hidden path | Builder identity and path must still match before publication |
| Cross-area graph | Code-owned classic finalizer derived from the unified plot | Model-authored cross-area arrays are cleared before reciprocal links are written |
| Publication admissibility | Stitcher's hidden-candidate registry projection and safety verdict | Required files, identities, analyzability, and integration safety all pass |
| Live module | `modules/<allocated-name>` | `os.replace(candidate, final)` publishes the entire directory |
| Registry projection | Exact precomputed `world_registry.json` bytes | Advisory post-rename write; failure cannot unpublish the module |
| Completion order | Durable intent keyed by completion ID and transition sequence | Intent becomes ready only after party destination commit; oldest ready drains first |
| Module completion | Archive, T038 summary, T039 export or conservative fallback | Campaign pending marker governs the multi-file commit |
| Restart identity | Same-ID completion receipt, work marker, pending marker, and lifecycle epoch | Recovery resumes or rolls back the same operation |

## Flow

1. `createNewModule` validates its action and takes the module-refresh lock.
2. `_resolve_module_creation_spec` uses complete explicit inputs directly; otherwise T030 fills missing values.
3. The publisher allocates the final name and invokes the build in `modules/.module_build_<uuid>/<name>`.
4. The compatible builder creates party context/directories, asks T031 for the overview, builds areas and locations through T022-T027 as required, builds area plots with T036/T037, asks T028 for the unified plot, finalizes cross-area links in code, builds NPCs/monsters through T035/T034 as required, reconciles identities with T088, validates, and may run T104 coherence.
5. T029 and T032/T033 are adjacent generation/stitching capabilities; they are not unconditional steps in every create run.
6. The optional story-first branch runs T098 outline, T099 area binding, T100 plot derivation, T101 NPC repair, T102 hardening, and T103 creature compilation, retaining T026 location fill. At this revision it is config/env gated and defaults off; model-limitation failure retries once with a fresh compatible candidate.
7. The builder confirms the candidate stayed at the assigned path and ensures `module_plot` exists.
8. The stitcher operates only on hidden files, resolves IDs against the live registry, creates travel narration and exact registry bytes, and requires `safety.allows_integration`.
9. The publisher fsyncs the candidate/workspace, proves the final path is still absent, and atomically renames the directory into place.
10. After publication, parent-directory sync, registry write retry, and workspace cleanup are advisory and best effort. No post-commit failure may turn the published module into an error result.
11. A cross-module transition durably stages a prepared completion intent before party publication and marks it ready only after the destination is proven.
12. The player-facing travel response is saved first. Main then drains staged module completions; startup also drains them before ordinary narration/context.
13. The oldest ready intent enters `complete_module`. A same-process future coalesces the same identity and file locks serialize other processes.
14. Recovery first resolves any campaign pending marker and module work marker. A valid same-ID receipt returns the committed result.
15. New work records its archive path before writing the archive, then checkpoints the archive fingerprint, T038 narrative summary, and T039 relationships/artifacts/hubs/world-state export. Invalid export uses a conservative tracker-derived fallback and records failure.
16. Under the campaign transaction lock, summary, campaign projection, and optional receipt are snapshotted in `pending.json`, atomically replaced, and verified. Failure restores every preimage; success marks work committed and removes pending state before best-effort cleanup.

## State and atomicity

- Build state lives in `modules/.module_build_<uuid>/`, the final module directory, `world_registry.json`, and the generated module files.
- Candidate files may be replaced independently while hidden. The directory `os.replace` is the sole live-publication commit; registry publication is intentionally outside it.
- Completion state includes the tracker, durable completion intents, per-module `.work.json`, completion receipts, campaign `pending.json`, conversation archives, module summaries, and `campaign.json`.
- The module-refresh lock protects build/registry preparation. The party-transition lock orders destination publication and intents. Per-module completion and campaign transaction locks order summary recovery and commit.
- T038 and T039 run before the final campaign commit lock; no provider wait is held under that lock.
- Campaign pending state contains all target preimages. A failed multi-file projection moves to rollback-required and restores them.
- The lifecycle epoch prevents a completion from an obsolete Load/Reset timeline from committing.
- `utils/module_lifecycle.py` and managed-builder lifecycle code remain in the tree, but the live create path uses `utils/module_publish.py`; old manifest/WAL code is not publication authority.
- Publication and campaign completion are separate transactions: a published module does not imply that a later departure summary has committed.
- Registry failure after directory publication is repairable advisory drift; it is not permission to remove or rebuild the live module.
- Startup treats an unresolved ready completion intent as load-bearing recovery work and does not narrate past it.

## Load-bearing seams

1. `core/ai/action_handler.py:3871-4184` - create action, lock, builder call, and result.
2. `core/generators/module_builder.py:105-187` - shared build boundary and fresh fallback candidate.
3. `core/generators/module_builder.py:471-545` - compatible builder stage order.
4. `core/generators/module_builder.py:2902-3028` - explicit/T030 spec authority and branch selection.
5. `core/generators/module_builder.py:2006-2105` - final context, T088, and validation.
6. `core/generators/module_builder.py:2496-2560` - code-owned cross-area links.
7. `core/generators/module_stitcher.py:3118-3278` - hidden-candidate safety and registry bytes.
8. `utils/module_publish.py:283-392` - hidden workspace and atomic directory publication.
9. `core/managers/campaign_manager.py:1776-1908` - intent-before-transition publication.
10. `core/managers/campaign_manager.py:2038-2405` - prepared/ready intent lifecycle and ordered drain.
11. `core/managers/campaign_manager.py:2468-3077` - archive, T038/T039, recovery, and transactional commit.
12. `main.py:6295-6327` and `main.py:7135-7154` - post-response and startup completion drains.

## Invariants

- See #193 Part 1 for B1/B2, AP-1 through AP-7, leanness, evidence, and lineage.
- See #193 Part 2 pages 1, 3, 8, 9, 11, and 12 for atomic publication, module ownership, completion history, lifecycle recovery, providers, and compatibility.
- See #193 Part 5 for Always Live, Single Path, and No-Limits rulings. The config-gated story-first branch above is observed baseline behavior, not a second policy authority.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- Active module behavior: #182, #204, #217, and #224.
- Provider/platform consistency: #166.
- Issues #140, #141, and #143 describe older manifest/allocation/backup-resume concerns; reconcile those trackers with the current publisher rather than treating the old lifecycle as live authority.
