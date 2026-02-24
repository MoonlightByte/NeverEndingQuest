# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Utilities for parsing TABLETOP MODE output markers."""

import re
from typing import Optional, Tuple


PREFILL_PATTERN = re.compile(r'\[prefill:([^\]]+)\]')

# TTS scope markers for non-narrative flow suppression
TTS_BLOCK_ON_MARKER = "[TTS_BLOCK_ON]"
TTS_BLOCK_OFF_MARKER = "[TTS_BLOCK_OFF]"


def detect_tts_scope_marker(content: str) -> int:
    """Detect TTS scope control markers.

    Returns:
        +1 if content contains [TTS_BLOCK_ON]
        -1 if content contains [TTS_BLOCK_OFF]
        0 if neither marker is present
    """
    if not isinstance(content, str):
        return 0
    stripped = content.strip()
    if stripped == TTS_BLOCK_ON_MARKER:
        return +1
    if stripped == TTS_BLOCK_OFF_MARKER:
        return -1
    return 0


def extract_output_markers(content: str) -> Tuple[str, bool, Optional[str]]:
    """Extract skipTTS and prefill markers from output content.

    Returns:
        (cleaned_content, skip_tts, prefill_input)
    """
    if not isinstance(content, str):
        content = str(content)

    cleaned_content = content
    skip_tts = cleaned_content.startswith('[skipTTS]')
    if skip_tts:
        cleaned_content = cleaned_content.replace('[skipTTS]', '', 1).strip()

    prefill_input = None
    prefill_match = PREFILL_PATTERN.search(cleaned_content)
    if prefill_match:
        prefill_input = prefill_match.group(1)
        cleaned_content = PREFILL_PATTERN.sub('', cleaned_content).strip()

    return cleaned_content, skip_tts, prefill_input
