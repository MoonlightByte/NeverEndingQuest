## Context

The live failure chain is now clear from the transcript and stdout:

1. The narrator places the party in `Priest's Lodging`, but no explicit location action is emitted.
2. Recent recap text also places the party in `Priest's Lodging`.
3. Startup/history refresh later reloads stale `party_tracker.json` at `NIG01`, so the GUI and rebuilt context revert to Ma's Watering Hole.
4. The reliquary is narrated as discovered, inspected, entrusted to Xorn, and later placed into Xorn's explorer's pack.
5. The model either emits no inventory action or emits a receiver-only update.
6. Narration-only skip path finalizes the turn without deterministic recovery, so later turns still show the old inventory state.

This means the missing behavior is a narrow runtime recovery layer, not a larger design rewrite. The runtime needs to recover canonical state from uniquely resolvable scene evidence before validator skip and before startup/history refresh trust stale stored state.

Constraints:

- MUST preserve explicit canonical actions when they already exist.
- MUST fail open on ambiguous ownership or ambiguous location identity.
- MUST keep host edits additive and ASCII-only.
- MUST remain localized to runtime reconciliation and history/startup repair.
- SHOULD avoid prompt-stack expansion beyond the acceptance criteria already required by validator parity.

## Goals / Non-Goals

**Goals:**

- Recover canonical giver/receiver inventory state for explicit party-to-party handoffs when one side is omitted.
- Recover receiver ownership when a later narration-only stow/use turn uniquely proves the receiver is now carrying the item.
- Recover stale startup/current-scene location from recent transcript evidence before UI/history rebuild.
- Support conservative room-title alias matching needed for room-labeled modules like `Night_of_the_Restless_Dead`.
- Prevent narration-only skip from bypassing deterministic recovery.

**Non-Goals:**

- No generic inventory parser for arbitrary prose.
- No broad scene-memory system.
- No replacement of explicit `transitionLocation` / `updatePartyTracker` flow when present.
- No cross-module location inference from recap prose.

## Decisions

### Decision 1: Party-to-party transfer recovery triggers only on explicit giver/receiver/item triples

Runtime SHALL only recover missing transfer state when the turn provides a uniquely resolvable giver, receiver, and item identity.

Rationale:

- Prevents accidental inventory mutation from broad social narration.
- Matches the user's lock case (`Redax` gives `the sacred reliquary` to `Xorn`).

Alternative considered:

- Recover any narrated item exchange involving party members.
- Rejected because implicit borrowing/offering language is too broad and risks false positives.

### Decision 2: Receiver-side self-stow may backfill missing ownership if recent transcript makes ownership unique

If a later narration-only turn has the receiver explicitly place or store the same item and runtime still lacks that item, recovery MAY backfill receiver ownership if the recent transcript history uniquely established that the item was entrusted to that receiver.

Rationale:

- The live reliquary chain proves the initial handoff may fail, but the later self-stow turn still supplies a safe recovery point.
- This keeps the system from requiring the user to repeat the transfer command.

Alternative considered:

- Reject all later self-stow turns unless the item is already present.
- Rejected because that preserves the broken state indefinitely after one missed handoff.

### Decision 3: Narration-only skip happens after deterministic recovery, not before

The validation/acceptance pipeline SHALL attempt deterministic inventory/location recovery before it decides a turn is safe to skip as narration-only.

Rationale:

- The live logs show `actions: []` causes an immediate validator skip, which blocks the missing recovery work.
- Recovery is still narrow and deterministic, so it belongs before the skip gate.

Alternative considered:

- Keep skip order unchanged and try to improve prompt compliance.
- Rejected because prompt compliance already failed in the lock transcript.

### Decision 4: Startup scene-location recovery uses recent transcript evidence, not full-history fuzzy search

Startup/history repair SHALL inspect a bounded recent transcript window and recover location only when one known active-module location is uniquely supported by recent scene text or recap text.

Rationale:

- The observed drift comes from recent stale-vs-live conflict, not missing ancient context.
- A bounded window keeps the heuristic narrow and avoids dragging old locations back into canon.

Alternative considered:

- Scan the full conversation history and choose the most frequent location mention.
- Rejected because it would overfit old scenes and create regressions.

### Decision 5: Room-style alias matching is part of canonical location recovery

Location reconciliation SHALL support conservative aliases derived from canonical module metadata, including:

- full room label (`Room 4: Priest's Lodging`)
- room-prefix-stripped title (`Priest's Lodging`)
- article-tolerant variants (`the priest's lodging`)
- `source_room_title` when available

Rationale:

- The lock transcript uses natural room-title prose, not always the fully prefixed canonical label.
- Alias support already proved necessary for live module narration style.

Alternative considered:

- Require exact canonical location label only.
- Rejected because real play does not reliably use the full prefixed room string.

## Risks / Trade-offs

- [Risk] Recovery could remove an item from the wrong giver if more than one candidate owns similar items.
  -> Mitigation: require explicit giver identity and fail open on ownership ambiguity.

- [Risk] Self-stow recovery could manufacture ownership from poetic language.
  -> Mitigation: require recent explicit entrust/give/hand phrasing plus unique item identity.

- [Risk] Startup location recovery could over-commit from stale recap text.
  -> Mitigation: use a bounded recent window, require exactly one resolved location, and preserve explicit stored location if evidence is weak.

- [Risk] Recovery-before-skip could widen low-risk turn work.
  -> Mitigation: only run narrow deterministic helpers on candidate narration-only turns with relevant item/location signals.

## Migration Plan

1. Add transcript-driven regression locks for reliquary handoff, receiver self-stow, and Priest's Lodging startup recovery.
2. Implement deterministic party-item transfer recovery helper(s).
3. Wire recovery before narration-only validation skip.
4. Add startup/history scene-location recovery before stale `party_tracker` refresh rehydrates UI/history.
5. Extend conservative alias support for room-title location matching.
6. Run targeted regression suites and `openspec validate`.

Rollback strategy:

- Revert the new recovery helpers while keeping the transcript locks if the heuristic over-commits.
- Location startup recovery and transfer recovery can be disabled independently if only one path proves too permissive.

## Open Questions

- Whether receiver self-stow recovery should write only the receiver add, or also synthesize the missing giver remove when the giver identity is still uniquely resolvable from the recent transcript window.
- Whether startup recovery should inspect the most recent recap block separately from ordinary recent assistant narration, or treat both surfaces uniformly.
