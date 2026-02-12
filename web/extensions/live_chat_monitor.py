# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Extension - Live chat monitoring
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Callable


LIVE_CHAT_LOG_FILE = "debug/logs/live_chat_monitor.json"
MAX_CHAT_ENTRIES = 100
ORIGINAL_EMIT_ATTR = "_tabletop_mode_original_emit"
LOG_FN_ATTR = "_tabletop_mode_log_chat_event"
WRAPPED_ATTR = "_tabletop_mode_emit_wrapped"


def setup_live_chat_monitor(socketio: Any) -> Callable[[str, Any, Any, Any], None]:
    """Attach live chat monitor wrapper and return log callable.

    Hook contract:
    - Owns all SocketIO emit wrapper lifecycle in this extension module.
    - Idempotent: repeated setup calls do not double-wrap socketio.emit.
    - Stores original emit on the socketio object for optional teardown.
    - Returns the same log function after the first successful setup.
    """
    live_chat_lock = threading.Lock()

    def _init_live_chat_log() -> None:
        try:
            os.makedirs(os.path.dirname(LIVE_CHAT_LOG_FILE), exist_ok=True)
            if not os.path.exists(LIVE_CHAT_LOG_FILE):
                with open(LIVE_CHAT_LOG_FILE, 'w', encoding='utf-8') as log_file:
                    json.dump([], log_file)
        except Exception as init_error:
            print(f"[TABLETOP MODE] Failed to init live chat log: {init_error}")

    def log_chat_event(event_type: str, content: Any, character: Any = None, metadata: Any = None) -> None:
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'content': content if isinstance(content, str) else str(content)[:500],
                'character': character,
                'metadata': metadata or {},
            }

            with live_chat_lock:
                entries = []
                if os.path.exists(LIVE_CHAT_LOG_FILE):
                    try:
                        with open(LIVE_CHAT_LOG_FILE, 'r', encoding='utf-8') as log_file:
                            entries = json.load(log_file)
                    except Exception:
                        entries = []

                entries.append(entry)
                entries = entries[-MAX_CHAT_ENTRIES:]

                with open(LIVE_CHAT_LOG_FILE, 'w', encoding='utf-8') as log_file:
                    json.dump(entries, log_file, indent=2)
        except Exception as log_error:
            print(f"[TABLETOP MODE] Chat logging error: {log_error}")

    _init_live_chat_log()

    existing_log_fn = getattr(socketio, LOG_FN_ATTR, None)
    if callable(existing_log_fn):
        return existing_log_fn

    original_socketio_emit = getattr(socketio, ORIGINAL_EMIT_ATTR, None)
    if not callable(original_socketio_emit):
        original_socketio_emit = socketio.emit
        setattr(socketio, ORIGINAL_EMIT_ATTR, original_socketio_emit)

    def _tabletop_mode_emit_wrapper(event: str, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        result = original_socketio_emit(event, data, *args, **kwargs)

        if event == 'game_output' and isinstance(data, dict):
            msg_type = data.get('type', 'unknown')
            content = data.get('content', '')

            if msg_type == 'narration':
                log_chat_event('ai_response', content, metadata={'type': 'narration'})
            elif msg_type == 'system':
                log_chat_event('system', content, metadata={'type': 'system'})
            elif msg_type == 'combat':
                log_chat_event('system', content, metadata={'type': 'combat'})

        return result

    setattr(socketio, LOG_FN_ATTR, log_chat_event)

    if not bool(getattr(socketio, WRAPPED_ATTR, False)):
        socketio.emit = _tabletop_mode_emit_wrapper
        setattr(socketio, WRAPPED_ATTR, True)
        print("[TABLETOP MODE] Real-time chat monitoring enabled - logs to debug/logs/live_chat_monitor.json")

    return log_chat_event


def teardown_live_chat_monitor(socketio: Any) -> bool:
    """Restore original SocketIO emit and clear monitor state.

    Returns True when original emit was restored, otherwise False.
    """
    original_socketio_emit = getattr(socketio, ORIGINAL_EMIT_ATTR, None)
    restored = False

    if callable(original_socketio_emit):
        socketio.emit = original_socketio_emit
        restored = True

    for attr_name in [ORIGINAL_EMIT_ATTR, LOG_FN_ATTR, WRAPPED_ATTR]:
        if hasattr(socketio, attr_name):
            delattr(socketio, attr_name)

    return restored
