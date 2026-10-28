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
import time
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



def _pending_roll():
    """The roll the game is holding for the player (D-1118-5 A, #1118 items 3 and 4), typed, from checks_state:
    {kind: "check" or "hitDie", label, dice}; a waiting check comes before a held rest, as the settle takes
    them. None when nothing is held. A harness never reads DM prose to find it."""
    try:
        from core.managers import checks_state
        from core.nql import checks

        pending = checks_state.pending_checks()
        if pending:
            check = pending[0]
            return {"kind": "check", "label": f"{checks.label(check.get('stat'))} for {check.get('characterName')}",
                    "dice": [{"count": check.get("faces"), "sides": 20}]}
        entry = checks_state.pending_rest()
    except Exception:
        return None
    if not entry:
        return None
    return {"kind": "hitDie", "label": f"Hit die for {entry.get('characterName')}",
            "dice": [{"count": entry.get("count"), "sides": entry.get("die")}]}

class HeadlessSession:
    def __init__(self, repo_root, game_dir=None, debug=False, writer=None):
        self.repo_root = os.path.abspath(repo_root)
        self.game_dir = os.path.abspath(game_dir) if game_dir else self.repo_root
        self.debug = debug
        self.writer = writer
        self.input_queue = queue.Queue()
        self.prompt_pending = threading.Event()
        self._quitting = False
        # #341: the control that set the quit latch through request_quit
        # ("quit" or "reset"); the startup wizard reads it at its input boundary.
        self._quit_kind = None
        self._exit_lock = threading.Lock()
        self._exit_emitted = False
        self._restart_in_progress = threading.Event()
        self._recovery_required = False
        self._restore_manager = None
        self._preflight_guard = threading.Lock()
        self._received_quit_id = None
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
        refreshed = [entry for entry in copied if entry.startswith("refreshed ")]
        if refreshed:
            self.writer.emit(
                "system",
                content=(
                    "This game folder held older copies of the game's files "
                    "and was updated from this install: %s."
                    % ", ".join(refreshed)))
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
            is_quitting=lambda: self._quitting,
            lifecycle_control=lambda: self._quit_kind if self._quitting else None)
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
            from updates.save_game_manager import RestoreRequest
            handoff = self._dm_main.main_game_loop()
            if isinstance(handoff, RestoreRequest):
                from utils.capture.live_provider_call import (
                    model_restore_owner_id,
                    release_lifecycle_owner,
                )

                # #270: main_game_loop claimed the owner record for the
                # model's Load; a fault before its terminal lets followers
                # run again (C4).
                owned = model_restore_owner_id()
                try:
                    self._restart_in_progress.set()
                    self._quitting = True
                    self.prompt_pending.clear()
                    self._restore_manager = handoff.manager

                    def publish_restore(_ok, data=None, error=None):
                        self.writer.emit('system', content=data['message'],
                                         restore_outcome=data['restore_outcome'],
                                         can_resume=data['can_resume'])
                        self._on_status(data['message'], False)

                    outcome = self._apply_restore(handoff.manager, handoff.save_folder)
                    self._finish_restore(outcome, handoff.manager, publish_restore, owned)
                finally:
                    release_lifecycle_owner(owned)
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

    def _on_stream_event(self, kind, *, commit_guard=None, **fields):
        if kind == "narration":
            # With the player-output sink routing (P2) this path should stay
            # quiet; anything arriving here is a print site the sink does
            # not cover yet -- the source tag makes such stragglers findable.
            self.writer.emit(
                "narration", channel=self._channel,
                content=fields.get("content", ""),
                source="stdout_scrape", commit_guard=commit_guard)
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
        if self._recovery_required and not is_processing:
            message = "Gameplay is paused. Choose a save to Load, Reset, or Quit."
        status_key = (str(message), bool(is_processing))
        if status_key == self._last_status:
            return
        self._last_status = status_key
        self.writer.emit("status", message=message,
                         is_processing=bool(is_processing),
                         recovery_required=self._recovery_required)

    def _on_compression(self, event_type, data):
        try:
            payload = dict(data)
        except Exception:
            payload = {"data": str(data)}
        self.writer.emit("compression", event=event_type, **payload)

    def _on_welcome(self, message, kind=None):
        # #214 D-214-4=A: background startup-welcome liveness. A separate
        # additive NDJSON event type - deliberately NOT a "status" event, so
        # harnesses never read it as input-locking processing state.
        if kind is None:
            self.writer.emit("welcome_progress", message=str(message))
        else:
            self.writer.emit("welcome_progress", message=str(message), kind=str(kind))

    def _on_player_output(self, payload, *, commit_guard=None):
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
            source="sink", commit_guard=commit_guard)

    def _classify_prompt(self, clean_prompt, snapshot):
        if "(Leveling Up)" in clean_prompt:
            return "levelup"
        if "[ROLL]" in clean_prompt:
            return "roll"
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
        # [HH:MM:SS] with no context. Accept both. #642: main prompts may lead
        # with the calendar day ([Springmonth 4]); it is reported as "date"
        # only when present, so older prompt lines parse to the same keys.
        match = re.search(
            r"(?:\[([A-Za-z]+ \d{1,2})\])?"
            r"\[(\d\d:\d\d)(?::\d\d)?(?: \(([^)]*)\))?\]\[HP:([^/\]]+)/([^\]]+)\]"
            r"\[XP:([^/\]]+)/([^\]]+)\]",
            clean_prompt)
        if match:
            stats = {
                "time": match.group(2),
                "time_context": match.group(3),
                "hp": match.group(4),
                "max_hp": match.group(5),
                "xp": match.group(6),
                "next_level_xp": match.group(7),
            }
            if match.group(1):
                stats["date"] = match.group(1)
        return stats

    def _on_prompt(self):
        # Runs on the engine thread from inside readline(), i.e. the engine
        # is idle and its post-turn saves are on disk.
        if self._quitting or self._recovery_required:
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
        extra = {}
        pending_roll = _pending_roll()
        if pending_roll is not None:
            extra["pendingRoll"] = pending_roll
        self.writer.emit(
            "prompt",
            kind=kind,
            raw_prompt=clean_prompt,
            stats=self._parse_prompt_stats(clean_prompt),
            **extra)
        self.writer.emit("state", **snapshot)

    # -- runner-side API ---------------------------------------------------

    def dispatch_input(self, content):
        if self._recovery_required or self._restart_in_progress.is_set():
            self.writer.emit(
                "result", id=None, ok=False,
                error=(
                    "Choose a save to Load, Reset, or Quit before continuing play."
                    if self._recovery_required else
                    "Load or Reset is in progress; wait for its result before continuing."
                ),
            )
            return
        # #1436: the web's notice for input held behind a new game's opening
        # scene, read before the queue as the web reads it.
        try:
            opening_scene = bool(self._dm_main and self._dm_main.opening_scene_pending())
        except Exception:
            opening_scene = False
        self.prompt_pending.clear()
        self.input_queue.put(content)
        if opening_scene:
            self.writer.emit("operation", name="input", status="accepted_deferred",
                             message="Your action is queued for after the opening scene.")
        from utils.capture.live_provider_call import get_live_turn_scope
        scope = get_live_turn_scope()
        if scope is not None and scope.purpose == "travel_recovery":
            self.writer.emit("operation", name="input", status="accepted_deferred",
                             message="Your action is queued for after travel recovery.")

    def _finish_restore(self, outcome, manager, result, owner_id=None):
        """Publish verified disk truth without terminating recovery command intake."""
        from utils.capture.live_provider_call import release_lifecycle_owner

        self._recovery_required = not outcome.can_resume
        # Preserve the original save-root context even if failed copying changed
        # party_tracker. This stays process-local; it is not a crash manifest.
        self._restore_manager = manager if self._recovery_required else None
        self._restart_in_progress.set()
        self._quitting = True
        self.prompt_pending.clear()
        self.input_queue.put(EOF_SENTINEL)
        selected = outcome.disposition == "selected_applied"
        result(
            selected,
            data={
                "message": outcome.message,
                "restore_outcome": outcome.disposition,
                "can_resume": outcome.can_resume,
            },
            error=None if selected else outcome.message,
        )
        # #270 C3: a restart answers the followers before the exit event;
        # recovery lets them run again against the recovered state.
        release_lifecycle_owner(owner_id, restarting=outcome.can_resume)
        if outcome.can_resume:
            self.emit_exit("restart", "clean game state available; relaunch the session")
        # No exit when recovery is required: ServeDriver remains able to accept
        # list/Load/Reset/Quit. A welcome handback calls this on the engine thread,
        # so it must return, never join or await its own quiescence.

    def _apply_restore(self, manager, folder):
        from updates.save_game_manager import RestoreOutcome

        try:
            return manager.restore_save_game_outcome(
                folder, previous_clean=not self._recovery_required
            )
        except Exception as exc:
            # Unexpected manager failure provides no verified disk outcome.
            return RestoreOutcome("recovery_required", str(exc))

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
            request_lifecycle_turn_supersession,
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
        claims = []
        if welcome_scope is not None:
            claims.append(welcome_scope.request_supersession(kind, requested_id))
        turn_scopes, turn_claims = request_lifecycle_turn_supersession(
            kind, requested_id
        )
        claims.extend(turn_claims)
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
        self._quit_kind = kind
        self._quitting = True
        self.prompt_pending.clear()
        if turn_scopes:
            self._wait_for_scope_quiescence(turn_scopes, operation_name)
        if kind == "quit":
            self._on_status("Quit complete", False)
        self.input_queue.put(EOF_SENTINEL)

        if kind == "quit" and self._recovery_required:
            if self._engine_thread is not None:
                self._engine_thread.join()
            self.emit_exit("player_exit", "player quit")

    def note_received_quit(self, operation_id):
        """Signal read-only preflight only; actual Quit still executes FIFO."""
        with self._preflight_guard:
            if self._received_quit_id is None:
                self._received_quit_id = operation_id

    def _check_preflight_quit(self):
        from utils.capture.live_provider_call import LiveProviderSuperseded

        with self._preflight_guard:
            cancelled = self._received_quit_id is not None
        if cancelled:
            raise LiveProviderSuperseded("Load validation cancelled by Quit")

    def _answer_quit_first(self, name, result, quit_id=None):
        from utils.capture.live_provider_call import lifecycle_follower_text

        result(False, data={
            "status": "cancelled",
            "cancelled_by_operation_id": quit_id,
            "state_changed": False,
        }, error=lifecycle_follower_text(name, "quit"), terminal="cancelled")

    def _follow_lifecycle_owner(self, owner, command, result):
        """Follow an earlier Load or Reset to its terminal, never preempting it (#270).

        A restart answers this command from the owner's terminal; otherwise it
        runs again once. A received Quit ends the wait (D-214, B2-ii).
        """
        from utils.capture.live_provider_call import (
            follow_lifecycle_owner,
            leave_lifecycle_owner,
            lifecycle_follower_text,
        )

        name = command.get("name")
        command_id = command.get("id")

        def answer(cause, owner_kind):
            result(False, data={
                "status": "not_run",
                "cause": cause,
                "state_changed": False,
            }, error=lifecycle_follower_text(name, cause, owner_kind), terminal="not run")

        follower = follow_lifecycle_owner(owner, name, command_id, answer)
        if follower is None:
            self.handle_command(command)
            return
        self.writer.emit(
            "operation",
            id=command_id,
            name=name,
            status="accepted_deferred",
            operation_id=str(command_id),
            waiting_for_current_operation=True,
            waiting_for_operation_id=owner.operation_id,
        )
        label = {"save": "Save", "restore": "Load", "reset": "Reset"}[name]
        owner_label = "Reset" if owner.kind == "reset" else "Load"
        elapsed = 0
        while not follower["answered"]:
            with self._preflight_guard:
                quit_id = self._received_quit_id
            # N2: answer only if this command is still ours to answer; once
            # the owner's release has taken it, that release answers it.
            if quit_id is not None and leave_lifecycle_owner(owner, follower):
                self._answer_quit_first(name, result, quit_id)
                return
            if owner.terminal.wait(timeout=1.0):
                break
            elapsed += 1
            self._on_status(
                "%s is waiting for the earlier %s to finish (%ds)"
                % (label, owner_label, elapsed),
                True,
            )
        if not follower["answered"]:
            self.handle_command(command)

    def handle_command(self, command):
        try:
            self._handle_command(command)
        finally:
            if command.get("name") in ("restore", "reset"):
                from utils.capture.live_provider_call import release_lifecycle_owner

                # #270 C4: an owner that leaves before its terminal lets its
                # followers run again; a queued record releases on complete.
                release_lifecycle_owner(str(command.get("id")), keep_queued=True)

    def _handle_command(self, command):
        command_id = command.get("id")
        name = command.get("name")
        args = command.get("args") or {}

        def result(ok, data=None, error=None, terminal=None):
            payload = {"id": command_id, "ok": ok}
            if data is not None:
                payload["data"] = data
            if error is not None:
                payload["error"] = error
            self.writer.emit("result", **payload)
            if name in ("save", "restore", "reset"):
                from utils.capture.live_provider_call import get_lifecycle_turn_scopes

                label = {"save": "Save", "restore": "Load", "reset": "Reset"}[name]
                terminal = terminal or ("complete" if ok else "failed")
                still_working = any(
                    not scope.quiescent.is_set()
                    for scope in get_lifecycle_turn_scopes()
                )
                if name == "save":
                    from utils.capture.live_provider_call import get_active_welcome_scope

                    welcome = get_active_welcome_scope()
                    still_working = still_working or not self.prompt_pending.is_set() or (
                        welcome is not None and not welcome.quiescent.is_set()
                    )
                self._on_status("%s %s" % (label, terminal), still_working)

        if name == "state":
            result(True, data=build_snapshot())
            return
        if name == "quit":
            result(True)
            self.request_quit(operation_id=command.get("_quit_operation_id", command_id))
            return
        if name == "reset":
            if args.get("confirmed") is not True:
                result(False, error="reset requires args.confirmed=true")
                return
            from utils.capture.live_provider_call import (
                claim_lifecycle_owner,
                release_lifecycle_owner,
            )

            holder = claim_lifecycle_owner("reset", command_id)
            if holder is not None:
                self._follow_lifecycle_owner(holder, command, result)
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
                from updates.save_game_manager import SaveGameManager

                self._restore_manager = self._restore_manager or SaveGameManager()
                backup_dir = perform_reset_logic()
                self._recovery_required = False
                result(
                    True,
                    data={
                        "message": "Campaign reset complete",
                        "backup_dir": backup_dir,
                    },
                )
                release_lifecycle_owner(str(command_id), restarting=True)
                self.emit_exit("restart", "campaign reset; relaunch the session")
            except Exception as exc:
                self._recovery_required = True
                result(False, error="%s: %s" % (type(exc).__name__, exc))
                release_lifecycle_owner(str(command_id))
            return

        if self._recovery_required and name not in ("list_saves", "restore"):
            result(False, error="Choose a save to Load, Reset, or Quit before continuing play.")
            return

        from utils.capture.live_provider_call import (
            get_active_welcome_scope,
            get_lifecycle_turn_scopes,
            lifecycle_owner_ahead,
        )

        turn_scopes = get_lifecycle_turn_scopes()
        live_scope = turn_scopes[0] if turn_scopes else None
        # #214: the detached startup welcome is deliberately NOT the live
        # turn scope; persistence commands must still coordinate with its
        # game-thread handback (the readline pump) instead of overlapping it.
        # (Reset needs no welcome branch: it quits+joins the engine first,
        # and request_quit already supersedes/quiesces a pending welcome.)
        welcome_scope = get_active_welcome_scope()
        if name in ("restore", "save") and live_scope is None and welcome_scope is None:
            # A scope can disappear before its engine publishes the next prompt
            # (or exits). Keep this same command until one of those authoritative
            # boundaries exists, rather than losing it to the old busy refusal.
            # Save waits here too, e.g. during startup before any prompt (#346).
            wait_started = time.monotonic()
            while (
                not self._recovery_required
                and not self.prompt_pending.is_set()
                and self._engine_thread is not None
                and self._engine_thread.is_alive()
                # #270: a Load stops waiting once another Load (the model's,
                # applying on the engine thread) owns the lifecycle, and
                # follows that owner from the claim below.
                and not (name == "restore" and lifecycle_owner_ahead(command_id))
            ):
                turn_scopes = get_lifecycle_turn_scopes()
                live_scope = turn_scopes[0] if turn_scopes else None
                welcome_scope = get_active_welcome_scope()
                if live_scope is not None or welcome_scope is not None:
                    break
                self._on_status(
                    "%s is waiting for the current game boundary (%ds)"
                    % ("Save" if name == "save" else "Load",
                       int(time.monotonic() - wait_started)), True,
                )
                self._engine_thread.join(timeout=0.5)
        if (
            name == "save"
            and live_scope is None
            and welcome_scope is None
            and not self.prompt_pending.is_set()
            and not self._recovery_required
            and (self._engine_thread is None or not self._engine_thread.is_alive())
        ):
            result(False, error="The game stopped before Save could run; nothing was saved.")
            return
        busy_persistence = (
            name == "delete_save"
            # #346: a startup welcome can begin before the first prompt; Save
            # queues against it below (#214 F8) instead of refusing busy.
            or (name == "save" and live_scope is None and welcome_scope is None)
        )
        if busy_persistence and not self.prompt_pending.is_set() and not self._recovery_required:
            result(False, error="engine is busy; wait for the next prompt "
                                "event before %s" % name)
            return

        try:
            from updates.save_game_manager import SaveGameManager
            manager = self._restore_manager or SaveGameManager()
            if name == "list_saves":
                result(True, data=manager.list_save_games())
            elif name == "save":
                save_cancelled = False
                def cancel_save(save_id, cause):
                    nonlocal save_cancelled
                    save_cancelled = True
                    self.writer.emit(
                        "result", id=save_id, ok=False,
                        data={"status": "cancelled", "superseding_operation_id": cause["operation_id"]},
                        error="Waiting Save cancelled by %s." % cause["kind"],
                    )

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
                        execute_save, complete_save, command_id,
                        scope=live_scope, cancel=cancel_save,
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

                    if getattr(welcome_scope, "purpose", "") == "maintenance":
                        from utils.capture.live_provider_call import (
                            claim_destructive_operation,
                        )

                        claim = claim_destructive_operation(
                            welcome_scope,
                            "save",
                            execute_welcome_save,
                            complete_welcome_save,
                            operation_id=str(command_id),
                        )
                        if claim["status"] == "queued":
                            welcome_scope.seal_advisory_scopes()
                            self.writer.emit(
                                "operation",
                                id=command_id,
                                name="save",
                                status="accepted_deferred",
                            )
                            return
                        if claim["status"] == "conflict":
                            if claim.get("owner") is not None:
                                self._follow_lifecycle_owner(claim["owner"], command, result)
                                return
                            if claim["kind"] in ("quit", "web_exit"):
                                self._answer_quit_first("save", result, claim["operation_id"])
                                return
                        # #270: a claim whose owner has already ended (or
                        # a closed welcome) runs again after this boundary.
                        welcome_scope.quiescent.wait()
                        self.handle_command(command)
                        return
                        welcome_scope.quiescent.wait()
                        self.handle_command(command)
                        return

                    queued = queue_live_save(
                        execute_welcome_save, complete_welcome_save,
                        command_id, scope=welcome_scope, cancel=cancel_save,
                    )
                    if queued is None:
                        # The welcome sealed before the enqueue: no welcome
                        # remains. Re-resolve authoritative state - queue
                        # against a now-live player turn, else honest retry
                        # (lands on the plain no-welcome path).
                        from utils.capture.live_provider_call import get_live_turn_scope
                        replacement_scope = get_live_turn_scope()
                        if replacement_scope is not None:
                            queued = queue_live_save(
                                execute_welcome_save, complete_welcome_save,
                                command_id, scope=replacement_scope, cancel=cancel_save,
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
                    if save_cancelled:
                        return
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
                from utils.capture.live_provider_call import LiveProviderSuperseded

                try:
                    valid, validation_error = manager.validate_restore_target(
                        folder,
                        include_manifest=True,
                        cancel_check=self._check_preflight_quit,
                    )
                except LiveProviderSuperseded:
                    result(False, data={
                        "status": "cancelled",
                        "cancelled_by_operation_id": self._received_quit_id,
                        "state_changed": False,
                        "message": "Load cancelled before changing the game; Quit is queued.",
                    }, terminal="cancelled")
                    return
                if not valid:
                    result(False, error=validation_error)
                    return
                # Validation is read-only and may overlap a turn boundary.
                # Only now can the current scope reserve destructive work.
                turn_scopes = get_lifecycle_turn_scopes()
                live_scope = turn_scopes[0] if turn_scopes else None
                welcome_scope = get_active_welcome_scope()
                if live_scope is not None and welcome_scope is None:
                    from utils.capture.live_provider_call import (
                        request_live_turn_supersession,
                    )

                    # #270: the owner record, not this flag, decides who
                    # runs; clear the flag only if this command set it.
                    already_reserved = self._restart_in_progress.is_set()
                    self._restart_in_progress.set()
                    may_apply_restore = False
                    supersession_error = None
                    try:
                        operation = request_live_turn_supersession(
                            "restore",
                            str(command_id),
                            scope=live_scope,
                            owner=True,
                        )
                    except Exception as exc:
                        operation = None
                        with live_scope.lock:
                            visible_claim = dict(live_scope.supersession or {})
                        claimed_here = (
                            visible_claim.get("kind") == "restore"
                            and visible_claim.get("operation_id") == str(command_id)
                        )
                        supersession_error = "%s: %s%s" % (
                            type(exc).__name__,
                            exc,
                            " after supersession claim" if claimed_here else "",
                        )
                    else:
                        if operation is None:
                            # No claim was accepted. The captured scope can
                            # disappear while validation runs; wait for that
                            # exact boundary and redispatch the original ID.
                            self._wait_for_scope_quiescence((live_scope,), "Load")
                            if not already_reserved:
                                self._restart_in_progress.clear()
                            self.handle_command(command)
                            return
                        elif operation.get("owner") is not None:
                            if not already_reserved:
                                self._restart_in_progress.clear()
                            self._follow_lifecycle_owner(operation["owner"], command, result)
                            return
                        elif operation.get("kind") == "turn_complete":
                            may_apply_restore = True
                        elif operation.get("accepted"):
                            may_apply_restore = True
                        elif operation.get("kind") in ("quit", "web_exit"):
                            if not already_reserved:
                                self._restart_in_progress.clear()
                            self._answer_quit_first("restore", result, operation.get("operation_id"))
                            return
                        else:
                            # #270: the slot's owner has already ended; run
                            # again once this turn has stopped.
                            self._wait_for_scope_quiescence(turn_scopes, "Load")
                            if not already_reserved:
                                self._restart_in_progress.clear()
                            self.handle_command(command)
                            return
                    if may_apply_restore:
                        self.writer.emit(
                            "operation",
                            id=command_id,
                            name="restore",
                            status="accepted_deferred",
                            operation_id=str(command_id),
                        )
                    self._wait_for_scope_quiescence(turn_scopes, "Load")
                    self._quitting = True
                    self.prompt_pending.clear()
                    self.input_queue.put(EOF_SENTINEL)
                    if self._engine_thread is not None:
                        self._engine_thread.join()
                    if not may_apply_restore:
                        from utils.capture.live_provider_call import release_lifecycle_owner

                        result(False, error=supersession_error)
                        release_lifecycle_owner(str(command_id), restarting=True, cause="stopped")
                        self.emit_exit("error", "state restore did not acquire authority")
                        return
                    self._on_status("Load is applying the selected save", True)
                    outcome = self._apply_restore(manager, folder)
                    self._finish_restore(outcome, manager, result, str(command_id))
                    return
                if live_scope is not None:
                    from utils.capture.live_provider_call import (
                        request_live_turn_supersession,
                    )

                    operation = request_live_turn_supersession(
                        "restore", str(command_id), owner=True
                    )
                    if operation is None:
                        self._wait_for_scope_quiescence(turn_scopes, "Load")
                        self.handle_command(command)
                        return
                    if operation.get("owner") is not None:
                        self._follow_lifecycle_owner(operation["owner"], command, result)
                        return
                    if operation["kind"] == "turn_complete":
                        self._wait_for_scope_quiescence(
                            turn_scopes, "Load"
                        )
                    elif operation["kind"] in ("quit", "web_exit") and not operation["accepted"]:
                        self._answer_quit_first("restore", result, operation["operation_id"])
                        return
                    elif not operation["accepted"]:
                        # #270: the slot's owner has already ended.
                        self._wait_for_scope_quiescence(turn_scopes, "Load")
                        self.handle_command(command)
                        return
                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="restore",
                        status="accepted_deferred",
                        operation_id=operation["operation_id"],
                    )
                    self._wait_for_scope_quiescence(turn_scopes, "Load")
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
                        return self._apply_restore(manager, folder)

                    def complete_welcome_restore(outcome):
                        self._finish_restore(outcome, manager, result, str(command_id))

                    # Claim/promotion AND record insertion are ONE scope-
                    # lock transaction: an accepted destructive claim always
                    # has its executable record queued (seal cannot split
                    # them; never mutate from this control thread).
                    already_reserved = self._restart_in_progress.is_set()
                    self._restart_in_progress.set()
                    claim = claim_destructive_operation(
                        welcome_scope, "restore",
                        execute_welcome_restore, complete_welcome_restore,
                        operation_id=str(command_id), owner=True,
                    )
                    if claim["status"] == "closed":
                        if not already_reserved:
                            self._restart_in_progress.clear()
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
                        if not already_reserved:
                            self._restart_in_progress.clear()
                        if claim.get("owner") is not None:
                            self._follow_lifecycle_owner(claim["owner"], command, result)
                            return
                        if claim["kind"] in ("quit", "web_exit"):
                            self._answer_quit_first("restore", result, claim["operation_id"])
                            return
                        # #270: the slot's owner has already ended; the
                        # same rule as "closed" below.
                        self._wait_for_scope_quiescence(
                            (welcome_scope,), "Load"
                        )
                        self.handle_command(command)
                        return
                    self.writer.emit(
                        "operation",
                        id=command_id,
                        name="restore",
                        status="accepted_deferred",
                        operation_id=claim["operation_id"],
                    )
                    return
                # Even an idle engine holds a projection of the old files.
                # Stop it before application, then let verified disk truth
                # determine restart versus continued recovery command intake.
                from utils.capture.live_provider_call import claim_lifecycle_owner

                holder = claim_lifecycle_owner("restore", command_id)
                if holder is not None:
                    self._follow_lifecycle_owner(holder, command, result)
                    return
                self._restart_in_progress.set()
                self._quitting = True
                self.prompt_pending.clear()
                self.input_queue.put(EOF_SENTINEL)
                if self._engine_thread is not None:
                    self._engine_thread.join()
                outcome = self._apply_restore(manager, folder)
                self._finish_restore(outcome, manager, result, str(command_id))
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
        try:
            from utils.capture.live_provider_call import answer_lifecycle_followers

            # #270 C3 backstop: no follower is left unanswered at the exit.
            answer_lifecycle_followers(
                {"restart": "restart", "player_exit": "quit"}.get(reason, "stopped")
            )
        except Exception:
            pass
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
