# Independent feature and architecture review loop

Scope: completeness and implementability of the full Ember port plan against the
public codebase and locked visual goal. Clean review means no unaddressed planning
findings; it does not mean code is implemented, regression-free or visually signed
off. Implementation discoveries reopen this review.

## Reviewer inputs

- Public worktree and baseline: `/mnt/e/NEQ-ember-public`, public main
  `5fe14683f2c2edfae447249c44e10b501b8c074c`.
- Server presentation donor: `/mnt/e/NEQ-ember-desktop`, read-only; never import
  private runtime contracts/history by assumption.
- Locked visual goal, which both reviewers must personally view:
  `/mnt/e/NEQ-ember-desktop/docs/design/ember-desktop/05-ember-inline-stacked.png`.
  SHA-256 `5ea38d43b52b6119894b0796f68087a233977e2dc79d7aaa44c6a987d2c76464`.
- `PORT-PLAN.md`, `INTERACTION-PARITY-AUDIT.md`, current implementation and legacy
  public templates/handlers. Gallery is a generally approved direction, not a
  complete child-state specification.

## Loop procedure

1. Feature reviewer traces data, triggers, detail fields and reachable screens;
   architecture reviewer traces ownership, contracts, lifecycle and isolation.
2. Record findings with code evidence and explicit acceptance criteria. Distinguish
   public regressions, shared donor limitations and incomplete specimens.
3. Update the plan; return revised files to both reviewers for independent closure
   or further findings. Do not silently downgrade a finding to obtain clean status.
4. Log final findings/status and commits. Implementation work must later meet the
   tests and personal visual checks; final owner approval is never delegated.

## Required loop during implementation

Repeat independent feature-development and architecture review after each
substantive implementation batch and again before handoff. Give both reviewers
the locked image, relevant approved additional-screen target, actual browser
captures, current diff, public source owners and applicable transition gates.
Feature review checks field/action/hover/media completeness; architecture review
checks public compatibility, state/event ownership and lifecycle. Fix code findings,
rerun affected tests and personally inspect updated captures, then return the
changed code for re-review until no unaddressed findings remain for that batch.
Record residual unimplemented scope rather than certifying the entire product
from one batch. A new discovery updates the plan and reopens its acceptance gate.

## Review rounds

Round 1: both reviewers confirmed personally viewing the locked image. Feature
review returned F1 inventory continuity, F2 portrait propagation, F3 live child
details, F4 asynchronous hover/media arbitration. Architecture review returned A1
breakpoint ownership, A2 media freshness/races, A3 audio coordination, A4 overlay
stack and A5 standalone/static deployment. None were rejected or waived.

All nine findings are addressed as explicit pending implementation/verification
requirements in `TRANSITION-GATES.md`, linked from the main plan. Overlapping
findings share gates but retain IDs. Round 2 will independently re-review these
revisions and check for remaining planning omissions.

Round 2: architecture reviewer independently rechecked code owners and closed
A1–A5 with no further uncovered architectural planning findings. Feature reviewer
closed F1–F4, but identified F5: canonical/alias spell lookup and explicit supplied
metadata coverage. F5 was added to `TRANSITION-GATES.md` with Acid Arrow/Melf's
Acid Arrow alias cases, full casting metadata and player/NPC/scroll tests. Sent
back for a third feature review; no product or visual approval is implied.

Round 3: feature reviewer re-read the revised endpoint/normalization and metadata
requirements and reported no unaddressed feature-planning findings. F1–F5 are
closed at planning level. Architecture A1–A5 remain planning-clean from round 2.
Both reviewers personally viewed the exact locked image. Ten identified findings
are retained as mandatory pending implementation/verification gates; none were
removed to achieve closure. Code, visual parity and final owner approval remain
incomplete. No production code or tests were changed during this planning loop.

## Implementation batch 1 — inventory/spell inspection

Feature and architecture agents reviewed the actual code against the locked image.
Round 1 found hover-only Escape, pinned-focus theft, metadata grid mismatch and
missing item subtype/level. All were fixed with browser tests. Round 2 source
review was clean; subsequent visual review found inherited orange spell summary
text, which was corrected and recaptured. Both agents then personally inspected
the final inventory/spell captures and closed this bounded review. The main agent
also inspected the final captures. Results and remaining scope are in PROGRESS.
This batch does not close all transition gates or the final owner review.
# Full-screen implementation review checkpoint — 2026-09-05

Independent architecture review corrected B1 nonmodal inspection/focus semantics,
B2 nested portal/in-root inertness and visual stacking, B3 stale audio completion
ownership, and B4 settings-only voice-disable cancellation. A subsequent review
removed unnecessary artwork invalidation on unchanged tab visibility. The latest
bounded architecture pass reports no remaining blocker in those inspected fixes.

