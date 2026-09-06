# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Web Interface
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# WEB_INTERFACE.PY - REAL-TIME WEB FRONTEND
# ============================================================================
#
# ARCHITECTURE ROLE: User Interface Layer - Real-Time Web Frontend
#
# This module provides a modern Flask-based web interface with SocketIO integration
# for real-time bidirectional communication between the browser and game engine,
# enabling responsive tabbed character data display and live game state updates.
#
# KEY RESPONSIBILITIES:
# - Flask + SocketIO real-time web server management
# - Tabbed interface design with dynamic character data presentation
# - Queue-based threaded output processing for responsive user experience
# - Real-time game state synchronization across multiple browser sessions
# - Cross-platform browser-based interface compatibility
# - Status broadcasting integration with console and web interfaces
# - Session state management linking web sessions to game state
#

"""
Web Interface for NeverEndingQuest

This module provides a Flask-based web interface for the dungeon master game,
with separate panels for game output and debug information.
"""
# Suppress httpx debug messages on startup
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import hashlib
import sys
import hmac
import secrets

# Add parent directory to path FIRST so we can import from utils, core, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, Response, abort, session
from flask_socketio import SocketIO, emit
import json
import threading
import queue
import time
import webbrowser
from datetime import datetime
from collections import deque
import io
import zipfile
from uuid import uuid4
from contextlib import redirect_stdout, redirect_stderr
from openai import OpenAI
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T094", "web/web_interface.py", 1816)
register_callsite("T095", "web/web_interface.py", 4277)
from utils.compendium_store import (
    MONSTER_COMPENDIUM_PATH,
    NPC_COMPENDIUM_PATH,
    compendium_entry_exists,
    merge_compendium_entries,
    merge_npc_description_pair,
    validate_generated_prose,
)
from utils.encoding_utils import sanitize_text
from PIL import Image

# Token tracking import
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# Install debug interceptor before importing main
from utils.redirect_debug_output import install_debug_interceptor, uninstall_debug_interceptor
install_debug_interceptor()

# Import the main game module and reset logic
import main as dm_main
import utils.reset_campaign as reset_campaign
from core.managers.status_manager import set_status_callback, set_compression_callback
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Import toolkit components for API support
try:
    from core.toolkit.pack_manager import PackManager
    from core.toolkit.monster_generator import MonsterGenerator
    from core.toolkit.video_processor import VideoProcessor
    TOOLKIT_AVAILABLE = True
except ImportError:
    TOOLKIT_AVAILABLE = False
    print("Module Toolkit not available - toolkit endpoints disabled")

# Set script name for logging
set_script_name("web_interface")

# Apply a web-set OpenAI key from user_settings.json at startup (no-op if none).
# Import config FIRST so apply_persisted_openai_key() has the canonical `config`
# module in sys.modules to write into (it no-ops if 'config' isn't loaded). Doing
# the import here means this does NOT depend on the transitive `import main`
# side-effect above -- it stays correct even if these import lines are reordered.
# config.py itself runs after `from model_config import *`, so its default
# OPENAI_API_KEY is already set by the time we overwrite it with the persisted one.
try:
    import config as _cfg_boot  # noqa: F401  (ensure config is loaded before applying)
    import model_config as _mc
    _mc.apply_persisted_openai_key()
    _mc.apply_persisted_gemini_key()
except Exception:
    pass

# Set up Flask with correct template and static paths
# Templates are in both web/templates (for game) and root templates (for toolkit)
# Get the directory where this file is located
current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')
static_dir = os.path.join(current_dir, 'static')

# Debug: Print paths for troubleshooting
print(f"Web Interface starting from: {current_dir}")
print(f"Looking for templates in: {template_dir}")
print(f"Looking for static files in: {static_dir}")

# Ensure template directory exists
if not os.path.exists(template_dir):
    print(f"WARNING: Template directory not found at {template_dir}")
    # Try alternate location
    alt_template_dir = os.path.join(os.path.dirname(current_dir), 'templates')
    if os.path.exists(alt_template_dir):
        template_dir = alt_template_dir
        print(f"Using alternate template directory: {template_dir}")
    else:
        print(f"ERROR: No template directory found! Checked:")
        print(f"  - {template_dir}")
        print(f"  - {alt_template_dir}")

# Check if game_interface.html exists
game_interface_path = os.path.join(template_dir, 'game_interface.html')
if os.path.exists(game_interface_path):
    print(f"Found game_interface.html at: {game_interface_path}")
else:
    print(f"WARNING: game_interface.html not found at: {game_interface_path}")

WEB_HOST = os.environ.get("NEQ_WEB_HOST", "127.0.0.1").strip() or "127.0.0.1"
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_OPERATOR_TOKEN = os.environ.get("NEQ_OPERATOR_TOKEN", "").strip()

if WEB_HOST not in _LOOPBACK_HOSTS and not _OPERATOR_TOKEN:
    raise RuntimeError(
        "Refusing to expose NeverEndingQuest beyond this computer without an "
        "operator token. Set NEQ_OPERATOR_TOKEN to a long random value."
    )

app = Flask(__name__,
            template_folder=template_dir,
            static_folder=static_dir)
# A random per-process secret is safe for local play and avoids a known signing
# key. Operators who need stable sessions can supply NEQ_FLASK_SECRET_KEY.
app.config['SECRET_KEY'] = os.environ.get("NEQ_FLASK_SECRET_KEY") or secrets.token_urlsafe(32)
# Same-origin is the safe default. Explicit cross-origin support is not needed
# for the bundled UI, which is served by this Flask application.
socketio = SocketIO(app, cors_allowed_origins=None)


@app.before_request
def require_operator_token_for_network_mode():
    """Protect every HTTP route whenever the operator explicitly enables LAN use."""
    if not _OPERATOR_TOKEN or session.get("operator_authenticated"):
        return None
    supplied = request.args.get("operator_token", "") or request.headers.get(
        "X-NEQ-Operator-Token", ""
    )
    if supplied and hmac.compare_digest(supplied, _OPERATOR_TOKEN):
        session["operator_authenticated"] = True
        return None
    abort(401)


@app.after_request
def add_security_headers(response):
    """Keep the optional LAN bootstrap token out of referrers and caches."""
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if _OPERATOR_TOKEN:
        response.headers.setdefault("Cache-Control", "no-store")
    return response

# Add static route for graphic_packs to improve thumbnail loading performance
@app.route('/graphic_packs/<path:filename>')
def serve_graphic_packs(filename):
    """Serve files from graphic_packs directory as static files for better performance"""
    from flask import send_from_directory
    import os
    graphic_packs_dir = os.path.abspath('graphic_packs')
    return send_from_directory(graphic_packs_dir, filename)

# Suppress werkzeug HTTP request logs (they clutter the console)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Only show errors, not every HTTP request

# Import shared state
from web.shared_state import (
    SAFE_ACTION_FAILURE_MESSAGE,
    module_progress_queue,
    set_player_output_sink,
)

# Global variables for managing output
game_output_queue = queue.Queue()
debug_output_queue = queue.Queue()
user_input_queue = queue.Queue()
# module_progress_queue imported from shared_state
game_thread = None
_ui_revision = 0
_ui_revision_lock = threading.Lock()
_server_instance_id = uuid4().hex
_ui_protocol_capabilities = {
    "protocol_version": 1,
    "request_metadata": True,
}
_ui_operation_lock = threading.Lock()
_ui_operations = {"compression": None, "module": None, "update": None, "restore": None}
# Preserve the original managed-save root while an in-process Load needs recovery.
# This is not a persisted recovery record and does not claim crash reconstruction.
_restore_manager = None
original_stdout = sys.stdout
original_stderr = sys.stderr
original_stdin = sys.stdin
STARTUP_RECOVERY_ACTION_COOLDOWN_SECONDS = 10
startup_recovery_attempts = {}
startup_recovery_attempts_lock = threading.Lock()
startup_handoff_active = False
startup_ready_emitted = False

# Message cache for persistence across restarts
MESSAGE_CACHE_FILE = "modules/conversation_history/game_interface_cache.json"
MESSAGE_CACHE_SIZE = 15  # Keep last 15 messages
message_cache = deque(maxlen=MESSAGE_CACHE_SIZE)
message_cache_lock = threading.RLock()

def _ui_response(request_data, payload):
    """Add optional correlation and a monotonic response revision.

    Legacy callers send no payload and ignore the extra response fields. React
    uses them to reject delayed responses from an earlier request/connection.
    """
    global _ui_revision
    with _ui_revision_lock:
        _ui_revision += 1
        revision = _ui_revision
    result = dict(payload)
    result['revision'] = revision
    result['server_instance_id'] = _server_instance_id
    if isinstance(request_data, dict) and request_data.get('request_id'):
        result['request_id'] = request_data['request_id']
    return result


def _remember_ui_operation(kind, payload):
    """Keep the latest operation state so reconnect snapshots can self-heal."""
    with _ui_operation_lock:
        _ui_operations[kind] = dict(payload) if isinstance(payload, dict) else None


def _web_restore_state():
    with _ui_operation_lock:
        return dict(_ui_operations.get('restore') or {})


def _web_gameplay_paused():
    state = _web_restore_state()
    return bool(state.get('pending') or state.get('restart_required')
                or state.get('can_resume') is False)


def _web_save_manager():
    from updates.save_game_manager import SaveGameManager
    with _ui_operation_lock:
        retained = _restore_manager
    return retained if retained is not None else SaveGameManager()


def _begin_web_restore(manager, message, previous_clean=True):
    global _restore_manager
    with _ui_operation_lock:
        _restore_manager = manager
        _ui_operations['restore'] = {
            'pending': True, 'message': message, 'can_resume': previous_clean,
        }


def _apply_web_restore(manager, save_folder, previous_clean):
    from updates.save_game_manager import RestoreOutcome
    try:
        _begin_web_restore(manager, 'Restoring the selected save.', previous_clean)
        return manager.restore_save_game_outcome(save_folder, previous_clean=previous_clean)
    except Exception as exc:
        # An exception outside the manager's verified outcome cannot prove a
        # clean directory. Keep the same control surface and original root.
        return RestoreOutcome('recovery_required', f'Load could not verify a clean state: {exc}')


def _finish_web_restore(manager, outcome):
    global _restore_manager
    payload = {
        'message': outcome.message,
        'restore_outcome': outcome.disposition,
        'can_resume': outcome.can_resume,
        'restart_required': outcome.can_resume,
    }
    if not outcome.can_resume:
        payload['message'] += ' Gameplay is paused. Choose Load, Reset, or Exit.'
    with _ui_operation_lock:
        _restore_manager = None if outcome.can_resume else manager
        _ui_operations['restore'] = payload
    # All attached clients must see the same admission/result, not only the
    # requesting tab. The welcome callback may run on the game thread: no join.
    try:
        socketio.emit('restore_complete', payload)
    finally:
        try:
            emit_status_update(payload['message'], False)
        finally:
            # A disconnected browser cannot veto the verified disk terminal.
            # Reconnect can obtain the stored operation if no restart is safe.
            if outcome.can_resume:
                try:
                    socketio.sleep(1)
                finally:
                    os._exit(0)


def _stop_web_game_reader():
    """Unwind stale in-memory gameplay before an idle controller replaces disk."""
    if game_thread and game_thread.is_alive():
        if game_thread is threading.current_thread():
            raise RuntimeError('A welcome restore must use its game-thread terminal')
        user_input_queue.put(None)
        started = time.monotonic()
        while game_thread.is_alive():
            game_thread.join(0.5)
            if game_thread.is_alive():
                try:
                    emit_status_update(
                        'Waiting for the previous game to stop safely (%d seconds)...'
                        % int(time.monotonic() - started), True,
                    )
                except Exception:
                    # Presentation failure is not permission to leave the
                    # reader running while Load replaces its state.
                    pass


@app.get('/api/server-instance')
def get_server_instance():
    return jsonify({'server_instance_id': _server_instance_id})

