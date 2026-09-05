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
