# Agentic Combat Slice 1 Recovery-Conflict Handoff

Date: 2026-08-24

Branch: `design/agentic-combat`

Provider: OpenAI

Browser port: `8368` (checked free before every launch)

## Outcome

The real neither-before-nor-after recovery case is now proven across the shipped
headless server, React `/play/`, and legacy `/` interfaces.

The process-kill fixture staged an owned hit-point transition from 10 to 5,
killed the exact transaction worker after the character write but before the
encounter receipt, then used the production OpenAI-backed character update path
to move the same hit points to 7. On restart, the transaction entered
`recovery_conflict`, preserved 7, kept `turnCursor` at 0, and exposed exactly:

> Combat recovery needs attention -- Load or Reset

Load restored the pre-operation character to 33 HP. Reset created a durable
campaign backup, replaced `party_tracker.json` with `{}`, and removed the live
character. No recovery run advanced or regenerated the frozen combat turn.

## Defects found and corrected

1. `pause_recovery_conflict` was not treated as a zero-actor automatic window,
   causing an automatic enemy-resolution loop. The combat loop now reports the
   exact recovery message and returns to a player command boundary without a
   provider call.
2. Resumed recovery bypassed the normal startup-ready marker, leaving browser
   Load/Reset disabled while the recovery alert promised they were available.
   The existing `startup_kickoff_skipped/already_done` marker now closes that
   established readiness protocol.
3. Headless advertised Reset but the protocol parser and session had no Reset
   command. Confirmed Reset is now accepted, the exact engine is stopped and
   joined before campaign authority is acquired, the existing reset operation
   runs, and one restart result is emitted. Unconfirmed Reset is rejected.

## Complete player/DM transcript captured by both browser clients

The React and legacy pages replayed the same complete visible game log before
the recovery action. UI chrome text (speaker labels, DM Voice, and Generate
Image controls) is omitted below; all narration and player input is verbatim.

**Dungeon Master**

> Welcome back! You stand in the Frostbound Guildhall, its hearth glowing
> against the chill of Frostmere Vale. Fresh slush tracks lead toward the
> eastern entrance, while a sealed watch notice rests on a nearby table. Scout
> Kira gives you a bright, knowing grin. "Back with us, Trouble Magnet?" Ranger
> Thane checks the hall in silence, and Scout Elen keeps her attention on the
> notice. The distant howls have not stopped, and the missing scout remains
> unaccounted for. What do you do next?

**Player**

> I look around the guildhall and quietly assess the room.

**Dungeon Master**

> You quietly assess the Frostbound Guildhall. The hearth burns low but steady,
> throwing amber light across benches, training dummies, and frost-rimmed
> beams. Scout Kira keeps still beside you, while Thane watches the entrances
> and Elen studies the room's details. Near the eastern doorway, fresh slush
> tracks cross the floor and end beneath a bench. On the table nearby lies a
> sealed watch notice bearing the local guard mark. Nothing moves, and no
> immediate threat reveals itself, but the tracks and notice both feel recent.
>
> Please make a Perception check. Roll 1d20 and add your Wisdom (Perception)
> modifier.

**Player**

> I look around the guildhall and quietly assess the room.

**Dungeon Master**

> You move quietly through the Frostbound Guildhall, letting your eyes adjust
> to the hearth's amber glow and the pale light leaking through the frosted
> windows. The benches, training dummies, eastern entrance, and sealed watch
> notice reveal no obvious threat. Kira remains motionless beside you, Thane
> watches the doors, and Elen studies the floor and rafters with practiced
> patience.
>
> Please make a Perception check. Roll 1d20 and add your Wisdom (Perception)
> modifier (+3).

**Player**

> I quietly verify the guildhall exits and return to my place.

**Recovery output**

> Combat recovery needs attention -- Load or Reset

The final player action was respectively:

- React Load: `Load Recovery conflict pre-operation baseline`
- React Reset: `Confirm Reset`
- Legacy Load: `Load Recovery conflict pre-operation baseline`
- Legacy Reset: `Confirm Reset`
- Headless Load: `Load save save_20260824_112241`
- Headless Reset: `Confirm Reset`

## Evidence

Ignored raw evidence is retained locally under:

- `validation_evidence/agentic_combat/slice1/recovery-conflict-openai-r4/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-headless-load-r3/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-headless-reset-r5/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-react-load-r2/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-react-reset-r2/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-legacy-load-r1/`
- `validation_evidence/agentic_combat/slice1/recovery-conflict-legacy-reset-r1/`

Each browser directory contains its full transcript, result JSON, full-page
screenshot, Playwright trace, and server logs. Headless directories contain the
full protocol-derived transcript and authoritative result JSON. The browser
console retained the already-known optional-media/release lookup 404 noise; no
recovery action request failed before the intentional server shutdown.

## Remaining Slice 1 work

This commit does not declare Slice 1 complete. Real compatibility/race evidence
for legacy and pre-typed encounters, reversed controller ownership, and the
remaining near-death/free-form-action matrix still follows.
