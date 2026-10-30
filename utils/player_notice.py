# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Player-visible operational notices (#212).

An out-of-fiction notice (recovery, upgrade, restart) goes to the player as the
typed ``"system"`` message every client already renders: web caches and queues
it, React and the legacy page show it as a notice card, headless emits a
``system`` event. With no frontend (the console) it prints ``[SYSTEM] <text>``,
as these notices always did. No text is parsed; the prefix is console rendering.
"""

from uuid import uuid4

from utils.enhanced_logger import warning


def show_player_notice(text, *, message_id=None, color=None, padded=False):
    """Show ``text`` to the player. False when nothing was shown: no text, or a
    frontend owns delivery but did not show it (paused or rejected). Either is
    logged, never printed.

    ``color`` and ``padded`` shape only the console line, never the message.
    """
    from web.shared_state import emit_player_output, has_player_output_sink

    if not isinstance(text, str) or not text.strip():
        # #1233, as display_dm_narration: no text is never shown, neither as
        # "None" nor as an empty card (#1611).
        warning("PLAYER_NOTICE: skipped a notice with no text (%r)" % (text,),
                category="player_notice")
        return False
    has_sink = has_player_output_sink()
    if emit_player_output({
        "type": "system",
        "channel": "system",
        "content": text,
        "message_id": message_id or "msg-%s" % uuid4().hex,
    }) is True:
        return True
    if has_sink:
        warning("PLAYER_NOTICE: not delivered (frontend paused or rejected it): %s" % text,
                category="player_notice")
        return False
    line = "[SYSTEM] " + text
    if color:
        from termcolor import colored

        line = colored(line, color)
    print("\n%s\n" % line if padded else line)
    return True


def show_reset_failed(exc):
    """The one Reset-failure notice (main menu, terminal restore, setup wizard)."""
    return show_player_notice("Reset did not finish: " + str(exc))


def show_player_wait(text):
    """A transient wait (#212): the working status line plus the console line.

    Not a notice card: a wait observer repeats while it waits, and a cached card
    would replay every repeat after a reload.
    """
    try:
        from core.managers.status_manager import status_manager

        status_manager.update_status(text, True)
    except Exception:
        pass
    print("[SYSTEM] " + text)
