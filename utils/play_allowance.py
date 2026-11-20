# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""The hosted play allowance, the game's side (#2072, owner D-HOSTED-3, D-UX-5).

A hosted world (started with --provider-gateway) reads the player's free-play
allowance from the gateway before accepting a new submission, and shows it on
the play page. A world with no gateway makes no request at all: every function
here returns at once.

The read is a check, not a reservation: two submissions can pass the same ok
read, and a turn that crosses the limit finishes (D-TURN-1). The host's backstop
(HTTP 429, type neq_gateway, utils/provider_errors.py) covers the far end.

A failed read fails open: the player plays on, the page hides the bars, and the
first failure in a process is logged as a warning (typed fields only; never a
body, header, token or query).
"""

import itertools
import threading
import time
from datetime import datetime, timezone

# --- The host contract (#2072), confirmed by the host (#315 comment
# 7031057773): the read is this path joined to the gateway base URL, with the
# world's own token as Bearer from the OpenAI key slot (the scene-image client).
READ_PATH = "/play-allowance"


def _read_client():
    import httpx

    from utils.openai_client import openai_api_client

    return openai_api_client(timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS))


READ_TIMEOUT_SECONDS = 2.0
CONNECT_TIMEOUT_SECONDS = 1.0
# A gate reuses a stored read this young instead of reading again.
FRESH_SECONDS = 10.0
# The shown-time re-read: never sooner than this, and this long after the time.
TIMER_FLOOR_SECONDS = 60.0
TIMER_SLACK_SECONDS = 5.0
# When the shown-time read still says locked with the same time (clock skew, a
# host that lags), at most these follow-up reads, counted from that read, then
# none until a new time, an ok or a reconnect (Orchestration D-AUTH-1).
FOLLOWUP_READ_SECONDS = (120.0, 300.0, 900.0)
# A backstop refusal triggers one read; repeats within this window do not.
BACKSTOP_READ_SECONDS = 2.0

STATES = ("ok", "player_limit", "paused_for_everyone", "paused_for_account")


class AcceptedLine(str):
    """A player line the web handler checked and accepted (#2072 a1): the game
    loop does not check it again."""


_lock = threading.Lock()
_sequence = itertools.count(1)
_stored = None            # {"seq", "at" (monotonic), "value" (dict, or None = unavailable)}
_warned = False
_publisher = None         # callable(payload, to) set by the web server
_stopping = None          # callable() -> bool set by the web server
_timer = None
_timer_time = None        # the shown time the last timer was set for
_timer_fired = False      # the timer for _timer_time has fired (follow-ups may follow)
_followups = 0            # follow-up reads armed for _timer_time
_fight_check = None       # callable() -> bool set by the game: a fight is live
_read_note = False
_last_backstop_read = 0.0


def enabled():
    """True only on a gateway world; a local game never reads."""
    from utils.provider_gateway import gateway

    return gateway() is not None


# --- Parsing (typed fields only) ---

def _utc(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("time")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("time zone")
    return parsed.astimezone(timezone.utc)


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment is not None else None


def _period(raw):
    if not isinstance(raw, dict):
        raise ValueError("period")
    fraction = raw.get("used_fraction")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or fraction != fraction:
        raise ValueError("used_fraction")
    minutes = raw.get("minutes_left_estimate")
    if minutes is not None:
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes != minutes:
            raise ValueError("minutes_left_estimate")
        minutes = max(0, int(minutes))
    return {
        "used_fraction": min(1.0, max(0.0, float(fraction))),
        "minutes_left_estimate": minutes,
        "resets_at": _iso(_utc(raw.get("resets_at"))),
    }


def parse(body):
    """The typed allowance from a response body, or raise ValueError."""
    if not isinstance(body, dict):
        raise ValueError("body")
    limited = body.get("limited")
    if not isinstance(limited, bool):
        raise ValueError("limited")
    if not limited:
        return {"limited": False}
    state = body.get("state")
    if state not in STATES:
        raise ValueError("state")
    resume = _utc(body.get("resume_at"))
    if state == "paused_for_account":
        resume = None
    return {
        "limited": True,
        "state": state,
        "day": _period(body.get("day")),
        "week": _period(body.get("week")),
        "resume_at": _iso(resume),
    }


# --- The read ---

def _fetch():
    import httpx

    response = _read_client().get(READ_PATH, cast_to=httpx.Response)
    if response.status_code != 200:
        raise _HttpStatus(response.status_code)
    return parse(response.json())


class _HttpStatus(Exception):
    def __init__(self, status):
        super().__init__(status)
        self.status = status


def _log_failure(exc):
    global _warned
    from utils.enhanced_logger import file_only, warning

    reason = "HTTP %s" % exc.status if isinstance(exc, _HttpStatus) else type(exc).__name__
    line = "PLAY_ALLOWANCE_READ_FAILED class=%s" % reason
    with _lock:
        first = not _warned
        _warned = True
    if first:
        warning(line, category="play_allowance")
    else:
        file_only(line, category="play_allowance")


def read():
    """Read the allowance once (gateway worlds only). Returns the typed value,
    or None when the read failed (fail open). The result is stored only if no
    read that started later was stored first."""
    if not enabled():
        return None
    with _lock:
        seq = next(_sequence)
    try:
        value = _fetch()
    except Exception as exc:  # fail open: never block a player on our own read
        value = None
        _log_failure(exc)
    _store(seq, value)
    return value


def _store(seq, value):
    global _stored
    with _lock:
        if _stored is not None and _stored["seq"] > seq:
            return False
        _stored = {"seq": seq, "at": time.monotonic(), "value": value}
    _schedule(value, seq)
    return True


def current():
    """The stored value: (found, value). value None = unavailable."""
    with _lock:
        if _stored is None:
            return False, None
        return True, _stored["value"]


def _fresh_value():
    with _lock:
        if _stored is not None and time.monotonic() - _stored["at"] < FRESH_SECONDS:
            return True, _stored["value"]
    return False, None


def set_fight_check(check):
    """The game's own read of a live fight (main.py registers it)."""
    global _fight_check
    _fight_check = check


def fight_live():
    """True while a fight is live (D-TURN-1: it goes on whatever the allowance
    says). An unreadable encounter counts as no fight, so the gates refuse."""
    if _fight_check is None:
        return False
    try:
        return bool(_fight_check())
    except Exception:
        return False


def refuses_turn():
    """The one gate condition (the loop, the web handlers and start_game): a
    good read says this player cannot play, and no fight is live."""
    return not allows_turn() and not fight_live()


def allows_turn():
    """False only on a good read that says this player cannot start a turn."""
    if not enabled():
        return True
    found, value = _fresh_value()
    if not found:
        value = read()
    if value is None or not value.get("limited"):
        return True
    return value.get("state") == "ok"


# --- Publishing to pages ---

def set_publisher(publisher, stopping=None):
    """The web server's emit for the play_allowance event, and its exit flag."""
    global _publisher, _stopping
    _publisher, _stopping = publisher, stopping


def payload(refused_input=None, refused_start=False):
    """The page's play_allowance payload from the stored value."""
    found, value = current()
    if not found or value is None:
        data = {"unavailable": True}
    else:
        data = dict(value)
        data["fight_live"] = fight_live()  # at publish time, from the gates' own read
    if refused_input is not None:
        data["refused_input"] = str(refused_input)
    if refused_start:
        data["refused_start"] = True
    return data


def publish(to=None, refused_input=None, refused_start=False):
    """Send the stored value to every page, or to one client (to=sid). Only a
    refusal to its sender carries refused_input or refused_start."""
    if not enabled() or _publisher is None:
        return
    try:
        _publisher(payload(refused_input if to is not None else None, refused_start and to is not None), to)
    except Exception:
        pass


def read_and_publish_async(to=None, min_age=0.0):
    """Read and publish on a daemon thread, so no turn or prompt waits for it.
    With min_age, a stored read younger than that is published without a new
    read (the prompt's read after a blank line)."""
    if not enabled():
        return

    def run():
        with _lock:
            young = _stored is not None and time.monotonic() - _stored["at"] < min_age
        if not young:
            read()
        publish(to)

    threading.Thread(target=run, name="play-allowance-read", daemon=True).start()


def after_backstop():
    """A backstop refusal arrived: one fresh read and publish (throttled)."""
    global _last_backstop_read
    if not enabled():
        return
    now = time.monotonic()
    with _lock:
        if now - _last_backstop_read < BACKSTOP_READ_SECONDS:
            return
        _last_backstop_read = now
    read_and_publish_async()


# --- The read note: was the line the game loop just read accepted by the web handler? ---

def note_read(accepted):
    global _read_note
    _read_note = bool(accepted)


def take_read_note():
    global _read_note
    accepted, _read_note = _read_note, False
    return accepted


# --- The shown time and its one re-read ---

def shown_time(value):
    """The time the state's line names (UTC datetime), or None."""
    if not value or not value.get("limited"):
        return None
    state = value.get("state")
    resume = _utc(value.get("resume_at"))
    if state == "paused_for_everyone":
        return resume
    if state == "player_limit":
        if resume is not None:
            return resume
        period = value["week"] if value["week"]["used_fraction"] >= 1 else value["day"]
        return _utc(period.get("resets_at"))
    return None


def _schedule(value, seq=None):
    """One daemon timer per distinct shown time (a1 b): never sooner than the
    floor, nothing when the time is the one already set, none when there is no
    time. After that timer has fired and a read still gives the same time, at
    most len(FOLLOWUP_READ_SECONDS) follow-up reads. Only the newest stored
    read schedules, and nothing is armed once the server is stopping."""
    global _timer, _timer_time, _timer_fired, _followups
    if value is None:
        return  # a failed read leaves any timer as it was
    try:
        moment = shown_time(value) if value.get("state") != "ok" else None
    except ValueError:
        moment = None
    stopping = _stopping is not None and _stopping()
    with _lock:
        if seq is not None and (_stored is None or _stored["seq"] != seq):
            return  # an older read finishing late never arms a timer
        if moment is not None and moment == _timer_time:
            if (_timer is not None or not _timer_fired or stopping
                    or _followups >= len(FOLLOWUP_READ_SECONDS)):
                return
            delay = FOLLOWUP_READ_SECONDS[_followups] - (
                FOLLOWUP_READ_SECONDS[_followups - 1] if _followups else 0.0)
            _followups += 1
        else:
            if _timer is not None:
                _timer.cancel()
            _timer, _timer_time, _timer_fired, _followups = None, moment, False, 0
            if moment is None or stopping:
                return
            delay = max(TIMER_FLOOR_SECONDS,
                        (moment - datetime.now(timezone.utc)).total_seconds() + TIMER_SLACK_SECONDS)
        timer = threading.Timer(delay, _on_timer)
        timer.daemon = True
        _timer = timer
    timer.start()


def _on_timer():
    global _timer, _timer_fired
    with _lock:
        # Only the current timer reads (threading.Timer is a Thread). A timer
        # that a newer time replaced, or that was cancelled, while it fired
        # returns: the newer timer's own firing does the read.
        if _timer is not threading.current_thread():
            return
        _timer, _timer_fired = None, True
    if _stopping is not None and _stopping():
        return
    read()
    publish()


def cancel_timer():
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = None


# --- Words (owner D-UX-5; plan-2072-r1-a2). The page has the same in allowanceText.ts. ---

def _clock(moment):
    local = moment.astimezone()
    hour = local.hour % 12 or 12
    return "%d:%02d %s" % (hour, local.minute, "AM" if local.hour < 12 else "PM")


def _weekday(moment):
    return moment.astimezone().strftime("%A")


SAVED = " Your adventure is saved."


def state_line(value):
    """The composer line for a state that is not ok, or None."""
    if not value or not value.get("limited"):
        return None
    state = value.get("state")
    if state == "paused_for_account":
        return "Free play is paused for this account. Please contact us if you think this is a mistake."
    moment = shown_time(value)
    if state == "paused_for_everyone":
        if moment is None:
            return "Free play is paused for everyone right now. Please check back later." + SAVED
        return "Free play is paused for everyone right now. It comes back at %s." % _clock(moment) + SAVED
    if state == "player_limit":
        if moment is None:
            return "You've used your free play for now. Please check back later." + SAVED
        if value["week"]["used_fraction"] >= 1:
            return ("You've used this week's free play. You can play again on %s at %s."
                    % (_weekday(moment), _clock(moment)) + SAVED)
        return "You've used today's free play. You can play again at %s." % _clock(moment) + SAVED
    return None


def refusal_line():
    """The stored state's line (for the terminal), or None."""
    found, value = current()
    return state_line(value) if found else None


def _reset_for_rows():
    """Row/test helper: forget everything (no timer left running)."""
    global _stored, _warned, _timer_time, _read_note, _last_backstop_read, _timer_fired, _followups
    cancel_timer()
    with _lock:
        _stored, _warned, _timer_time, _read_note, _last_backstop_read = None, False, None, False, 0.0
        _timer_fired, _followups = False, 0