# Message cache functions
def load_message_cache():
    """Load message cache from file"""
    global message_cache
    try:
        if os.path.exists(MESSAGE_CACHE_FILE):
            with open(MESSAGE_CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_messages = json.load(f)
                migrated = False
                for index, message in enumerate(cached_messages):
                    if isinstance(message, dict) and not message.get("message_id"):
                        canonical = json.dumps(message, sort_keys=True, ensure_ascii=False)
                        digest = hashlib.sha256(f"{index}:{canonical}".encode("utf-8")).hexdigest()[:24]
                        message["message_id"] = f"legacy-{digest}"
                        migrated = True
                message_cache = deque(cached_messages, maxlen=MESSAGE_CACHE_SIZE)
                if migrated:
                    save_message_cache()
                print(f"[MESSAGE_CACHE] Loaded {len(message_cache)} cached messages")
                return cached_messages
    except Exception as e:
        print(f"[MESSAGE_CACHE] Failed to load cache: {e}")
    return []

def save_message_cache():
    """Save message cache to file"""
    try:
        from utils.file_operations import safe_write_json

        return safe_write_json(
            MESSAGE_CACHE_FILE,
            list(message_cache),
            create_backup=False,
        )
    except Exception as e:
        print(f"[MESSAGE_CACHE] Failed to save cache: {e}")
        return False


def _message_cache_matches(message):
    """Accept replay only when durable stable identity and content match."""
    if not isinstance(message, dict):
        return False
    message_id = message.get("message_id")
    if not isinstance(message_id, str) or not message_id:
        return False
    with message_cache_lock:
        from utils.file_operations import atomic_writer

        acquired = False
        try:
            atomic_writer.acquire_lock(MESSAGE_CACHE_FILE)
            acquired = True
            if not os.path.exists(MESSAGE_CACHE_FILE):
                return False
            with open(MESSAGE_CACHE_FILE, 'r', encoding='utf-8') as handle:
                durable = json.load(handle)
            if not isinstance(durable, list):
                return False
            message_cache.clear()
            message_cache.extend(durable[-MESSAGE_CACHE_SIZE:])
            for cached in durable:
                if not isinstance(cached, dict):
                    continue
                if cached.get("message_id") == message_id:
                    return cached == message
        except Exception:
            return False
        finally:
            if acquired:
                atomic_writer.release_lock(MESSAGE_CACHE_FILE)
    return False

def add_to_message_cache(message):
    """Add a message once; stable IDs deduplicate replayable safe output."""
    if not isinstance(message, dict):
        return False
    message_id = message.get("message_id")
    if message_id is not None and (
        not isinstance(message_id, str) or not message_id.strip()
    ):
        return False
    cacheable = message.get('type') in ['narration', 'user-input']
    cacheable = cacheable or message_id is not None
    if not cacheable:
        return False
    if message_id is None:
        # Cache/live/reconnect delivery must carry one identity. Mutating the
        # payload is intentional: the same ID is persisted and emitted live.
        message_id = f"msg-{uuid4().hex}"
        message["message_id"] = message_id
    with message_cache_lock:
        from utils.file_operations import atomic_writer, safe_write_json

        acquired = False
        try:
            # The file lock makes read/merge/write one cross-process operation.
            # Atomic replacement alone prevents torn JSON but cannot prevent
            # two server processes from overwriting each other's stable IDs.
            atomic_writer.acquire_lock(MESSAGE_CACHE_FILE)
            acquired = True
            if os.path.exists(MESSAGE_CACHE_FILE):
                with open(MESSAGE_CACHE_FILE, 'r', encoding='utf-8') as handle:
                    durable = json.load(handle)
                if not isinstance(durable, list):
                    return False
                base = durable[-MESSAGE_CACHE_SIZE:]
            else:
                base = list(message_cache)
            if message_id is not None and any(
                cached.get("message_id") == message_id
                for cached in base
                if isinstance(cached, dict)
            ):
                message_cache.clear()
                message_cache.extend(base)
                return False
            candidate = (base + [dict(message)])[-MESSAGE_CACHE_SIZE:]
            if not safe_write_json(
                MESSAGE_CACHE_FILE,
                candidate,
                create_backup=False,
                acquire_lock=False,
            ):
                return False
            message_cache.clear()
            message_cache.extend(candidate)
        except Exception:
            return False
        finally:
            if acquired:
                atomic_writer.release_lock(MESSAGE_CACHE_FILE)
    return True


def _queue_safe_player_output(message):
    """Route normalized player output through the existing web game queue."""
    try:
        payload = dict(message)
        if not add_to_message_cache(payload):
            # Stable-ID replay is successful when the exact message already
            # exists in the durable cache; do not enqueue a duplicate.
            return _message_cache_matches(payload)
        game_output_queue.put(payload)
        return True
    except Exception:
        return False


# NOTE: the sink is installed in handle_start_game(), NOT here at import
# time. This module is imported by action_handler even in terminal and
# headless modes; claiming the sink at import would silently swallow
# player output into game_output_queue where nothing drains it.


def _emit_pending_game_output(emit_function):
    """Drain current player output through a supplied Socket.IO emitter."""
    emitted = 0
    while True:
        try:
            message = game_output_queue.get_nowait()
        except queue.Empty:
            break
        try:
            emit_function("game_output", message)
            emitted += 1
        except Exception:
            break
    return emitted

def log_web_audit(event_name, **fields):
    """Emit a compact audit/debug log line for web actions."""
    details = ", ".join(f"{key}={value}" for key, value in fields.items())
    message = f"AUDIT: {event_name}"
    if details:
        message = f"{message} | {details}"
    debug(message, category="web_interface")

# Status callback function
def emit_status_update(status_message, is_processing):
    """Emit status updates to the frontend"""
    restore = _web_restore_state()
    recovery_required = restore.get('can_resume') is False
    if restore.get('pending') and not is_processing:
        status_message = restore.get('message', 'The lifecycle operation is finishing safely.')
        is_processing = True
    if recovery_required and not is_processing:
        status_message = restore.get('message', 'Gameplay is paused. Choose Load, Reset, or Exit.')
    socketio.emit('status_update', {
        'message': status_message,
        'is_processing': is_processing,
        'recovery_required': recovery_required,
    })

# Set the status callback
set_status_callback(emit_status_update)

# Set the compression callback
def emit_compression_event(event_type, data):
    """Emit compression progress events to the web interface"""
    operation = dict(data)
    operation['event'] = event_type
    operation['status'] = 'failed' if event_type == 'compression_error' else ('complete' if event_type == 'compression_complete' else 'running')
    _remember_ui_operation('compression', operation)
    socketio.emit(event_type, data)

set_compression_callback(emit_compression_event)

def emit_welcome_progress(message):
    """#214 D-214-4=A: background startup-welcome liveness. A SEPARATE
    presentational channel - never status_update{is_processing}, so it can
    never lock the command input."""
    socketio.emit('welcome_progress', {'message': message})

try:
    from core.managers.status_manager import status_manager as _status_manager_instance
    _status_manager_instance.set_welcome_callback(emit_welcome_progress)
except Exception:
    pass

def _is_operational_diagnostic(clean_line):
    """E2E gate 2a: operational diagnostics that must reach the Debug tab, not be
    swallowed as DM narration. The DM-section terminators only recognize UPPERCASE
    'DEBUG:/ERROR:/WARNING:'; recovery/quarantine/module lines carry an UNAMBIGUOUS
    bracket tag and were being appended to the narration buffer. We match ONLY those
    reserved bracket tags (by line prefix) -- deliberately NOT bare 'Error:'/'Warning:'
    words, which in-fiction DM prose could legitimately start a wrapped line with
    (a read-aloud sign/note), which would truncate narration. Engine diagnostics
    that must surface use one of these tags."""
    if not isinstance(clean_line, str):
        return False
    return clean_line.lstrip().startswith(('[LIFECYCLE]', '[MODULES]', '[STARTUP]'))


class WebOutputCapture:
    """Captures output and routes it to appropriate queues"""
    def __init__(self, queue, original_stream, is_error=False):
        self.queue = queue
        self.original_stream = original_stream
        self.is_error = is_error
        self.buffer = ""
        self.in_dm_section = False
        self.dm_buffer = []
        self.dm_section_is_startup = False

    def _flush_dm_buffer(self):
        global startup_ready_emitted
        if not self.dm_buffer:
            return
        try:
            combined_content = '\n'.join(self.dm_buffer)
            combined_content = combined_content.replace('Dungeon Master:', '', 1).strip()
            if combined_content.strip():
                # DM narration is always type 'narration' so the client renders it
                # with the full DM message styling (avatar, header, Generate Image).
                # The old 'startup' type rendered as plain text with no formatting.
                message = {
                    'type': 'narration',
                    'content': combined_content
                }
                game_output_queue.put(message)
                add_to_message_cache(message)
                debug_output_queue.put({
                    'type': 'debug',
                    'content': f"[OUTPUT_TRACE] Sent DM content to game_output: {len(combined_content)} chars",
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            try:
                debug_output_queue.put({
                    'type': 'debug',
                    'content': f"[OUTPUT_ERROR] DM content processing failed: {str(e)} - Buffer: {str(self.dm_buffer)}",
                    'timestamp': datetime.now().isoformat()
                })
            except Exception:
                pass
        finally:
            self.in_dm_section = False
            self.dm_buffer = []
            self.dm_section_is_startup = False
    
    def _mark_ready_from_player_prompt(self, clean_line):
        """Publish web readiness when the engine reaches its input prompt.

        ``input(prompt)`` writes the prompt without a trailing newline.  The
        legacy page waits for ``game_started``, so checking only completed
        lines can leave it stuck on ``Starting...`` even though the engine is
        already blocked for the player's command.
        """
        global startup_handoff_active, startup_ready_emitted
        if not (
            clean_line.startswith('[')
            and ('HP:' in clean_line or 'XP:' in clean_line)
        ):
            return False
        if not startup_ready_emitted:
            startup_handoff_active = False
            startup_ready_emitted = True
            debug_output_queue.put({
                'type': 'debug',
                'content': '[STARTUP_FALLBACK] game_started emitted via prompt detection - primary marker path may have failed',
                'timestamp': datetime.now().isoformat()
            })
            socketio.emit(
                "startup_status", {"status": "ready", "phase": "prompt_detected"}
            )
            socketio.emit(
                'game_started', {'message': 'Game started successfully'}
            )
        return True

    def write(self, text):
        global startup_handoff_active, startup_ready_emitted
        # Write to original stream for console visibility (with error handling)
        try:
            # Ensure text is a string and handle encoding issues
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            elif not isinstance(text, str):
                text = str(text)
            
            self.original_stream.write(text)
            self.original_stream.flush()
        except (BrokenPipeError, OSError, UnicodeEncodeError, AttributeError):
            # Ignore broken pipe errors, encoding errors, and attribute errors during output capture
            pass
        except Exception:
            # Catch any other unexpected errors and continue
            pass
        
        # Buffer text until we have a complete line
        self.buffer += text
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            # Process all complete lines
            for line in lines[:-1]:
                # Clean the line of ANSI codes for checking content
                clean_line = self.strip_ansi_codes(line)

                # Startup marker stream: drive web readiness state.
                marker_line = False
                if "STARTUP_MARKER:" in clean_line:
                    try:
                        marker_line = True
                        marker_payload = clean_line.split("STARTUP_MARKER:", 1)[1].strip()
                        marker_data = json.loads(marker_payload)
                        phase = marker_data.get("phase", "")
                        if phase in {
                            "startup_handoff_begin",
                            "startup_wizard_sync",
                            "startup_wizard_complete",
                            "startup_context_built",
                            "startup_kickoff_attempted",
                        }:
                            startup_handoff_active = True
                            socketio.emit("startup_status", {"status": "in_progress", "phase": phase})
                        if phase in {"startup_kickoff_done", "startup_loop_ready"}:
                            # #214: startup_loop_ready fires when the game
                            # loop reaches its input read - input unlocks
                            # IMMEDIATELY while a background welcome may still
                            # be generating (D-214-1=B).
                            startup_handoff_active = False
                            socketio.emit("startup_status", {"status": "ready", "phase": phase})
                            # Marker is authoritative - emit immediately when detected
                            if not startup_ready_emitted:
                                startup_ready_emitted = True
                                socketio.emit('game_started', {'message': 'Game started successfully'})
                        elif phase == "startup_kickoff_skipped":
                            if marker_data.get("result") == "already_done":
                                startup_handoff_active = False
                                socketio.emit("startup_status", {"status": "ready", "phase": phase})
                                if not startup_ready_emitted:
                                    startup_ready_emitted = True
                                    socketio.emit('game_started', {'message': 'Game started successfully'})
                        elif phase in {"startup_kickoff_failed", "startup_kickoff_stale_discarded"}:
                            startup_handoff_active = False
                            startup_state = dm_main.load_startup_state() or {}
                            socketio.emit("startup_status", {
                                "status": "failed",
                                "phase": phase,
                                "startupAttemptId": startup_state.get("startup_attempt_id"),
                            })
                    except Exception:
                        pass
                    if marker_line:
                        continue
                
                # Check if this is a player status/prompt line
                if self._mark_ready_from_player_prompt(clean_line):
                    # This is a player prompt - send to debug
                    debug_output_queue.put({
                        'type': 'debug',
                        'content': clean_line,
                        'timestamp': datetime.now().isoformat()
                    })
                # Check if this starts a Dungeon Master section
                elif "Dungeon Master:" in clean_line:
                    try:
                        # Start capturing DM content
                        self.in_dm_section = True
                        self.dm_buffer = [clean_line]
                        self.dm_section_is_startup = startup_handoff_active
                        # Debug trace for combat output
                        debug_output_queue.put({
                            'type': 'debug',
                            'content': f"[OUTPUT_TRACE] Started DM section: {clean_line[:100]}...",
                            'timestamp': datetime.now().isoformat()
                        })
                    except Exception:
                        # If DM section initialization fails, send to debug instead
                        debug_output_queue.put({
                            'type': 'debug',
                            'content': f"[OUTPUT_ERROR] DM section init failed: {clean_line}",
                            'timestamp': datetime.now().isoformat()
                        })
                elif self.in_dm_section:
                    # Check if we're still in DM section
                    if line.strip() == "":
                        try:
                            # Empty line - still part of DM section, add to buffer
                            self.dm_buffer.append("")
                        except Exception:
                            # If buffer append fails, reset DM section
                            self.in_dm_section = False
                            self.dm_buffer = []
                    elif any(marker in clean_line for marker in ['DEBUG:', 'ERROR:', 'WARNING:']) or \
                         _is_operational_diagnostic(clean_line) or \
                         clean_line.startswith('[') and ('HP:' in clean_line or 'XP:' in clean_line) or \
                         clean_line.startswith('>'):
                        # This ends the DM section - send accumulated DM content as single message
                        # (issue #167 / E2E 2a: operational diagnostics now terminate the DM
                        # section and route to debug instead of being swallowed as narration.)
                        self._flush_dm_buffer()
                        # Send this line to debug
                        try:
                            debug_output_queue.put({
                                'type': 'debug',
                                'content': clean_line,
                                'timestamp': datetime.now().isoformat(),
                                'is_error': self.is_error or 'ERROR:' in clean_line
                            })
                        except Exception:
                            # If debug queue fails, just continue
                            pass
                    else:
                        # Still in DM section - check if it's a debug message
                        if any(marker in clean_line for marker in [
                            'Lightweight chat history updated',
                            'System messages removed:',
                            'User messages:',
                            'Assistant messages:',
                            'not found. Skipping',
                            'not found. Returning None',
                            'has an invalid JSON format',
                            'Current Time:',
                            'Time Advanced:',
                            'New Time:',
                            'Days Passed:',
                            'Loading module areas',
                            'Graph built:',
                            '[OK] Loaded'
                        ]):
                            # This is a debug message - send to debug output instead
                            debug_output_queue.put({
                                'type': 'debug',
                                'content': clean_line,
                                'timestamp': datetime.now().isoformat()
                            })
                            # End the DM section and send what we have so far
                            if self.dm_buffer:
                                try:
                                    combined_content = '\n'.join(self.dm_buffer)
                                    combined_content = combined_content.replace('Dungeon Master:', '', 1).strip()
                                    if combined_content.strip():
                                        message = {
                                            'type': 'narration',
                                            'content': combined_content
                                        }
                                        game_output_queue.put(message)
                                        add_to_message_cache(message)
                                except Exception:
                                    # If DM content processing fails, just continue
                                    pass
                            self.in_dm_section = False
                            self.dm_buffer = []
                        else:
                            try:
                                # Not a debug message - add to buffer
                                self.dm_buffer.append(clean_line)
                            except Exception:
                                # If buffer append fails, reset DM section
                                self.in_dm_section = False
                                self.dm_buffer = []
                else:
                    # Not in DM section - check if it's a debug message that should be filtered
                    if any(marker in clean_line for marker in [
                        'Lightweight chat history updated',
                        'System messages removed:',
                        'User messages:',
                        'Assistant messages:',
                        'not found. Skipping',
                        'not found. Returning None',
                        'has an invalid JSON format',
                        'Current Time:',
                        'Time Advanced:',
                        'New Time:',
                        'Days Passed:',
                        'Loading module areas',
                        'Graph built:',
                        '[OK] Loaded'
                    ]):
                        # These are debug messages - send to debug output
                        debug_output_queue.put({
                            'type': 'debug',
                            'content': clean_line,
                            'timestamp': datetime.now().isoformat()
                        })
                    elif line.strip():  # Only send non-empty lines
                        debug_output_queue.put({
                            'type': 'debug',
                            'content': clean_line,
                            'timestamp': datetime.now().isoformat(),
                            'is_error': self.is_error or 'ERROR:' in clean_line
                        })
            # Keep the incomplete line in buffer
            self.buffer = lines[-1]
    
        # ``input(prompt)`` does not append a newline. Inspect the buffered
        # fragment as well so both web clients become playable at the exact
        # point where the engine begins accepting input.
        self._mark_ready_from_player_prompt(self.strip_ansi_codes(self.buffer))

    def strip_ansi_codes(self, text):
        """Remove ANSI escape codes from text"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def flush(self):
        # If we're in a DM section, flush it as single message
        if self.in_dm_section and self.dm_buffer:
            combined_content = '\n'.join(self.dm_buffer)
            # Remove "Dungeon Master:" prefix from the beginning if present
            combined_content = combined_content.replace('Dungeon Master:', '', 1).strip()
            if combined_content.strip():  # Only send if there's actual content
                message = {
                    'type': 'narration',
                    'content': combined_content
                }
                game_output_queue.put(message)
                add_to_message_cache(message)
            self.in_dm_section = False
            self.dm_buffer = []
        
        if self.buffer:
            # Don't recursively call write() - just add newline to buffer
            self.buffer += '\n'
        try:
            self.original_stream.flush()
        except (BrokenPipeError, OSError, UnicodeEncodeError, AttributeError):
            # Ignore broken pipe errors, encoding errors, and attribute errors during flush
            pass
        except Exception:
            # Catch any other unexpected errors and continue
            pass

class WebInput:
    """Handles input from the web interface"""
    def __init__(self, queue):
        self.queue = queue
    
    def readline(self):
        from utils.capture.live_provider_call import (
            LiveProviderSuperseded, service_live_input_boundary,
        )

        service_live_input_boundary()
        if _web_gameplay_paused():
            raise LiveProviderSuperseded('An accepted lifecycle control stopped gameplay')
        # Signal that we're ready for input (with error handling)
        try:
            from core.managers.status_manager import status_ready
            # Game thread parking for input = authoritative open-input
            # boundary, even mid-scope (combat sub-loop turns).
            status_ready(at_input_boundary=True)
        except Exception:
            # If status_ready fails, continue without it
            pass
        
        # Wait patiently for input from the web interface. A turn-based game
        # should block at the prompt indefinitely, exactly like a terminal would.
        # (Previously this capped at 1000 * 0.1s = 100s and then returned '\n',
        # which made the combat loop busy-spin on empty input -- see issue #122.)
        while True:
            drained = service_live_input_boundary()
            if _web_gameplay_paused():
                raise LiveProviderSuperseded('An accepted lifecycle control stopped gameplay')
            if drained:
                # Re-open only the game thread's existing parked input boundary.
                try:
                    from core.managers.status_manager import status_ready
                    status_ready(at_input_boundary=True)
                except Exception:
                    pass
            try:
                user_input = self.queue.get(timeout=0.5)
            except queue.Empty:
                # #214: the game thread parks here between turns; this pump
                # services the off-thread startup-welcome lifecycle (lease
                # renewal, handback apply/discard) without fake player input.
                try:
                    from core.managers.status_manager import run_input_poll_hook
                    run_input_poll_hook()
                except Exception:
                    pass
                continue
            except (BrokenPipeError, OSError, IOError, EOFError):
                # Genuine end-of-input: return '' so input() raises EOFError and
                # the caller's loop exits cleanly instead of spinning on empty lines.
                return ''
            except Exception:
                # Unexpected failure: signal EOF for a clean exit rather than
                # looping forever on empty input.
                return ''
            service_live_input_boundary()
            if _web_gameplay_paused():
                raise LiveProviderSuperseded('An accepted lifecycle control stopped gameplay')
            if user_input is None:
                return ''
            if isinstance(user_input, str):
                return user_input + '\n'
            return str(user_input) + '\n'

@app.route('/')
def index():
    """Serve the main game interface"""
    # Read version from VERSION file
    try:
        with open('VERSION', 'r') as f:
            version = f.read().strip()
    except:
        version = "0.3.2"

    return render_template('game_interface.html', version=version)

@app.route('/static/media/videos/<path:filename>')
def serve_video(filename):
    """Serve video files from the media directory"""
    import os
    from flask import send_file
    video_path = os.path.join(os.path.dirname(__file__), 'static', 'media', 'videos', filename)
    if os.path.exists(video_path):
        return send_file(video_path, mimetype='video/mp4')
    return "Video not found", 404

@app.route('/static/dm_logo.png')
def serve_dm_logo():
    """Serve the DM logo image"""
    import mimetypes
    from flask import send_file
    # Go up one directory to find dm_logo.png at the root
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dm_logo.png')
    return send_file(logo_path, mimetype='image/png')

@app.route('/static/icons/<path:filename>')
def serve_icon(filename):
    """Serve icon images from the icons directory"""
    import mimetypes
    from flask import send_file
    # Ensure the filename ends with .png for security
    if not filename.endswith('.png'):
        return "Not found", 404
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icons', filename)
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype='image/png')
    return "Not found", 404

@app.route('/static/portraits/<path:filename>')
def serve_portrait(filename):
    """Serve character portrait images."""
    import mimetypes
    from flask import send_file
    # Ensure the filename ends with .png for security
    if not filename.endswith('.png'):
        return "Not found", 404
    portrait_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'portraits', filename)
    if os.path.exists(portrait_path):
        return send_file(portrait_path, mimetype='image/png')
    return "Not found", 404

@app.route('/media/<media_type>/<path:filename>')
def serve_module_media(media_type, filename):
    """
    Smart media endpoint that checks module-specific media first, then falls back to static.
    Priority order:
    1. modules/[current_module]/media/[type]/[filename]
    2. web/static/media/[type]/[filename]
    
    media_type: 'monsters', 'npcs', or 'environment'
    filename: the requested file (e.g., 'goblin_thumb.jpg', 'grimjaw_video.mp4')
    """
    import mimetypes
    from flask import send_file
    from utils.file_operations import safe_read_json
    
    # Validate media type
    if media_type not in ['monsters', 'npcs', 'environment']:
        return "Invalid media type", 404
    
    # Determine current module from party tracker
    current_module = None
    party_data = safe_read_json('party_tracker.json')
    if party_data:
        # Check both 'module' and 'module_name' fields for compatibility
        current_module = party_data.get('module') or party_data.get('module_name')
    
    # Priority 1: Check current module's media folder first
    if current_module:
        module_media_path = os.path.join('modules', current_module, 'media', media_type, filename)
        if os.path.exists(module_media_path):
            mimetype, _ = mimetypes.guess_type(module_media_path)
            info(f"Serving {media_type}/{filename} from current module: {current_module}")
            return send_file(os.path.abspath(module_media_path), mimetype=mimetype)
    
    # Priority 2: Check ALL other modules for the media file
    modules_dir = 'modules'
    if os.path.exists(modules_dir):
        for module_name in os.listdir(modules_dir):
            # Skip non-directories and the current module
            module_path = os.path.join(modules_dir, module_name)
            if os.path.isdir(module_path) and module_name != current_module:
                module_media_path = os.path.join(module_path, 'media', media_type, filename)
                if os.path.exists(module_media_path):
                    mimetype, _ = mimetypes.guess_type(module_media_path)
                    info(f"Serving {media_type}/{filename} from module: {module_name}")
                    return send_file(os.path.abspath(module_media_path), mimetype=mimetype)
    
    # Priority 3: Fall back to static media folder
    static_media_path = os.path.join(os.path.dirname(__file__), 'static', 'media', media_type, filename)
    if os.path.exists(static_media_path):
        mimetype, _ = mimetypes.guess_type(static_media_path)
        info(f"Serving {media_type}/{filename} from static folder")
        return send_file(static_media_path, mimetype=mimetype)
    
    warning(f"Media file not found in any location: {media_type}/{filename}")
    return "Media not found", 404

@app.route('/get_character_data')
def get_character_data():
    """Get character data including class for NPC portraits."""
    try:
        from utils.file_operations import safe_read_json
        
        character_name = request.args.get('character_name')
        if not character_name:
            return jsonify({'error': 'No character name provided'}), 400
        
        # Look for character file in characters folder
        character_path = f'characters/{character_name}.json'
        character_data = safe_read_json(character_path)
        
        if character_data:
            # Return relevant character data
            return jsonify({
                'name': character_data.get('name'),
                'class': character_data.get('class'),
                'race': character_data.get('race'),
                'level': character_data.get('level')
            })
        else:
            return jsonify({'error': 'Character not found'}), 404
            
    except Exception as e:
        error(f"Error getting character data: {e}", exception=e, category="web_interface")
        return jsonify({'error': str(e)}), 500


def _effective_character_for_ui(character_data):
    """Project declarative modifiers without changing the saved sheet."""
    if not isinstance(character_data, dict):
        return character_data
    try:
        from core.effects.effective import effective_sheet
        return effective_sheet(character_data)
    except Exception:
        pass
    return character_data

@app.route('/upload-portrait', methods=['POST'])
def upload_portrait():
    """Handle character portrait upload, cropping, and saving."""
    try:
        if 'portrait' not in request.files:
            return jsonify({'success': False, 'message': 'No file part'})
        
        file = request.files['portrait']
        character_name = request.form.get('characterName')

        if file.filename == '' or not character_name:
            return jsonify({'success': False, 'message': 'No selected file or character name'})

        import re
        if not re.fullmatch(r"[a-z0-9_'-]{1,100}", character_name):
            return jsonify({'success': False, 'message': 'Invalid character name'}), 400
        if request.content_length and request.content_length > 10 * 1024 * 1024:
            return jsonify({'success': False, 'message': 'Portrait must be smaller than 10 MB'}), 413

        if file:
            # Create the portraits directory if it doesn't exist
            portraits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'portraits')
            os.makedirs(portraits_dir, exist_ok=True)

            # Open the image with Pillow
            img = Image.open(file.stream)
            img.verify()
            file.stream.seek(0)
            img = Image.open(file.stream).convert('RGB')

            # --- Cropping Logic ---
            width, height = img.size
            if width != height:
                # Find the smaller dimension
                min_dim = min(width, height)
                # Calculate coordinates for a center crop
                left = (width - min_dim) / 2
                top = (height - min_dim) / 2
                right = (width + min_dim) / 2
                bottom = (height + min_dim) / 2
                img = img.crop((left, top, right, bottom))
            
            # Resize to a standard size (e.g., 256x256) for consistency
            img = img.resize((256, 256), Image.Resampling.LANCZOS)

            # Save the processed image as PNG in web static folder
            save_filename = f"{character_name}.png"
            save_path = os.path.join(portraits_dir, save_filename)
            img.save(save_path, 'PNG')
            
            # Also save to the character's module folder for persistence
            try:
                # Get current module from party tracker
                party_tracker_path = 'party_tracker.json'
                if os.path.exists(party_tracker_path):
                    with open(party_tracker_path, 'r', encoding='utf-8') as f:
                        party_tracker = json.load(f)
                        current_module = party_tracker.get('module', '').replace(' ', '_')
                        
                        if current_module:
                            from utils.module_path_manager import ModulePathManager
                            manager = ModulePathManager(current_module)
                            module_portraits_dir = os.path.join(manager.get_module_dir(), 'portraits')
                            os.makedirs(module_portraits_dir, exist_ok=True)
                            module_save_path = os.path.join(module_portraits_dir, save_filename)
                            img.save(module_save_path, 'PNG')
                            info(f"PORTRAIT: Also saved to module folder at {module_save_path}")
            except Exception as e:
                warning(f"PORTRAIT: Could not save to module folder: {e}")
            
            info(f"PORTRAIT: Saved new portrait for {character_name} to {save_path}")
            return jsonify({'success': True, 'message': 'Portrait uploaded successfully'})

    except Exception as e:
        error(f"PORTRAIT: Upload failed", exception=e, category="web_interface")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/spell-data')
def get_spell_data():
    """Serve spell repository data for tooltips"""
    try:
        from core.ai.srd_reference import load_srd_reference_index

        spell_data = load_srd_reference_index().compatibility_spell_map()
        return jsonify(spell_data)
    except (FileNotFoundError, OSError, ValueError):
        return jsonify({})

# ============================================================================
# MODULE TOOLKIT API ENDPOINTS
# ============================================================================

@app.route('/toolkit')
def toolkit_interface():
    """Serve the module toolkit interface"""
    if not TOOLKIT_AVAILABLE:
        return "Module Toolkit not available", 503
    return render_template('module_toolkit.html')

@app.route('/api/toolkit/packs')
def get_packs():
    """Get list of available graphic packs"""
    if not TOOLKIT_AVAILABLE:
        # Return an error if the toolkit isn't available, so the frontend knows why it's empty.
        return jsonify({'error': 'Module Toolkit components are not available on the server.'}), 503

    try:
        manager = PackManager()
        # First, get the complete list of packs, including the unwanted ones.
        all_packs = manager.list_available_packs()
        
        # Now, filter the list to exclude any pack whose 'name' starts with a '.'
        # This is a standard way to handle hidden/system folders.
        filtered_packs = [pack for pack in all_packs if not pack.get('name', '').startswith('.')]
        
        # Return only the clean, filtered list to the frontend.
        return jsonify(filtered_packs)
    except Exception as e:
        # This is the most important change.
        # Instead of failing silently, we now send the actual error back to the browser.
        error_message = f"TOOLKIT: Failed to list packs: {e}"
        error(error_message) # Log the error to the server console
        # Return a JSON object with the error and a 500 Internal Server Error status.
        return jsonify({'error': str(e)}), 500

@app.route('/api/toolkit/packs/create', methods=['POST'])
def create_pack():
    """Create a new graphic pack"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        manager = PackManager()
        # Pass all the new fields to the manager
        result = manager.create_pack(
            name=data.get('name'),
            display_name=data.get('display_name'),
            style_template=data.get('style', 'custom'),  # Default to custom style
            author=data.get('author', 'Module Toolkit User'),
            description=data.get('description', '')
        )
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to create pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/packs/<pack_name>/activate', methods=['POST'])
def activate_pack(pack_name):
    """Activate a graphic pack with optional backup"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        # Check if backup should be created
        create_backup = request.json.get('create_backup', False) if request.json else False
        
        # If backup requested, create a backup pack from current live game assets FIRST
        if create_backup:
            backup_result = create_live_assets_backup_pack()
            if not backup_result.get('success'):
                warning(f"TOOLKIT: Failed to create live assets backup: {backup_result.get('error')}")
        
        manager = PackManager()
        result = manager.activate_pack(pack_name, create_backup=False)  # Don't need pack backup since we did live backup
        
        # If activation successful, copy all assets to the live game folders
        if result.get('success'):
            # First, copy the monster assets (NO individual backup needed)
            copy_pack_monsters_to_game(pack_name)
            # Then, copy the NPC assets (NO individual backup needed)
            copy_pack_npcs_to_game(pack_name)
        
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to activate pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/packs/<pack_name>/export')
def export_pack(pack_name):
    """Export a pack as ZIP file"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        import tempfile
        manager = PackManager()
        
        # Export to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            result = manager.export_pack(pack_name, temp_dir)
            if result['success']:
                # Send the ZIP file
                zip_path = result['zip_path']
                with open(zip_path, 'rb') as f:
                    zip_data = f.read()
                
                response = Response(
                    zip_data,
                    mimetype='application/zip',
                    headers={
                        'Content-Disposition': f'attachment; filename={os.path.basename(zip_path)}'
                    }
                )
                return response
            else:
                return jsonify(result), 400
    except Exception as e:
        error(f"TOOLKIT: Failed to export pack: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toolkit/packs/<pack_name>', methods=['DELETE'])
def delete_pack(pack_name):
    """Delete a graphic pack"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        manager = PackManager()
        result = manager.delete_pack(pack_name)
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to delete pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/packs/<pack_name>/merge', methods=['POST'])
def merge_pack(pack_name):
    """Merges a specified pack into the currently active pack."""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503

    try:
        # --- BACKEND LOGIC TO BE IMPLEMENTED ---
        # 1. Create an instance of PackManager.
        #    manager = PackManager()
        #
        # 2. Get the currently active pack. This will be the DESTINATION.
        #    active_pack = manager.get_active_pack()
        #    if not active_pack:
        #        return jsonify({'success': False, 'error': 'No active pack found to merge into.'})
        #
        # 3. The `pack_name` from the URL is the SOURCE pack.
        #
        # 4. Call a new method on the manager, e.g., `manager.merge_pack(source_pack_name=pack_name, dest_pack_name=active_pack['name'])`
        #    This method will need to:
        #      a. Get the file paths for both packs.
        #      b. Iterate through all files (monsters, videos) in the source pack.
        #      c. For each file, copy it to the destination pack, overwriting if it exists.
        #      d. After copying, re-scan the destination pack's manifest to update monster/video counts.
        #
        # 5. Return the result from the manager.
        # --- END OF LOGIC TO BE IMPLEMENTED ---

        # For now, return a placeholder success message.
        info(f"TOOLKIT: Placeholder merge request for pack '{pack_name}'")
        return jsonify({'success': True, 'message': f"Placeholder: Successfully merged '{pack_name}' into the active pack."})

    except Exception as e:
        error(f"TOOLKIT: Failed to merge pack '{pack_name}': {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toolkit/export-monsters-to-pack', methods=['POST'])
def export_monsters_to_pack():
    """Export selected monsters from a source pack to a new custom pack"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503
    
    try:
        data = request.json
        pack_name = data.get('pack_name')
        display_name = data.get('display_name')
        author = data.get('author')
        description = data.get('description', '')
        style = data.get('style', 'custom')
        source_pack = data.get('source_pack')
        monster_ids = data.get('monster_ids', [])
        
        if not all([pack_name, display_name, author, source_pack, monster_ids]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        info(f"TOOLKIT: Creating new pack '{pack_name}' with {len(monster_ids)} monsters from '{source_pack}'")
        
        import os
        import shutil
        import json
        from datetime import datetime
        
        # Create pack directory
        pack_dir = os.path.join('graphic_packs', pack_name)
        if os.path.exists(pack_dir):
            return jsonify({'success': False, 'error': f'Pack "{pack_name}" already exists'})
        
        os.makedirs(pack_dir)
        monsters_dir = os.path.join(pack_dir, 'monsters')
        os.makedirs(monsters_dir)
        
        # Source pack directory
        source_dir = os.path.join('graphic_packs', source_pack, 'monsters')
        if not os.path.exists(source_dir):
            shutil.rmtree(pack_dir)  # Clean up
            return jsonify({'success': False, 'error': f'Source pack "{source_pack}" not found'})
        
        # Copy monster files
        exported_count = 0
        skipped = []
        
        for monster_id in monster_ids:
            copied = False
            
            # Try to copy image file (jpg or png)
            for ext in ['.jpg', '.png']:
                source_image = os.path.join(source_dir, f'{monster_id}{ext}')
                if os.path.exists(source_image):
                    dest_image = os.path.join(monsters_dir, f'{monster_id}{ext}')
                    shutil.copy2(source_image, dest_image)
                    copied = True
                    
                    # Copy thumbnail if exists
                    source_thumb = os.path.join(source_dir, f'{monster_id}_thumb{ext}')
                    if os.path.exists(source_thumb):
                        dest_thumb = os.path.join(monsters_dir, f'{monster_id}_thumb{ext}')
                        shutil.copy2(source_thumb, dest_thumb)
                    break
            
            # Copy video if exists
            source_video = os.path.join(source_dir, f'{monster_id}_video.mp4')
            if os.path.exists(source_video):
                dest_video = os.path.join(monsters_dir, f'{monster_id}_video.mp4')
                shutil.copy2(source_video, dest_video)
                copied = True
            
            if copied:
                exported_count += 1
            else:
                skipped.append(monster_id)
                warning(f"TOOLKIT: Monster '{monster_id}' not found in source pack")
        
        # Create manifest.json
        manifest = {
            "name": pack_name,
            "display_name": display_name,
            "author": author,
            "description": description,
            "version": "1.0.0",
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "style_template": style,
            "total_monsters": exported_count,
            "total_videos": len([f for f in os.listdir(monsters_dir) if f.endswith('_video.mp4')]),
            "monsters": monster_ids,
            "source": f"Exported from {source_pack}"
        }
        
        manifest_path = os.path.join(pack_dir, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        info(f"TOOLKIT: Successfully created pack '{pack_name}' with {exported_count} monsters")
        
        return jsonify({
            'success': True,
            'exported_count': exported_count,
            'skipped': skipped,
            'pack_name': pack_name
        })
        
    except Exception as e:
        error(f"TOOLKIT: Failed to export monsters to pack: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toolkit/packs/preview', methods=['POST'])
def preview_pack():
    """Reads the manifest from a ZIP file without saving it."""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    if 'pack' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided for preview'})
    
    file = request.files['pack']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})

    try:
        # Read the file into memory
        zip_in_memory = io.BytesIO(file.read())
        
        with zipfile.ZipFile(zip_in_memory, 'r') as zip_ref:
            # Check for manifest file
            if 'manifest.json' not in zip_ref.namelist():
                return jsonify({'success': False, 'error': 'manifest.json not found in archive.'})
            
            # Read and parse the manifest
            with zip_ref.open('manifest.json') as manifest_file:
                manifest_data = json.load(manifest_file)
                
                # Count assets in the ZIP
                monster_count = 0
                npc_count = 0
                video_count = 0
                
                for filename in zip_ref.namelist():
                    if filename.startswith('monsters/'):
                        if filename.endswith('.mp4'):
                            video_count += 1
                        elif filename.endswith(('.png', '.jpg', '.jpeg')) and '_thumb' not in filename:
                            monster_count += 1
                    elif filename.startswith('npcs/'):
                        if filename.endswith(('.png', '.jpg', '.jpeg')) and '_thumb' not in filename:
                            npc_count += 1
                
                # Add counts to manifest data
                manifest_data['total_monsters'] = monster_count
                manifest_data['total_npcs'] = npc_count
                manifest_data['total_videos'] = video_count
                
                return jsonify({'success': True, 'data': manifest_data})

    except zipfile.BadZipFile:
        return jsonify({'success': False, 'error': 'Invalid .zip file.'})
    except Exception as e:
        error(f"TOOLKIT: Failed to preview pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/packs/import', methods=['POST'])
def import_pack():
    """Import a pack from ZIP file"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        if 'pack' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        file = request.files['pack']
        # Get the target folder name and import options from the form data
        target_folder_name = request.form.get('target_folder_name')
        import_monsters = request.form.get('import_monsters', 'true').lower() == 'true'
        import_npcs = request.form.get('import_npcs', 'true').lower() == 'true'

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Save to temp file
        import tempfile
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                tmp_file = tmp.name
                file.save(tmp.name)
            
            # File is now closed, safe to process
            manager = PackManager()
            # Pass the target folder name and import options to the manager
            result = manager.import_pack(
                tmp_file, 
                target_folder_name=target_folder_name,
                import_monsters=import_monsters,
                import_npcs=import_npcs
            )
            
            return jsonify(result)
        finally:
            # Clean up temp file in finally block to ensure it happens
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except Exception as cleanup_error:
                    # Log but don't fail if we can't delete temp file
                    error(f"TOOLKIT: Could not delete temp file {tmp_file}: {cleanup_error}")
    except Exception as e:
        error(f"TOOLKIT: Failed to import pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/monsters')
def get_monsters():
    """Get list of available monsters"""
    if not TOOLKIT_AVAILABLE:
        return jsonify([])
    
    try:
        # Get pack parameter from query string
        pack_name = request.args.get('pack', 'photorealistic')
        
        # Use a temporary generator instance to get monster list
        from config import OPENAI_API_KEY
        generator = MonsterGenerator(api_key=OPENAI_API_KEY)
        monsters = generator.get_monster_list(pack_name=pack_name)
        return jsonify(monsters)
    except Exception as e:
        error(f"TOOLKIT: Failed to get monster list: {e}")
        return jsonify([])

@app.route('/toolkit/pack_image/<pack_name>/<filename>')
def serve_pack_image(pack_name, filename):
    """Serve an image from a graphic pack"""
    from flask import send_from_directory
    import os
    
    # Construct the absolute path to the image - all files in monsters folder now
    pack_dir = os.path.abspath(os.path.join('graphic_packs', pack_name, 'monsters'))
    
    # Check if file exists - NO FALLBACK
    file_path = os.path.join(pack_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(pack_dir, filename)
    
    # Return 404 if not found - no fallback to other directories
    return '', 404

@app.route('/toolkit/pack_video/<pack_name>/<filename>')
def serve_pack_video(pack_name, filename):
    """Serve a video from a graphic pack"""
    from flask import send_from_directory
    import os
    
    # Construct the absolute path to the video - all files in monsters folder now
    pack_dir = os.path.abspath(os.path.join('graphic_packs', pack_name, 'monsters'))
    
    # Check if file exists - NO FALLBACK
    file_path = os.path.join(pack_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(pack_dir, filename)
    
    # Return 404 if not found - no fallback to other directories
    return '', 404

@app.route('/api/toolkit/check_existing_images', methods=['POST'])
def check_existing_images():
    """Check if images already exist for the given monsters in a pack"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        pack_name = data.get('pack_name')
        monster_ids = data.get('monster_ids', [])
        
        if not pack_name or not monster_ids:
            return jsonify({'success': False, 'error': 'Missing pack_name or monster_ids'})
        
        # Check which files exist
        pack_dir = Path(f"graphic_packs/{pack_name}/monsters")
        existing = []
        
        if pack_dir.exists():
            for monster_id in monster_ids:
                # Check for .jpg files only (the correct format)
                jpg_path = pack_dir / f"{monster_id}.jpg"
                
                if jpg_path.exists():
                    existing.append(monster_id)
        
        return jsonify({
            'success': True,
            'existing': existing,
            'total_checked': len(monster_ids)
        })
    
    except Exception as e:
        error(f"TOOLKIT: Error checking existing images: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/generate', methods=['POST'])
def generate_monsters():
    """Start monster generation task"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        pack_name = data.get('pack_name')
        style = data.get('style', 'photorealistic')
        model = data.get('model', 'auto')
        monsters = data.get('monsters', [])
        
        # Start generation in background thread
        import uuid
        import asyncio
        task_id = str(uuid.uuid4())
        
        def run_generation():
            try:
                from config import OPENAI_API_KEY
                generator = MonsterGenerator(api_key=OPENAI_API_KEY)
                
                # Create progress callback
                def progress_callback(progress_data):
                    socketio.emit('generation_progress', progress_data)
                
                # Run the async function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    generator.batch_generate_pack(
                        pack_name=pack_name,
                        style=style,
                        monsters=monsters,
                        model=model,
                        progress_callback=progress_callback
                    )
                )
                
                socketio.emit('generation_complete', result)
            except Exception as e:
                error(f"TOOLKIT: Generation failed: {e}")
                socketio.emit('generation_error', {'error': str(e)})
        
        # Start in background thread
        thread = threading.Thread(target=run_generation)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        error(f"TOOLKIT: Failed to start generation: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/process-video', methods=['POST'])
def process_video():
    """Process a monster video"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        file = request.files['video']
        monster_id = request.form.get('monster_id')
        pack_name = request.form.get('pack_name')
        copy_to_monsters = request.form.get('copy_to_monsters', 'false').lower() == 'true'
        copy_to_npcs = request.form.get('copy_to_npcs', 'false').lower() == 'true'
        
        if not monster_id or not pack_name:
            return jsonify({'success': False, 'error': 'Missing monster_id or pack_name'})
        
        # Save to temp file
        import tempfile
        import time
        
        tmp_file = None
        result = {'success': False, 'error': 'Unknown error'}  # Initialize result
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                tmp_file = tmp.name
                file.save(tmp_file)
            
            print(f"[INFO] Processing video for {monster_id}")
            print(f"[INFO] Temp file: {tmp_file}")
            print(f"[INFO] File size: {os.path.getsize(tmp_file)} bytes")
            
            processor = VideoProcessor()
            result = processor.process_monster_video(
                input_path=tmp_file,
                monster_id=monster_id,
                pack_name=pack_name,
                skip_compression=False,  # Enable compression
                copy_to_monsters=copy_to_monsters,
                copy_to_npcs=copy_to_npcs
            )
            
            # Try to clean up temp file with retries for Windows
            for attempt in range(5):
                try:
                    if tmp_file and os.path.exists(tmp_file):
                        os.unlink(tmp_file)
                    break
                except PermissionError:
                    if attempt < 4:  # Don't sleep on last attempt
                        time.sleep(0.5)  # Wait half a second and retry
                    else:
                        # Log warning but don't fail the request
                        print(f"Warning: Could not delete temp file {tmp_file}")
                        
        except Exception as process_error:
            # Capture the actual error in result
            error(f"TOOLKIT: Video processing error: {process_error}")
            result = {'success': False, 'error': str(process_error)}
            
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to process video: {e}")
        return jsonify({'success': False, 'error': str(e)})

def _job_identity(data, prefix):
    """Return a client-known job ID and its optional Socket.IO target room."""
    supplied = data.get('job_id')
    if isinstance(supplied, str) and supplied.strip() and len(supplied) <= 128:
        job_id = supplied.strip()
    else:
        job_id = f"{prefix}-{uuid4().hex}"
    target_room = (
        data.get('socket_sid') or data.get('socket_id') or data.get('room')
    )
    if not isinstance(target_room, str) or not target_room.strip():
        target_room = None
    else:
        target_room = target_room.strip()
    return job_id, target_room


def _emit_job_event(event_name, payload, *, job_id, target_room=None):
    """Attach correlation data to every event and target its initiating client."""
    correlated = dict(payload)
    correlated['job_id'] = job_id
    if target_room:
        socketio.emit(event_name, correlated, to=target_room)
    else:
        socketio.emit(event_name, correlated)
    return correlated


def _run_bestiary_update_job(
    module_name,
    monster_ids,
    job_id,
    *,
    target_room=None,
    updater_factory=None,
):
    """Run T083 and emit a single result whose counts come from the updater."""
    requested = len(monster_ids)
    try:
        if updater_factory is None:
            from utils.bestiary_updater import BestiaryUpdater
            updater_factory = BestiaryUpdater
        updater = updater_factory()
        monster_names = [
            monster_id.replace('_', ' ').title()
            for monster_id in monster_ids
        ]
        _emit_job_event(
            'bestiary_update_progress',
            {
                'status': 'started',
                'requested': requested,
                'message': f'Starting to process {requested} monsters...',
            },
            job_id=job_id,
            target_room=target_room,
        )
        import asyncio
        result = asyncio.run(
            updater.process_missing_monsters(
                module_name=module_name,
                monster_names=monster_names,
                test_mode=False,
            )
        )
        required = {
            'requested', 'added', 'skipped', 'failed', 'error', 'success'
        }
        if not isinstance(result, dict) or set(result) != required:
            raise RuntimeError('Bestiary updater returned an invalid result')
        count_fields = ('requested', 'added', 'skipped', 'failed')
        if any(
            type(result[field]) is not int or result[field] < 0
            for field in count_fields
        ):
            raise RuntimeError('Bestiary updater returned invalid counts')
        if result['requested'] != (
            result['added'] + result['skipped'] + result['failed']
        ):
            raise RuntimeError('Bestiary updater counts do not balance')
        expected_success = result['failed'] == 0 and result['error'] is None
        if (
            not isinstance(result['success'], bool)
            or result['success'] != expected_success
        ):
            raise RuntimeError('Bestiary updater returned inconsistent success status')

        if result['success']:
            message = (
                f"Added {result['added']} of {result['requested']} requested "
                f"monsters; {result['skipped']} skipped."
            )
        else:
            message = (
                f"Added {result['added']} of {result['requested']} requested "
                f"monsters; {result['failed']} failed."
            )
        _emit_job_event(
            'bestiary_update_complete',
            {
                **result,
                'status': 'complete' if result['success'] else 'failed',
                'message': message,
            },
            job_id=job_id,
            target_room=target_room,
        )
        return result
    except Exception as exc:
        error(f"TOOLKIT: Bestiary update failed: {exc}")
        failure = {
            'requested': requested,
            'added': 0,
            'skipped': 0,
            'failed': requested,
            'error': str(exc),
            'success': False,
        }
        _emit_job_event(
            'bestiary_update_error',
            {**failure, 'status': 'failed'},
            job_id=job_id,
            target_room=target_room,
        )
        return failure


@app.route('/api/toolkit/add-to-bestiary', methods=['POST'])
def add_to_bestiary():
    """Adds monsters to the bestiary using a correlated background job."""
    try:
        data = request.json or {}
        module_name = data.get('module_name')
        monster_ids = data.get('monster_ids', [])

        if not module_name or not isinstance(monster_ids, list) or not monster_ids:
            return jsonify({'success': False, 'error': 'Missing module_name or monster_ids'})
        if any(
            not isinstance(monster_id, str) or not monster_id.strip()
            for monster_id in monster_ids
        ):
            return jsonify({'success': False, 'error': 'Monster IDs must be non-empty strings'})

        job_id, target_room = _job_identity(data, 'bestiary')
        monster_snapshot = [monster_id.strip() for monster_id in monster_ids]
        info(
            f"TOOLKIT: Request to add {len(monster_snapshot)} monsters "
            f"to bestiary from module: {module_name}"
        )
        thread = threading.Thread(
            target=_run_bestiary_update_job,
            kwargs={
                'module_name': module_name,
                'monster_ids': monster_snapshot,
                'job_id': job_id,
                'target_room': target_room,
            },
            daemon=True,
        )
        thread.start()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'Started processing {len(monster_snapshot)} monsters.',
        })
    except Exception as exc:
        error(f"TOOLKIT: Failed to start bestiary update: {exc}")
        return jsonify({'success': False, 'error': str(exc)})

@app.route('/toolkit/get_style_prompt/<style_id>')
def get_style_prompt(style_id):
    """Get the prompt for a specific style"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'prompt': ''})
    
    try:
        from core.toolkit.style_manager import StyleManager
        manager = StyleManager()
        prompt = manager.get_style_prompt(style_id)
        return jsonify({'prompt': prompt or ''})
    except Exception as e:
        error(f"TOOLKIT: Failed to get style prompt: {e}")
        return jsonify({'prompt': ''})

@app.route('/toolkit/get_styles')
def get_all_styles():
    """Get all available style templates"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'builtin': {}, 'custom': {}})
    
    try:
        from core.toolkit.style_manager import StyleManager
        manager = StyleManager()
        styles = manager.get_all_styles()
        
        # Organize by type
        builtin = {k: v for k, v in styles.items() if v['type'] == 'builtin'}
        custom = {k: v for k, v in styles.items() if v['type'] == 'custom'}
        
        return jsonify({'builtin': builtin, 'custom': custom})
    except Exception as e:
        error(f"TOOLKIT: Failed to get styles: {e}")
        return jsonify({'builtin': {}, 'custom': {}})

@app.route('/toolkit/save_style_template', methods=['POST'])
def save_style_template():
    """Save a custom style template"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        name = data.get('name')
        prompt = data.get('prompt')
        
        if not name or not prompt:
            return jsonify({'success': False, 'error': 'Name and prompt are required'})
        
        from core.toolkit.style_manager import StyleManager
        manager = StyleManager()
        result = manager.save_custom_style(name, prompt)
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to save style: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/toolkit/update_style_prompt', methods=['POST'])
def update_style_prompt():
    """Update an existing style's prompt"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        style_id = data.get('style_id')
        prompt = data.get('prompt')
        
        if not style_id or not prompt:
            return jsonify({'success': False, 'error': 'Style ID and prompt are required'})
        
        from core.toolkit.style_manager import StyleManager
        manager = StyleManager()
        # Use overwrite_style which handles both builtin and custom styles
        result = manager.overwrite_style(style_id, prompt)
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to update style: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/toolkit/get_monster_description/<monster_id>')
def get_monster_description(monster_id):
    """Get the description for a specific monster"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'description': '', 'name': monster_id})
    
    try:
        # Load monster compendium with explicit UTF-8 encoding
        import json
        compendium_path = 'data/bestiary/monster_compendium.json'
        with open(compendium_path, 'r', encoding='utf-8') as f:
            compendium = json.load(f)
        
        # Look for monster in compendium
        monsters = compendium.get('monsters', {})
        if monster_id in monsters:
            monster_data = monsters[monster_id]
            description = monster_data.get('description', '')
            name = monster_data.get('name', monster_id)
            info(f"TOOLKIT: Found {monster_id} - desc length: {len(description)}")
            return jsonify({
                'description': description,
                'name': name
            })
        else:
            # Try with underscores replaced by spaces
            monster_id_alt = monster_id.replace('_', ' ').lower()
            for mid, mdata in monsters.items():
                if mid.lower() == monster_id_alt or mdata.get('name', '').lower() == monster_id_alt:
                    return jsonify({
                        'description': mdata.get('description', ''),
                        'name': mdata.get('name', monster_id)
                    })
        
        return jsonify({'description': '', 'name': monster_id})
    except Exception as e:
        error(f"TOOLKIT: Failed to get monster description: {e}")
        return jsonify({'description': '', 'name': monster_id})

@app.route('/toolkit/update_monster_description', methods=['POST'])
def update_monster_description():
    """Update a monster's description"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        monster_id = data.get('monster_id')
        description = data.get('description')
        
        if not monster_id or not description:
            return jsonify({'success': False, 'error': 'Monster ID and description are required'})
        
        compendium_path = MONSTER_COMPENDIUM_PATH
        compendium = {}
        if os.path.exists(compendium_path):
            from utils.file_operations import safe_read_json
            compendium = safe_read_json(compendium_path) or {}
        monsters = compendium.get('monsters', {})
        resolved_id = monster_id
        existing_entry = monsters.get(monster_id)
        if existing_entry is None:
            monster_id_alt = monster_id.replace('_', ' ').lower()
            for candidate_id, candidate in monsters.items():
                if (
                    candidate_id.lower() == monster_id_alt
                    or (
                        isinstance(candidate, dict)
                        and candidate.get('name', '').lower() == monster_id_alt
                    )
                ):
                    resolved_id = candidate_id
                    existing_entry = candidate
                    break

        entry = dict(existing_entry) if isinstance(existing_entry, dict) else {}
        entry.update({
            'name': entry.get('name') or monster_id.replace('_', ' ').title(),
            'description': sanitize_text(description),
        })
        entry.setdefault('type', 'unknown')
        entry.setdefault('tags', [])
        merge_compendium_entries(
            compendium_path,
            'monsters',
            {resolved_id: entry},
            overwrite=True,
        )
        
        return jsonify({'success': True, 'message': 'Monster description updated'})
    except Exception as e:
        error(f"TOOLKIT: Failed to update monster description: {e}")
        return jsonify({'success': False, 'error': str(e)})


def _provider_credentials_available(provider):
    """Check only credentials required by the selected provider."""
    import config

    if provider == "lmstudio":
        return True
    if provider in ("legacy", "openai"):
        key = getattr(config, "OPENAI_API_KEY", "")
        placeholder = "your_openai_api_key_here"
    elif provider == "gemini":
        key = getattr(config, "GEMINI_API_KEY", "")
        placeholder = "your_gemini_api_key_here"
    else:
        return False
    return isinstance(key, str) and bool(key.strip()) and key.strip() != placeholder


def _persist_promoted_monster(monster_id, entry, compendium_path):
    return merge_compendium_entries(
        compendium_path,
        "monsters",
        {monster_id: entry},
        overwrite=False,
    )

@app.route('/api/toolkit/promote-to-bestiary', methods=['POST'])
def promote_to_bestiary():
    """Creates a new bestiary entry for a pack-exclusive monster."""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        monster_id = data.get('monster_id')
        
        if not monster_id:
            return jsonify({'success': False, 'error': 'Monster ID is required'})

        compendium_path = MONSTER_COMPENDIUM_PATH
        if compendium_entry_exists(compendium_path, "monsters", monster_id):
            return jsonify({'success': False, 'error': f'Monster "{monster_id}" already exists in the bestiary.'})

        monster_name = monster_id.replace('_', ' ').title()
        prompt = f"""Generate a compelling 5th edition of the world's most popular roleplaying game style bestiary description for a monster named "{monster_name}".
        The description should be concise (around 100-150 words) and focus on its appearance, typical behavior, and combat tactics.
        Make it sound like an entry from an official monster manual. Do not include stat blocks.
        Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols."""
        
        from model_config import get_provider
        provider_snapshot = get_provider()
        import config
        if provider_snapshot == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif provider_snapshot == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif provider_snapshot == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        elif provider_snapshot == "legacy":
            mini_cfg = config.MINI_UTIL_LEGACY
        else:
            raise ValueError(f"Unsupported model provider: {provider_snapshot}")

        response = capture_and_fanout("T094", api_client.create_completion,
            _request_provider=provider_snapshot,
            messages=[
                {"role": "system", "content": "You are a creative writer for a fantasy role-playing game, specializing in monster lore."},
                {"role": "user", "content": prompt}
            ],
            model=mini_cfg["model"],
            temperature=0.7,
            response_format=None,
            **{k: v for k, v in mini_cfg.items() if k != "model"})

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'web_dm', 'purpose': 'web_interface_response', 'interface': 'web'})
            except:
                pass
        
        description = validate_generated_prose(
            sanitize_text(response.choices[0].message.content),
            minimum_words=20,
        )

        new_entry = {
            "name": monster_name,
            "description": description,
            "type": "unknown",
            "tags": ["custom", "pack-promoted"]
        }
        merge_result = _persist_promoted_monster(
            monster_id,
            new_entry,
            compendium_path,
        )
        if monster_id in merge_result.skipped:
            return jsonify({
                'success': False,
                'error': f'Monster "{monster_id}" already exists in the bestiary.'
            })
        
        info(f"TOOLKIT: Promoted pack monster '{monster_id}' to the bestiary.")
        return jsonify({'success': True, 'message': f'Successfully added {monster_name} to the bestiary.'})

    except Exception as e:
        error(f"TOOLKIT: Failed to promote monster to bestiary: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/toolkit/create_pack', methods=['POST'])
def create_pack_toolkit():
    """Create a new graphic pack from toolkit"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        manager = PackManager()
        result = manager.create_pack(
            name=data.get('name'),
            style_template=data.get('style_template', 'photorealistic'),
            author=data.get('author', 'Module Toolkit'),
            description=data.get('description', '')
        )
        return jsonify(result)
    except Exception as e:
        error(f"TOOLKIT: Failed to create pack: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/settings', methods=['POST'])
def save_toolkit_settings():
    """Save toolkit settings"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'})
    
    try:
        data = request.json
        active_pack = data.get('active_pack')
        api_key = data.get('api_key')
        
        # Save active pack
        if active_pack:
            manager = PackManager()
            manager.activate_pack(active_pack)
        
        # API key would be saved to config if provided
        # For now, just acknowledge
        
        return jsonify({'success': True})
    except Exception as e:
        error(f"TOOLKIT: Failed to save settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toolkit/modules')
def get_available_modules_api():
    """Get list of available adventure modules."""
    if not TOOLKIT_AVAILABLE:
        return jsonify([]), 503
    
    try:
        # This function already exists and gives us what we need.
        from core.generators.module_stitcher import list_available_modules
        modules = list_available_modules()
        return jsonify(modules)
    except Exception as e:
        error(f"TOOLKIT: Failed to get module list: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toolkit/modules/<module_name>/monsters')
def get_module_monsters_api(module_name):
    """Get list of monster IDs found in a specific module."""
    if not TOOLKIT_AVAILABLE:
        return jsonify([]), 503
    
    try:
        from utils.module_path_manager import ModulePathManager
        from utils.file_operations import safe_read_json
        import os
        import re

        path_manager = ModulePathManager(module_name)
        monster_ids = set()

        # Build areas directory path
        areas_dir = os.path.join('modules', module_name, 'areas')
        
        # Scan area backup files (_BU.json) for monsters in locations
        if os.path.exists(areas_dir):
            for filename in os.listdir(areas_dir):
                # Only check backup files which contain original unmodified data
                if filename.endswith('_BU.json'):
                    area_path = os.path.join(areas_dir, filename)
                    area_data = safe_read_json(area_path)
                    if area_data and 'locations' in area_data:
                        for location in area_data.get('locations', []):
                            if 'monsters' in location and location['monsters']:
                                for monster in location['monsters']:
                                    if isinstance(monster, dict) and 'name' in monster:
                                        # Normalize the name to match our monster IDs:
                                        # "Bandit Captain Gorvek" -> "bandit_captain_gorvek"
                                        monster_id = monster['name'].lower().replace(' ', '_')
                                        monster_ids.add(monster_id)
                                    elif isinstance(monster, str):
                                        # Handle string format like "1 Tainted Naiad"
                                        # Extract just the monster name
                                        match = re.search(r'\d*\s*(.+?)(?:\s*\(|$)', monster)
                                        if match:
                                            monster_name = match.group(1).strip()
                                            monster_id = monster_name.lower().replace(' ', '_')
                                            monster_ids.add(monster_id)
        
        # Also scan the monsters folder for this module
        monsters_dir = os.path.join('modules', module_name, 'monsters')
        if os.path.exists(monsters_dir):
            for filename in os.listdir(monsters_dir):
                if filename.endswith('.json'):
                    # Extract monster ID from filename
                    # e.g., "bandit_captain_gorvek.json" -> "bandit_captain_gorvek"
                    monster_id = filename[:-5]  # Remove .json extension
                    monster_ids.add(monster_id)

        info(f"TOOLKIT: Found {len(monster_ids)} unique monsters in module {module_name}: {list(monster_ids)[:5]}...")
        return jsonify(list(monster_ids))
        
    except Exception as e:
        error(f"TOOLKIT: Failed to get monsters for module {module_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toolkit/modules/<module_name>/unified-assets')
def get_module_unified_assets(module_name):
    """
    Get unified list of all NPCs and monsters in a module with their asset status.
    Returns detailed information about description existence and media availability.
    """
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503
    
    try:
        from utils.file_operations import safe_read_json
        from utils.bestiary_updater import BestiaryUpdater
        import os
        import re
        
        info(f"TOOLKIT: Scanning unified assets for module {module_name}")
        
        # Initialize collections
        npcs = {}
        monsters = {}
        
        # Build areas directory path
        areas_dir = os.path.join('modules', module_name, 'areas')
        
        # Scan area backup files for both NPCs and monsters
        if os.path.exists(areas_dir):
            for filename in os.listdir(areas_dir):
                if filename.endswith('_BU.json'):
                    area_path = os.path.join(areas_dir, filename)
                    area_data = safe_read_json(area_path)
                    if area_data and 'locations' in area_data:
                        for location in area_data.get('locations', []):
                            # Extract NPCs
                            if 'npcs' in location and location['npcs']:
                                for npc in location['npcs']:
                                    if isinstance(npc, dict) and 'name' in npc:
                                        npc_id = npc['name'].lower().replace(' ', '_').replace("'", "")
                                        if npc_id not in npcs:
                                            npcs[npc_id] = {'name': npc['name'], 'type': 'npc'}
                            
                            # Extract monsters
                            if 'monsters' in location and location['monsters']:
                                for monster in location['monsters']:
                                    if isinstance(monster, dict) and 'name' in monster:
                                        monster_id = monster['name'].lower().replace(' ', '_')
                                        if monster_id not in monsters:
                                            monsters[monster_id] = {'name': monster['name'], 'type': 'monster'}
                                    elif isinstance(monster, str):
                                        match = re.search(r'\d*\s*(.+?)(?:\s*\(|$)', monster)
                                        if match:
                                            monster_name = match.group(1).strip()
                                            monster_id = monster_name.lower().replace(' ', '_')
                                            if monster_id not in monsters:
                                                monsters[monster_id] = {'name': monster_name, 'type': 'monster'}
        
        # Check for descriptions and media status
        def check_asset_status(asset_id, asset_type, asset_name):
            """Check the status of descriptions and media for an asset."""
            status = {
                'id': asset_id,
                'name': asset_name,
                'type': asset_type,
                'has_description': False,
                'has_image': False,
                'has_thumbnail': False,
                'has_video': False,
                'image_location': 'none',  # 'module', 'static', or 'none'
            }
            
            # Check for description
            if asset_type == 'monster':
                # Check bestiary first
                bestiary_path = 'data/bestiary/monster_compendium.json'
                if os.path.exists(bestiary_path):
                    bestiary_data = safe_read_json(bestiary_path) or {}
                    monsters_dict = bestiary_data.get('monsters', {})
                    if asset_id in monsters_dict:
                        monster_entry = monsters_dict[asset_id]
                        if monster_entry.get('description'):
                            status['has_description'] = True
                
                # If not in bestiary, check module's monster file
                if not status['has_description']:
                    monster_file_path = os.path.join('modules', module_name, 'monsters', f'{asset_id}.json')
                    if os.path.exists(monster_file_path):
                        monster_data = safe_read_json(monster_file_path) or {}
                        if monster_data.get('description'):
                            status['has_description'] = True
            else:  # NPC
                # Check NPC compendium first
                npc_compendium_path = 'data/bestiary/npc_compendium.json'
                if os.path.exists(npc_compendium_path):
                    npc_compendium = safe_read_json(npc_compendium_path) or {}
                    npcs_dict = npc_compendium.get('npcs', {})
                    if asset_id in npcs_dict:
                        npc_entry = npcs_dict[asset_id]
                        if npc_entry.get('description'):
                            status['has_description'] = True
                
                # Fall back to temp descriptions file for backward compatibility
                if not status['has_description']:
                    desc_file = f'temp/npc_descriptions_{module_name}.json'
                    if os.path.exists(desc_file):
                        descriptions = safe_read_json(desc_file) or {}
                        if asset_id in descriptions:
                            status['has_description'] = True
            
            # Check for media files
            media_type_folder = 'monsters' if asset_type == 'monster' else 'npcs'
            
            # Check module-specific media first
            module_media_dir = os.path.join('modules', module_name, 'media', media_type_folder)
            if os.path.exists(module_media_dir):
                # Check for main image
                for ext in ['.jpg', '.png']:
                    if os.path.exists(os.path.join(module_media_dir, f"{asset_id}{ext}")):
                        status['has_image'] = True
                        status['image_location'] = 'module'
                        break
                
                # Check for thumbnail
                for ext in ['_thumb.jpg', '_thumb.png']:
                    if os.path.exists(os.path.join(module_media_dir, f"{asset_id}{ext}")):
                        status['has_thumbnail'] = True
                        break
                
                # Check for video
                if os.path.exists(os.path.join(module_media_dir, f"{asset_id}_video.mp4")):
                    status['has_video'] = True
            
            # If not in module, check static folder
            if not status['has_image']:
                static_media_dir = os.path.join('web', 'static', 'media', media_type_folder)
                if os.path.exists(static_media_dir):
                    for ext in ['.jpg', '.png']:
                        if os.path.exists(os.path.join(static_media_dir, f"{asset_id}{ext}")):
                            status['has_image'] = True
                            status['image_location'] = 'static'
                            break
                    
                    # Check thumbnail in static
                    if not status['has_thumbnail']:
                        for ext in ['_thumb.jpg', '_thumb.png']:
                            if os.path.exists(os.path.join(static_media_dir, f"{asset_id}{ext}")):
                                status['has_thumbnail'] = True
                                break
                    
                    # Check video in static
                    if not status['has_video']:
                        if os.path.exists(os.path.join(static_media_dir, f"{asset_id}_video.mp4")):
                            status['has_video'] = True
            
            return status
        
        # Build unified asset list with status
        unified_assets = []
        
        # Process NPCs
        for npc_id, npc_data in npcs.items():
            asset_status = check_asset_status(npc_id, 'npc', npc_data['name'])
            unified_assets.append(asset_status)
        
        # Process monsters
        for monster_id, monster_data in monsters.items():
            asset_status = check_asset_status(monster_id, 'monster', monster_data['name'])
            unified_assets.append(asset_status)
        
        # Sort by type then name
        unified_assets.sort(key=lambda x: (x['type'], x['name']))
        
        info(f"TOOLKIT: Found {len(npcs)} NPCs and {len(monsters)} monsters in module {module_name}")
        
        return jsonify({
            'success': True,
            'module': module_name,
            'assets': unified_assets,
            'summary': {
                'total_npcs': len(npcs),
                'total_monsters': len(monsters),
                'total_assets': len(unified_assets),
                'with_descriptions': sum(1 for a in unified_assets if a['has_description']),
                'with_images': sum(1 for a in unified_assets if a['has_image']),
                'complete': sum(1 for a in unified_assets if a['has_description'] and a['has_image'] and a['has_thumbnail'])
            }
        })
        
    except Exception as e:
        error(f"TOOLKIT: Failed to get unified assets for module {module_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _emit_game_resumed():
    """Tell the currently-connecting client it is (re)attached to a live game.

    Approach A for issue #122: the server volunteers session state so a reopened
    browser tab can restore its `gameStarted` flag and re-enable input. Uses the
    request-context `emit` (this client only), not the all-clients broadcast.
    """
    from core.managers.status_manager import status_manager
    try:
        _status_message, is_processing = status_manager.get_status()
    except Exception:
        is_processing = False
    emit('game_resumed', {
        'is_processing': is_processing,
        'message': 'Reconnected to your game in progress.'
    })


@socketio.on('request_ui_snapshot')
def handle_ui_snapshot_request(data=None):
    """Return one authoritative lifecycle/processing snapshot on reconnect."""
    from core.managers.status_manager import status_manager
    try:
        status_message, is_processing = status_manager.get_status()
    except Exception:
        status_message, is_processing = '', False
    running = bool(game_thread and game_thread.is_alive() and not _web_gameplay_paused())
    with _ui_operation_lock:
        operations = {
            key: dict(value) if isinstance(value, dict) else None
            for key, value in _ui_operations.items()
        }
    restore = operations.get('restore') or {}
    if restore.get('pending') or restore.get('can_resume') is False:
        status_message = restore.get('message', status_message)
        is_processing = bool(restore.get('pending'))
    emit('ui_state_snapshot', _ui_response(data, {
        'game_running': running,
        'is_processing': bool(is_processing),
        'status_message': status_message or '',
        'startup': {
            'status': 'ready' if startup_ready_emitted or running else ('in_progress' if startup_handoff_active else 'idle'),
            'phase': status_message or '',
        },
        'operations': operations,
    }))


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    # This is the sole connect handler. Flask-SocketIO keeps one handler per
    # event, so putting the LAN check here avoids it being silently replaced by
    # the normal game-reconnect handler below.
    if _OPERATOR_TOKEN and not session.get("operator_authenticated"):
        return False
    emit('connected', {
        'data': 'Connected to NeverEndingQuest',
        'capabilities': dict(_ui_protocol_capabilities),
        'server_instance_id': _server_instance_id,
    })

    # Load the durable player ledger before any stable-ID recovery writes.
    # Otherwise a first recovered message could overwrite an older on-disk
    # cache from an empty process-local deque.
    cached_messages = load_message_cache() if not _web_gameplay_paused() else []

    # Claim the player-output sink before any reconnect replay below (e.g. combat
    # output recovery) so replayed prose reaches web clients rather than falling
    # back to a console print. (P2b: the module-publication receipt recovery that
    # used to run here is gone -- module creation now publishes atomically and
    # narrates in the same turn, so there is nothing to replay on reconnect.)
    set_player_output_sink(_queue_safe_player_output)

    # Combat uses the same stable-ID player-output boundary. This recovery is
    # provider-free and mechanics-free; it only replays prose already stored
    # in the active encounter receipt.
    try:
        from core.managers.combat_manager import recover_pending_combat_output

        if not _web_gameplay_paused():
            recover_pending_combat_output()
    except Exception as combat_receipt_error:
        error(
            f"Pending combat delivery recovery deferred: {combat_receipt_error}",
            category="combat_events",
        )

    # Check for updates and notify client
    try:
        from utils.version_checker import check_for_updates
        status, local_ver, remote_ver, message = check_for_updates(silent=True)

        emit('version_status', {
            'update_available': status == 'update_available',
            'local_version': local_ver,
            'remote_version': remote_ver,
            'message': message
        })
    except Exception as e:
        print(f"[VERSION_CHECK] Error checking for updates: {e}")

    # Load and send cached messages from previous session
    with message_cache_lock:
        cached_messages = list(message_cache)
    if cached_messages:
        emit('cached_messages', cached_messages)
        print(f"[MESSAGE_CACHE] Sent {len(cached_messages)} cached messages to client")

    # If a game is already running, tell THIS client to reattach (issue #122).
    if game_thread and game_thread.is_alive() and not _web_gameplay_paused():
        _emit_game_resumed()

    # Send any queued messages
    _emit_pending_game_output(emit)

    while not debug_output_queue.empty():
        msg = debug_output_queue.get()
        emit('debug_output', msg)
    
    # Check for module progress updates
    while not module_progress_queue.empty():
        progress_data = module_progress_queue.get()
        _remember_ui_operation('module', progress_data)
        emit('module_creation_progress', progress_data)

@socketio.on('user_input')
def handle_user_input(data):
    """Handle input from the user"""
    if _web_gameplay_paused():
        emit('error', {'message': 'Gameplay is paused. Choose Load, Reset, or Exit.'})
        return
    user_input = data.get('input', '')
    if not isinstance(user_input, str) or not user_input.strip():
        return
    # #214 CR-1: supersede a pending background welcome AT THE ENQUEUE
    # BOUNDARY, before the game thread can pop this text - the game thread
    # then completes the discard handback before processing the input.
    try:
        from utils.capture.live_provider_call import get_active_welcome_scope
        welcome_scope = get_active_welcome_scope()
        if welcome_scope is not None:
            welcome_scope.request_supersession("player_acted")
    except Exception:
        pass
    # Commit the player-visible ledger entry before releasing the command to
    # the game thread, so a fast local response cannot appear above its input.
    message = {
        'type': 'user-input',
        'content': user_input
    }
    add_to_message_cache(message)
    emit('game_output', message)
    user_input_queue.put(user_input)

@socketio.on('action')
def handle_action(data, _operation_id=None):
    """Handle direct action requests from the UI (save, load, reset)."""
    action_type = data.get('action')
    if action_type in {'restoreGame', 'nuclearReset'} and _operation_id is None:
        _operation_id = str(uuid4())
    parameters = data.get('parameters', {})
    from utils.capture.live_provider_call import (
        get_lifecycle_turn_scopes,
        get_active_welcome_scope,
        request_lifecycle_turn_supersession,
    )

    turn_scopes = get_lifecycle_turn_scopes()
    live_scope = turn_scopes[0] if turn_scopes else None
    # #214: a background startup welcome must never make the gate refuse
    # Save/Load/Reset (effective scope = player-turn scope OR welcome scope).
    welcome_scope = get_active_welcome_scope()
    debug(f"WEB_REQUEST: Received direct action from client: {action_type}", category="web_interface")

    if _web_gameplay_paused() and action_type in {'saveGame', 'deleteSave', 'recover_startup_handoff'}:
        emit('error', {'message': 'Gameplay is paused. Choose Load, Reset, or Exit.'})
        return

    if action_type in {'saveGame', 'nuclearReset'}:
        try:
            from core.managers.status_manager import status_manager

            if (
                status_manager.is_processing()
                and live_scope is None
                and welcome_scope is None
                and not _web_gameplay_paused()
            ):
                emit('error', {
                    'message': (
                        'The game is finishing the current action. '
                        'Please retry when it is ready for input.'
                    )
                })
                return
        except Exception:
            # The persistence layer also takes the active combat lease, so a
            # status-service problem cannot bypass the consistency boundary.
            pass

    if action_type == 'listSaves':
        try:
            manager = _web_save_manager()
            saves = manager.list_save_games()
            emit('save_list_response', saves)
        except Exception as e:
            print(f"Error listing saves: {e}")
            emit('save_list_response', [])

    elif action_type == 'saveGame':
        try:
            from updates.save_game_manager import SaveGameManager
            manager = SaveGameManager()
            description = parameters.get("description", "")
            save_mode = parameters.get("saveMode", "essential")
            if live_scope is not None:
                from utils.capture.live_provider_call import queue_live_save

                session_id = getattr(request, 'sid', None) or 'unknown-session'
                operation_id = "save:%s:%s:%s" % (
                    session_id,
                    description,
                    save_mode,
                )
                emit('system_message', {
                    'content': 'Save accepted and queued until the current turn reaches a safe boundary.'
                })

                def execute_save():
                    return manager.create_save_game(description, save_mode)

                def complete_save(outcome):
                    success, message = outcome
                    if success:
                        socketio.emit('system_message', {'content': f"Game saved: {message}"}, to=session_id)
                    else:
                        socketio.emit('error', {'message': f"Save failed: {message}"}, to=session_id)

                queued_id = queue_live_save(
                    execute_save, complete_save, operation_id
                )
                if queued_id is None:
                    live_scope.quiescent.wait()
                    complete_save(execute_save())
                return
            if welcome_scope is not None:
                # #214 F8: Save never cancels a healthy background welcome -
                # it QUEUES against the welcome scope and executes on the
                # game thread inside the welcome terminal, before quiescence
                # releases the loop back to player input (never concurrent).
                from utils.capture.live_provider_call import queue_live_save

                session_id = getattr(request, 'sid', None) or 'unknown-session'

                def execute_welcome_save():
                    return manager.create_save_game(description, save_mode)

                def complete_welcome_save(outcome):
                    success, message = outcome
                    if success:
                        socketio.emit('system_message', {'content': f"Game saved: {message}"}, to=session_id)
                    else:
                        socketio.emit('error', {'message': f"Save failed: {message}"}, to=session_id)

                queued_id = queue_live_save(
                    execute_welcome_save, complete_welcome_save,
                    "save:%s:%s:%s" % (session_id, description, save_mode),
                    scope=welcome_scope,
                )
                if queued_id is None:
                    # The welcome sealed before the enqueue: no welcome
                    # remains. Re-resolve authoritative state - queue against
                    # a now-live player turn, else honest retry (the retry
                    # lands on the plain no-welcome path).
                    queued_id = queue_live_save(
                        execute_welcome_save, complete_welcome_save,
                        "save:%s:%s:%s" % (session_id, description, save_mode),
                    )
                if queued_id is None:
                    # Sealed scope: wait for ITS quiescent (set only AFTER
                    # the registry is cleared), then re-dispatch the SAME
                    # request against freshly read scopes - the next capture
                    # can only be a genuinely different scope, so this
                    # terminates structurally (no tight recursion).
                    welcome_scope.quiescent.wait()
                    return handle_action(data)
                # Acceptance is emitted only once a queue holds the record -
                # never an accepted-then-retry contradiction.
                emit('system_message', {
                    'content': (
                        'Save accepted and queued until the welcome-back '
                        'narration reaches a safe boundary.'
                    )
                })
                return
            success, message = manager.create_save_game(description, save_mode)
            if success:
                emit('system_message', {'content': f"Game saved: {message}"})
            else:
                emit('error', {'message': f"Save failed: {message}"})
        except Exception as e:
            emit('error', {'message': f"Save failed: {str(e)}"})
        finally:
            # An idle Save can have published a filesystem-wait status. Its
            # terminal must release that status, but a queued Save does not
            # own its still-running turn/welcome's input boundary.
            if (not get_lifecycle_turn_scopes()
                    and get_active_welcome_scope() is None
                    and not _web_gameplay_paused()):
                from core.managers.status_manager import status_ready

                status_ready()

    elif action_type == 'restoreGame':
        try:
            manager = _web_save_manager()
            save_folder = parameters.get("saveFolder")
            valid, validation_message = manager.validate_restore_target(save_folder)
            if not valid:
                clean = _web_restore_state().get('can_resume') is not False
                emit('restore_complete', {
                    'message': validation_message,
                    'restore_outcome': 'unchanged' if clean else 'recovery_required',
                    'can_resume': clean,
                    'restart_required': False,
                })
                return
            previous_clean = _web_restore_state().get('can_resume') is not False
            if live_scope is not None:
                operation_id = _operation_id
                turn_scopes, operations = request_lifecycle_turn_supersession(
                    "restore", operation_id
                )
                if not turn_scopes:
                    # The captured scope left the registry before the claim.
                    # Follow its exact terminal and redispatch this control,
                    # not an unowned replacement operation or player retry.
                    live_scope.quiescent.wait()
                    return handle_action(data, _operation_id)
                conflict = next(
                    (
                        operation for operation in operations
                        if operation is not None
                        and operation.get('kind') != 'turn_complete'
                        and not operation.get('accepted')
                    ),
                    None,
                )
                if conflict is not None:
                    emit('error', {
                        'message': (
                            'Another lifecycle operation is already pending: '
                            + conflict['kind']
                        )
                    })
                    return
                emit('system_message', {
                    'content': 'Load accepted. The current turn is stopping safely before the save is restored.',
                    'operation_id': operation_id,
                })
                for turn_scope in turn_scopes:
                    turn_scope.quiescent.wait()
            if welcome_scope is not None:
                # #214 F9: Load supersedes the background welcome and QUEUES
                # the restore to execute ON THE GAME THREAD inside the
                # welcome terminal (after discard handback, before quiescence
                # releases player input) - the destructive op stays
                # authoritative; no post-quiescence scheduling gap.
                from utils.capture.live_provider_call import (
                    claim_destructive_operation,
                )

                def execute_welcome_restore():
                    return _apply_web_restore(manager, save_folder, previous_clean)

                def complete_welcome_restore(outcome):
                    _finish_web_restore(manager, outcome)

                # Claim/promotion AND record insertion are ONE scope-lock
                # transaction: an accepted destructive claim always has its
                # executable record queued (seal can never split them).
                claim = claim_destructive_operation(
                    welcome_scope, "restore",
                    execute_welcome_restore, complete_welcome_restore,
                    operation_id=_operation_id,
                )
                if claim['status'] == 'closed':
                    # Closed before the claim: Load is NEVER refused (#193).
                    # Wait for the CAPTURED scope's quiescent (set only
                    # AFTER the registry is cleared), then re-dispatch the
                    # SAME request against freshly read scopes - never the
                    # stale scope, never a player resubmit, and never tight
                    # recursion on the seal-before-clear window.
                    welcome_scope.quiescent.wait()
                    return handle_action(data, _operation_id)
                if claim['status'] == 'conflict':
                    emit('error', {
                        'message': (
                            'Another lifecycle operation is already pending: '
                            + str(claim['kind'])
                        )
                    })
                    return
                emit('system_message', {
                    'content': 'Load accepted. The welcome-back narration is stopping safely first.',
                    'operation_id': claim['operation_id'],
                })
                return
            _begin_web_restore(manager, 'Load is stopping the previous game safely.', previous_clean)
            _stop_web_game_reader()
            _finish_web_restore(manager, _apply_web_restore(manager, save_folder, previous_clean))
        except Exception as e:
            emit('error', {'message': f"Restore failed: {str(e)}"})
    
    elif action_type == 'deleteSave':
        try:
            from updates.save_game_manager import SaveGameManager
            manager = SaveGameManager()
            save_folder = parameters.get("saveFolder")
            success, message = manager.delete_save_game(save_folder)
            if success:
                emit('system_message', {'content': f"Save deleted: {message}"})
            else:
                emit('error', {'message': f"Delete failed: {message}"})
        except Exception as e:
            emit('error', {'message': f"Delete failed: {str(e)}"})

    elif action_type == 'nuclearReset':
        manager = None
        try:
            manager = _web_save_manager()
            if live_scope is not None:
                operation_id = _operation_id
                turn_scopes, operations = request_lifecycle_turn_supersession(
                    "reset", operation_id
                )
                if not turn_scopes:
                    live_scope.quiescent.wait()
                    return handle_action(data, _operation_id)
                conflict = next(
                    (
                        operation for operation in operations
                        if operation is not None
                        and operation.get('kind') != 'turn_complete'
                        and not operation.get('accepted')
                    ),
                    None,
                )
                if conflict is not None:
                    emit('error', {
                        'message': (
                            'Another lifecycle operation is already pending: '
                            + conflict['kind']
                        )
                    })
                    return
                emit('system_message', {
                    'content': 'Reset accepted. The current turn is stopping safely before reset.',
                    'operation_id': operation_id,
                })
                for turn_scope in turn_scopes:
                    turn_scope.quiescent.wait()
            if welcome_scope is not None:
                # #214 F9: same discipline as Load - supersede and QUEUE the
                # reset to execute on the game thread inside the welcome
                # terminal, before player input is released.
                from utils.capture.live_provider_call import (
                    claim_destructive_operation,
                )

                session_id = getattr(request, 'sid', None) or 'unknown-session'

                def execute_welcome_reset():
                    try:
                        _begin_web_restore(manager, 'Resetting the campaign.')
                        reset_campaign.perform_reset_logic()
                        message_cache.clear()
                        save_message_cache()
                        return (True, 'reset')
                    except Exception as exc:
                        return (False, str(exc))

                def complete_welcome_reset(outcome):
                    success, message = outcome
                    if success:
                        socketio.emit('reset_complete', {'message': 'Campaign has been reset. Reloading...'}, to=session_id)
                        socketio.sleep(1)
                        print("INFO: Campaign reset complete. Server is shutting down for restart.")
                        os._exit(0)
                    else:
                        from updates.save_game_manager import RestoreOutcome
                        _finish_web_restore(manager, RestoreOutcome('recovery_required', f'Campaign reset failed: {message}'))

                # One atomic claim+record transaction (same as Load).
                claim = claim_destructive_operation(
                    welcome_scope, "reset",
                    execute_welcome_reset, complete_welcome_reset,
                    operation_id=_operation_id,
                )
                if claim['status'] == 'closed':
                    # Same rule as Load: wait for the captured scope's
                    # quiescent, then re-dispatch.
                    welcome_scope.quiescent.wait()
                    return handle_action(data, _operation_id)
                if claim['status'] == 'conflict':
                    emit('error', {
                        'message': (
                            'Another lifecycle operation is already pending: '
                            + str(claim['kind'])
                        )
                    })
                    return
                emit('system_message', {
                    'content': 'Reset accepted. The welcome-back narration is stopping safely first.',
                    'operation_id': claim['operation_id'],
                })
                return
            _begin_web_restore(manager, 'Resetting the campaign.')
            _stop_web_game_reader()
            reset_campaign.perform_reset_logic()
            # Clear the message cache on campaign reset
            global message_cache
            message_cache.clear()
            save_message_cache()
            emit('reset_complete', {'message': 'Campaign has been reset. Reloading...'})
            socketio.sleep(1)
            print("INFO: Campaign reset complete. Server is shutting down for restart.")
            os._exit(0)
        except Exception as e:
            if manager is None:
                emit('error', {'message': f'Campaign reset could not start: {e}'})
                return
            from updates.save_game_manager import RestoreOutcome
            _finish_web_restore(manager, RestoreOutcome('recovery_required', f'Campaign reset failed: {e}'))

    elif action_type == 'recover_startup_handoff':
        session_id = getattr(request, 'sid', None) or 'unknown-session'
        recovery_token = parameters.get('recoveryToken')
        startup_attempt_id = parameters.get('startupAttemptId')
        source = 'socketio.action'

        try:
            import config

            expected_token = getattr(config, 'STARTUP_RECOVERY_TOKEN', None)
            if not expected_token:
                log_web_audit(
                    'recover_startup_handoff',
                    source=source,
                    session=session_id,
                    result='failed',
                    reason='missing_server_token',
                )
                payload = {'status': 'failed', 'error': 'server_token_not_configured'}
                emit('startup_recovery_response', payload)
                return payload

            if not recovery_token or recovery_token != expected_token:
                log_web_audit(
                    'recover_startup_handoff',
                    source=source,
                    session=session_id,
                    result='failed',
                    reason='invalid_token',
                )
                payload = {'status': 'failed', 'error': 'invalid_recovery_token'}
                emit('startup_recovery_response', payload)
                return payload

            current_state = dm_main.load_startup_state()
            expected_attempt_id = current_state.get('startup_attempt_id')
            if not startup_attempt_id:
                payload = {'status': 'failed', 'error': 'missing_startup_attempt_id'}
                emit('startup_recovery_response', payload)
                return payload
            if expected_attempt_id and startup_attempt_id != expected_attempt_id:
                payload = {
                    'status': 'failed',
                    'error': 'stale_startup_attempt_id',
                    'expectedStartupAttemptId': expected_attempt_id,
                }
                emit('startup_recovery_response', payload)
                return payload

            now = time.monotonic()
            with startup_recovery_attempts_lock:
                last_attempt = startup_recovery_attempts.get(session_id)
                if last_attempt is not None:
                    elapsed = now - last_attempt
                    if elapsed < STARTUP_RECOVERY_ACTION_COOLDOWN_SECONDS:
                        retry_after = max(
                            1,
                            int(
                                STARTUP_RECOVERY_ACTION_COOLDOWN_SECONDS - elapsed + 0.999
                            ),
                        )
                        log_web_audit(
                            'recover_startup_handoff',
                            source=source,
                            session=session_id,
                            result='failed',
                            reason='cooldown_active',
                            retry_after_seconds=retry_after,
                        )
                        payload = {
                            'status': 'failed',
                            'error': 'cooldown_active',
                            'retryAfterSeconds': retry_after,
                        }
                        emit('startup_recovery_response', payload)
                        return payload
                startup_recovery_attempts[session_id] = now

            log_web_audit(
                'recover_startup_handoff',
                source=source,
                session=session_id,
                result='attempting',
            )
            recovery_result = dm_main.recover_startup_handoff() or {}
            from updates.save_game_manager import RestoreRequest
            if isinstance(recovery_result, RestoreRequest):
                return handle_action({
                    'action': 'restoreGame',
                    'parameters': {'saveFolder': recovery_result.save_folder},
                })
            status = recovery_result.get('status', 'failed')
            if status not in {'recovered', 'already_ready', 'failed', 'in_progress', 'not_recoverable'}:
                status = 'failed'

            payload = {'status': status}
            if status == 'failed':
                payload['error'] = (
                    recovery_result.get('error')
                    or recovery_result.get('reason')
                    or 'unknown'
                )

            log_web_audit(
                'recover_startup_handoff',
                source=source,
                session=session_id,
                result=status,
            )
            emit('startup_recovery_response', payload)
            return payload
        except Exception as e:
            log_web_audit(
                'recover_startup_handoff',
                source=source,
                session=session_id,
                result='failed',
                reason='exception',
                error=str(e),
            )
            payload = {'status': 'failed', 'error': str(e)}
            emit('startup_recovery_response', payload)
            return payload

@socketio.on('start_game')
def handle_start_game():
    """Start the game in a separate thread"""
    global game_thread, startup_handoff_active, startup_ready_emitted, message_cache
    if _web_gameplay_paused():
        emit('error', {'message': 'Gameplay is paused. Choose Load, Reset, or Exit.'})
        return
    
    if game_thread and game_thread.is_alive():
        # Browser reopened on a live game: reconnect this client instead of
        # erroring out (issue #122 -- this error was the literal report title).
        _emit_game_resumed()
        return
    
    # Uninstall debug interceptor to prevent competing stdout redirections
    uninstall_debug_interceptor()

    # Set up output capture - both go to debug by default, filtering happens in write()
    sys.stdout = WebOutputCapture(debug_output_queue, original_stdout)
    sys.stderr = WebOutputCapture(debug_output_queue, original_stderr, is_error=True)
    sys.stdin = WebInput(user_input_queue)
    # Claim the player-output sink only now that a web game session owns
    # the frontend (see the note at the old import-time install site).
    set_player_output_sink(_queue_safe_player_output)
    
    # Start the game in a separate thread
    startup_handoff_active = True
    startup_ready_emitted = False
    message_cache.clear()
    save_message_cache()
    game_thread = threading.Thread(target=run_game_loop, daemon=True)
    game_thread.start()

    emit('startup_status', {'status': 'in_progress', 'phase': 'launching'})

@socketio.on('request_player_data')
def handle_player_data_request(data=None):
    """Handle requests for player data (inventory, stats, NPCs)"""
    data = data if isinstance(data, dict) else {}
    dataType = data.get('dataType', 'stats')
    try:
        response_data = None
        
        # Load party tracker to get player name and NPCs
        party_tracker_path = 'party_tracker.json'
        if os.path.exists(party_tracker_path):
            with open(party_tracker_path, 'r', encoding='utf-8') as f:
                party_tracker = json.load(f)
        else:
            emit('player_data_response', _ui_response(data, {'dataType': dataType, 'data': None, 'error': 'Party tracker not found'}))
            return
        
        if dataType == 'stats' or dataType == 'inventory' or dataType == 'spells':
            # Get player name from party tracker
            if party_tracker.get('partyMembers') and len(party_tracker['partyMembers']) > 0:
                from updates.update_character_info import normalize_character_name
                player_name = normalize_character_name(party_tracker['partyMembers'][0])
                
                # Try module-specific path first
                from utils.module_path_manager import ModulePathManager
                current_module = party_tracker.get("module", "").replace(" ", "_")
                path_manager = ModulePathManager(current_module)
                
                try:
                    player_file = path_manager.get_character_path(player_name)
                    if os.path.exists(player_file):
                        with open(player_file, 'r', encoding='utf-8') as f:
                            response_data = json.load(f)
                            response_data = _effective_character_for_ui(response_data)
                except:
                    # Fallback to characters directory
                    player_file = path_manager.get_character_path(player_name)
                    if os.path.exists(player_file):
                        with open(player_file, 'r', encoding='utf-8') as f:
                            response_data = json.load(f)
                            response_data = _effective_character_for_ui(response_data)
        
        elif dataType == 'npcs':
            # Get NPC data from party tracker
            npcs = []
            from utils.module_path_manager import ModulePathManager
            current_module = party_tracker.get("module", "").replace(" ", "_")
            path_manager = ModulePathManager(current_module)
            
            for npc_info in party_tracker.get('partyNPCs', []):
                npc_name = npc_info['name']
                
                try:
                    # Use fuzzy matching to find the correct NPC file
                    from updates.update_character_info import find_character_file_fuzzy
                    matched_name = find_character_file_fuzzy(npc_name)
                    
                    if matched_name:
                        npc_file = path_manager.get_character_path(matched_name)
                        if os.path.exists(npc_file):
                            with open(npc_file, 'r', encoding='utf-8') as f:
                                npc_data = json.load(f)
                                npc_data = _effective_character_for_ui(npc_data)
                                npcs.append(npc_data)
                except:
                    pass
            
            response_data = npcs
        
        payload = {'dataType': dataType, 'data': response_data}
        if dataType in ('stats', 'inventory', 'spells') and response_data is None:
            payload['error'] = 'Player data not found'
        emit('player_data_response', _ui_response(data, payload))
    
    except Exception as e:
        emit('player_data_response', _ui_response(data, {'dataType': dataType, 'data': None, 'error': str(e)}))

@socketio.on('request_location_data')
def handle_location_data_request(data=None):
    """Handle requests for current location information"""
    try:
        # Load party tracker to get current location
        party_tracker_path = 'party_tracker.json'
        if os.path.exists(party_tracker_path):
            with open(party_tracker_path, 'r', encoding='utf-8') as f:
                party_tracker = json.load(f)
            
            world_conditions = party_tracker.get('worldConditions', {})
            location_info = {
                'currentLocation': world_conditions.get('currentLocation', 'Unknown'),
                'currentArea': world_conditions.get('currentArea', 'Unknown'),
                'currentLocationId': world_conditions.get('currentLocationId', ''),
                'currentAreaId': world_conditions.get('currentAreaId', ''),
                'time': world_conditions.get('time', ''),
                'day': world_conditions.get('day', ''),
                'month': world_conditions.get('month', ''),
                'year': world_conditions.get('year', '')
            }
            
            emit('location_data_response', _ui_response(data, {'data': location_info}))
        else:
            emit('location_data_response', _ui_response(data, {'data': None, 'error': 'Party tracker not found'}))
    
    except Exception as e:
        emit('location_data_response', _ui_response(data, {'data': None, 'error': str(e)}))

@socketio.on('request_npc_saves')
def handle_npc_saves_request(data):
    """Handle requests for NPC saving throws"""
    try:
        npc_name = data.get('npcName', '')
        
        # Load the NPC file
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc_name)
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            npc_file = path_manager.get_character_path(normalize_character_name(npc_name))
        if os.path.exists(npc_file):
            with open(npc_file, 'r', encoding='utf-8') as f:
                npc_data = json.load(f)
            npc_data = _effective_character_for_ui(npc_data)
            
            emit('npc_details_response', {'npcName': npc_name, 'data': npc_data, 'modalType': 'saves'})
        else:
            emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': 'NPC file not found'})
            
    except Exception as e:
        emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': str(e)})

@socketio.on('request_npc_skills')
def handle_npc_skills_request(data):
    """Handle requests for NPC skills"""
    try:
        npc_name = data.get('npcName', '')
        
        # Load the NPC file
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc_name)
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            npc_file = path_manager.get_character_path(normalize_character_name(npc_name))
        if os.path.exists(npc_file):
            with open(npc_file, 'r', encoding='utf-8') as f:
                npc_data = json.load(f)
            npc_data = _effective_character_for_ui(npc_data)
            
            emit('npc_details_response', {'npcName': npc_name, 'data': npc_data, 'modalType': 'skills'})
        else:
            emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': 'NPC file not found'})
            
    except Exception as e:
        emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': str(e)})

@socketio.on('request_npc_spells')
def handle_npc_spells_request(data):
    """Handle requests for NPC spellcasting"""
    try:
        npc_name = data.get('npcName', '')
        
        # Load the NPC file
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc_name)
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            npc_file = path_manager.get_character_path(normalize_character_name(npc_name))
        if os.path.exists(npc_file):
            with open(npc_file, 'r', encoding='utf-8') as f:
                npc_data = json.load(f)
            npc_data = _effective_character_for_ui(npc_data)
            
            emit('npc_details_response', {'npcName': npc_name, 'data': npc_data, 'modalType': 'spells'})
        else:
            emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': 'NPC file not found'})
            
    except Exception as e:
        emit('npc_details_response', {'npcName': npc_name, 'data': None, 'error': str(e)})

@socketio.on('request_npc_inventory')
def handle_npc_inventory_request(data):
    """Handle requests for NPC inventory"""
    try:
        npc_name = data.get('npcName', '')
        
        # Load the NPC file
        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc_name)
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            npc_file = path_manager.get_character_path(normalize_character_name(npc_name))
        if os.path.exists(npc_file):
            with open(npc_file, 'r', encoding='utf-8') as f:
                npc_data = json.load(f)
            npc_data = _effective_character_for_ui(npc_data)
            
            # Extract equipment for inventory display
            equipment = npc_data.get('equipment', [])
            emit('npc_inventory_response', {'npcName': npc_name, 'data': equipment})
        else:
            emit('npc_inventory_response', {'npcName': npc_name, 'data': None, 'error': 'NPC file not found'})
            
    except Exception as e:
        emit('npc_inventory_response', {'npcName': npc_name, 'data': None, 'error': str(e)})

@socketio.on('request_party_data')
def handle_party_data_request(data=None):
    """Handle requests for party member display and current location NPCs (non-combat)."""
    try:
        from utils.file_operations import safe_read_json
        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Load party tracker
        party_tracker = safe_read_json("party_tracker.json")
        if not party_tracker:
            emit('party_data_response', _ui_response(data, {
                'members': [],
                'location_npcs': [],
                'error': 'Party tracker not found',
            }))
            return
        
        # Get module info for path resolution
        current_module = party_tracker.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)
        
        party_members = []
        
        # Add player first
        if party_tracker.get('partyMembers') and len(party_tracker['partyMembers']) > 0:
            player_name = normalize_character_name(party_tracker['partyMembers'][0])
            
            # Try to load player data for HP info
            try:
                player_file = path_manager.get_character_path(player_name)
                if os.path.exists(player_file):
                    player_data = safe_read_json(player_file)
                    if player_data:
                        player_data = _effective_character_for_ui(player_data)
                        # Extract spell data organized by level
                        spells_by_level = {}
                        spellcasting = player_data.get('spellcasting', {})
                        if spellcasting.get('spells'):
                            spells_data = spellcasting['spells']
                            # Handle cantrips
                            if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                spells_by_level[0] = spells_data['cantrips']
                            # Handle leveled spells (level1, level2, etc.)
                            for i in range(1, 10):
                                key = f'level{i}'
                                if spells_data.get(key) and len(spells_data[key]) > 0:
                                    spells_by_level[i] = spells_data[key]
                        
                        # Extract class features for tooltip
                        class_features = []
                        for feature in player_data.get('classFeatures', []):
                            # Include feature name and brief info about usage if available
                            feature_info = {'name': feature.get('name', '')}
                            if 'usage' in feature:
                                usage = feature['usage']
                                if usage.get('current') is not None and usage.get('max'):
                                    feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                            class_features.append(feature_info)
                        
                        # Get primary attack from attacksAndSpellcasting
                        primary_attack = {'bonus': 0, 'damage': '1d4'}  # Default unarmed
                        attacks = player_data.get('attacksAndSpellcasting', [])
                        if attacks and isinstance(attacks, list) and len(attacks) > 0:
                            # Use the first attack as primary
                            first_attack = attacks[0]
                            damage_dice = first_attack.get('damageDice', '1d4')
                            damage_bonus = first_attack.get('damageBonus', 0)
                            # Format damage string properly
                            if damage_bonus > 0:
                                damage_str = f"{damage_dice}+{damage_bonus}"
                            elif damage_bonus < 0:
                                damage_str = f"{damage_dice}{damage_bonus}"
                            else:
                                damage_str = damage_dice
                            primary_attack = {
                                'bonus': first_attack.get('attackBonus', 0),
                                'damage': damage_str,
                                'name': first_attack.get('name', 'Attack')
                            }

                        party_members.append({
                            'name': player_data.get('name', player_name),
                            'type': 'player',
                            'currentHp': player_data.get('hitPoints', player_data.get('currentHp', 0)),
                            'maxHp': player_data.get('maxHitPoints', player_data.get('maxHp', 0)),
                            'level': player_data.get('level', 1),
                            'class': player_data.get('class', 'Unknown'),
                            'ac': player_data.get('armorClass', 10),
                            'speed': player_data.get('speed', 30),
                            'initiative': player_data.get('initiative', 0),
                            'primaryAttack': primary_attack,
                            'spellSlots': spellcasting.get('spellSlots', player_data.get('spellSlots', {})),
                            'spells': spells_by_level,
                            'conditions': player_data.get('conditions', []),
                            'classFeatures': class_features
                        })
            except:
                # Fallback if can't load player data
                party_members.append({
                    'name': player_name,
                    'type': 'player'
                })
        
        # Add NPCs in order
        for npc_info in party_tracker.get('partyNPCs', []):
            npc_name = npc_info['name']
            
            try:
                # Use fuzzy matching to find NPC file
                matched_name = find_character_file_fuzzy(npc_name)
                if matched_name:
                    npc_file = path_manager.get_character_path(matched_name)
                    if os.path.exists(npc_file):
                        npc_data = safe_read_json(npc_file)
                        if npc_data:
                            npc_data = _effective_character_for_ui(npc_data)
                            # Extract spell data organized by level
                            spells_by_level = {}
                            spellcasting = npc_data.get('spellcasting', {})
                            if spellcasting.get('spells'):
                                spells_data = spellcasting['spells']
                                # Handle cantrips
                                if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                    spells_by_level[0] = spells_data['cantrips']
                                # Handle leveled spells (level1, level2, etc.)
                                for i in range(1, 10):
                                    key = f'level{i}'
                                    if spells_data.get(key) and len(spells_data[key]) > 0:
                                        spells_by_level[i] = spells_data[key]
                            
                            # Extract class features for tooltip
                            class_features = []
                            for feature in npc_data.get('classFeatures', []):
                                # Include feature name and brief info about usage if available
                                feature_info = {'name': feature.get('name', '')}
                                if 'usage' in feature:
                                    usage = feature['usage']
                                    if usage.get('current') is not None and usage.get('max'):
                                        feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                                class_features.append(feature_info)
                            
                            # Get primary attack from attacksAndSpellcasting
                            primary_attack = {'bonus': 0, 'damage': '1d4'}  # Default unarmed
                            attacks = npc_data.get('attacksAndSpellcasting', [])
                            if attacks and isinstance(attacks, list) and len(attacks) > 0:
                                # Use the first attack as primary
                                first_attack = attacks[0]
                                damage_dice = first_attack.get('damageDice', '1d4')
                                damage_bonus = first_attack.get('damageBonus', 0)
                                # Format damage string properly
                                if damage_bonus > 0:
                                    damage_str = f"{damage_dice}+{damage_bonus}"
                                elif damage_bonus < 0:
                                    damage_str = f"{damage_dice}{damage_bonus}"
                                else:
                                    damage_str = damage_dice
                                primary_attack = {
                                    'bonus': first_attack.get('attackBonus', 0),
                                    'damage': damage_str,
                                    'name': first_attack.get('name', 'Attack')
                                }

                            # Get ammunition data
                            ammunition_info = []
                            ammunition = npc_data.get('ammunition', [])
                            if ammunition:
                                for ammo in ammunition:
                                    if isinstance(ammo, dict):
                                        ammo_name = ammo.get('name', 'Unknown')
                                        ammo_qty = ammo.get('quantity', 0)
                                        ammunition_info.append({'name': ammo_name, 'quantity': ammo_qty})

                            party_members.append({
                                'name': npc_data.get('name', npc_name),
                                'type': 'npc',
                                'currentHp': npc_data.get('hitPoints', npc_data.get('currentHp', 0)),
                                'maxHp': npc_data.get('maxHitPoints', npc_data.get('maxHp', 0)),
                                'level': npc_data.get('level', 1),
                                'class': npc_data.get('class', 'Unknown'),
                                'ac': npc_data.get('armorClass', 10),
                                'speed': npc_data.get('speed', 30),
                                'initiative': npc_data.get('initiative', 0),
                                'primaryAttack': primary_attack,
                                'ammunition': ammunition_info,
                                'spellSlots': spellcasting.get('spellSlots', npc_data.get('spellSlots', {})),
                                'spells': spells_by_level,
                                'conditions': npc_data.get('conditions', []),
                                'classFeatures': class_features
                            })
                            continue
            except:
                pass
            
            # Fallback if can't load NPC data
            party_members.append({
                'name': npc_name,
                'type': 'npc'
            })
        
        # Find NPCs in current location
        location_npcs = []
        world_conditions = party_tracker.get("worldConditions", {})
        current_area_id = world_conditions.get("currentAreaId")
        current_location_id = world_conditions.get("currentLocationId")

        if current_module and current_area_id and current_location_id:
            # Construct the path to the current area file
            areas_dir = os.path.join("modules", current_module, "areas")
            area_file_path = os.path.join(areas_dir, f"{current_area_id}.json")
            
            if os.path.exists(area_file_path):
                area_data = safe_read_json(area_file_path)
                if area_data and 'locations' in area_data:
                    # Find the specific location the player is in
                    current_location_data = next((loc for loc in area_data['locations'] 
                                                 if loc.get('locationId') == current_location_id), None)
                    
                    if current_location_data and 'npcs' in current_location_data:
                        # Extract the names of the NPCs in that location
                        for npc in current_location_data['npcs']:
                            npc_name = npc.get('name') if isinstance(npc, dict) else npc
                            if npc_name:
                                # Exclude NPCs that are already in the player's party
                                # Also exclude NPCs whose names are contained within any party member's name
                                # Example: "Eirik" should be excluded if "Eirik Hearthwise" is in the party
                                if not any(npc_name.lower() in member['name'].lower() for member in party_members):
                                    # Try to load NPC data for HP info
                                    npc_data_dict = {'name': npc_name, 'type': 'location_npc'}
                                    try:
                                        matched_name = find_character_file_fuzzy(npc_name)
                                        if matched_name:
                                            npc_file = path_manager.get_character_path(matched_name)
                                            if os.path.exists(npc_file):
                                                npc_data = safe_read_json(npc_file)
                                                if npc_data:
                                                    npc_data = _effective_character_for_ui(npc_data)
                                                    npc_data_dict['currentHp'] = npc_data.get('hitPoints', npc_data.get('currentHp', 0))
                                                    npc_data_dict['maxHp'] = npc_data.get('maxHitPoints', npc_data.get('maxHp', 0))
                                    except:
                                        pass
                                    location_npcs.append(npc_data_dict)
        
        # Send both lists to the frontend
        emit('party_data_response', _ui_response(data, {'members': party_members, 'location_npcs': location_npcs}))
        
    except Exception as e:
        error(f"Failed to get party data: {str(e)}", exception=e, category="web_interface")
        emit('party_data_response', _ui_response(data, {
            'members': [],
            'location_npcs': [],
            'error': str(e),
        }))

def _overlay_authoritative_character_state(combatant_data, character_data):
    """Overlay character-file state onto an encounter UI projection."""
    projected = dict(combatant_data or {})
    if not isinstance(character_data, dict):
        return projected
    character_data = _effective_character_for_ui(character_data)

    if character_data.get("hitPoints") is not None:
        projected["currentHp"] = character_data["hitPoints"]
    if character_data.get("maxHitPoints") is not None:
        projected["maxHp"] = character_data["maxHitPoints"]
    return projected


@socketio.on('request_initiative_data')
def handle_initiative_data_request(data=None):
    """Handles requests for the current combat initiative order."""
    try:
        from utils.file_operations import safe_read_json
        
        # Check if combat is active via party_tracker.json
        party_tracker = safe_read_json("party_tracker.json")
        if not party_tracker:
            emit('initiative_data_response', _ui_response(data, {
                'active': False,
                'combatants': [],
                'error': 'Party tracker not found',
            }))
            return

        # Get the active combat encounter ID
        active_encounter_id = party_tracker.get("worldConditions", {}).get("activeCombatEncounter")
        if not active_encounter_id:
            # No combat is active
            emit('initiative_data_response', _ui_response(data, {'active': False, 'combatants': []}))
            return

        # Load the specific encounter file
        encounter_file = f"modules/encounters/encounter_{active_encounter_id}.json"
        encounter_data = safe_read_json(encounter_file)
        if not encounter_data or "creatures" not in encounter_data:
            emit('initiative_data_response', _ui_response(data, {'active': False, 'combatants': []}))
            return

        from core.managers.combat_state import initiative_ui_projection

        # Typed encounters project membership/order/current input ownership from
        # the committed combat ledger. Legacy encounters preserve the existing
        # living-roster/raw-initiative response behavior.
        sorted_combatants = initiative_ui_projection(encounter_data)
        combat_state = encounter_data.get("combatState") or {}
        recovery_conflict = combat_state.get("recoveryConflict")
        recovery = None
        if (
            isinstance(recovery_conflict, dict)
            and recovery_conflict.get("status") == "pending"
        ):
            recovery = {
                "required": True,
                "message": str(
                    recovery_conflict.get("playerMessage")
                    or "Combat recovery needs attention -- Load or Reset"
                ),
                "actions": ["load", "reset"],
            }

        if not sorted_combatants:
            # Combat is over if no one is alive
            emit('initiative_data_response', _ui_response(data, {'active': False, 'combatants': []}))
            return

        # Prepare clean data for frontend with full character data for tooltips
        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy

        party_tracker = safe_read_json("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else ""
        path_manager = ModulePathManager(current_module) if current_module else None

        combatant_list = []
        for c in sorted_combatants:
            combatant_data = {
                "name": c.get("name"),
                "type": c.get("type"),  # 'player', 'npc', or 'enemy'
                "initiative": c.get("initiative"),
                "currentHp": c.get("currentHitPoints"),
                "maxHp": c.get("maxHitPoints"),
                "monsterType": c.get("monsterType"),  # For enemy type lookup
                "class": c.get("class")  # For NPC class lookup
            }
            for projected_field in ("combatantId", "controller", "isCurrent"):
                if projected_field in c:
                    combatant_data[projected_field] = c[projected_field]

            # Load full character data for players and NPCs to enable tooltips
            if path_manager and c.get("type") in ['player', 'npc']:
                try:
                    character_name = normalize_character_name(c.get("name", ""))

                    # Try to load character data
                    if c.get("type") == 'npc':
                        # Use fuzzy matching for NPCs
                        matched_name = find_character_file_fuzzy(character_name)
                        if matched_name:
                            char_file = path_manager.get_character_path(matched_name)
                        else:
                            char_file = None
                    else:
                        # Direct path for players
                        char_file = path_manager.get_character_path(character_name)

                    if char_file and os.path.exists(char_file):
                        char_data = safe_read_json(char_file)
                        if char_data:
                            # Player HP is persisted in the character file;
                            # NPC/enemy combat HP remains encounter-owned.
                            if c.get("type") == "player":
                                combatant_data = _overlay_authoritative_character_state(
                                    combatant_data, char_data
                                )
                            # Extract spell data organized by level
                            spells_by_level = {}
                            spellcasting = char_data.get('spellcasting', {})
                            if spellcasting.get('spells'):
                                spells_data = spellcasting['spells']
                                # Handle cantrips
                                if spells_data.get('cantrips') and len(spells_data['cantrips']) > 0:
                                    spells_by_level[0] = spells_data['cantrips']
                                # Handle leveled spells (level1, level2, etc.)
                                for i in range(1, 10):
                                    key = f'level{i}'
                                    if spells_data.get(key) and len(spells_data[key]) > 0:
                                        spells_by_level[i] = spells_data[key]

                            # Extract class features for tooltip
                            class_features = []
                            for feature in char_data.get('classFeatures', []):
                                feature_info = {'name': feature.get('name', '')}
                                if 'usage' in feature:
                                    usage = feature['usage']
                                    if usage.get('current') is not None and usage.get('max'):
                                        feature_info['usage'] = f"{usage['current']}/{usage['max']}"
                                class_features.append(feature_info)

                            # Get primary attack from attacksAndSpellcasting
                            primary_attack = {'bonus': 0, 'damage': '1d4'}  # Default unarmed
                            attacks = char_data.get('attacksAndSpellcasting', [])
                            if attacks and isinstance(attacks, list) and len(attacks) > 0:
                                # Use the first attack as primary
                                first_attack = attacks[0]
                                damage_dice = first_attack.get('damageDice', '1d4')
                                damage_bonus = first_attack.get('damageBonus', 0)
                                # Format damage string properly
                                if damage_bonus > 0:
                                    damage_str = f"{damage_dice}+{damage_bonus}"
                                elif damage_bonus < 0:
                                    damage_str = f"{damage_dice}{damage_bonus}"
                                else:
                                    damage_str = damage_dice
                                primary_attack = {
                                    'bonus': first_attack.get('attackBonus', 0),
                                    'damage': damage_str,
                                    'name': first_attack.get('name', 'Attack')
                                }

                            # Get ammunition data for combat tooltips
                            ammunition_info = []
                            ammunition = char_data.get('ammunition', [])
                            if ammunition:
                                for ammo in ammunition:
                                    if isinstance(ammo, dict):
                                        ammo_name = ammo.get('name', 'Unknown')
                                        ammo_qty = ammo.get('quantity', 0)
                                        ammunition_info.append({'name': ammo_name, 'quantity': ammo_qty})

                            # Add full character data for tooltips
                            combatant_data.update({
                                'level': char_data.get('level', 1),
                                'ac': char_data.get('armorClass', 10),
                                'speed': char_data.get('speed', 30),
                                'primaryAttack': primary_attack,
                                'ammunition': ammunition_info,
                                'spellSlots': spellcasting.get('spellSlots', char_data.get('spellSlots', {})),
                                'spells': spells_by_level,
                                'conditions': char_data.get('conditions', []),
                                'classFeatures': class_features,
                                'abilities': char_data.get('abilities', {})
                            })
                except Exception as e:
                    # Log error but continue with minimal data
                    error(f"Error loading character data for {c.get('name', 'unknown')}: {e}", category="web_interface")

            combatant_list.append(combatant_data)

        # Send the data to the browser
        emit('initiative_data_response', _ui_response(data, {
            'active': True,
            'combatants': combatant_list,
            'round': encounter_data.get('combat_round', 1),
            'recovery': recovery,
        }))

    except Exception as e:
        error(f"Error handling initiative data request: {e}", exception=e, category="web_interface")
        emit('initiative_data_response', _ui_response(data, {
            'active': False,
            'combatants': [],
            'error': str(e),
        }))

# Add this entire function to web_interface.py

@socketio.on('request_plot_data')
def handle_plot_data_request(data=None):
    """Handle requests for the current module's plot data."""
    try:
        # Step 1: Find out which module is currently active by checking the party tracker.
        party_tracker_path = 'party_tracker.json'
        if not os.path.exists(party_tracker_path):
            emit('plot_data_response', _ui_response(data, {'data': None, 'error': 'Party tracker not found'}))
            return

        with open(party_tracker_path, 'r', encoding='utf-8') as f:
            party_tracker = json.load(f)
        
        current_module = party_tracker.get("module", "").replace(" ", "_")
        if not current_module:
            emit('plot_data_response', _ui_response(data, {'data': None, 'error': 'Current module not set in party tracker'}))
            return

        # Step 2: Use the ModulePathManager to get the correct path to the plot file for that module.
        # This makes sure we always load the plot for the adventure the player is actually on.
        from utils.module_path_manager import ModulePathManager
        path_manager = ModulePathManager(current_module)
        
        # Step 2.5: Use derived player quests only when their source digest
        # still matches the current exact module_plot.json bytes.
        from utils.quest_player_formatter import load_current_player_quests

        player_quests_data = load_current_player_quests(current_module)

        if player_quests_data is not None:
            # Use current player-friendly quest descriptions.
            
            # Convert player quest format back to module_plot format for compatibility
            plot_data = {
                "plotPoints": []
            }
            
            for quest_id, quest_data in player_quests_data.get("quests", {}).items():
                plot_point = {
                    "id": quest_data.get("id"),
                    "title": quest_data.get("title"),
                    "description": quest_data.get("playerDescription", quest_data.get("originalDescription", "")),
                    "status": quest_data.get("status"),
                    "sideQuests": []
                }
                
                # Add side quests
                for sq_id, sq_data in quest_data.get("sideQuests", {}).items():
                    plot_point["sideQuests"].append({
                        "id": sq_data.get("id"),
                        "title": sq_data.get("title"),
                        "description": sq_data.get("playerDescription", ""),
                        "status": sq_data.get("status")
                    })
                
                plot_data["plotPoints"].append(plot_point)
            
            debug(f"WEB_INTERFACE: Using player-friendly quests for {current_module}", category="web_interface")
        else:
            # Fallback to original module_plot.json
            plot_file_path = path_manager.get_plot_path()

            if not os.path.exists(plot_file_path):
                emit('plot_data_response', _ui_response(data, {'data': None, 'error': f'Plot file not found for module: {current_module}'}))
                return
                
            # Step 3: Read the plot file and send its data back to the browser.
            with open(plot_file_path, 'r', encoding='utf-8') as f:
                plot_data = json.load(f)
            
            debug(f"WEB_INTERFACE: Using original plot data for {current_module} (player quests unavailable or stale)", category="web_interface")
        
        # The 'emit' function sends the data over the web socket connection to the player's browser.
        emit('plot_data_response', _ui_response(data, {'data': plot_data}))

    except Exception as e:
        # If anything goes wrong, send an error message so we can debug it.
        emit('plot_data_response', _ui_response(data, {'data': None, 'error': str(e)}))

# CORRECTLY PLACED STORAGE HANDLER
@socketio.on('request_storage_data')
def handle_request_storage_data(data=None):
    """Handles a request from the client to view all player storage."""
    debug("WEB_REQUEST: Received request for storage data from client", category="web_interface")
    try:
        from core.managers.storage_manager import get_storage_manager
        manager = get_storage_manager()
        # Calling view_storage() with no location_id gets ALL storage containers.
        storage_data = manager.view_storage()
        
        if storage_data.get("success"):
            emit('storage_data_response', _ui_response(data, {'data': storage_data}))
        else:
            emit('storage_data_response', _ui_response(data, {'data': {}, 'error': 'Failed to retrieve storage data.'}))
            
    except Exception as e:
        print(f"ERROR handling storage request: {e}")
        emit('storage_data_response', _ui_response(data, {'data': {}, 'error': 'An internal error occurred while fetching storage data.'}))

@socketio.on('user_exit')
def handle_user_exit():
    """Handle intentional user exit - log and clean up"""
    try:
        print("INFO: User has initiated exit from the game")
        from utils.capture.live_provider_call import (
            get_live_turn_scope,
            request_live_turn_supersession,
        )

        live_scope = get_live_turn_scope()
        if live_scope is not None:
            operation = request_live_turn_supersession("web_exit")
            emit('system_message', {
                'content': 'Exit accepted. The current turn is stopping safely.',
                'operation_id': operation['operation_id'],
            })
            live_scope.quiescent.wait()
        from utils.capture.live_provider_call import get_active_welcome_scope
        welcome_scope = get_active_welcome_scope()
        if welcome_scope is not None:
            # #214: player exit must not leave welcome work attached to the
            # exited player - supersede, then wait for the game-thread
            # discard handback (readline pump) to reach quiescence.
            welcome_scope.request_supersession("web_exit")
            emit('system_message', {
                'content': 'Exit accepted. The welcome-back narration is stopping safely.',
            })
            welcome_scope.quiescent.wait()
        emit('exit_acknowledged', {'message': 'Exit acknowledged'})
        # Note: We do NOT shut down the server here
        # Multiple users might be connected, and server shutdown is an admin function
        # The disconnect event will handle any necessary cleanup when the socket closes
    except Exception as e:
        print(f"ERROR handling user exit: {e}")

@socketio.on('get_model_provider')
def handle_get_provider():
    """Return current provider setting for UI sync on page load."""
    try:
        import model_config
        provider = model_config.get_provider()
        emit('provider_changed', {'provider': provider})
    except Exception as e:
        error(f"Error getting provider: {e}", exception=e, category="web_interface")
        emit('provider_changed', {'provider': 'legacy'})  # Safe fallback


@socketio.on('set_model_provider')
def handle_set_provider(data):
    """Handle provider selection from web UI settings dropdown."""
    try:
        import model_config
        provider = data.get('provider', 'legacy')
        model_config.set_provider(provider)
        model_config.persist_provider(provider)

        debug(f"Model provider set to: {provider}", category="web_interface")

        emit('provider_changed', {'provider': provider}, broadcast=True)

    except ValueError as e:
        error(f"Invalid provider: {e}", category="web_interface")
        emit('error', {'message': str(e)})
    except Exception as e:
        error(f"Error setting provider: {e}", exception=e, category="web_interface")
        emit('error', {'message': f"Failed to set provider: {str(e)}"})


@socketio.on('get_local_endpoint')
def handle_get_local_endpoint():
    """Report the Local/Custom endpoint for UI sync. Never returns the raw key."""
    try:
        import model_config
        ep = model_config.get_local_endpoint()
        emit('local_endpoint_changed', {
            'base_url': ep['base_url'],
            'model': ep['model'],
            'has_key': bool(ep['api_key']) and ep['api_key'] != 'not-needed',
        })
    except Exception as e:
        error(f"Error getting local endpoint: {e}", exception=e, category="web_interface")
        emit('local_endpoint_changed',
             {'base_url': 'http://localhost:1234/v1', 'model': '', 'has_key': False})


@socketio.on('set_local_endpoint')
def handle_set_local_endpoint(data):
    """Persist the Local/Custom endpoint. Applies live (openai_client reads it per call)."""
    try:
        import model_config
        data = data or {}
        # Blank api_key => keep the existing stored key (UI promises "leave blank
        # to keep" and the field auto-clears after save); a value sets it.
        raw_key = (data.get('api_key') or '').strip()
        model_config.persist_local_endpoint(
            base_url=data.get('base_url', ''),
            api_key=(raw_key if raw_key else None),
            model=data.get('model', ''))
        debug("Local endpoint updated via web UI", category="web_interface")
        ep = model_config.get_local_endpoint()
        emit('local_endpoint_changed', {
            'base_url': ep['base_url'],
            'model': ep['model'],
            'has_key': bool(ep['api_key']) and ep['api_key'] != 'not-needed',
        }, broadcast=True)
    except Exception as e:
        error(f"Error setting local endpoint: {e}", exception=e, category="web_interface")
        emit('error', {'message': "Failed to save local endpoint"})


@socketio.on('get_openai_key')
def handle_get_openai_key():
    """Report ONLY whether an OpenAI key is configured. Never sends the secret."""
    try:
        import model_config, config as _cfg
        stored = model_config.has_openai_key()
        live = bool(getattr(_cfg, "OPENAI_API_KEY", "")) and \
            getattr(_cfg, "OPENAI_API_KEY", "") != "your_openai_api_key_here"
        emit('openai_key_status', {'has_key': bool(stored or live)})
    except Exception as e:
        error(f"Error getting openai key status: {e}", exception=e, category="web_interface")
        emit('openai_key_status', {'has_key': False})


@socketio.on('set_openai_key')
def handle_set_openai_key(data):
    """Set the OpenAI key from the UI: update config live AND persist. No echo.

    Scope of the live update: writing config.OPENAI_API_KEY reaches every reader
    that reads it at call time (utils/openai_client.get_openai_client and the
    per-request toolkit generators). A few long-lived managers cache an OpenAI
    client in __init__ (e.g. campaign_manager, storage_processor); those keep the
    previous key until the next restart -- a pre-existing pattern, not specific to
    this feature. The PERSISTED key is applied at startup for ALL readers (see the
    boot-time apply_persisted_openai_key above), so a player who sets the key in
    Settings before starting a game -- the intended flow -- is fully covered.
    """
    try:
        import model_config, config as _cfg
        api_key = ((data or {}).get('api_key') or '').strip()
        if not api_key:
            # Blank submit: do NOT wipe an existing key (prevents accidental erase
            # from a double-click after the field auto-clears). Report status only.
            live = bool(getattr(_cfg, "OPENAI_API_KEY", "")) and \
                getattr(_cfg, "OPENAI_API_KEY", "") != "your_openai_api_key_here"
            emit('openai_key_status', {'has_key': model_config.has_openai_key() or live})
            return
        _cfg.OPENAI_API_KEY = api_key            # live: all config.OPENAI_API_KEY readers
        model_config.persist_openai_key(api_key) # survive restart
        debug("OpenAI API key updated via web UI", category="web_interface")
        emit('openai_key_status', {'has_key': model_config.has_openai_key()}, broadcast=True)
    except Exception as e:
        error(f"Error setting openai key: {e}", exception=e, category="web_interface")
        emit('error', {'message': "Failed to set OpenAI API key"})  # generic: no key leak

@socketio.on('get_gemini_key')
def handle_get_gemini_key():
    """Report ONLY whether a Gemini key is configured. Never sends the secret."""
    try:
        import model_config, config as _cfg
        stored = model_config.has_gemini_key()
        live = bool(getattr(_cfg, "GEMINI_API_KEY", "")) and \
            getattr(_cfg, "GEMINI_API_KEY", "") != "your_gemini_api_key_here"
        emit('gemini_key_status', {'has_key': bool(stored or live)})
    except Exception as e:
        error(f"Error getting gemini key status: {e}", exception=e, category="web_interface")
        emit('gemini_key_status', {'has_key': False})

@socketio.on('set_gemini_key')
def handle_set_gemini_key(data):
    """Set the Gemini key from the UI: update config live AND persist. No echo.

    The runtime Gemini client (utils/capture/gemini_caller._get_client) reads
    config.GEMINI_API_KEY lazily on first use and caches the client. So a key set
    in Settings BEFORE the first Gemini call -- the intended flow -- is fully
    covered. If a Gemini client was already created earlier this session, the new
    key applies after the next restart (the persisted key is re-applied at boot).
    Mirrors handle_set_openai_key.
    """
    try:
        import model_config, config as _cfg
        api_key = ((data or {}).get('api_key') or '').strip()
        if not api_key:
            # Blank submit: do NOT wipe an existing key. Report status only.
            live = bool(getattr(_cfg, "GEMINI_API_KEY", "")) and \
                getattr(_cfg, "GEMINI_API_KEY", "") != "your_gemini_api_key_here"
            emit('gemini_key_status', {'has_key': model_config.has_gemini_key() or live})
            return
        _cfg.GEMINI_API_KEY = api_key            # live: config.GEMINI_API_KEY readers
        model_config.persist_gemini_key(api_key) # survive restart
        debug("Gemini API key updated via web UI", category="web_interface")
        emit('gemini_key_status', {'has_key': model_config.has_gemini_key()}, broadcast=True)
    except Exception as e:
        error(f"Error setting gemini key: {e}", exception=e, category="web_interface")
        emit('error', {'message': "Failed to set Gemini API key"})  # generic: no key leak

@socketio.on('test_local_endpoint')
def handle_test_local_endpoint(data):
    """Isolated liveness probe for the Local/Custom endpoint. Tests POSTED values
    (not saved), cheapest-first (models.list, then a 1-token chat). Emits
    {ok, detail}. Never echoes the key. Does NOT use capture_and_fanout/the 67
    callsite paths.
    """
    data = data or {}
    base_url = (data.get('base_url') or '').strip()
    api_key = (data.get('api_key') or '').strip() or 'not-needed'
    model = (data.get('model') or '').strip()

    if not base_url:
        emit('local_endpoint_test_result', {'ok': False, 'detail': 'Base URL is required.'})
        return
    try:
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=10.0)
    except Exception as e:
        emit('local_endpoint_test_result', {'ok': False, 'detail': f'Could not create client: {e}'})
        return
    try:
        result = client.models.list()
        names = [m.id for m in (getattr(result, 'data', None) or [])]
        detail = (f'Connected. {len(names)} model(s) available.' if names
                  else 'Connected. Server responded (no models listed).')
        if model and names and model not in names:
            detail += f' Warning: "{model}" not in the model list.'
        emit('local_endpoint_test_result', {'ok': True, 'detail': detail})
        return
    except Exception as list_err:
        last = str(list_err)
        debug(f"test_local_endpoint: models.list failed: {last}", category="web_interface")
    if not model:
        emit('local_endpoint_test_result',
             {'ok': False, 'detail': f'Could not list models and no model set. Last error: {last}'})
        return
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK only."}],
        )
        emit('local_endpoint_test_result',
             {'ok': True, 'detail': f'Connected. Chat completion succeeded with "{model}".'})
    except Exception as chat_err:
        emit('local_endpoint_test_result', {'ok': False, 'detail': f'Connection failed: {chat_err}'})

@socketio.on('generate_image')
def handle_generate_image(data):
    """Handle image generation requests"""
    try:
        prompt = data.get('prompt', '')
        if not prompt:
            emit('image_generation_error', {'message': 'No prompt provided', 'request_id': data.get('request_id'), 'source_message_id': data.get('source_message_id')})
            return
        
        import config
        import requests
        from datetime import datetime
        from utils.file_operations import safe_read_json, safe_write_json
        
        # Initialize OpenAI client
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Try to generate image
        try:
            # Generate image using DALL-E 3
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                n=1,
            )
            # Get the image URL
            image_url = response.data[0].url
        except Exception as dalle_error:
            # Check if it's a content policy violation
            if "content_policy_violation" in str(dalle_error) or "400" in str(dalle_error):
                # Silently sanitize and retry
                from utils.prompt_sanitizer import sanitize_prompt
                sanitized_prompt = sanitize_prompt(prompt)
                
                # Retry with sanitized prompt
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=sanitized_prompt,
                    size="1024x1024",
                    n=1,
                )
                image_url = response.data[0].url
            else:
                # Re-raise if it's not a content policy issue
                raise dalle_error
        
        # Save the image locally with metadata
        try:
            # Get current module and game state
            party_data = safe_read_json("party_tracker.json")
            current_module = party_data.get("module", "unknown_module")
            world_conditions = party_data.get("worldConditions", {})
            
            # Get game time
            game_year = world_conditions.get("year", 0)
            game_month = world_conditions.get("month", "Unknown")
            game_day = world_conditions.get("day", 0)
            game_time = world_conditions.get("time", "00:00:00")
            location_id = world_conditions.get("currentLocationId", "unknown")
            location_name = world_conditions.get("currentLocation", "Unknown Location")
            
            # Create images directory for the module
            images_dir = os.path.join("modules", current_module, "images")
            os.makedirs(images_dir, exist_ok=True)
            
            # Generate filename with both timestamps
            real_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_timestamp = f"{game_year}_{game_month}_{game_day}_{game_time.replace(':', '')}"
            filename = f"img_{real_timestamp}_game_{game_timestamp}_{location_id}.png"
            filepath = os.path.join(images_dir, filename)
            
            # Download and save the image
            img_response = requests.get(image_url)
            if img_response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(img_response.content)
                print(f"Saved image to: {filepath}")
                
                # Save metadata
                metadata_file = os.path.join(images_dir, "image_metadata.json")
                metadata = safe_read_json(metadata_file) or {"images": []}
                
                metadata["images"].append({
                    "filename": filename,
                    "prompt": prompt,
                    "real_world_time": datetime.now().isoformat(),
                    "game_time": {
                        "year": game_year,
                        "month": game_month,
                        "day": game_day,
                        "time": game_time
                    },
                    "location": {
                        "id": location_id,
                        "name": location_name,
                        "area": world_conditions.get("currentArea", "Unknown Area"),
                        "area_id": world_conditions.get("currentAreaId", "unknown")
                    },
                    "module": current_module,
                    "original_url": image_url
                })
                
                safe_write_json(metadata_file, metadata)
                print(f"Updated image metadata in: {metadata_file}")
            
        except Exception as save_error:
            # Don't fail the whole operation if saving fails
            print(f"Warning: Failed to save image locally: {save_error}")
        
        # Emit the image URL back to the client
        emit('image_generated', {
            'image_url': image_url,
            'prompt': prompt,
            'request_id': data.get('request_id'),
            'source_message_id': data.get('source_message_id')
        })
        
    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        emit('image_generation_error', {
            'message': error_msg,
            'request_id': data.get('request_id') if isinstance(data, dict) else None,
            'source_message_id': data.get('source_message_id') if isinstance(data, dict) else None,
        })

