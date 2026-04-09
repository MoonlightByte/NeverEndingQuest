## Context

The current journal write path is transition-driven. `main.py` scans conversation history for the latest unprocessed `Location transition:` marker, generates an enhanced adventure summary, and appends that summary to `journal.json` via `update_journal_with_summary(...)`. This keeps the journal compact, but it leaves same-location play underrepresented. In the observed failure case, the party spent multiple sessions inside `NC01` and the true campaign state progressed well beyond the latest journal row because no later persisted location transition was available to trigger another checkpoint.

At the same time, the desired product behavior is not to journal every turn. The journal and the confirmed Players Diary should feel like reflective after-the-fact records, not a combat transcript. Travel transitions and long rests are the two most natural cadence anchors for that style.

Constraints:
- Transition journaling already exists and SHOULD remain the primary checkpoint path.
- Long-rest checkpoint generation MUST be fail-open and MUST NOT interfere with successful rest processing.
- The design SHOULD remain KISS and additive rather than introducing a new persistence-heavy checkpoint subsystem.
- This change MUST stay scoped to journal cadence only and MUST NOT fold in location-narrative authority work.

## Goals / Non-Goals

**Goals:**
- Preserve transition-based journal writes.
- Add long-rest checkpoint generation as a second, in-world-plausible journaling trigger.
- Prevent duplicate journal rows for the same transition or long-rest event.
- Keep the journal compact by refusing per-turn cadence and by skipping empty/no-delta checkpoints.
- Improve downstream Players Diary freshness by making `journal.json` less likely to stall during extended same-location play.

**Non-Goals:**
- Solving NC01/NC05 narrative drift or boss-scene exclusivity.
- Replacing the Players Diary markdown artifact design.
- Rewriting the existing summary-generation architecture into a new memory system.
- Adding short-rest checkpointing by default.

## Decisions

### Decision: Keep transitions and add long rests as the only default journal cadence triggers
The system SHALL keep transition-generated journal checkpoints and SHALL add long-rest-generated checkpoints. Short rests SHALL remain out of scope by default.

Rationale:
- Transitions represent natural scene or chapter boundaries.
- Long rests represent reflective downtime where an in-world diary entry is believable.
- Short rests are too frequent and too mechanically narrow to be reliable high-signal journal anchors.

Alternatives considered:
- Long rests only: rejected because travel transitions already work well and should not be removed.
- Transitions + short rests + long rests: rejected because it risks noisy, repetitive journal growth.
- Per-turn journaling: rejected because it collapses the journal into a transcript.

### Decision: Long-rest checkpoint generation happens only after successful rest completion
The journal cadence hook for long rests SHALL run only after the long rest action has succeeded and the rest summary/system feedback has been produced.

Rationale:
- A failed or partial rest should not create a misleading reflective checkpoint.
- This keeps rest mechanics authoritative and journaling secondary.
- It preserves fail-open behavior: if the journal checkpoint fails, the long rest still stands.

Alternatives considered:
- Pre-rest checkpoint generation: rejected because it can create summaries for rests that fail or are interrupted.
- Save-time journal backfill only: rejected because it leaves same-location, no-save sessions underrepresented.

### Decision: Additive checkpoint metadata SHALL make cadence idempotent
Journal entries created by cadence hooks SHOULD carry additive metadata sufficient to identify the triggering checkpoint deterministically. The metadata SHOULD distinguish at least:
- checkpoint kind (`transition` or `long_rest`)
- checkpoint key (stable idempotency key)
- source location id when available
- source world time when available

Rationale:
- Transition journaling already depends on fragile conversation-history scanning; long-rest journaling would otherwise add another path that can duplicate rows on retries or resume.
- Additive metadata enables exact duplicate suppression without changing the journal's player-facing summary text contract.

Alternatives considered:
- Summary-text similarity only: rejected because prose can vary while the underlying checkpoint is identical.
- Separate checkpoint-state file: rejected because the journal itself can safely carry additive idempotency metadata with lower moving-part cost.

### Decision: Long-rest checkpoints summarize only meaningful unjournaled delta since the previous successful checkpoint
The long-rest path SHALL create a checkpoint only when there is meaningful gameplay delta since the last successful journal checkpoint. If there is no meaningful delta, the long rest SHOULD no-op for journal purposes.

Rationale:
- This prevents immediate duplicate rows when a long rest follows right after a transition that already created a checkpoint.
- It keeps journal output readable and useful for the Players Diary.

Alternatives considered:
- Always write on every long rest: rejected because it will inevitably create low-signal or duplicate journal rows.

### Decision: Reuse the existing summary-generation path rather than inventing a separate long-rest diary model
The design SHOULD reuse the existing enhanced-adventure-summary path as much as possible, with the cadence hook deciding *when* to checkpoint and the checkpoint metadata deciding *whether* it has already happened.

Rationale:
- The problem is cadence and idempotency, not the existence of an entirely separate summary engine.
- This keeps implementation small and easier to verify.

Alternatives considered:
- Build a separate rest-only summary generator: rejected as unnecessary complexity for this scope.

## Risks / Trade-offs

- [Long rest immediately follows a transition] -> suppress journal write if the meaningful delta is empty or the checkpoint key already exists.
- [Resume/retry flows re-run the same long rest hook] -> enforce deterministic checkpoint keys and duplicate suppression.
- [Long-rest journaling fails and leaves the journal stale] -> keep failure non-blocking and rely on the next valid cadence trigger to recover freshness.
- [Metadata fields leak into player-facing diary prose] -> keep checkpoint metadata additive and machine-oriented only.

## Migration Plan

1. Add additive checkpoint metadata support to transition-generated journal rows.
2. Introduce a shared idempotency check for journal cadence hooks.
3. Add a long-rest checkpoint hook after successful long-rest completion.
4. Suppress no-delta and duplicate long-rest journal writes.
5. Add focused regression coverage for transition preservation, long-rest cadence, and dedupe behavior.

Rollback strategy:
- Long-rest cadence can be disabled while leaving transition journaling intact.
- Additive checkpoint metadata can remain in `journal.json` harmlessly even if the new cadence hook is reverted.

## Open Questions

- Should a long rest use the current location name only, or should it preserve a richer location id/module stamp whenever available?
- Should a future follow-up add optional short-rest cadence behind a stricter threshold, or remain long-rest-only permanently?
