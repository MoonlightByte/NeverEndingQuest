# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The game clock in the engine's live_state document (D4, NQL X4).

The document (format v4) holds the clock: ``{"unit": "second", "tick": N}``.
The engine is its only writer while it is available. The tracker's
``worldConditions`` time is a projection of it, written here and nowhere
else when the engine answers.

- Every live-state world declares the tracker's time
  (``utils/roster_conversion.py`` world_source). The engine takes it once,
  into a new or a v3 document, and ignores it after (LIVE_STATE.md "The
  clock"). So the first call of a session, a Load, a new game and a
  re-created document all start from the tracker's real time.
- After each engine answer, ``project`` writes the four clock fields of the
  tracker from the document's tick (a historical answer too).
- Time that passes (a DM ``updateTime``, a trip's approved time) is an
  ``advance time by <seconds>;`` request with a stable id, so a retried turn
  is answered historical instead of adding the time twice.
- ``reconcile`` runs before each writing call: a document ahead of the
  tracker projects the tracker (a crash between the two writes); a tracker
  ahead of the document catches the engine up (an outage fallback). The
  tracker never moves backwards and nothing is refused, so no refusal can
  repeat on every call.
- J2: a travel ``updateTime`` records the trip's ``arrival`` journal entry
  after its ``advance time by`` (stamped at the approved arrival), or in a
  request of its own when the clock already reached it
  (core/nql/journal.py).
"""
import os
from typing import Any, Dict, Optional

from core.effects import clock as calendar
from utils.encoding_utils import safe_json_dump, safe_json_load
from utils.enhanced_logger import info, warning
from utils.path_transaction_lock import path_transaction_lock

UNIT = "second"
CLOCK_FIELDS = ("time", "day", "month", "year")
# The new-game start (utils/startup_wizard.py). An unreadable tracker clock
# declares it: the earliest sensible time, so a later correction is always
# the engine catching up, never the tracker jumping.
START = {"year": 1492, "month": "Springmonth", "day": 1, "time": "09:00:00"}


def _tracker_path(root: str) -> str:
    return os.path.join(root, "party_tracker.json")


def _lock(root: str):
    # The same identity as campaign_manager._party_module_transition_lock,
    # reentrant within a thread (a deferred updateTime already holds it).
    return path_transaction_lock(_tracker_path(root), suffix=".module-transition.lock")


def tracker_seconds(tracker: Any) -> Optional[int]:
    """The tracker's game time in seconds, or None when it is unreadable."""
    world = tracker.get("worldConditions") if isinstance(tracker, dict) else None
    try:
        return calendar.scalar_from_calendar({f: (world or {}).get(f) for f in CLOCK_FIELDS
                                              if (world or {}).get(f) is not None})
    except calendar.GameTimeError:
        return None


def declared_tick(tracker: Any) -> int:
    """The tick a live-state world declares: the tracker's time, else START."""
    seconds = tracker_seconds(tracker)
    if seconds is None:
        warning("CLOCK: the tracker's time is unreadable; the world declares the new-game start",
                category="location_transitions")
        return calendar.scalar_from_calendar(START)
    return seconds


def document_tick(live: Any) -> Optional[int]:
    """The document's clock tick, or None when it holds no clock."""
    held = live.get("clock") if isinstance(live, dict) else None
    if isinstance(held, dict) and held.get("unit") == UNIT and type(held.get("tick")) is int:
        return held["tick"]
    return None


def project(root: str, tick: int) -> bool:
    """Write the tracker's four clock fields from the document's tick when they
    differ. A read-modify-write of those fields only, under the transition
    lock, read back; never a rewrite of the tracker from an earlier copy."""
    try:
        fields = calendar.calendar_from_scalar(tick)
    except calendar.GameTimeError:
        return False
    path = _tracker_path(root)
    with _lock(root):
        tracker = safe_json_load(path)
        world = tracker.get("worldConditions") if isinstance(tracker, dict) else None
        if not isinstance(world, dict):
            warning("CLOCK: the tracker is unavailable; its time is not projected",
                    category="location_transitions")
            return False
        if {f: world.get(f) for f in CLOCK_FIELDS} == fields:
            return True
        before = tracker_seconds(tracker)
        if before is not None and before > tick:
            # Never backwards: reconcile catches the engine up instead.
            return False
        for f in CLOCK_FIELDS:
            world[f] = fields[f]
        safe_json_dump(tracker, path, indent=4)
        verified = safe_json_load(path)
        verified_world = verified.get("worldConditions", {}) if isinstance(verified, dict) else {}
        if {f: verified_world.get(f) for f in CLOCK_FIELDS} != fields:
            warning("CLOCK: the tracker's time did not verify after the projection",
                    category="location_transitions")
            return False
    return True


def advance(seconds: int, request_id: str, *, root: str = ".") -> Optional[Dict[str, Any]]:
    """One ``advance time`` request on the document (the tracker follows by
    projection). None when the engine is unavailable; nothing is sent for
    zero or less (the engine refuses ``advance time by 0``)."""
    from core.nql import occupants
    if type(seconds) is not int or seconds <= 0:
        return {"ok": True, "skipped": True}
    return occupants.request("advance time by %d;" % seconds, request_id, root=root, align=False)


def advance_to(target: int, request_id: str, *, root: str = ".", arrival: Optional[str] = None) -> str:
    """Bring the document's clock to `target` (an approved arrival time).
    The engine's own trip ticks already count toward it; what is left is
    sent once. Returns "advanced", "reached" (nothing left, e.g. the trip
    took longer), "unavailable" or "refused". `arrival` is the trip's
    arrival entry id (J2): recorded at the tracker's place after the
    advance, or alone under "<request_id>:arrival" when nothing is left."""
    from core.nql import journal, occupants
    from utils import travel_map
    live = occupants._load(root)
    held = document_tick(live)
    if held is None:
        return "unavailable"
    entry = None
    if arrival:
        here = travel_map.tracker_place(safe_json_load(_tracker_path(root)) or {})
        entry = journal.line(arrival, "arrival", here, live)
    if held >= target:
        project(root, held)
        if entry:
            journal.send([entry], "%s:arrival" % request_id, root=root)
        return "reached"
    lines = [("advance time by %d;" % (target - held), None)] + ([entry] if entry else [])
    response, _ = journal.send(lines, request_id, root=root, resend_on_record=True)
    if response is None:
        return "unavailable"
    return "advanced" if response.get("ok") else "refused"


def advance_minutes(value: Any, request_id: str, *, root: str = ".") -> bool:
    """A DM ``updateTime`` (minutes) as an engine request. True when handled:
    sent, already applied, or nothing to send (zero, or not a number, which
    the old path skips too). False when the engine is unavailable or refused
    it: the caller writes the tracker as before and ``reconcile`` catches
    the engine up on the next call."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        warning("CLOCK: updateTime %r is not a number of minutes; no time passes" % (value,),
                category="location_transitions")
        return True
    if minutes <= 0:
        return True
    response = advance(minutes * 60, request_id, root=root)
    if response is None or not response.get("ok"):
        warning("CLOCK: the engine did not take updateTime %d min (%s); the tracker is written "
                "and the engine catches up later" % (minutes, (response or {}).get("error") or "unavailable"),
                category="location_transitions")
        return False
    return True


def apply_staged(receipt: Dict[str, Any], request_id: str, *, root: str = ".",
                 arrival: Optional[str] = None) -> str:
    """A deferred travel ``updateTime``: the clock reaches the approved
    arrival (the receipt's ``after``). The engine's trip ticks already
    count toward it. Without the engine, the tracker alone moves forward to
    it (never back) and the engine catches up later. `arrival` is the
    trip's arrival journal entry id (J2, advance_to). Returns "committed"."""
    try:
        target = calendar.scalar_from_calendar(receipt["after"])
    except (KeyError, TypeError, calendar.GameTimeError):
        warning("CLOCK: the staged updateTime has no readable arrival time; no time passes",
                category="location_transitions")
        return "committed"
    outcome = advance_to(target, request_id, root=root, arrival=arrival)
    if outcome in ("unavailable", "refused"):
        warning("CLOCK: the staged updateTime %s was %s; the tracker moves to the arrival time"
                % (request_id, outcome), category="location_transitions")
        project(root, target)
    return "committed"


def reconcile(root: str, world: str, live: Dict[str, Any], call) -> Dict[str, Any]:
    """Before a writing call: bring the tracker and the document to the same
    time without moving either backwards. `call(world, live, actions, id)`
    is occupants' engine call. Returns the document to use."""
    held = document_tick(live)
    if held is None:
        return live
    tracker = safe_json_load(_tracker_path(root))
    seconds = tracker_seconds(tracker)
    if seconds is None or seconds == held:
        if seconds is None:
            project(root, held)
        return live
    if held > seconds:
        info("CLOCK: the document is ahead of the tracker (%d s); the tracker follows" % (held - seconds),
             category="location_transitions")
        project(root, held)
        return live
    request_id = "clock-catchup:%d:%d" % (held, seconds)
    response = call(world, live, "advance time by %d;" % (seconds - held), request_id)
    if not response.get("ok"):
        warning("CLOCK: the engine's catch-up %s was refused (%s); play goes on"
                % (request_id, response.get("error")), category="location_transitions")
        return live
    info("CLOCK: the engine caught up %d s to the tracker (%s)" % (seconds - held, request_id),
         category="location_transitions")
    return response.get("live_state") or live