# REMOVED - Duplicate handler was here (lines 2725-2940)
# The actual working implementation is in the second handle_generate_unified_assets function at line 4157

@app.route('/api/tts', methods=['POST'])
def generate_tts():
    """Generate text-to-speech audio using OpenAI TTS API"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        voice = data.get('voice', None)  # Get voice from request, or use default
        model = data.get('model', None)  # Get model from request (tts-1 or tts-1-hd)
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Limit text length to avoid excessive API costs
        if len(text) > 4096:
            text = text[:4096]
        
        import config
        from model_config import TTS_MODEL, TTS_VOICE, TTS_SPEED
        
        # Use provided voice or fall back to config default
        # Valid voices: alloy, echo, fable, onyx, nova, shimmer
        valid_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        if voice and voice in valid_voices:
            selected_voice = voice
        else:
            selected_voice = TTS_VOICE
        
        # Use provided model or fall back to config default
        valid_models = ['tts-1', 'tts-1-hd']
        if model and model in valid_models:
            selected_model = model
        else:
            selected_model = TTS_MODEL
        
        # Initialize OpenAI client
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Generate speech
        response = client.audio.speech.create(
            model=selected_model,
            voice=selected_voice,
            input=text,
            speed=TTS_SPEED
        )
        
        # Return audio as streaming response
        return Response(
            response.iter_bytes(),
            mimetype='audio/mpeg',
            headers={
                'Content-Type': 'audio/mpeg',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        error_msg = f"TTS generation failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        return jsonify({'error': error_msg}), 500

""" BEGIN COMMENTED OUT DUPLICATE CODE
                                bestiary_data = safe_read_json(bestiary_path) or {}
                                
                                # Ensure 'monsters' key exists (consistent with existing bestiary structure)
                                if 'monsters' not in bestiary_data:
                                    bestiary_data['monsters'] = {}
                                
                                # Save under the 'monsters' key to match how we read it
                                bestiary_data['monsters'][asset['id']] = {
                                    'name': asset['name'],
                                    'description': description
                                }
                                safe_write_json(bestiary_path, bestiary_data)
                                
                                completed += 1
                                percent = int((completed / total_assets) * 30)  # 30% for descriptions
                                emit('unified_generation_progress', {
                                    'percent': percent,
                                    'message': f"Generated description for {asset['name']}",
                                    'asset_id': asset['id'],
                                    'status': 'Description Generated'
                                })
                                
                                # Rate limiting
                                time.sleep(2)
                            except Exception as e:
                                error(f"TOOLKIT: Failed to generate description for {asset['name']}: {e}")
                    
                    # Generate NPC descriptions
                    if npcs_needing_descriptions:
                        context = extract_module_context_for_npcs(module_name)
                        
                        # Load NPC compendium
                        npc_compendium_path = 'data/bestiary/npc_compendium.json'
                        npc_compendium = safe_read_json(npc_compendium_path) or {}
                        
                        # Ensure proper structure
                        if 'npcs' not in npc_compendium:
                            npc_compendium['npcs'] = {}
                        
                        for i, asset in enumerate(npcs_needing_descriptions):
                            try:
                                info(f"TOOLKIT: Generating description for NPC: {asset['name']}")
                                # Use existing NPC description generation logic
                                prompt = f"Generate a 150-200 word visual description for {asset['name']} suitable for AI image generation."
                                # This would call the actual AI API
                                description = "Generated description placeholder"  # Replace with actual API call
                                
                                # Save to NPC compendium
                                npc_compendium['npcs'][asset['id']] = {
                                    'name': asset['name'],
                                    'description': description,
                                    'module': module_name,
                                    'generated_at': datetime.now().isoformat()
                                }
                                
                                completed += 1
                                percent = int((completed / total_assets) * 30)
                                emit('unified_generation_progress', {
                                    'percent': percent,
                                    'message': f"Generated description for {asset['name']}",
                                    'asset_id': asset['id'],
                                    'status': 'Description Generated'
                                })
                                
                                time.sleep(2)
                            except Exception as e:
                                error(f"TOOLKIT: Failed to generate NPC description for {asset['name']}: {e}")
                        
                        # Update metadata and save compendium
                        npc_compendium['total_npcs'] = len(npc_compendium.get('npcs', {}))
                        npc_compendium['last_updated'] = datetime.now().isoformat()
                        safe_write_json(npc_compendium_path, npc_compendium)
                
                # Phase 2: Generate images
                if generate_images:
                    emit('unified_generation_progress', {
                        'percent': 30,
                        'message': 'Phase 2: Generating images...'
                    })
                    
                    # Create directories for raw images
                    raw_images_dir = os.path.join('raw_images', 'modules', module_name)
                    os.makedirs(os.path.join(raw_images_dir, 'monsters'), exist_ok=True)
                    os.makedirs(os.path.join(raw_images_dir, 'npcs'), exist_ok=True)
                    
                    assets_needing_images = [a for a in assets if not a['has_image'] or overwrite]
                    
                    for i, asset in enumerate(assets_needing_images):
                        try:
                            if asset['type'] == 'monster':
                                info(f"TOOLKIT: Generating image for monster: {asset['name']}")
                                # generator = MonsterImageGenerator(style)  # This class doesn't exist
                                
                                # Get description from bestiary
                                bestiary_data = safe_read_json('data/bestiary/monster_compendium.json') or {}
                                description = bestiary_data.get(asset['id'], {}).get('description', '')
                                
                                if description:
                                    # Generate image (this would call DALL-E)
                                    # For now, placeholder
                                    image_path = f"raw_images/modules/{module_name}/monsters/{asset['id']}.jpg"
                                    thumb_path = f"modules/{module_name}/media/monsters/{asset['id']}_thumb.jpg"
                                    
                                    # Copy to module media folder
                                    module_media_dir = os.path.join('modules', module_name, 'media', 'monsters')
                                    os.makedirs(module_media_dir, exist_ok=True)
                                    
                                    # In real implementation, this would:
                                    # 1. Generate image with DALL-E
                                    # 2. Save raw to raw_images
                                    # 3. Create compressed version
                                    # 4. Create thumbnail
                                    # 5. Copy to module media folder
                                    
                                    completed += 1
                                    percent = 30 + int((completed / total_assets) * 70)
                                    emit('unified_generation_progress', {
                                        'percent': percent,
                                        'message': f"Generated image for {asset['name']}",
                                        'asset_id': asset['id'],
                                        'status': 'Image Generated'
                                    })
                                    
                                    time.sleep(3)  # Rate limiting for image generation
                            
                            elif asset['type'] == 'npc':
                                info(f"TOOLKIT: Generating portrait for NPC: {asset['name']}")
                                # generator = NPCImageGenerator(style)  # This is also a placeholder
                                
                                # Get description from NPC compendium first
                                description = ''
                                npc_compendium_path = 'data/bestiary/npc_compendium.json'
                                if os.path.exists(npc_compendium_path):
                                    npc_compendium = safe_read_json(npc_compendium_path) or {}
                                    npcs_dict = npc_compendium.get('npcs', {})
                                    if asset['id'] in npcs_dict:
                                        description = npcs_dict[asset['id']].get('description', '')
                                
                                # Fall back to temp file if not in compendium
                                if not description:
                                    desc_file = f'temp/npc_descriptions_{module_name}.json'
                                    descriptions = safe_read_json(desc_file) or {}
                                    desc_data = descriptions.get(asset['id'], {})
                                    if isinstance(desc_data, dict):
                                        description = desc_data.get('description', '')
                                    else:
                                        description = desc_data
                                
                                if description:
                                    # Generate portrait
                                    image_path = f"raw_images/modules/{module_name}/npcs/{asset['id']}.png"
                                    thumb_path = f"modules/{module_name}/media/npcs/{asset['id']}_thumb.jpg"
                                    
                                    # Copy to module media folder
                                    module_media_dir = os.path.join('modules', module_name, 'media', 'npcs')
                                    os.makedirs(module_media_dir, exist_ok=True)
                                    
                                    completed += 1
                                    percent = 30 + int((completed / total_assets) * 70)
                                    emit('unified_generation_progress', {
                                        'percent': percent,
                                        'message': f"Generated portrait for {asset['name']}",
                                        'asset_id': asset['id'],
                                        'status': 'Portrait Generated'
                                    })
                                    
                                    time.sleep(3)
                                    
                        except Exception as e:
                            error(f"TOOLKIT: Failed to generate image for {asset['name']}: {e}")
                            emit('unified_generation_progress', {
                                'percent': percent,
                                'message': f"Failed: {asset['name']} - {str(e)}",
                                'asset_id': asset['id'],
                                'status': 'Failed'
                            })
                
                # Complete
                emit('unified_generation_complete', {
                    'message': f'Successfully processed {completed} assets'
                })
                info(f"TOOLKIT: Unified generation complete for module {module_name}")
                
            except Exception as e:
                error(f"TOOLKIT: Unified generation failed: {e}")
                emit('unified_generation_error', {'error': str(e)})
        
        # Start generation in background thread
        thread = threading.Thread(target=generate_assets)
        thread.daemon = True
        thread.start()
        