Independent feature review found unscrollable long feature/stat tooltips, missing
NPC scroll metadata, absent asset-pack invalidation, unregistered inventory search,
inaccessible toolkit confirmations, and incomplete preview fixtures. These now
have implementation and targeted tests. Toolkit review additionally corrected
false success on failed generation, unverified export-completion claims and
populated phone table/toast overflow. Its bounded implementation check is clean;
a fresh independent feature audit and primary-agent final visual pass remain open.

Actual browser testing after source review also found and fixed inspection panels
covering their own pointer target, dice results portaled into a removed breakpoint
host, and the shared modal fallback referring to a nonexistent selected-tab class.
The last fallback correction passed its focused browser recheck and the complete
13-test current-commit isolated Flask browser rerun.

A fresh feature agent independently found four final issues: Settings close
cancelling another audio owner, phone Settings overflow, missing builder sample
state, and invisible keyboard toggle focus. All four were fixed and independently
reverified in the browser; the bounded re-review is clean. Primary-agent final
map/operation visual inspection is also complete. See HANDOFF.md for the remaining
unverified release matrix and owner approval gate.

Final clean-install review corrected a startup test that incorrectly expected
duplicate requests while hydration was in flight; the independent reviewer
confirmed the new response/trailing-refresh assertion matches production. The
preview read-stream guard was also corrected after the reviewer reproduced an
incorrect HTTP 200 on missing assets. Re-review reproduced the intended 503 and
confirmed partial-response errors destroy the stream. This final bounded check
is clean; the complete unit rerun is 31 files / 287 passing tests.

These statements close specific reported findings only. They are not owner
approval, comprehensive production validation or a claim of raster pixel parity.

## Post-handoff acceptance loop

Feature testing found cached/late endpoint statuses reappearing on reopening an
idle Settings panel. A pending-owner guard fixed that narrow behavior; six browser
and ten settings unit tests pass. Architecture review confirmed the fix and
explicitly retained the existing no-request-ID correlation limitation.

Real provider tests exposed a public-main bug where a failed durable save still
changed the live provider. The first fix was independently reviewed and expanded
with a provider-selection lock and deterministic overlapping-selection test.
The re-review found no remaining blocker for this bounded defect; all 25 handler
tests pass. Broader unrelated settings-file concurrency is not claimed solved.

The independent entry-point probe verified actual Flask and launcher behavior and
then reproduced stale build detection when only shared Ember tokens changed. The
minimal exact-input watch fix passed the probe and nine existing launcher tests;
a second agent reviewed its scope and isolation cleanly.

Primary-agent contrast review corrected desktop endpoint status colors/type and
personally inspected both browser captures. A browser check verifies PASS/FAIL
contrast and the existing phone fallback; independent source review is clean.
Main goldens and interactive preview tests still pass without baseline updates.
These receipts do not close every acceptance-matrix row or owner approval.

## Lifecycle and narrow-width review loop

Independent architecture review checked the actual-handler lifecycle probe's
export, no-network/write containment, credential isolation and assertion scope.
Its findings clarified busy-save assertions and retained-backup versus tested
backup recovery. Both save modes pass, with those limits documented.

Independent feature review inspected selected Load, reset and compression
captures after the primary agent's CSS correction. It requested explicit
selected/hover assertions and a clearer distinction between blocking module and
nonblocking compression failure. The new assertion exposed a higher-specificity
generic hover rule; excluding save cards fixed it. All four edge-state tests
then passed, and the reviewer personally inspected the final capture cleanly.
An architecture reviewer also found no blocker in the subsequent presentation-only
combat round-badge correction; 27 existing party unit tests and the updated
desktop/phone browser assertions pass.

A separate agent created the plan-required review-only intermediate-width drawer
prototype using the locked image and public tokens/art. Independent review tested
touch, native modality, focus containment/return and reviewed the 1024 captures.
The author added explicit native-inert/touch tests; all three cases passed in both
the author's run and a primary-agent rerun. No production navigation was changed.
Owner approval and unverified full-plan rows remain open.

## Startup, empty states and authoring review

Independent ledger review traced actual storage/plot response schemas and found
no lost fields or undiscovered-quest leakage. Browser review checked all eight
desktop states, then exercised error → close → successful reopen with exact
focus return. The author added a phone-preservation case and safe fixture stream
handling; nine cases pass. Primary agent inspected all eight final dialog cards.

Primary-agent startup inspection found legacy loading/notice/error presentation
and small recovery result text. Independent review confirmed presentation-only
scope, unconditional hooks and unchanged recovery/game contracts. The reviewer
requested precise phone assertions, including Character loading's 16px Courier
exception; all three tabs are now checked. Six startup/bootstrap cases pass,
including failed-start no-turn authorization and keyboard-reachable Done. The
reviewer personally inspected final bootstrap captures and independently tested
1024/390/1586 resizing without overflow or browser errors; bounded review clean.

Independent authoring probe ran actual safe create/export/import/delete and
builder validation in a disposable tracked export. Another reviewer read the
probe, real handlers and retained result and found no actionable probe flaw.
The existing merge placeholder is excluded, not disguised as working. No agent
executed generation, activation or a live browser-to-backend authoring journey.
