# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Narration Streaming Event Transport
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from __future__ import annotations

import threading
import time
import uuid
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from utils.enhanced_logger import debug


NARRATION_STREAM_START_EVENT = "narration_stream_start"
NARRATION_STREAM_DELTA_EVENT = "narration_stream_delta"
NARRATION_STREAM_END_EVENT = "narration_stream_end"
NARRATION_STREAM_ERROR_EVENT = "narration_stream_error"
NARRATION_STREAM_SUPERSEDED_EVENT = "narration_stream_superseded"
NARRATION_STREAM_COMMIT_EVENT = "narration_stream_commit"


@dataclass
class StreamState:
    """Track server-side stream assembly and ordering metadata."""

    stream_id: str
    turn_id: str
    mode: str
    attempt: int
    skip_tts: bool = False
    started_at: float = field(default_factory=time.time)
    last_seq: int = 0
    full_text: str = ""
    ended: bool = False
    committed: bool = False
    superseded: bool = False


_state_lock = threading.Lock()
_streams: Dict[str, StreamState] = {}
_socket_emit: Optional[Callable[[str, Dict[str, Any]], None]] = None
_pending_canonical_suppressions: Dict[str, int] = {}


def _normalize_narration_text(text: str) -> str:
    """Normalize narration text for safe dedupe comparisons."""
    if not isinstance(text, str):
        return ""
    normalized = text.replace("Dungeon Master:", "", 1).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def extract_narration_for_stream(raw_text: str) -> str:
    """Extract narration value from full/partial JSON response text.

    Returns empty string when narration cannot yet be extracted safely.
    """
    if not isinstance(raw_text, str) or not raw_text:
        return ""

    key_match = re.search(r'"narration"\s*:\s*"', raw_text)
    if not key_match:
        return ""

    start_idx = key_match.end()
    idx = start_idx
    out_chars = []
    escaped = False

    while idx < len(raw_text):
        ch = raw_text[idx]

        if escaped:
            if ch == "n":
                out_chars.append("\n")
            elif ch == "r":
                out_chars.append("\r")
            elif ch == "t":
                out_chars.append("\t")
            elif ch in ('"', "\\", "/"):
                out_chars.append(ch)
            elif ch == "u":
                # Best-effort Unicode decoding when complete; otherwise ignore partial escape.
                hex_chunk = raw_text[idx + 1: idx + 5]
                if len(hex_chunk) == 4 and all(c in "0123456789abcdefABCDEF" for c in hex_chunk):
                    try:
                        out_chars.append(chr(int(hex_chunk, 16)))
                    except Exception:
                        pass
                    idx += 4
            else:
                out_chars.append(ch)
            escaped = False
            idx += 1
            continue

        if ch == "\\":
            escaped = True
            idx += 1
            continue

        if ch == '"':
            # End of narration value.
            break

        out_chars.append(ch)
        idx += 1

    return "".join(out_chars)


def should_suppress_canonical_narration(content: str) -> bool:
    """Return True once when content matches a committed stream render."""
    normalized = _normalize_narration_text(content)
    if not normalized:
        return False

    with _state_lock:
        pending = _pending_canonical_suppressions.get(normalized, 0)
        if pending <= 0:
            return False
        if pending == 1:
            _pending_canonical_suppressions.pop(normalized, None)
        else:
            _pending_canonical_suppressions[normalized] = pending - 1
        return True


def configure_stream_transport(socket_emit: Callable[[str, Dict[str, Any]], None]) -> None:
    """Register SocketIO emit function for stream transport."""
    global _socket_emit
    _socket_emit = socket_emit


def _streaming_enabled() -> bool:
    """Return True when streaming is enabled by config and transport exists."""
    try:
        from model_config import ENABLE_CHAT_STREAMING
    except Exception:
        return False
    return bool(ENABLE_CHAT_STREAMING and _socket_emit is not None)


def _emit(event_name: str, payload: Dict[str, Any]) -> None:
    """Emit stream event with defensive logging and no caller failure."""
    if _socket_emit is None:
        return
    try:
        _socket_emit(event_name, payload)
    except Exception as emit_error:
        debug(
            f"STREAM: Failed to emit {event_name}: {emit_error}",
            category="web_interface",
        )


def start_stream(turn_id: str, mode: str, attempt: int, skip_tts: bool = False) -> Optional[str]:
    """Start a narration stream attempt and emit start event."""
    if not _streaming_enabled():
        return None

    stream_id = f"stream_{uuid.uuid4().hex}"
    stream_state = StreamState(
        stream_id=stream_id,
        turn_id=turn_id,
        mode=mode,
        attempt=attempt,
        skip_tts=skip_tts,
    )

    with _state_lock:
        _streams[stream_id] = stream_state

    _emit(
        NARRATION_STREAM_START_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": 0,
            "skipTTS": skip_tts,
            "timestamp": time.time(),
        },
    )
    return stream_id