END COMMENTED OUT DUPLICATE CODE """

def extract_module_context_for_monsters(module_name):
    """Extract context for monster description generation"""
    try:
        from utils.file_operations import safe_read_json
        import os
        
        context_parts = []
        
        # Read module plot
        plot_file = os.path.join('modules', module_name, 'module_plot.json')
        if os.path.exists(plot_file):
            plot_data = safe_read_json(plot_file)
            if plot_data:
                context_parts.append(f"Module: {module_name}")
                context_parts.append(f"Setting: {plot_data.get('setting', 'Fantasy world')}")
                context_parts.append(f"Theme: {plot_data.get('theme', 'Adventure')}")
        
        return "\n".join(context_parts)
        
    except Exception as e:
        error(f"Failed to extract monster context: {e}")
        return f"Module: {module_name}"

def run_game_loop():
    """Run the main game loop with enhanced error handling"""
    try:
        # Start the output sender thread
        output_thread = threading.Thread(target=send_output_to_clients, daemon=True)
        output_thread.start()
        
        # Run the main game
        from updates.save_game_manager import RestoreRequest
        handoff = dm_main.main_game_loop()
        if isinstance(handoff, RestoreRequest):
            previous_clean = _web_restore_state().get('can_resume') is not False
            _finish_web_restore(
                handoff.manager,
                _apply_web_restore(handoff.manager, handoff.save_folder, previous_clean),
            )
    except (BrokenPipeError, OSError) as e:
        # Handle broken pipe errors specifically
        try:
            print(f"Stream error detected: {e}")
        except Exception:
            pass  # If even this fails, continue silently
        
        try:
            # Attempt to reset streams
            sys.stdout = WebOutputCapture(debug_output_queue, original_stdout)
            sys.stderr = WebOutputCapture(debug_output_queue, original_stderr, is_error=True)
            sys.stdin = WebInput(user_input_queue)
            try:
                print("Stream recovery attempted")
            except Exception:
                pass
        except Exception:
            try:
                print("Stream recovery failed")
            except Exception:
                pass
        
        # Send a user-friendly message
        try:
            game_output_queue.put({
                'type': 'info',
                'content': 'Connection restored. You may continue playing.',
                'timestamp': datetime.now().isoformat()
            })
        except Exception:
            pass
    except Exception as e:
        # Handle other errors with more detail
        import traceback
        internal_error = f"Game error: {str(e)}"
        try:
            print(f"Game loop error: {internal_error}")
            print(f"Traceback: {traceback.format_exc()}")
        except Exception:
            pass
        
        try:
            game_output_queue.put({
                'type': 'error',
                'content': SAFE_ACTION_FAILURE_MESSAGE,
                'timestamp': datetime.now().isoformat()
            })
        except Exception:
            pass
    finally:
        try:
            # #214 r9 section 3: teardown supersedes + reaps a pending
            # background welcome (discard, never apply) before scope abort.
            dm_main.shutdown_welcome_lifecycle("engine_stop")
        except Exception:
            pass
        try:
            from utils.capture.live_provider_call import abort_live_turn_scope

            abort_live_turn_scope()
        except Exception:
            pass
        # Restore original streams safely
        try:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            sys.stdin = original_stdin
        except Exception:
            # If restoration fails, try to at least restore stdout
            try:
                sys.stdout = original_stdout
            except Exception:
                pass

def send_output_to_clients():
    """Send queued output to all connected clients"""
    global module_progress_queue
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"DEBUG: [Web Interface] [{timestamp}] send_output_to_clients thread started")
    last_token_update = time.time()
    
    while True:
        try:
            # Send game output
            _emit_pending_game_output(socketio.emit)
            
            # Send debug output
            while not debug_output_queue.empty():
                try:
                    msg = debug_output_queue.get()
                    socketio.emit('debug_output', msg)
                except Exception:
                    # If queue operation or emit fails, just continue
                    break
            
            # Send module progress updates
            if not module_progress_queue.empty():
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"DEBUG: [Web Interface] [{timestamp}] Module progress queue has items, processing...")
            while not module_progress_queue.empty():
                try:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    progress_data = module_progress_queue.get()
                    print(f"DEBUG: [Web Interface] [{timestamp}] Got progress data from queue: Stage {progress_data.get('stage')}")
                    _remember_ui_operation('module', progress_data)
                    socketio.emit('module_creation_progress', progress_data)
                    print(f"DEBUG: [Web Interface] [{timestamp}] Emitted module_creation_progress - Stage {progress_data.get('stage')}/{progress_data.get('total_stages')}")
                except Exception as e:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"DEBUG: [Web Interface] [{timestamp}] Failed to emit module progress: {e}")
                    import traceback
                    traceback.print_exc()
                    # If queue operation or emit fails, just continue
                    break
            
            # Try to send token updates every 2 seconds (completely isolated)
            current_time = time.time()
            if current_time - last_token_update > 2:
                last_token_update = current_time  # Update time FIRST to prevent retry loops
                try:
                    # Try to import and get stats
                    from utils.openai_usage_tracker import get_usage_stats
                    stats = get_usage_stats()
                    # Send to UI silently
                    socketio.emit('token_update', {
                        'tpm': stats.get('tpm', 0),
                        'rpm': stats.get('rpm', 0),
                        'total_tokens': stats.get('total_tokens', 0)
                    })
                except:
                    # If anything fails, just send zeros (but don't spam)
                    try:
                        socketio.emit('token_update', {
                            'tpm': 0,
                            'rpm': 0,
                            'total_tokens': 0
                        })
                    except:
                        pass  # Even sending zeros failed, just skip
                        
        except Exception:
            # If any other error occurs, just continue
            pass
        
        time.sleep(0.1)  # Small delay to prevent CPU spinning

def send_output_to_clients_original():
    """Send queued output to all connected clients"""
    last_token_update = time.time()
    
    while True:
        try:
            # Send game output
            while not game_output_queue.empty():
                try:
                    msg = game_output_queue.get()
                    socketio.emit('game_output', msg)
                except Exception:
                    # If queue operation or emit fails, just continue
                    break
            
            # Send debug output
            while not debug_output_queue.empty():
                try:
                    msg = debug_output_queue.get()
                    socketio.emit('debug_output', msg)
                except Exception:
                    # If queue operation or emit fails, just continue
                    break
            
            # Send token updates every 2 seconds
            current_time = time.time()
            if current_time - last_token_update > 2:
                try:
                    from utils.token_tracker import get_tracker
                    tracker = get_tracker()
                    stats = tracker.get_stats()
                    socketio.emit('token_update', {
                        'tpm': stats['tpm'],
                        'rpm': stats['rpm'],
                        'total_tokens': stats['total_tokens']
                    })
                except (ImportError, AttributeError, Exception):
                    # If token tracking fails for any reason, send zeros to UI
                    # Don't let token errors block the main output processing
                    try:
                        socketio.emit('token_update', {
                            'tpm': 0,
                            'rpm': 0,
                            'total_tokens': 0
                        })
                    except Exception:
                        # If even sending zeros fails, just skip token updates
                        pass
                finally:
                    # Always update the timestamp to prevent infinite retries
                    last_token_update = current_time
        except Exception:
            # If any other error occurs, just continue
            pass
        
        time.sleep(0.1)  # Small delay to prevent CPU spinning

def open_browser():
    """Open the web browser after a short delay"""
    time.sleep(1.5)  # Wait for server to start
    try:
        import config
        port = getattr(config, 'WEB_PORT', 8357)
    except ImportError:
        port = 8357
    start_path = os.environ.get('NEQ_START_PATH', '/')
    if start_path not in {'/', '/play/'}:
        start_path = '/'
    webbrowser.open(f'http://localhost:{port}{start_path}')


# ============================================================================
# NPC MANAGEMENT API ENDPOINTS
# ============================================================================

@app.route('/api/toolkit/modules/<module_name>/npcs')
def get_module_npcs(module_name):
    """
    Scans a module for NPCs and checks for portraits in the pack's npcs/ folder
    and optionally in the live game folder.
    """
    if not TOOLKIT_AVAILABLE:
        return jsonify([]), 503
    
    pack_name = request.args.get('pack')
    include_local = request.args.get('include_local', 'false').lower() == 'true'

    if not pack_name:
        return jsonify({'error': 'A target pack must be specified.'}), 400
        
    try:
        import os
        from utils.file_operations import safe_read_json
        
        npcs_found = {}
        
        # Always scan a module to get the list of required NPCs
        areas_dir = os.path.join('modules', module_name, 'areas')
        if os.path.exists(areas_dir):
            for filename in os.listdir(areas_dir):
                if filename.endswith('_BU.json'):
                    area_path = os.path.join(areas_dir, filename)
                    area_data = safe_read_json(area_path)
                    if area_data and 'locations' in area_data:
                        for location in area_data.get('locations', []):
                            if 'npcs' in location and location['npcs']:
                                for npc in location['npcs']:
                                    if isinstance(npc, dict) and 'name' in npc:
                                        npc_name = npc['name']
                                        npc_id = npc_name.lower().replace(' ', '_').replace("'", "").replace("-", "_")
                                        if npc_id not in npcs_found:
                                            npcs_found[npc_id] = {'name': npc_name, 'id': npc_id}
                                    elif isinstance(npc, str):
                                        npc_name = npc
                                        npc_id = npc_name.lower().replace(' ', '_').replace("'", "").replace("-", "_")
                                        if npc_id not in npcs_found:
                                            npcs_found[npc_id] = {'name': npc_name, 'id': npc_id}

        # Check portrait existence based on findings
        npc_list = []
        pack_npcs_dir = os.path.join('graphic_packs', pack_name, 'npcs')
        local_npcs_dir = os.path.join('web', 'static', 'media', 'npcs')  # Correct NPC location
        
        for npc_id, npc_info in npcs_found.items():
            result = {
                'name': npc_info['name'],
                'id': npc_id,
                'has_portrait': False,
                'is_local': False,
                'pack_name': pack_name,
            }

            # Check 1: In the pack's 'npcs' folder
            if os.path.exists(pack_npcs_dir):
                for ext in ['.png', '.jpg', '_thumb.png', '_thumb.jpg']:
                    if os.path.exists(os.path.join(pack_npcs_dir, f'{npc_id}{ext}')):
                        result['has_portrait'] = True
                        break

            # Check 2: In the live 'web/static/media/npcs' folder (if requested)
            if include_local:
                # Check for any NPC asset in the game folder
                if os.path.exists(local_npcs_dir):
                    for ext in ['.png', '.jpg', '_thumb.png', '_thumb.jpg', '_video.mp4']:
                        if os.path.exists(os.path.join(local_npcs_dir, f'{npc_id}{ext}')):
                            result['is_local'] = True
                            break

            npc_list.append(result)
        
        npc_list.sort(key=lambda x: x['name'])
        
        info(f"TOOLKIT: Found {len(npc_list)} NPCs for module '{module_name}' (Include Local: {include_local})")
        return jsonify(npc_list)
        
    except Exception as e:
        error(f"TOOLKIT: Failed to get NPCs for module {module_name}: {e}")
        return jsonify({'error': str(e)}), 500

def _run_npc_description_job(
    module_name,
    npcs,
    provider_snapshot,
    *,
    job_id=None,
    target_room=None,
    compendium_path,
    descriptions_file,
    request_delay=2,
):
    """Run T095 with per-item isolation and one terminal event on every path."""
    if not job_id:
        job_id = f"npc-description-{uuid4().hex}"
    total = len(npcs)
    completed = 0
    failures = []
    job_error = None

    try:
        if not _provider_credentials_available(provider_snapshot):
            raise RuntimeError(
                f"{provider_snapshot} provider credentials are not configured"
            )

        import config
        if provider_snapshot == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif provider_snapshot == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif provider_snapshot == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        elif provider_snapshot == "legacy":
            mini_cfg = config.MINI_UTIL_LEGACY
        else:
            raise ValueError(f"Unsupported model provider: {provider_snapshot}")
        module_context = extract_module_context_for_npcs(module_name)

        for index, npc_data in enumerate(npcs):
            npc_name = "Unknown NPC"
            try:
                if not isinstance(npc_data, dict):
                    raise ValueError("NPC request item must be an object")
                npc_name = npc_data.get("name")
                npc_id = npc_data.get("id")
                if not isinstance(npc_name, str) or not npc_name.strip():
                    raise ValueError("NPC request item has no usable name")
                if not isinstance(npc_id, str) or not npc_id.strip():
                    raise ValueError("NPC request item has no usable ID")

                prompt = f"""Generate a rich, descriptive prompt for an AI image generator to create a fantasy character portrait.

