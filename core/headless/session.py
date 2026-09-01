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
from uuid import uuid4

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
        self._restart_in_progress = threading.Event()
        self._engine_thread = None
        self._stdout_shim = None
        self._raw_log = None
        self._real_streams = None
        self._channel = "main"
        self._dm_main = None
        self._seed_character_file = None
        self._seed_module = None
        self._last_startup_marker = None
        self._last_status = None

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
            set_status_callback, set_compression_callback, status_manager)
        set_status_callback(self._on_status)
        set_compression_callback(self._on_compression)
        status_manager.set_welcome_callback(self._on_welcome)
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
        # web.web_interface (pulled in by the main import chain) claims the
        # welcome callback at import time too; reclaim it or #214 welcome
        # liveness would flow to Socket.IO instead of this NDJSON stream.
        status_manager.set_welcome_callback(self._on_welcome)
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
                shutdown = getattr(
                    self._dm_main, "shutdown_welcome_lifecycle", None)
                if shutdown is not None:
                    shutdown("engine_stop")
            except Exception:
                pass
            try:
                from utils.capture.live_provider_call import abort_live_turn_scope

                abort_live_turn_scope()
            except Exception:
                pass
            try:
                self._stdout_shim.flush()
            except Exception:
                pass
            # Restore/Reset own the terminal restart event.  Suppress the
            # engine thread's ordinary player_exit while one of those
            # lifecycle operations is deliberately unwinding the prompt.
            if not self._restart_in_progress.is_set():
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
        status_key = (str(message), bool(is_processing))
        if status_key == self._last_status:
            return
        self._last_status = status_key
        self.writer.emit("status", message=message,
                         is_processing=bool(is_processing))

    def _on_compression(self, event_type, data):
        try:
            payload = dict(data)
        except Exception:
            payload = {"data": str(data)}
        self.writer.emit("compression", event=event_type, **payload)

    def _on_welcome(self, message):
        # #214 D-214-4=A: background startup-welcome liveness. A separate
        # additive NDJSON event type - deliberately NOT a "status" event, so
        # harnesses never read it as input-locking processing state.
        self.writer.emit("welcome_progress", message=str(message))

    def _on_player_output(self, payload):
        # Structured sink messages (all DM narration since P2, plus module
        # transitions and safe-action failures). Returning normally marks
        # the message handled, which suppresses the engine's fallback
        # print -- no double delivery.
        msg_type = payload.get("type", "system")
        event_type = "narration" if msg_type == "narration" else "system"
        return self.writer.emit(
            event_type,
            channel=payload.get("channel", "system"),
            content=payload.get("content", ""),
            message_id=payload.get("message_id"),
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

    def _wait_for_scope_quiescence(self, scopes, operation_name):
        """Wait without a deadline while one lifecycle status remains visible."""
        pending = []
        seen = set()
        for scope in scopes:
            if scope is None or id(scope) in seen:
                continue
            seen.add(id(scope))
            pending.append(scope)
        elapsed = 0
        while any(not scope.quiescent.is_set() for scope in pending):
            self._on_status(
                "%s is waiting for current game work to finish safely (%ds)"
                % (operation_name, elapsed),
                True,
            )
            next(
                scope for scope in pending if not scope.quiescent.is_set()
            ).quiescent.wait(timeout=1.0)
            elapsed += 1

    def request_quit(self, kind="quit", operation_id=None):
        from utils.capture.live_provider_call import (
            get_active_welcome_scope,
            get_live_turn_scope,
            request_live_turn_supersession,
        )

        kind = str(kind)
        requested_id = str(operation_id or uuid4())
        operation_name = "Reset" if kind == "reset" else "Quit"

        # #214: a background startup welcome must quiesce BEFORE the quit
        # intent is latched. The game thread is parked at the prompt, and its
        # readline pump is the only path that services the welcome discard
        # handback -- but that pump stops the moment self._quitting is set,
        # so waiting after latching would deadlock. The supersession lets the
        # child exit instead of burning provider work past a player quit.
        welcome_scope = get_active_welcome_scope()
        live_scope = get_live_turn_scope()
        claims = []
        if welcome_scope is not None:
            claims.append(welcome_scope.request_supersession(kind, requested_id))
        if live_scope is not None:
            operation = request_live_turn_supersession(
                kind, requested_id, scope=live_scope
            )
            if operation is not None:
                claims.append(operation)
        if claims:
            exact_owner = all(
                claim.get("kind") == kind
                and claim.get("operation_id") == requested_id
                for claim in claims
            )
            self.writer.emit(
                "operation",
                id=requested_id,
                name=kind,
                status="accepted_deferred",
                operation_id=requested_id,
                waiting_for_current_operation=not exact_owner,
            )
        if welcome_scope is not None:
            self._wait_for_scope_quiescence((welcome_scope,), operation_name)

        # Preserve the historical terminal reason even when a live turn must
        # quiesce first. The engine thread may finish its superseded turn while
        # this control thread is waiting; setting the intent afterward races
        # that completion and misreports a player quit as ``engine_stop``.
        self._quitting = True
        self.prompt_pending.clear()
        if live_scope is not None:
            self._wait_for_scope_quiescence((live_scope,), operation_name)
        if kind == "quit":
            self._on_status("Quit complete", False)
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
            if name in ("restore", "reset"):
                label = "Load" if name == "restore" else "Reset"
                terminal = "complete" if ok else "failed"
                self._on_status("%s %s" % (label, terminal), False)

        if name == "state":
            result(True, data=build_snapshot())
            return
        if name == "quit":
            result(True)
            self.request_quit()
            return
        if name == "reset":
            if args.get("confirmed") is not True:
                result(False, error="reset requires args.confirmed=true")
                return
            self._restart_in_progress.set()
            self._on_status("Reset is starting safely", True)
            try:
                # The synchronous combat loop can retain module/campaign
                # authority while it waits at a player prompt.  End and join
                # that exact engine before Reset attempts to acquire the same
                # authority; no filesystem lock is held during this wait.
                self.request_quit("reset", str(command_id))
                if self._engine_thread is not None:
                    self._engine_thread.join()
                from utils.reset_campaign import perform_reset_logic

                backup_dir = perform_reset_logic()
                result(
                    True,
                    data={
                        "message": "Campaign reset complete",
                        "backup_dir": backup_dir,
                    },
                )
                self.emit_exit("restart", "campaign reset; relaunch the session")
            except Exception as exc:
                result(False, error="%s: %s" % (type(exc).__name__, exc))
                self.emit_exit("error", "campaign reset failed")
            return

        from utils.capture.live_provider_call import (
            get_active_welcome_scope,
            get_live_turn_scope,
        )

        live_scope = get_live_turn_scope()
        # #214: the detached startup welcome is deliberately NOT the live
        # turn scope; persistence commands must still coordinate with its
        # game-thread handback (the readline pump) instead of overlapping it.
        # (Reset needs no welcome branch: it quits+joins the engine first,
        # and request_quit already supersedes/quiesces a pending welcome.)
        welcome_scope = get_active_welcome_scope()
        busy_persistence = (
            name == "delete_save"
            or (name in ("save", "restore") and live_scope is None)
        )
        if busy_persistence and not self.prompt_pending.is_set():
            result(False, error="engine is busy; wait for the next prompt "
                                "event before %s" % name)
            return

        try:
            from updates.save_game_manager import SaveGameManager
            manager = SaveGameManager()
            if name == "list_saves":
                result(True, data=manager.list_save_games())
            elif name == "save":
                if live_scope is not None:
                    from utils.capture.live_provider_call import queue_live_save

                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="save",
                        status="accepted_deferred",
                    )

                    def execute_save():
                        return manager.create_save_game(
                            description=args.get("description", ""),
                            save_mode=args.get("save_mode", "essential"),
                        )

                    def complete_save(outcome):
                        ok, message = outcome
                        result(
                            bool(ok),
                            data={"message": message} if ok else None,
                            error=None if ok else message,
                        )

                    queued_id = queue_live_save(
                        execute_save, complete_save, command_id
                    )
                    if queued_id is None:
                        live_scope.quiescent.wait()
                        complete_save(execute_save())
                    return
                if welcome_scope is not None:
                    # #214 F8: Save never cancels a healthy background
                    # welcome - it QUEUES against the welcome scope and
                    # executes on the game thread inside the welcome
                    # terminal, before quiescence releases player input.
                    from utils.capture.live_provider_call import (
                        queue_live_save,
                    )

                    def execute_welcome_save():
                        return manager.create_save_game(
                            description=args.get("description", ""),
                            save_mode=args.get("save_mode", "essential"),
                        )

                    def complete_welcome_save(outcome):
                        ok2, message2 = outcome
                        result(
                            bool(ok2),
                            data={"message": message2} if ok2 else None,
                            error=None if ok2 else message2,
                        )

                    queued = queue_live_save(
                        execute_welcome_save, complete_welcome_save,
                        command_id, scope=welcome_scope,
                    )
                    if queued is None:
                        # The welcome sealed before the enqueue: no welcome
                        # remains. Re-resolve authoritative state - queue
                        # against a now-live player turn, else honest retry
                        # (lands on the plain no-welcome path).
                        queued = queue_live_save(
                            execute_welcome_save, complete_welcome_save,
                            command_id,
                        )
                    if queued is None:
                        # Sealed scope: wait for ITS quiescent (set only
                        # AFTER the registry is cleared), then re-dispatch
                        # the SAME command against freshly read scopes -
                        # terminates structurally, no tight recursion, and
                        # exactly one result is emitted (by the re-dispatch).
                        welcome_scope.quiescent.wait()
                        self.handle_command(command)
                        return
                    # Acceptance only once a queue holds the record.
                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="save",
                        status="accepted_deferred",
                    )
                    return
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
                self._on_status("Load is starting safely", True)
                if live_scope is not None:
                    from utils.capture.live_provider_call import (
                        request_live_turn_supersession,
                    )

                    operation = request_live_turn_supersession(
                        "restore", str(command_id)
                    )
                    if operation["kind"] == "turn_complete":
                        self._wait_for_scope_quiescence(
                            (live_scope,), "Load"
                        )
                    elif not operation["accepted"]:
                        result(
                            False,
                            error=(
                                "another lifecycle operation is already pending: "
                                + operation["kind"]
                            ),
                        )
                        return
                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="restore",
                        status="accepted_deferred",
                        operation_id=operation["operation_id"],
                    )
                    self._wait_for_scope_quiescence((live_scope,), "Load")
                if welcome_scope is not None:
                    # #214 F9: Load supersedes the background welcome and
                    # QUEUES the restore to execute ON THE GAME THREAD inside
                    # the welcome terminal (after discard handback, before
                    # quiescence releases player input) - the destructive op
                    # stays authoritative; no post-quiescence gap.
                    from utils.capture.live_provider_call import (
                        claim_destructive_operation,
                    )

                    def execute_welcome_restore():
                        return manager.restore_save_game(folder)

                    def complete_welcome_restore(outcome):
                        ok2, message2 = outcome
                        if not ok2:
                            result(False, error=message2)
                            return
                        result(True, data={"message": message2})
                        self.emit_exit(
                            "restart",
                            "state restored; relaunch the session")

                    # Claim/promotion AND record insertion are ONE scope-
                    # lock transaction: an accepted destructive claim always
                    # has its executable record queued (seal cannot split
                    # them; never mutate from this control thread).
                    claim = claim_destructive_operation(
                        welcome_scope, "restore",
                        execute_welcome_restore, complete_welcome_restore,
                        operation_id=str(command_id),
                    )
                    if claim["status"] == "closed":
                        # Closed before the claim: restore is NEVER refused
                        # (#193). Wait for the CAPTURED scope's quiescent
                        # (set only AFTER the registry is cleared), then
                        # re-dispatch the SAME command against freshly read
                        # scopes - never the stale scope, no tight
                        # recursion, exactly one result (the re-dispatch's).
                        self._wait_for_scope_quiescence(
                            (welcome_scope,), "Load"
                        )
                        self.handle_command(command)
                        return
                    if claim["status"] == "conflict":
                        result(
                            False,
                            error=(
                                "another lifecycle operation is already "
                                "pending: " + str(claim["kind"])
                            ),
                        )
                        return
                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="restore",
                        status="accepted_deferred",
                        operation_id=claim["operation_id"],
                    )
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
