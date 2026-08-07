# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""HeadlessSession: run the unmodified game engine behind stream shims.

Lifecycle (order is load-bearing):
  1. bootstrap()      - config.py, game dir, runtime dirs, character seed.
                        Engine modules are imported lazily AFTER config exists.
  2. start_engine()   - install stdin/stdout/stderr shims, register the
                        status / compression / player-output callbacks, THEN
                        import main (so enhanced_logger's stdout handler
                        binds to the shim), and run main_game_loop() in a
                        daemon thread.
  3. dispatch_input() / handle_command() - called by a runner (serve or
                        script driver in run_headless.py).

The `prompt` protocol event is the synchronization point: it fires from
inside HeadlessInput.readline(), which the engine only reaches after its
post-turn save block, so the state snapshot attached alongside it reflects
the completed turn.
"""

import os
import queue
import threading
import traceback

from core.headless import bootstrap as bootstrap_mod
from core.headless.classifier import strip_ansi, looks_like_prompt
from core.headless.protocol import PROTOCOL_VERSION
from core.headless.state_reader import build_snapshot
from core.headless.streams import (
    EOF_SENTINEL,
    HeadlessInput,
    HeadlessOutputCapture,
)

_WIZARD_PROMPT_MARKERS = (
    "Your choice",
    "Your response",
    "Press Enter",
    "(y/n)",
    "Enter your",
    # Deterministic character-creation prompts (utils/startup_wizard.py).
    "Character name",
    "Choose your",
    "Assign score",
    "Your character's",
    "Your decision",
)

RAW_LOG_PATH = os.path.join("modules", "logs", "headless_raw.log")


class HeadlessSession:
    def __init__(self, repo_root, game_dir=None, debug=False, writer=None):
        self.repo_root = os.path.abspath(repo_root)
        self.game_dir = os.path.abspath(game_dir) if game_dir else self.repo_root
        self.debug = debug
        self.writer = writer
        self.input_queue = queue.Queue()
        self.prompt_pending = threading.Event()
        self._quitting = False
        self._exit_lock = threading.Lock()
        self._exit_emitted = False
        self._engine_thread = None
        self._stdout_shim = None
        self._raw_log = None
        self._real_streams = None
        self._channel = "main"
        self._dm_main = None
        self._seed_character_file = None
        self._seed_module = None
        self._last_startup_marker = None

    # -- bootstrap ---------------------------------------------------------

    def bootstrap(self, character_file=None, module=None):
        """Pure-stdlib preparation. MUST NOT import any engine module:
        the first engine import binds enhanced_logger's console handler to
        the current sys.stdout, and the shims are not installed yet -- an
        early import would leak logger output onto the protocol stream.
        Engine-touching steps run in start_engine() after the shims.
        """
        if character_file and not module:
            raise bootstrap_mod.BootstrapError("--character requires --module")
        config_status = bootstrap_mod.ensure_config(self.repo_root)
        if config_status == "created_without_key":
            self.writer.emit(
                "system",
                content=(
                    "config.py was created from the template but no "
                    "OPENAI_API_KEY environment variable was set. Cloud "
                    "providers will fail until a key is added."))
        copied = bootstrap_mod.prepare_game_dir(
            self.game_dir, self.repo_root, module=module)
        os.chdir(self.game_dir)
        bootstrap_mod.ensure_runtime_dirs()
        if copied and self.debug:
            self.writer.emit(
                "debug", content="fixture copies: %s" % ", ".join(copied),
                is_error=False)
        self._seed_character_file = character_file
        self._seed_module = module

    # -- engine start ------------------------------------------------------

    def start_engine(self):
        os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
        self._raw_log = open(RAW_LOG_PATH, "a", encoding="utf-8",
                             errors="replace")

        import sys
        self._real_streams = (sys.stdout, sys.stderr, sys.stdin)
        self._stdout_shim = HeadlessOutputCapture(
            self._on_stream_event, self._raw_log)
        stderr_shim = HeadlessOutputCapture(
            self._on_stream_event, self._raw_log, is_error=True)
        stdin_shim = HeadlessInput(
            self.input_queue, on_prompt=self._on_prompt,
            is_quitting=lambda: self._quitting)
        sys.stdout = self._stdout_shim
        sys.stderr = stderr_shim
        sys.stdin = stdin_shim

        # Callbacks are transport-agnostic seams; register before the engine
        # import so nothing races them.
        from core.managers.status_manager import (
            set_status_callback, set_compression_callback)
        set_status_callback(self._on_status)
        set_compression_callback(self._on_compression)
        from web.shared_state import set_player_output_sink
        set_player_output_sink(self._on_player_output)

        # Engine-touching bootstrap steps, now safe behind the shims.
        # startup_wizard registers its own terminal status callback at import
        # time (it duck-types web mode by class NAME, which ours fails), so
        # ours must be re-registered afterwards.
        bootstrap_mod.run_engine_prechecks()
        set_status_callback(self._on_status)
        if self._seed_character_file:
            name = bootstrap_mod.seed_character(
                self._seed_character_file, self._seed_module)
            self.writer.emit(
                "system",
                content="Seeded character %r into module %r; startup wizard "
                        "will be skipped." % (name, self._seed_module))

        # Import main AFTER the shims: enhanced_logger's console handler
        # binds sys.stdout at import time. This also lets main.py's
        # module-level prints flow through the classifier.
        import main as dm_main
        # Importing main pulls in action_handler, which imports
        # web.web_interface for its socketio handle -- and web_interface
        # installs DebugOutputInterceptor over our stdout shim at import
        # time. That interceptor DROPS bare newline writes, gluing every
        # engine line together and eating input() prompts. Web mode
        # uninstalls it before starting the game loop; headless must too.
        try:
            from utils.redirect_debug_output import uninstall_debug_interceptor
            uninstall_debug_interceptor()
        except ImportError:
            pass
        # main.py claims the status callback at import time, and web session
        # handlers claim the sink when they run; re-register both so
        # headless owns them for this session (defensive for the sink,
        # load-bearing for the status callback).
        set_status_callback(self._on_status)
        set_player_output_sink(self._on_player_output)
        self._dm_main = dm_main

        self.writer.emit(
            "hello",
            protocol=PROTOCOL_VERSION,
            game_dir=self.game_dir,
            pid=os.getpid())

        self._engine_thread = threading.Thread(
            target=self._run_engine, name="headless-engine", daemon=True)
        self._engine_thread.start()

        progress_thread = threading.Thread(
            target=self._pump_module_progress, name="headless-module-progress",
            daemon=True)
        progress_thread.start()

    def _run_engine(self):
        reason = "engine_stop"
        detail = None
        try:
            self._dm_main.main_game_loop()
        except (EOFError, SystemExit):
            reason = "player_exit"
        except BaseException as exc:
            if self._quitting:
                reason = "player_exit"
            else:
                reason = "error"
                detail = "%s: %s" % (type(exc).__name__, exc)
                self.writer.emit(
                    "debug", content=traceback.format_exc(), is_error=True)
        else:
            if self._quitting:
                reason = "player_exit"
        finally:
            try:
                self._stdout_shim.flush()
            except Exception:
                pass
            self.emit_exit(reason, detail)

    def _pump_module_progress(self):
        from web.shared_state import module_progress_queue
        while True:
            try:
                item = module_progress_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            except Exception:
                return
            try:
                self.writer.emit("module_progress", **dict(item))
            except Exception:
                pass

    # -- engine-side event handlers ---------------------------------------

    def _on_stream_event(self, kind, **fields):
        if kind == "narration":
            # With the player-output sink routing (P2) this path should stay
            # quiet; anything arriving here is a print site the sink does
            # not cover yet -- the source tag makes such stragglers findable.
            self.writer.emit(
                "narration", channel=self._channel,
                content=fields.get("content", ""),
                source="stdout_scrape")
        elif kind == "startup":
            # Each STARTUP_MARKER line is emitted twice by the engine (once
            # via print for the stream parser, once via the logger whose
            # console handler is also bound to our shim); dedupe on the
            # marker payload.
            marker_key = (fields.get("phase"), fields.get("timestamp"))
            if marker_key == self._last_startup_marker:
                return
            self._last_startup_marker = marker_key
            self.writer.emit("startup", **fields)
        elif kind == "debug":
            if self.debug:
                self.writer.emit("debug", **fields)
        # Raw text already went to the mirror log regardless.

    def _on_status(self, message, is_processing):
        self.writer.emit("status", message=message,
                         is_processing=bool(is_processing))

    def _on_compression(self, event_type, data):
        try:
            payload = dict(data)
        except Exception:
            payload = {"data": str(data)}
        self.writer.emit("compression", event=event_type, **payload)

    def _on_player_output(self, payload):
        # Structured sink messages (all DM narration since P2, plus module
        # transitions and safe-action failures). Returning normally marks
        # the message handled, which suppresses the engine's fallback
        # print -- no double delivery.
        msg_type = payload.get("type", "system")
        event_type = "narration" if msg_type == "narration" else "system"
        self.writer.emit(
            event_type,
            channel=payload.get("channel", "system"),
            content=payload.get("content", ""),
            source="sink")

    def _classify_prompt(self, clean_prompt, snapshot):
        if "(Leveling Up)" in clean_prompt:
            return "levelup"
        if looks_like_prompt(clean_prompt) or clean_prompt.endswith(":"):
            combat = snapshot.get("combat") or {}
            if combat.get("active"):
                return "combat"
            if looks_like_prompt(clean_prompt):
                return "main"
        if any(marker in clean_prompt for marker in _WIZARD_PROMPT_MARKERS):
            return "wizard"
        if clean_prompt.startswith("User:"):
            return "main"
        return "unknown"

    def _parse_prompt_stats(self, clean_prompt):
        import re
        stats = {}
        # Main prompts show [HH:MM (context)]; combat prompts show the raw
        # [HH:MM:SS] with no context. Accept both.
        match = re.search(
            r"\[(\d\d:\d\d)(?::\d\d)?(?: \(([^)]*)\))?\]\[HP:([^/\]]+)/([^\]]+)\]"
            r"\[XP:([^/\]]+)/([^\]]+)\]",
            clean_prompt)
        if match:
            stats = {
                "time": match.group(1),
                "time_context": match.group(2),
                "hp": match.group(3),
                "max_hp": match.group(4),
                "xp": match.group(5),
                "next_level_xp": match.group(6),
            }
        return stats

    def _on_prompt(self):
        # Runs on the engine thread from inside readline(), i.e. the engine
        # is idle and its post-turn saves are on disk.
        if self._quitting:
            return
        pending = ""
        if self._stdout_shim is not None:
            pending = self._stdout_shim.consume_pending()
        clean_prompt = strip_ansi(pending).strip()
        snapshot = build_snapshot()
        kind = self._classify_prompt(clean_prompt, snapshot)
        if kind in ("main", "combat", "levelup"):
            self._channel = kind
        # Set BEFORE emitting: the prompt event's observers may dispatch an
        # input (clearing the flag) synchronously from inside emit(), and a
        # serve agent may react the instant it sees the event. Setting after
        # would leave the flag stuck set for the whole following turn,
        # defeating the save/restore busy-guard.
        self.prompt_pending.set()
        self.writer.emit(
            "prompt",
            kind=kind,
            raw_prompt=clean_prompt,
            stats=self._parse_prompt_stats(clean_prompt))
        self.writer.emit("state", **snapshot)

    # -- runner-side API ---------------------------------------------------

    def dispatch_input(self, content):
        self.prompt_pending.clear()
        self.input_queue.put(content)

    def request_quit(self):
        self._quitting = True
        self.prompt_pending.clear()
        self.input_queue.put(EOF_SENTINEL)

    def handle_command(self, command):
        command_id = command.get("id")
        name = command.get("name")
        args = command.get("args") or {}

        def result(ok, data=None, error=None):
            payload = {"id": command_id, "ok": ok}
            if data is not None:
                payload["data"] = data
            if error is not None:
                payload["error"] = error
            self.writer.emit("result", **payload)

        if name == "state":
            result(True, data=build_snapshot())
            return
        if name == "quit":
            result(True)
            self.request_quit()
            return

        if name in ("save", "restore", "delete_save") and not \
                self.prompt_pending.is_set():
            result(False, error="engine is busy; wait for the next prompt "
                                "event before %s" % name)
            return

        try:
            from updates.save_game_manager import SaveGameManager
            manager = SaveGameManager()
            if name == "list_saves":
                result(True, data=manager.list_save_games())
            elif name == "save":
                ok, message = manager.create_save_game(
                    description=args.get("description", ""),
                    save_mode=args.get("save_mode", "essential"))
                result(bool(ok), data={"message": message} if ok else None,
                       error=None if ok else message)
            elif name == "delete_save":
                folder = args.get("save_folder")
                if not folder:
                    result(False, error="delete_save requires args.save_folder")
                    return
                ok, message = manager.delete_save_game(folder)
                result(bool(ok), data={"message": message} if ok else None,
                       error=None if ok else message)
            elif name == "restore":
                folder = args.get("save_folder")
                if not folder:
                    result(False, error="restore requires args.save_folder")
                    return
                ok, message = manager.restore_save_game(folder)
                if not ok:
                    result(False, error=message)
                    return
                # In-memory engine state is now stale; the only safe move is
                # a process restart (web mode uses os._exit; headless ends
                # cleanly and lets the agent relaunch).
                result(True, data={"message": message})
                self.emit_exit("restart",
                               "state restored; relaunch the session")
            else:
                result(False, error="unhandled command %r" % name)
        except Exception as exc:
            result(False, error="%s: %s" % (type(exc).__name__, exc))

    # -- shutdown ----------------------------------------------------------

    def emit_exit(self, reason, detail=None):
        with self._exit_lock:
            if self._exit_emitted:
                return
            self._exit_emitted = True
        payload = {"reason": reason}
        if detail:
            payload["detail"] = detail
        self.writer.emit("exit", **payload)

    def restore_streams(self):
        if self._real_streams is None:
            return
        import sys
        sys.stdout, sys.stderr, sys.stdin = self._real_streams
        self._real_streams = None
        if self._raw_log is not None:
            try:
                self._raw_log.close()
            except Exception:
                pass
            self._raw_log = None
