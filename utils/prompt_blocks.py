# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Prompt text with marked in-play-build blocks (#2065, D-HOSTED-1).

A prompt file marks the text that describes building a new adventure during
play. A block is a line that is exactly OPEN, the lines it holds, and a line
that is exactly CLOSE; a span is SPAN_OPEN ... SPAN_CLOSE inside one line.
Where in-play builds are allowed (no gateway) only the markers are removed,
so the text is the file's text as read before the markers existed. On a
hosted world each block and span is removed with its content. One copy of
each file serves both.
"""

import re

OPEN = "<<IN-PLAY-BUILD>>"
CLOSE = "<</IN-PLAY-BUILD>>"
SPAN_OPEN = "<<IN-PLAY-BUILD:>>"
SPAN_CLOSE = "<</IN-PLAY-BUILD:>>"
_SPAN = re.compile(re.escape(SPAN_OPEN) + "(.*?)" + re.escape(SPAN_CLOSE))


class PromptBlockError(ValueError):
    """A prompt file's build markers are unbalanced, nested or misplaced."""


def apply_blocks(text, builds_allowed):
    """``text`` with its build blocks and spans kept (markers removed) or
    removed whole. Raises PromptBlockError on an unbalanced or nested block
    or span."""
    lines = text.split("\n")
    out = []
    inside = False
    for number, line in enumerate(lines, 1):
        if line == OPEN:
            if inside:
                raise PromptBlockError("nested block at line %d" % number)
            inside = True
            continue
        if line == CLOSE:
            if not inside:
                raise PromptBlockError("close without open at line %d" % number)
            inside = False
            continue
        if OPEN in line or CLOSE in line:
            raise PromptBlockError("block marker inside a line at line %d" % number)
        if inside and not builds_allowed:
            continue
        rest = _SPAN.sub("", line)
        if SPAN_OPEN in rest or SPAN_CLOSE in rest:
            raise PromptBlockError("unbalanced span at line %d" % number)
        if builds_allowed:
            line = _SPAN.sub(lambda match: match.group(1), line)
        else:
            line = rest
        out.append(line)
    if inside:
        raise PromptBlockError("block not closed")
    return "\n".join(out)


def load_prompt(path):
    """The prompt file at ``path`` (text mode, as before), its build blocks
    applied by the one rule (utils.provider_gateway.in_play_builds_allowed)."""
    from utils.provider_gateway import in_play_builds_allowed

    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    # The main prompt is found in history by its first 50 characters
    # (ensure_main_system_prompt; conversation_utils reads the raw file for
    # them), so no marker may sit there in any prompt file.
    for marker in (OPEN, CLOSE, SPAN_OPEN, SPAN_CLOSE):
        at = text.find(marker)
        if 0 <= at < 50:
            raise PromptBlockError("a build marker in the first 50 characters")
    return apply_blocks(text, in_play_builds_allowed())