NPC Name: {npc_name}
Module Context: {module_context}

The output should be a single paragraph (150-200 words) that is itself a high-quality image prompt. It must include:
1.  **Physical Appearance:** Race, build, key features.
2.  **Clothing & Gear:** Detailed description of their armor, clothes, and weapons (sheathed or at rest).
3.  **Background/Setting:** A description of the environment (e.g., 'standing in a sun-dappled ancient forest', 'leaning against a table in a rustic tavern', 'in a dimly lit dungeon corridor').
4.  **Atmosphere & Lighting:** Keywords for the mood (e.g., 'cinematic lighting', 'magical aura', 'dust motes in the air', 'soft morning light').

The character must appear friendly, capable, and trustworthy, like a potential party ally. Do NOT use words like 'photorealistic', 'photo', 'cosplay', '3D render'. Focus on descriptive language for a digital painting.
Use only standard ASCII characters in the prompt -- no smart quotes, no em-dashes, no Unicode symbols.

Return only the image prompt as prose, without JSON, headings, or commentary.
"""

                response = capture_and_fanout(
                    "T095",
                    api_client.create_completion,
                    _request_provider=provider_snapshot,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert AI prompt engineer specializing in fantasy character art. Your task is to write image generation prompts, not narrative descriptions. The prompts you write will be used to create digital paintings.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    model=mini_cfg["model"],
                    temperature=0.8,
                    response_format=None,
                    **{k: v for k, v in mini_cfg.items() if k != "model"},
                )

                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(
                            response,
                            context={
                                'endpoint': 'web_validation',
                                'purpose': 'validate_web_response',
                                'interface': 'web',
                            },
                        )
                    except Exception:
                        pass

                description = validate_generated_prose(
                    sanitize_text(response.choices[0].message.content),
                    minimum_words=30,
                )
                generated_at = datetime.now().isoformat()
                entry = {
                    'name': npc_name.strip(),
                    'description': description,
                    'module': module_name,
                    'generated_at': generated_at,
                }
                legacy_entry = {
                    'name': npc_name.strip(),
                    'description': description,
                    'generated_at': generated_at,
                }
                merge_npc_description_pair(
                    compendium_path,
                    descriptions_file,
                    {npc_id: entry},
                    {npc_id: legacy_entry},
                )

                completed += 1
                info(
                    f"TOOLKIT: Generated description for {npc_name} "
                    f"({index + 1}/{total})"
                )
                _emit_job_event(
                    'npc_description_progress',
                    {
                        'current': index + 1,
                        'total': total,
                        'npc_name': npc_name,
                        'status': 'success',
                    },
                    job_id=job_id,
                    target_room=target_room,
                )
            except Exception as exc:
                failure = {'npc_name': npc_name, 'error': str(exc)}
                failures.append(failure)
                error(f"TOOLKIT: Failed to generate description for {npc_name}: {exc}")
                _emit_job_event(
                    'npc_description_progress',
                    {
                        'current': index + 1,
                        'total': total,
                        'npc_name': npc_name,
                        'status': 'error',
                        'error': str(exc),
                    },
                    job_id=job_id,
                    target_room=target_room,
                )

            if request_delay and index < total - 1:
                time.sleep(request_delay)

        info(f"TOOLKIT: Completed description generation for module {module_name}")
    except Exception as exc:
        job_error = str(exc)
        error(f"TOOLKIT: Description generation failed: {exc}")
    finally:
        success = job_error is None and not failures and completed == total
        terminal_payload = {
            'job_id': job_id,
            'success': success,
            'status': 'complete' if success else 'failed',
            'module_name': module_name,
            'provider': provider_snapshot,
            'completed': completed,
            'failed': total - completed,
            'total': total,
        }
        if job_error is not None:
            terminal_payload['error'] = job_error
        elif failures:
            terminal_payload['errors'] = failures
        _emit_job_event(
            'npc_description_complete',
            terminal_payload,
            job_id=job_id,
            target_room=target_room,
        )

    return terminal_payload


@app.route('/api/toolkit/npcs/fetch-descriptions', methods=['POST'])
def fetch_npc_descriptions():
    """Start a background T095 NPC description generation job."""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503

    data = request.json or {}
    module_name = data.get('module_name')
    npcs = data.get('npcs', [])
    if not module_name or not isinstance(npcs, list) or not npcs:
        return jsonify({'success': False, 'error': 'Missing module name or NPC list'}), 400

    from model_config import get_provider
    provider_snapshot = get_provider()
    job_id, target_room = _job_identity(data, 'npc-description')
    npc_snapshot = [dict(item) if isinstance(item, dict) else item for item in npcs]
    descriptions_file = f'temp/npc_descriptions_{module_name}.json'
    thread = threading.Thread(
        target=_run_npc_description_job,
        kwargs={
            'module_name': module_name,
            'npcs': npc_snapshot,
            'provider_snapshot': provider_snapshot,
            'job_id': job_id,
            'target_room': target_room,
            'compendium_path': NPC_COMPENDIUM_PATH,
            'descriptions_file': descriptions_file,
        },
        daemon=True,
    )
    thread.start()

    info(f"TOOLKIT: Started description generation for {len(npcs)} NPCs in {module_name}")
    return jsonify({
        'success': True,
        'job_id': job_id,
        'message': 'Description generation started.',
    })

def extract_module_context_for_npcs(module_name):
    """
    Extracts the FULL context from a module, including the entire plot file
    and all area files, to ensure maximum accuracy for NPC descriptions.
    """
    try:
        from utils.file_operations import safe_read_json
        import os
        import json
        
        context_parts = []
        
        # Header for the entire context block
        context_parts.append(f"--- START OF CONTEXT FOR MODULE: {module_name} ---")

        # 1. Read and append the entire module plot file
        plot_file = os.path.join('modules', module_name, 'module_plot.json')
        if os.path.exists(plot_file):
            plot_data = safe_read_json(plot_file)
            if plot_data:
                context_parts.append("\n--- MODULE PLOT FILE: module_plot.json ---")
                context_parts.append(json.dumps(plot_data, indent=2))
        
        # 2. Read and append EVERY area file (_BU.json version)
        areas_dir = os.path.join('modules', module_name, 'areas')
        if os.path.exists(areas_dir):
            area_files = sorted([f for f in os.listdir(areas_dir) if f.endswith('_BU.json')])
            for filename in area_files:
                area_path = os.path.join(areas_dir, filename)
                area_data = safe_read_json(area_path)
                if area_data:
                    context_parts.append(f"\n--- AREA FILE: {filename} ---")
                    context_parts.append(json.dumps(area_data, indent=2))
        
        context_parts.append(f"\n--- END OF CONTEXT FOR MODULE: {module_name} ---")
        
        # Join all parts into a single, massive string
        full_context = "\n".join(context_parts)
        info(f"TOOLKIT: Compiled full module context for '{module_name}', total length: {len(full_context)} characters.")
        return full_context

    except Exception as e:
        error(f"Failed to extract full module context: {e}")
        return f"Error building context for adventure module: {module_name}"

@app.route('/api/toolkit/npcs/description', methods=['GET', 'POST'])
def handle_npc_description():
    """
    Gets or sets a single NPC's description from the temporary JSON file.
    """
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503

    if request.method == 'GET':
        module_name = request.args.get('module')
        npc_id = request.args.get('npc_id')
        
        if not module_name or not npc_id:
            return jsonify({'error': 'Missing module or NPC ID'}), 400
        
        try:
            from utils.file_operations import safe_read_json
            
            # Check NPC compendium first
            npc_compendium_path = 'data/bestiary/npc_compendium.json'
            if os.path.exists(npc_compendium_path):
                npc_compendium = safe_read_json(npc_compendium_path) or {}
                npcs_dict = npc_compendium.get('npcs', {})
                if npc_id in npcs_dict:
                    return jsonify({'description': npcs_dict[npc_id].get('description', '')})
            
            # Fall back to temp file
            descriptions_file = f'temp/npc_descriptions_{module_name}.json'
            descriptions = safe_read_json(descriptions_file) or {}
            
            if npc_id in descriptions:
                desc_data = descriptions[npc_id]
                if isinstance(desc_data, dict):
                    return jsonify({'description': desc_data.get('description', '')})
                else:
                    return jsonify({'description': desc_data})
            
            return jsonify({'description': ''})
                
        except Exception as e:
            error(f"TOOLKIT: Failed to load NPC description: {e}")
            return jsonify({'error': str(e)}), 500
    
    if request.method == 'POST':
        data = request.json
        module_name = data.get('module_name')
        npc_id = data.get('npc_id')
        npc_name = data.get('npc_name')
        description = data.get('description')
        
        if not all([module_name, npc_id, description]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        try:
            from utils.encoding_utils import sanitize_text
            
            sanitized_description = sanitize_text(description)
            clean_name = npc_name or npc_id.replace('_', ' ').title()
            updated_at = datetime.now().isoformat()
            primary_entry = {
                'name': clean_name,
                'description': sanitized_description,
                'module': module_name,
                'updated_at': updated_at,
            }
            descriptions_file = f'temp/npc_descriptions_{module_name}.json'
            legacy_entry = {
                'name': clean_name,
                'description': sanitized_description,
                'updated_at': updated_at,
            }
            merge_npc_description_pair(
                NPC_COMPENDIUM_PATH,
                descriptions_file,
                {npc_id: primary_entry},
                {npc_id: legacy_entry},
            )
            
            info(f"TOOLKIT: Description for NPC '{clean_name}' (ID: {npc_id}) was updated")
            return jsonify({'success': True})
            
        except Exception as e:
            error(f"TOOLKIT: Failed to save NPC description: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toolkit/npcs/generate-portraits', methods=['POST'])
def generate_npc_portraits():
    """Generate portrait images for selected NPCs using NPCGenerator"""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503
    
    data = request.json
    module_name = data.get('module_name')
    pack_name = data.get('pack_name')
    model = data.get('model', 'dall-e-3')
    style = data.get('style', 'photorealistic')
    style_prompt = data.get('style_prompt', '')
    npcs = data.get('npcs', [])
    
    if not all([module_name, pack_name, npcs]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Start background thread for portrait generation
    def generate_portraits():
        try:
            from core.toolkit.npc_generator import NPCGenerator
            from utils.file_operations import safe_read_json
            import asyncio
            
            # Get API key
            try:
                from config import OPENAI_API_KEY
            except ImportError:
                OPENAI_API_KEY = None
                error("TOOLKIT: OpenAI API key not found")
                return
            
            if not OPENAI_API_KEY:
                error("TOOLKIT: OpenAI API key not configured")
                return
                
            # Initialize NPC generator
            generator = NPCGenerator(api_key=OPENAI_API_KEY)
            
            # Load descriptions from NPC compendium first
            npc_compendium_path = 'data/bestiary/npc_compendium.json'
            npc_compendium = safe_read_json(npc_compendium_path) or {}
            npcs_dict = npc_compendium.get('npcs', {})
            
            # Also load temp file for backward compatibility
            descriptions_file = f'temp/npc_descriptions_{module_name}.json'
            temp_descriptions = safe_read_json(descriptions_file) or {}
            
            # Prepare NPC data with descriptions
            npcs_with_descriptions = []
            for npc_data in npcs:
                npc_id = npc_data['id']
                npc_name = npc_data['name']
                
                # Get description from compendium first, then temp file
                description = ''
                if npc_id in npcs_dict:
                    description = npcs_dict[npc_id].get('description', '')
                
                if not description and npc_id in temp_descriptions:
                    npc_desc_data = temp_descriptions[npc_id]
                    if isinstance(npc_desc_data, dict):
                        description = npc_desc_data.get('description', '')
                    else:
                        description = npc_desc_data
                
                if not description:
                    description = f'A fantasy NPC named {npc_name}'
                
                npcs_with_descriptions.append({
                    'id': npc_id,
                    'name': npc_name,
                    'description': description
                })
            
            # Create progress callback
            def progress_callback(progress_data):
                socketio.emit('npc_portrait_progress', progress_data)
            
            # Run the async batch generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                generator.batch_generate_portraits(
                    npcs=npcs_with_descriptions,
                    pack_name=pack_name,
                    style=style,
                    model=model,
                    progress_callback=progress_callback
                )
            )
            
            # Update pack manifest to include NPC count
            update_pack_manifest_with_npcs(pack_name)
            
            # Log results
            info(f"TOOLKIT: Completed portrait generation - {len(result['successful'])} successful, {len(result['failed'])} failed")
            
            # Emit completion with detailed results
            socketio.emit('npc_generation_complete', {
                'module_name': module_name,
                'pack_name': pack_name,
                'successful': result.get('successful', []),
                'failed': result.get('failed', []),
                'total': len(result.get('successful', [])) + len(result.get('failed', []))
            })
            
        except Exception as e:
            error(f"TOOLKIT: Portrait generation failed: {e}")
    
    # Start background thread
    thread = threading.Thread(target=generate_portraits)
    thread.daemon = True
    thread.start()
    
    info(f"TOOLKIT: Started portrait generation for {len(npcs)} NPCs")
    return jsonify({'success': True, 'message': 'Portrait generation started.'})

def update_pack_manifest_with_npcs(pack_name):
    """Update pack manifest to include NPC information"""
    try:
        from utils.file_operations import safe_read_json, safe_write_json
        import os
        
        manifest_path = os.path.join('graphic_packs', pack_name, 'manifest.json')
        manifest = safe_read_json(manifest_path) or {}
        
        # Count NPCs
        npcs_dir = os.path.join('graphic_packs', pack_name, 'npcs')
        npc_count = 0
        npc_list = []
        
        if os.path.exists(npcs_dir):
            for filename in os.listdir(npcs_dir):
                if filename.endswith('.png') and not filename.endswith('_thumb.png'):
                    npc_id = filename[:-4]  # Remove .png
                    npc_list.append(npc_id)
                    npc_count += 1
        
        # Update manifest
        manifest['total_npcs'] = npc_count
        manifest['npcs_included'] = sorted(npc_list)
        manifest['last_modified'] = datetime.now().strftime("%Y-%m-%d")
        
        safe_write_json(manifest_path, manifest)
        info(f"TOOLKIT: Updated manifest for pack '{pack_name}' with {npc_count} NPCs")
        
    except Exception as e:
        error(f"TOOLKIT: Failed to update pack manifest: {e}")

def create_live_assets_backup_pack():
    """
    Creates a backup pack from the current live game assets.
    This preserves ALL assets currently in use, regardless of their source.
    """
    try:
        import os
        import shutil
        from datetime import datetime
        import json
        
        # Generate backup pack name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"live_backup_{timestamp}"
        backup_dir = os.path.join('graphic_packs', backup_name)
        
        # Create the backup pack directory
        os.makedirs(backup_dir, exist_ok=True)
        
        # Define source and destination paths
        live_monsters_dir = os.path.join('web', 'static', 'media', 'monsters')
        live_npcs_dir = os.path.join('web', 'static', 'media', 'npcs')
        backup_monsters_dir = os.path.join(backup_dir, 'monsters')
        backup_npcs_dir = os.path.join(backup_dir, 'npcs')
        
        copied_monsters = 0
        copied_npcs = 0
        
        # Copy monster assets if they exist
        if os.path.exists(live_monsters_dir) and os.listdir(live_monsters_dir):
            os.makedirs(backup_monsters_dir, exist_ok=True)
            for filename in os.listdir(live_monsters_dir):
                src_path = os.path.join(live_monsters_dir, filename)
                dest_path = os.path.join(backup_monsters_dir, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dest_path)
                    copied_monsters += 1
        
        # Copy NPC assets if they exist
        if os.path.exists(live_npcs_dir) and os.listdir(live_npcs_dir):
            os.makedirs(backup_npcs_dir, exist_ok=True)
            for filename in os.listdir(live_npcs_dir):
                src_path = os.path.join(live_npcs_dir, filename)
                dest_path = os.path.join(backup_npcs_dir, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dest_path)
                    copied_npcs += 1
        
        # Create manifest for the backup pack
        manifest = {
            "name": backup_name,
            "display_name": f"Live Assets Backup ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            "description": f"Automatic backup of all live game assets. Contains {copied_monsters} monster files and {copied_npcs} NPC files.",
            "is_backup": True,
            "backup_type": "live_assets",
            "backup_date": datetime.now().isoformat(),
            "monster_count": copied_monsters,
            "npc_count": copied_npcs,
            "created_by": "System"
        }
        
        manifest_path = os.path.join(backup_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        info(f"TOOLKIT: Created live assets backup pack '{backup_name}' with {copied_monsters} monsters and {copied_npcs} NPCs")
        
        return {
            "success": True,
            "backup_name": backup_name,
            "monsters": copied_monsters,
            "npcs": copied_npcs
        }
        
    except Exception as e:
        error(f"TOOLKIT: Failed to create live assets backup: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def copy_pack_monsters_to_game(pack_name):
    """
    Replaces live monster assets with assets from the specified pack.
    Note: Backup should be done at pack level before calling this.
    """
    try:
        import os
        import shutil

        # Define source and destination paths
        source_dir = os.path.join('graphic_packs', pack_name, 'monsters')
        live_dir = os.path.join('web', 'static', 'media', 'monsters')

        if not os.path.exists(source_dir):
            info(f"TOOLKIT: Pack '{pack_name}' has no 'monsters' folder. Skipping monster asset copy.")
            return

        # Clear existing live directory
        if os.path.exists(live_dir):
            shutil.rmtree(live_dir)
        
        # Create fresh live directory
        os.makedirs(live_dir, exist_ok=True)

        # 3. Copy all files from the pack's monster folder to the live folder
        copied_count = 0
        for filename in os.listdir(source_dir):
            src_path = os.path.join(source_dir, filename)
            dest_path = os.path.join(live_dir, filename)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dest_path)
                copied_count += 1
        
        info(f"TOOLKIT: Copied {copied_count} monster files from pack '{pack_name}' to live game folder.")

    except Exception as e:
        error(f"TOOLKIT: Failed to copy monster assets to game folder: {e}")

def copy_pack_npcs_to_game(pack_name):
    """
    Replaces live NPC assets with assets from the specified pack.
    Note: Backup should be done at pack level before calling this.
    """
    try:
        import os
        import shutil
        
        pack_npcs_dir = os.path.join('graphic_packs', pack_name, 'npcs')
        game_npcs_dir = os.path.join('web', 'static', 'media', 'npcs')
        
        if not os.path.exists(pack_npcs_dir):
            info(f"TOOLKIT: Pack '{pack_name}' has no NPCs folder")
            return
        
        # Clear existing live directory
        if os.path.exists(game_npcs_dir):
            shutil.rmtree(game_npcs_dir)
        
        # Create fresh live directory
        os.makedirs(game_npcs_dir, exist_ok=True)
        
        # Copy all NPC files to game folder
        copied_count = 0
        for filename in os.listdir(pack_npcs_dir):
            src_path = os.path.join(pack_npcs_dir, filename)
            dest_path = os.path.join(game_npcs_dir, filename)
            
            # Convert PNG thumbnails to JPG for game use
            if filename.endswith('_thumb.png'):
                from PIL import Image
                img = Image.open(src_path)
                if img.mode == 'RGBA':
                    # Convert RGBA to RGB for JPG
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                    img = rgb_img
                jpg_filename = filename[:-4] + '.jpg'  # Replace .png with .jpg
                jpg_path = os.path.join(game_npcs_dir, jpg_filename)
                img.save(jpg_path, 'JPEG', quality=85)
                info(f"TOOLKIT: Converted {filename} to {jpg_filename}")
            else:
                # Copy other files as-is
                shutil.copy2(src_path, dest_path)
                copied_count += 1
        
        info(f"TOOLKIT: Copied {copied_count} NPC files from pack '{pack_name}' to game folder")
        
    except Exception as e:
        error(f"TOOLKIT: Failed to copy NPCs to game folder: {e}")

@app.route('/api/toolkit/packs/<pack_name>/npcs/<npc_id>/thumbnail')
def get_npc_thumbnail(pack_name, npc_id):
    """Serve NPC thumbnail image from a specific graphic pack."""
    if not TOOLKIT_AVAILABLE:
        return '', 404
    
    try:
        from flask import send_from_directory
        import os
        
        npcs_dir = os.path.abspath(os.path.join('graphic_packs', pack_name, 'npcs'))
        
        # Try to find a thumbnail first (png or jpg)
        for ext in ['.png', '.jpg']:
            thumb_filename = f'{npc_id}_thumb{ext}'
            thumb_path = os.path.join(npcs_dir, thumb_filename)
            if os.path.exists(thumb_path):
                info(f"TOOLKIT: Serving NPC thumbnail {thumb_filename} from {pack_name}")
                return send_from_directory(npcs_dir, thumb_filename)
        
        # If no thumbnail, try to find the full portrait
        for ext in ['.png', '.jpg']:
            portrait_filename = f'{npc_id}{ext}'
            portrait_path = os.path.join(npcs_dir, portrait_filename)
            if os.path.exists(portrait_path):
                info(f"TOOLKIT: Serving NPC portrait {portrait_filename} from {pack_name}")
                return send_from_directory(npcs_dir, portrait_filename)
        
        # If nothing is found, return a 404
        warning(f"TOOLKIT: No image found for NPC {npc_id} in {pack_name}")
        return '', 404
        
    except Exception as e:
        error(f"TOOLKIT: Failed to serve NPC thumbnail for {npc_id} in {pack_name}: {e}")
        return '', 500

@app.route('/api/toolkit/packs/<pack_name>/npcs/<npc_id>/image')
def get_npc_image(pack_name, npc_id):
    """Serve full NPC image from a specific graphic pack."""
    if not TOOLKIT_AVAILABLE:
        return '', 404
    
    try:
        from flask import send_from_directory
        import os
        
        npcs_dir = os.path.abspath(os.path.join('graphic_packs', pack_name, 'npcs'))
        
        # Try to find the full image (png or jpg)
        for ext in ['.png', '.jpg']:
            image_filename = f'{npc_id}{ext}'
            image_path = os.path.join(npcs_dir, image_filename)
            if os.path.exists(image_path):
                info(f"TOOLKIT: Serving NPC image {image_filename} from {pack_name}")
                return send_from_directory(npcs_dir, image_filename)
        
        warning(f"TOOLKIT: No full image found for NPC {npc_id} in {pack_name}")
        return '', 404
        
    except Exception as e:
        error(f"TOOLKIT: Failed to serve NPC image for {npc_id} in {pack_name}: {e}")
        return '', 500

@app.route('/api/toolkit/packs/<pack_name>/npcs/<npc_id>/video')
def get_npc_video(pack_name, npc_id):
    """Serve NPC video from a specific graphic pack."""
    if not TOOLKIT_AVAILABLE:
        return '', 404
    
    try:
        from flask import send_from_directory
        import os
        
        npcs_dir = os.path.abspath(os.path.join('graphic_packs', pack_name, 'npcs'))
        
        # Try to find video files with different naming patterns
        video_patterns = [
            f'{npc_id}_video.mp4',
            f'{npc_id}_video_low.mp4',
            f'{npc_id}.mp4'
        ]
        
        for video_filename in video_patterns:
            video_path = os.path.join(npcs_dir, video_filename)
            if os.path.exists(video_path):
                info(f"TOOLKIT: Serving NPC video {video_filename} from {pack_name}")
                return send_from_directory(npcs_dir, video_filename)
        
        warning(f"TOOLKIT: No video found for NPC {npc_id} in {pack_name}")
        return '', 404
        
    except Exception as e:
        error(f"TOOLKIT: Failed to serve NPC video for {npc_id} in {pack_name}: {e}")
        return '', 500

@app.route('/api/toolkit/npcs/export-to-pack', methods=['POST'])
def export_npcs_to_pack():
    """Copies selected NPC portraits from the live game folder to a specified pack."""
    if not TOOLKIT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Toolkit not available'}), 503
        
    try:
        import os
        import shutil
        
        data = request.json
        pack_name = data.get('pack_name')
        npc_ids = data.get('npc_ids', [])

        if not pack_name or not npc_ids:
            return jsonify({'success': False, 'error': 'Missing pack name or NPC IDs.'}), 400

        source_dir = os.path.join('web', 'static', 'media', 'npcs')  # Correct NPC location
        dest_dir = os.path.join('graphic_packs', pack_name, 'npcs')
        os.makedirs(dest_dir, exist_ok=True)

        exported_count = 0
        skipped_count = 0

        for npc_id in npc_ids:
            exported = False
            # Try to export any NPC asset found (image, thumbnail, or video)
            for ext in ['.png', '.jpg', '_thumb.png', '_thumb.jpg', '_video.mp4']:
                source_file = os.path.join(source_dir, f"{npc_id}{ext}")
                if os.path.exists(source_file):
                    dest_file = os.path.join(dest_dir, f"{npc_id}{ext}")
                    shutil.copy2(source_file, dest_file)
                    if not exported:  # Count once per NPC, not per file
                        exported_count += 1
                        exported = True
                    info(f"TOOLKIT: Exported NPC asset '{npc_id}{ext}' to pack '{pack_name}'")
            
            if not exported:
                skipped_count += 1
                warning(f"TOOLKIT: Could not find any assets for '{npc_id}' in local game files to export.")

        # After exporting, update the destination pack's manifest
        update_pack_manifest_with_npcs(pack_name)

        info(f"TOOLKIT: Export complete - {exported_count} portraits exported, {skipped_count} skipped")
        return jsonify({
            'success': True,
            'message': f"Exported {exported_count} NPC portraits to '{pack_name}'.",
            'exported_count': exported_count,
            'skipped_count': skipped_count
        })

    except Exception as e:
        error(f"TOOLKIT: Failed to export NPCs to pack: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# REACT PLAYER FRONTEND (P4 standalone) - serves web/frontend/dist at /play
# Added after all existing routes; does not modify any existing route.
# ============================================================================

@app.route('/play')
@app.route('/play/')
@app.route('/play/<path:filename>')
def serve_react_play(filename='index.html'):
    """Serve the built React player app (web/frontend/dist).

    The app is built with Vite base '/play/', so its hashed assets resolve to
    /play/assets/... and are served by this same route. Unknown paths fall
    back to index.html (SPA behavior). Requires `npm run build` in
    web/frontend first; returns a plain 503 hint if dist/ is missing.
    """
    from flask import send_from_directory
    from werkzeug.utils import safe_join
    import os
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')
    if not os.path.isfile(os.path.join(dist_dir, 'index.html')):
        return ("React frontend not built. Run 'npm run build' in web/frontend.", 503)
    requested_path = safe_join(dist_dir, filename)
    if requested_path is None or not os.path.isfile(requested_path):
        filename = 'index.html'
    response = send_from_directory(dist_dir, filename)
    if filename == 'index.html':
        version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'VERSION')
        try:
            with open(version_path, 'r', encoding='utf-8') as version_file:
                version = version_file.read().strip()
        except OSError:
            version = '0.3.2'
        # send_from_directory streams files in direct-passthrough mode.  The
        # index is tiny; materialize it so the server can inject the local
        # version before returning the React shell.
        response.direct_passthrough = False
        response.set_data(response.get_data(as_text=True).replace('__NEQ_VERSION__', version))
    return response


# ============================================================================
# MODULE BUILDER SOCKET HANDLERS
# ============================================================================

# In-memory state for the build process to handle cancellation
build_process_thread = None
cancel_build_flag = threading.Event()

@socketio.on('request_module_list')
def handle_request_module_list():
    """Scans for modules using the ModuleStitcher and returns a detailed list."""
    try:
        # This function provides all the necessary details: level, areas, locations, etc.
        from core.generators.module_stitcher import list_available_modules
        
        detailed_modules = list_available_modules()
        info(f"MODULE_BUILDER: Found {len(detailed_modules)} modules to display.")
        
        # The frontend is already set up to handle this detailed data structure.
        emit('module_list_response', detailed_modules)
        
    except Exception as e:
        error(f"Error fetching detailed module list: {e}")
        emit('module_list_response', [])  # Send an empty list on error

def simulate_build_process(params):
    """Run the toolkit build through the hidden managed lifecycle."""
    global cancel_build_flag
    cancel_build_flag.clear()

    try:
        from core.ai.module_creation_contract import normalize_user_module_name
        from core.generators.module_builder import (
            ModuleCreationCancelledError,
            ModuleCreationFailedError,
            ai_driven_module_creation,
        )

        module_name = params.get('module_name', 'New_Module')
        narrative = params.get('narrative', 'A classic fantasy adventure')
        num_areas = params.get('num_areas', 5)
        locations_per_area = params.get('locations_per_area', 3)
        per_area_locations = params.get('per_area_locations')
        # Accept apostrophes, hyphens and the like rather than rejecting the
        # build outright (issue #131).
        module_name = normalize_user_module_name(module_name) or 'New_Module'

        def progress_callback(payload):
            if cancel_build_flag.is_set():
                raise ModuleCreationCancelledError("Module generation cancelled")
            socketio.emit('module_progress', dict(payload))
            return True

        creation_params = {
            'narrative': narrative,
            'module_name': module_name,
            'num_areas': num_areas,
            'locations_per_area': locations_per_area,
        }
        if per_area_locations is not None:
            creation_params['per_area_locations'] = per_area_locations
        success, created_name = ai_driven_module_creation(
            creation_params,
            progress_callback=progress_callback,
            policy="toolkit",
        )
        if not success or not created_name:
            raise RuntimeError("Module generation failed")
        socketio.emit(
            'module_complete',
            {
                'module_name': created_name,
                'message': f'Module "{created_name}" successfully generated.',
            },
        )
    except ModuleCreationCancelledError:
        info("Module build cancelled by operator.")
        socketio.emit(
            'module_error',
            {'error': 'Module generation cancelled.', 'cancelled': True},
        )
    except Exception as e:
        # str(e) now carries the actual reason instead of a generic string
        # (issue #130), so the operator can see what to fix.
        error(f"Module build failed: {e}")
        import traceback
        error(f"Full traceback: {traceback.format_exc()}")
        socketio.emit('module_error', {'error': str(e)})


@socketio.on('start_build')
def handle_start_build(data):
    """Starts the module build process in a background thread."""
    global build_process_thread
    if build_process_thread and build_process_thread.is_alive():
        emit('module_error', {'error': 'A build is already in progress.'})
        return

    info(f"Starting build for module: {data.get('module_name')}")
    emit('build_started', {'message': 'Build process initiated...'})
    
    build_process_thread = threading.Thread(target=simulate_build_process, args=(data,))
    build_process_thread.start()

@socketio.on('cancel_build')
def handle_cancel_build():
    """Sets a flag to cancel the ongoing build process."""
    global cancel_build_flag
    if build_process_thread and build_process_thread.is_alive():
        info("Cancellation request received for module build.")
        cancel_build_flag.set()
    else:
        emit('module_error', {'error': 'No active build to cancel.'})

@socketio.on('generate_unified_assets')
def handle_generate_unified_assets(data):
    """Generate missing descriptions and images for module assets"""
    module_name = data.get('module_name')
    assets = data.get('assets', [])
    options = data.get('options', {})
    
    # Debug logging
    info(f"TOOLKIT: Received generation request for module: {module_name}")
    info(f"TOOLKIT: Assets count: {len(assets)}")
    info(f"TOOLKIT: Options received: {options}")
    info(f"TOOLKIT: Overwrite setting: {options.get('overwrite', False)}")
    info(f"TOOLKIT: Generate images: {options.get('generate_images', True)}")
    info(f"TOOLKIT: Generate descriptions: {options.get('generate_descriptions', True)}")
    
    def generate_assets():
        try:
            info(f"TOOLKIT: generate_assets() thread started")
            socketio.emit('unified_generation_progress', {
                'percent': 0,
                'message': 'Thread started, initializing generators...'
            })
            
            import asyncio
            from utils.bestiary_updater import BestiaryUpdater
            from core.toolkit.npc_generator import NPCGenerator
            from core.toolkit.monster_generator import MonsterGenerator
            from pathlib import Path
            import time
            import json
            from utils.file_operations import safe_read_json, safe_write_json
            
            info(f"TOOLKIT: Imports completed, processing {len(assets)} assets")
            
            total_assets = len(assets)
            completed = 0
            
            # Initialize generators
            bestiary_updater = BestiaryUpdater()
            npc_generator = NPCGenerator()
            
            # Extract module context once for all descriptions
            module_context = bestiary_updater.extract_all_area_context(module_name)
            
            # Phase 1: Generate descriptions for assets without them (or all if overwrite)
            overwrite = options.get('overwrite', False)
            if overwrite and options.get('generate_descriptions', True):
                # If overwrite is enabled, generate for all assets
                description_targets = assets
            else:
                # Otherwise only generate for assets without descriptions
                description_targets = [a for a in assets if not a.get('has_description')]
            
            if description_targets:
                socketio.emit('unified_generation_progress', {
                    'percent': 0,
                    'message': f"Generating descriptions for {len(description_targets)} assets..."
                })
                
                # Separate monsters and NPCs
                monsters_to_describe = [a for a in description_targets if a['type'] == 'monster']
                npcs_to_describe = [a for a in description_targets if a['type'] == 'npc']
                
                # Generate monster descriptions
                if monsters_to_describe:
                    async def generate_monster_descriptions():
                        nonlocal completed
                        for asset in monsters_to_describe:
                            try:
                                description_found = False
                                description_text = ""
                                monster_data = None
                                bestiary_entry = {}
                                
                                # First check if description exists in bestiary
                                bestiary_path = MONSTER_COMPENDIUM_PATH
                                if os.path.exists(bestiary_path):
                                    bestiary_data = safe_read_json(bestiary_path) or {}
                                    monsters_dict = bestiary_data.get('monsters', {})
                                    if asset['id'] in monsters_dict:
                                        monster_entry = monsters_dict[asset['id']]
                                        if isinstance(monster_entry, dict):
                                            bestiary_entry.update(monster_entry)
                                        if monster_entry.get('description'):
                                            description_found = True
                                            description_text = monster_entry['description']
                                            info(f"Using existing description from bestiary for {asset['name']}")
                                
                                # If not in bestiary, generate new description
                                if not description_found:
                                    monster_data = await bestiary_updater.generate_monster_description(
                                        asset['name'], 
                                        module_context
                                    )
                                    if monster_data:
                                        description_text = monster_data.get('description', '')
                                        info(f"Generated new description for {asset['name']}")
                                
                                # Save to module's monster file AND bestiary
                                if description_text:
                                    # Save to module file
                                    monster_file = Path(f"modules/{module_name}/monsters/{asset['id']}.json")
                                    if monster_file.exists():
                                        existing_data = safe_read_json(str(monster_file))
                                        if existing_data:
                                            existing_data['description'] = description_text
                                            safe_write_json(str(monster_file), existing_data)
                                    
                                    # Also save transactionally so concurrent jobs
                                    # cannot replace the complete compendium document.
                                    bestiary_path = MONSTER_COMPENDIUM_PATH
                                    if isinstance(monster_data, dict):
                                        bestiary_entry.update(monster_data)
                                    bestiary_entry.update({
                                        'name': asset['name'],
                                        'description': description_text,
                                    })
                                    merge_compendium_entries(
                                        bestiary_path,
                                        'monsters',
                                        {asset['id']: bestiary_entry},
                                        overwrite=True,
                                    )
                                    info(f"Saved {asset['name']} description to both module and bestiary")
                                    
                                    completed += 1
                                    progress = int((completed / total_assets) * 100)
                                    socketio.emit('unified_generation_progress', {
                                        'percent': progress,
                                        'message': f"Generated description for {asset['name']}...",
                                        'asset_id': asset.get('id'),
                                        'asset_name': asset.get('name'),
                                        'status': 'Description Generated'
                                    })
                            except Exception as e:
                                error(f"Failed to generate description for {asset['name']}: {e}")
                                completed += 1
                    
                    # Run async function
                    asyncio.run(generate_monster_descriptions())
                
                # Generate NPC descriptions
                if npcs_to_describe:
                    async def generate_npc_descriptions():
                        nonlocal completed
                        for asset in npcs_to_describe:
                            try:
                                description_found = False
                                description_text = ""
                                existing_npc_entry = {}

                                # First check if description exists in NPC compendium
                                npc_compendium_path = 'data/bestiary/npc_compendium.json'
                                if os.path.exists(npc_compendium_path):
                                    compendium_data = safe_read_json(npc_compendium_path) or {}
                                    npcs_dict = compendium_data.get('npcs', {})
                                    if asset['id'] in npcs_dict:
                                        npc_entry = npcs_dict[asset['id']]
                                        if isinstance(npc_entry, dict):
                                            existing_npc_entry.update(npc_entry)
                                        if npc_entry.get('description'):
                                            description_found = True
                                            description_text = npc_entry['description']
                                            info(f"Using existing description from compendium for {asset['name']}")

                                # If not in compendium, check area files
                                if not description_found:
                                    areas_dir = Path(f"modules/{module_name}/areas")
                                    if areas_dir.exists():
                                        for area_file in areas_dir.glob("*.json"):
                                            if area_file.stem.endswith('_BU'):
                                                continue
                                            area_data = safe_read_json(str(area_file))
                                            if area_data and 'locations' in area_data:
                                                for location in area_data['locations']:
                                                    if 'npcs' in location:
                                                        for npc in location['npcs']:
                                                            if isinstance(npc, dict):
                                                                npc_name = npc.get('name', '')
                                                                npc_id = npc_name.lower().replace(' ', '_').replace("'", "")
                                                                if npc_id == asset['id']:
                                                                    description_text = npc.get('description', '')
                                                                    if description_text:
                                                                        description_found = True
                                                                        info(f"Using existing description from area file for {asset['name']}")
                                                                    break
                                                    if description_found:
                                                        break
                                            if description_found:
                                                break

                                # If still no description, generate new one with AI
                                if not description_found:
                                    # Use the NPC builder to generate a description
                                    from core.generators.npc_builder import NPCBuilder
                                    npc_builder = NPCBuilder()

                                    # Generate description based on module context
                                    npc_data = await asyncio.to_thread(
                                        npc_builder.generate_npc_description,
                                        asset['name'],
                                        module_context
                                    )
                                    if npc_data:
                                        description_text = npc_data.get('description', '')
                                        info(f"Generated new AI description for {asset['name']}")

                                # Save to NPC compendium
                                if description_text:
                                    npc_compendium_path = NPC_COMPENDIUM_PATH
                                    generated_at = datetime.now().isoformat()
                                    primary_entry = dict(existing_npc_entry)
                                    primary_entry.update({
                                        'name': asset['name'],
                                        'description': description_text,
                                        'module': module_name,
                                        'generated_at': generated_at,
                                    })
                                    legacy_entry = {
                                        'name': asset['name'],
                                        'description': description_text,
                                        'generated_at': generated_at,
                                    }
                                    merge_npc_description_pair(
                                        npc_compendium_path,
                                        f'temp/npc_descriptions_{module_name}.json',
                                        {asset['id']: primary_entry},
                                        {asset['id']: legacy_entry},
                                    )
                                    info(f"Saved {asset['name']} description to NPC compendium")

                                    completed += 1
                                    progress = int((completed / total_assets) * 100)
                                    socketio.emit('unified_generation_progress', {
                                        'percent': progress,
                                        'message': f"Generated description for {asset['name']}...",
                                        'asset_id': asset.get('id'),
                                        'asset_name': asset.get('name'),
                                        'status': 'Description Generated'
                                    })
                            except Exception as e:
                                error(f"Failed to generate description for {asset['name']}: {e}")
                                completed += 1

                    # Run async function
                    asyncio.run(generate_npc_descriptions())
            
            # Phase 2: Generate images for assets without them (or all if overwrite)
            generate_images = options.get('generate_images', True)
            overwrite = options.get('overwrite', False)
            info(f"TOOLKIT: Phase 2 - Image generation. Generate images: {generate_images}, Overwrite: {overwrite}")
            info(f"TOOLKIT: Assets with images: {[a['name'] for a in assets if a.get('has_image')]}")
            info(f"TOOLKIT: Assets without images: {[a['name'] for a in assets if not a.get('has_image')]}")

            if generate_images:
                if overwrite:
                    # If overwrite is enabled, generate for all assets that were selected
                    image_targets = assets
                    info(f"TOOLKIT: Overwrite enabled - will generate for all {len(image_targets)} assets")
                else:
                    # Otherwise only generate for assets without images
                    image_targets = [a for a in assets if not a.get('has_image')]
                    info(f"TOOLKIT: Overwrite disabled - will generate only for {len(image_targets)} assets without images")
            else:
                image_targets = []
                info(f"TOOLKIT: Image generation disabled by user - skipping")

            if image_targets:
                socketio.emit('unified_generation_progress', {
                    'phase': 'images',
                    'percent': 0,
                    'message': f"Generating images for {len(image_targets)} assets..."
                })
                
                # Separate monsters and NPCs for image generation
                monsters_to_image = [a for a in image_targets if a['type'] == 'monster']
                npcs_to_image = [a for a in image_targets if a['type'] == 'npc']
                
                # Generate NPC portraits
                for asset in npcs_to_image:
                    try:
                        # Get NPC description - check multiple sources
                        description = ""

                        # First check NPC compendium
                        npc_compendium_path = 'data/bestiary/npc_compendium.json'
                        if os.path.exists(npc_compendium_path):
                            compendium_data = safe_read_json(npc_compendium_path) or {}
                            npcs_dict = compendium_data.get('npcs', {})
                            if asset['id'] in npcs_dict:
                                description = npcs_dict[asset['id']].get('description', '')

                        # If no description in compendium, check area files
                        if not description:
                            areas_dir = Path(f"modules/{module_name}/areas")
                            if areas_dir.exists():
                                for area_file in areas_dir.glob("*.json"):
                                    if area_file.stem.endswith('_BU'):
                                        continue  # Skip backup files
                                    area_data = safe_read_json(str(area_file))
                                    if area_data and 'locations' in area_data:
                                        for location in area_data['locations']:
                                            if 'npcs' in location:
                                                for npc in location['npcs']:
                                                    if isinstance(npc, dict):
                                                        npc_name = npc.get('name', '')
                                                        npc_id = npc_name.lower().replace(' ', '_').replace("'", "")
                                                        if npc_id == asset['id']:
                                                            description = npc.get('description', '')
                                                            break
                                            if description:
                                                break
                                    if description:
                                        break

                        # If still no description, check character file
                        if not description:
                            npc_file = Path(f"modules/{module_name}/characters/{asset['id']}.json")
                            if npc_file.exists():
                                npc_data = safe_read_json(str(npc_file))
                                if npc_data:
                                    description = npc_data.get('description', '')

                        # Fallback description
                        if not description:
                            description = f"A fantasy NPC named {asset['name']}"

                        # Generate portrait using selected style and model
                        style = options.get('style', 'photorealistic')
                        model = options.get('model', 'dall-e-3')
                        result = npc_generator.generate_npc_portrait(
                            npc_id=asset['id'],
                            npc_name=asset['name'],
                            npc_description=description,
                            style=style,
                            model=model,
                            pack_name=None  # We'll save directly to module
                        )

                        if result['success']:
                            # Get image from result (either image_object or download from URL)
                            from PIL import Image
                            import requests
                            from io import BytesIO

                            img = None

                            # Try getting image_object first (returned when pack_name=None)
                            if result.get('image_object'):
                                img = result['image_object']
                                info(f"Using image object from NPC generator for {asset['name']}")
                            # Otherwise download from URL
                            elif result.get('image_url') and result['image_url'] != 'base64_image':
                                response = requests.get(result['image_url'])
                                img = Image.open(BytesIO(response.content))
                                info(f"Downloaded image from URL for {asset['name']}")

                            if img:
                                # Save original uncompressed PNG to raw_images folder
                                raw_dir = Path('raw_images') / 'npcs' / module_name
                                raw_dir.mkdir(parents=True, exist_ok=True)
                                raw_path = raw_dir / f"{asset['id']}.png"
                                img.save(raw_path, 'PNG')

                                # Save to module media folder
                                media_dir = Path(f"modules/{module_name}/media/npcs")
                                media_dir.mkdir(parents=True, exist_ok=True)

                                # Convert to RGB if needed (JPEG doesn't support transparency)
                                if img.mode == 'RGBA':
                                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                    rgb_img.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                                    img_to_save = rgb_img
                                else:
                                    img_to_save = img

                                # Save compressed JPEG (matching monster generator quality)
                                img_to_save.save(media_dir / f"{asset['id']}.jpg", 'JPEG', quality=95)

                                # Create and save thumbnail as JPEG
                                thumb = img_to_save.copy()
                                thumb.thumbnail((128, 128), Image.Resampling.LANCZOS)
                                thumb.save(media_dir / f"{asset['id']}_thumb.jpg", 'JPEG', quality=85)

                                info(f"Saved NPC images for {asset['name']} to {media_dir}")
                            else:
                                error(f"No image data available for {asset['name']}")
                        
                        completed += 1
                        progress = int((completed / total_assets) * 100)
                        socketio.emit('unified_generation_progress', {
                            'phase': 'images',
                            'percent': progress,
                            'message': f"Generated portrait for {asset['name']}..."
                        })
                        
                        # Rate limiting between API calls
                        time.sleep(3)
                        
                    except Exception as e:
                        error(f"Failed to generate image for NPC {asset['name']}: {e}")
                        completed += 1
                
                # Generate monster images
                if monsters_to_image:
                    style = options.get('style', 'photorealistic')
                    model = options.get('model', 'dall-e-3')
                    
                    # Initialize monster generator (it gets API key from config)
                    monster_generator = MonsterGenerator()
                    
                    for asset in monsters_to_image:
                        try:
                            info(f"Generating image for monster: {asset['name']}")
                            
                            # Get monster description
                            description = ""
                            
                            # First check monster compendium
                            monster_compendium_path = 'data/bestiary/monster_compendium.json'
                            if os.path.exists(monster_compendium_path):
                                compendium_data = safe_read_json(monster_compendium_path) or {}
                                monsters_dict = compendium_data.get('monsters', {})
                                if asset['id'] in monsters_dict:
                                    description = monsters_dict[asset['id']].get('description', '')
                            
                            # If no description in compendium, check module file
                            if not description:
                                monster_file = Path(f"modules/{module_name}/monsters/{asset['id']}.json")
                                if monster_file.exists():
                                    monster_data = safe_read_json(str(monster_file))
                                    if monster_data:
                                        description = monster_data.get('description', '')
                            
                            # Fallback description
                            if not description:
                                description = f"A fearsome {asset['name']} monster"
                            
                            # Generate the image
                            result = monster_generator.generate_monster_image(
                                monster_id=asset['id'],
                                style=style,
                                model=model,
                                pack_name=None  # Save to module instead of pack
                            )
                            
                            if result.get('success'):
                                info(f"Successfully generated image for {asset['name']}")
                                
                                # Copy the generated images to the module's media folder
                                import shutil
                                module_media_dir = Path(f"modules/{module_name}/media/monsters")
                                module_media_dir.mkdir(parents=True, exist_ok=True)
                                
                                # Copy main image and thumbnail from the result paths
                                if result.get('image_path'):
                                    source_image = Path(result['image_path'])
                                    if source_image.exists():
                                        dest_image = module_media_dir / f"{asset['id']}.jpg"
                                        shutil.copy2(source_image, dest_image)
                                        info(f"Copied image to module: {dest_image}")
                                
                                if result.get('thumbnail_path'):
                                    source_thumb = Path(result['thumbnail_path'])
                                    if source_thumb.exists():
                                        dest_thumb = module_media_dir / f"{asset['id']}_thumb.jpg"
                                        shutil.copy2(source_thumb, dest_thumb)
                                        info(f"Copied thumbnail to module: {dest_thumb}")
                                
                                socketio.emit('unified_generation_progress', {
                                    'percent': int((completed + 1) / total_assets * 100),
                                    'message': f"Generated image for {asset['name']}",
                                    'asset_id': asset['id'],
                                    'asset_name': asset['name'],
                                    'status': 'Image Generated'
                                })
                            else:
                                error(f"Failed to generate image for {asset['name']}: {result.get('error')}")
                                socketio.emit('unified_generation_progress', {
                                    'percent': int((completed + 1) / total_assets * 100),
                                    'message': f"Failed to generate image for {asset['name']}: {result.get('error')}",
                                    'asset_id': asset['id'],
                                    'asset_name': asset['name'],
                                    'status': 'Failed'
                                })
                            
                            completed += 1
                            
                            # Rate limiting between API calls
                            time.sleep(3)
                            
                        except Exception as e:
                            error(f"Failed to generate image for monster {asset['name']}: {e}")
                            completed += 1
                            socketio.emit('unified_generation_progress', {
                                'percent': int(completed / total_assets * 100),
                                'message': f"Error generating {asset['name']}: {str(e)}",
                                'asset_id': asset['id'],
                                'asset_name': asset['name'],
                                'status': 'Error'
                            })
            
            info(f"TOOLKIT: Generation completed. Description targets: {len(description_targets) if 'description_targets' in locals() else 0}, Image targets: {len(image_targets) if 'image_targets' in locals() else 0}")
            socketio.emit('unified_generation_complete', {
                'success': True,
                'message': f"Successfully generated assets for {module_name}",
                'generated_count': len(description_targets) if 'description_targets' in locals() else 0 + len(image_targets) if 'image_targets' in locals() else 0
            })
            
        except Exception as e:
            error(f"Asset generation failed: {e}")
            socketio.emit('unified_generation_complete', {
                'success': False,
                'error': str(e)
            })
    
    # Run generation in background thread
    info(f"TOOLKIT: About to start background thread for generation")
    import threading
    thread = threading.Thread(target=generate_assets)
    thread.daemon = True
    thread.start()
    info(f"TOOLKIT: Background thread started")
    
    return {'status': 'started'}

@socketio.on('trigger_update')
def handle_trigger_update():
    """Handle auto-update request from client"""
    import subprocess
    import sys
    import os

    update_state = {'status': 'running', 'log': [], 'error': None, 'complete': None}

    def emit_update(event_type, payload):
        if event_type == 'update_log':
            update_state['log'].append(payload.get('message', ''))
        elif event_type == 'update_error':
            update_state.update(status='failed', error=payload.get('error'))
        elif event_type == 'update_complete':
            update_state.update(status='complete', complete=payload.get('message'))
        _remember_ui_operation('update', update_state)
        emit(event_type, payload)

    emit_update('update_log', {'message': 'Starting auto-update...'})
    print("[AUTO_UPDATE] Handler triggered")  # Console debug

    try:
        # Get the current working directory
        repo_path = os.getcwd()
        print(f"[AUTO_UPDATE] Current directory: {repo_path}")  # Console debug
        emit_update('update_log', {'message': f'Repository path: {repo_path}'})

        # Normalize path separators for Git (Git expects forward slashes even on Windows)
        # C:\dungeon_master_v1 -> C:/dungeon_master_v1
        git_safe_path = repo_path.replace('\\', '/')
        print(f"[AUTO_UPDATE] Git safe path: {git_safe_path}")  # Console debug
        emit_update('update_log', {'message': f'Git path format: {git_safe_path}'})

        # Step 1: Git pull with safe.directory config applied directly
        # Use -c flag to pass safe.directory config inline (avoids persistent config issues)
        git_cmd = ["git", "-c", f"safe.directory={git_safe_path}", "pull"]
        print(f"[AUTO_UPDATE] Git command: {' '.join(git_cmd)}")  # Console debug
        emit_update('update_log', {'message': f'Running: git -c safe.directory={git_safe_path} pull'})
        emit_update('update_log', {'message': 'Pulling latest code from GitHub...'})

        result = subprocess.run(
            git_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_path
        )

        if result.returncode != 0:
            emit_update('update_error', {'error': f'Git pull failed: {result.stderr}'})
            return

        emit_update('update_log', {'message': f'Git: {result.stdout.strip()}'})

        # Step 2: Pip install
        emit_update('update_log', {'message': 'Updating dependencies...'})

        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"]

        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            emit_update('update_error', {'error': f'Pip install failed: {result.stderr}'})
            return

        emit_update('update_log', {'message': 'Dependencies updated successfully!'})

        # Keep /play/ deployable after an update. Reuse the same freshness
        # check/build path as the normal launcher instead of re-execing a
        # server that may point at stale or missing frontend assets.
        from run_web import ensure_react_frontend
        emit_update('update_log', {'message': 'Checking React player build...'})
        if not ensure_react_frontend(repo_root=repo_path):
            emit_update('update_error', {'error': 'React player build failed; server was not restarted.'})
            return

        # Step 3: Restart server
        emit_update('update_complete', {'message': 'Update complete! Server restarting...'})

        # Give client time to receive message
        socketio.sleep(1)

        # Restart the server process
        os.execv(sys.executable, ['python'] + sys.argv)

    except Exception as e:
        emit_update('update_error', {'error': str(e)})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    print("Starting NeverEndingQuest Web Interface...")
    try:
        import config
        port = getattr(config, 'WEB_PORT', 8357)
    except ImportError:
        port = 8357
    start_path = os.environ.get('NEQ_START_PATH', '/')
    if start_path not in {'/', '/play/'}:
        start_path = '/'
    print(f"Opening browser at http://localhost:{port}{start_path}")
    
    # Run the Flask app with SocketIO
    socketio.run(app,
                host=WEB_HOST,
                port=port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True)