def emit_stream_delta(stream_id: str, delta_text: str) -> int:
    """Append delta text to stream state and emit ordered delta event."""
    if not _streaming_enabled() or not delta_text:
        return 0

    with _state_lock:
        stream_state = _streams.get(stream_id)
        if not stream_state or stream_state.ended:
            return 0
        stream_state.last_seq += 1
        stream_state.full_text += delta_text
        seq = stream_state.last_seq
        turn_id = stream_state.turn_id
        attempt = stream_state.attempt
        mode = stream_state.mode
        skip_tts = stream_state.skip_tts

    _emit(
        NARRATION_STREAM_DELTA_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": seq,
            "delta": delta_text,
            "skipTTS": skip_tts,
            "timestamp": time.time(),
        },
    )
    return seq


def end_stream(stream_id: str, full_text: Optional[str] = None) -> str:
    """Finalize a stream attempt and emit assembled full text."""
    if not _streaming_enabled():
        return full_text or ""

    with _state_lock:
        stream_state = _streams.get(stream_id)
        if not stream_state:
            return full_text or ""

        if full_text is not None:
            stream_state.full_text = full_text
        stream_state.ended = True

        assembled_text = stream_state.full_text
        seq = stream_state.last_seq
        turn_id = stream_state.turn_id
        attempt = stream_state.attempt
        mode = stream_state.mode
        skip_tts = stream_state.skip_tts

    _emit(
        NARRATION_STREAM_END_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": seq,
            "fullText": assembled_text,
            "skipTTS": skip_tts,
            "timestamp": time.time(),
        },
    )
    return assembled_text


def emit_stream_error(stream_id: str, message: str, recoverable: bool = True) -> None:
    """Emit stream error for current attempt."""
    if not _streaming_enabled():
        return

    with _state_lock:
        stream_state = _streams.get(stream_id)
        if not stream_state:
            return

        seq = stream_state.last_seq
        turn_id = stream_state.turn_id
        attempt = stream_state.attempt
        mode = stream_state.mode

    _emit(
        NARRATION_STREAM_ERROR_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": seq,
            "message": message,
            "recoverable": recoverable,
            "timestamp": time.time(),
        },
    )


def supersede_stream(stream_id: str, reason: str = "validation_retry") -> None:
    """Mark a stream attempt as superseded and notify the frontend."""
    if not _streaming_enabled():
        return

    try:
        from model_config import STREAM_SUPERSEDED_VISIBLE
    except Exception:
        stream_visible = False
    else:
        stream_visible = bool(STREAM_SUPERSEDED_VISIBLE)

    with _state_lock:
        stream_state = _streams.get(stream_id)
        if not stream_state:
            return
        stream_state.superseded = True

        seq = stream_state.last_seq
        turn_id = stream_state.turn_id
        attempt = stream_state.attempt
        mode = stream_state.mode

    _emit(
        NARRATION_STREAM_SUPERSEDED_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": seq,
            "reason": reason,
            "visible": stream_visible,
            "timestamp": time.time(),
        },
    )


def commit_stream(stream_id: str, committed_text: Optional[str] = None) -> str:
    """Mark stream as canonical for this turn and emit commit event."""
    if not _streaming_enabled():
        return committed_text or ""

    with _state_lock:
        stream_state = _streams.get(stream_id)
        if not stream_state:
            return committed_text or ""

        if stream_state.superseded:
            return committed_text or ""

        if committed_text is not None:
            stream_state.full_text = committed_text
        stream_state.committed = True

        final_text = stream_state.full_text
        normalized = _normalize_narration_text(final_text)
        if normalized:
            _pending_canonical_suppressions[normalized] = _pending_canonical_suppressions.get(normalized, 0) + 1
        seq = stream_state.last_seq
        turn_id = stream_state.turn_id
        attempt = stream_state.attempt
        mode = stream_state.mode
        skip_tts = stream_state.skip_tts

    _emit(
        NARRATION_STREAM_COMMIT_EVENT,
        {
            "streamId": stream_id,
            "turnId": turn_id,
            "mode": mode,
            "attempt": attempt,
            "seq": seq,
            "fullText": final_text,
            "skipTTS": skip_tts,
            "timestamp": time.time(),
        },
    )
    return final_text


def consume_stream_text(stream_id: str) -> str:
    """Return assembled text and remove stream state."""
    with _state_lock:
        stream_state = _streams.pop(stream_id, None)
    if not stream_state:
        return ""
    return stream_state.full_text


def get_stream_text(stream_id: str) -> str:
    """Return currently assembled text for a stream ID."""
    with _state_lock:
        stream_state = _streams.get(stream_id)
    if not stream_state:
        return ""
    return stream_state.full_text
