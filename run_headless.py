#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Headless CLI mode: drive the full game engine without the HTML interface.

Primary agentic mode (NDJSON protocol on stdio; see docs/HEADLESS_MODE.md):
    python run_headless.py serve [--game-dir DIR] [--debug]
                                 [--module NAME --character FILE]

CI-style scripted smoke (feeds inputs, enforces a per-turn silence timeout):
    python run_headless.py script inputs.txt [--max-turns N]
                                 [--timeout-per-turn SECONDS] [...]

No-engine utilities:
    python run_headless.py state    [--game-dir DIR]
    python run_headless.py new-game --module NAME --character FILE [--game-dir DIR]
    python run_headless.py saves    {list|create|restore|delete} [...]

Exit codes: 0 clean (player_exit / engine_stop / restart), 2 engine error,
3 per-turn timeout (script mode), 4 bootstrap/usage error.
"""

import argparse
import json
import os
import sys
import threading
import time

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.headless.protocol import ProtocolWriter, parse_command_line

EXIT_OK = 0
EXIT_ENGINE_ERROR = 2
EXIT_TIMEOUT = 3
EXIT_BOOTSTRAP = 4

_EXIT_CODE_BY_REASON = {
    "player_exit": EXIT_OK,
    "engine_stop": EXIT_OK,
    "restart": EXIT_OK,
    "error": EXIT_ENGINE_ERROR,
}


class ServeDriver:
    """Interactive driver: agent commands arrive on the real stdin."""

    def __init__(self, real_stdin):
        self._real_stdin = real_stdin
        self._session = None

    def on_event(self, event):
        pass

    def start(self, session):
        self._session = session
        reader = threading.Thread(
            target=self._read_loop, name="headless-agent-stdin", daemon=True)
        reader.start()

    def _read_loop(self):
        try:
            for line in self._real_stdin:
                self._dispatch_line(line)
        except Exception:
            pass
        # Agent closed our stdin: treat as quit.
        try:
            self._session.request_quit()
        except Exception:
            pass

    def _dispatch_line(self, line):
        message, parse_error = parse_command_line(line)
        if parse_error:
            self._session.writer.emit(
                "result", id=None, ok=False, error=parse_error)
            return
        if message is None:
            return
        if message["type"] == "input":
            self._session.dispatch_input(message["content"])
        else:
            self._session.handle_command(message)

    def wait(self, done, last_activity, timeout_per_turn=None):
        done.wait()
        return None  # exit code comes from the exit event reason


class ScriptDriver:
    """Scripted driver: answers each prompt from a fixed input list."""

    def __init__(self, inputs, max_turns):
        self._inputs = list(inputs)
        self._max_turns = max_turns
        self._sent = 0
        self._session = None
        self._finished = False

    def on_event(self, event):
        if event.get("type") != "prompt" or self._session is None:
            return
        if self._finished:
            return
        if not self._inputs or self._sent >= self._max_turns:
            self._finished = True
            self._session.request_quit()
            return
        self._sent += 1
        self._session.dispatch_input(self._inputs.pop(0))

    def start(self, session):
        self._session = session

    def wait(self, done, last_activity, timeout_per_turn=None):
        while not done.wait(0.5):
            if timeout_per_turn and \
                    time.time() - last_activity[0] > timeout_per_turn:
                self._session.writer.emit(
                    "exit", reason="error",
                    detail="no engine activity for %ss (per-turn timeout)"
                           % timeout_per_turn)
                return EXIT_TIMEOUT
        return None


def _run_session(args, driver, timeout_per_turn=None):
    from core.headless.bootstrap import BootstrapError
    from core.headless.session import HeadlessSession

    real_stdout = sys.stdout
    done = threading.Event()
    last_activity = [time.time()]
    exit_reason = ["engine_stop"]

    def observer(event):
        last_activity[0] = time.time()
        try:
            driver.on_event(event)
        except Exception:
            pass
        if event.get("type") == "exit":
            exit_reason[0] = event.get("reason", "error")
            done.set()

    writer = ProtocolWriter(real_stdout, observer=observer)
    session = HeadlessSession(
        REPO_ROOT, game_dir=args.game_dir, debug=args.debug, writer=writer)
    try:
        try:
            session.bootstrap(
                character_file=getattr(args, "character", None),
                module=getattr(args, "module", None))
            session.start_engine()
        except BootstrapError as exc:
            writer.emit("exit", reason="error", detail=str(exc))
            return EXIT_BOOTSTRAP
        driver.start(session)
        forced_code = driver.wait(done, last_activity, timeout_per_turn)
        if forced_code is not None:
            return forced_code
        return _EXIT_CODE_BY_REASON.get(exit_reason[0], EXIT_ENGINE_ERROR)
    finally:
        session.restore_streams()


def cmd_serve(args):
    return _run_session(args, ServeDriver(sys.stdin))


def cmd_script(args):
    try:
        with open(args.inputs, "r", encoding="utf-8") as handle:
            inputs = [line.rstrip("\n") for line in handle
                      if line.strip() and not line.lstrip().startswith("#")]
    except OSError as exc:
        print(json.dumps({"type": "exit", "reason": "error",
                          "detail": "cannot read inputs file: %s" % exc}))
        return EXIT_BOOTSTRAP
    driver = ScriptDriver(inputs, args.max_turns)
    return _run_session(args, driver, timeout_per_turn=args.timeout_per_turn)


def cmd_state(args):
    if args.game_dir:
        os.chdir(args.game_dir)
    from core.headless.state_reader import build_snapshot
    print(json.dumps(build_snapshot(), indent=2, ensure_ascii=True))
    return EXIT_OK


def cmd_new_game(args):
    from core.headless import bootstrap as bootstrap_mod
    try:
        bootstrap_mod.ensure_config(REPO_ROOT)
        bootstrap_mod.prepare_game_dir(
            args.game_dir or REPO_ROOT, REPO_ROOT, module=args.module)
        os.chdir(args.game_dir or REPO_ROOT)
        bootstrap_mod.ensure_runtime_dirs()
        bootstrap_mod.run_engine_prechecks()
        name = bootstrap_mod.seed_character(args.character, args.module)
    except bootstrap_mod.BootstrapError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return EXIT_BOOTSTRAP
    print(json.dumps({"ok": True, "character": name, "module": args.module,
                      "game_dir": os.getcwd()}))
    return EXIT_OK


def cmd_build_module(args):
    from core.headless.bootstrap import (
        BootstrapError, ensure_config, prepare_game_dir)
    from core.headless.streams import HeadlessOutputCapture
    from core.headless.protocol import ProtocolWriter

    real_streams = (sys.stdout, sys.stderr)
    writer = ProtocolWriter(real_streams[0])

    narrative = args.narrative
    if args.narrative_file:
        try:
            with open(args.narrative_file, "r", encoding="utf-8") as handle:
                narrative = handle.read()
        except OSError as exc:
            writer.emit("build_error",
                        error="cannot read narrative file: %s" % exc)
            return EXIT_BOOTSTRAP
    if not narrative or not narrative.strip():
        writer.emit("build_error",
                    error="--narrative or --narrative-file is required")
        return EXIT_BOOTSTRAP

    try:
        ensure_config(REPO_ROOT)
        if args.game_dir:
            prepare_game_dir(args.game_dir, REPO_ROOT)
            os.chdir(args.game_dir)
    except BootstrapError as exc:
        writer.emit("build_error", error=str(exc))
        return EXIT_BOOTSTRAP

    def on_stream(kind, **fields):
        if args.debug:
            if kind == "debug":
                writer.emit("debug", **fields)
            else:
                writer.emit("debug", content=json.dumps(fields),
                            is_error=False)

    os.makedirs(os.path.join("modules", "logs"), exist_ok=True)
    raw_log = open(os.path.join("modules", "logs", "headless_raw.log"),
                   "a", encoding="utf-8", errors="replace")
    sys.stdout = HeadlessOutputCapture(on_stream, raw_log)
    sys.stderr = HeadlessOutputCapture(on_stream, raw_log, is_error=True)
    try:
        from core.ai.module_creation_contract import normalize_user_module_name
        from core.generators.module_builder import (
            ModuleCreationCancelledError,
            ModuleCreationFailedError,
            ai_driven_module_creation,
        )
        # These imports can pull in web_interface, which installs a
        # newline-dropping stdout interceptor over our shim; remove it.
        try:
            from utils.redirect_debug_output import uninstall_debug_interceptor
            uninstall_debug_interceptor()
        except ImportError:
            pass

        module_name = normalize_user_module_name(args.name) or "New_Module"

        def progress_callback(payload):
            writer.emit("module_progress", **dict(payload))
            return True

        params = {
            "narrative": narrative,
            "module_name": module_name,
            "num_areas": args.areas,
            "locations_per_area": args.locations_per_area,
        }
        success, created_name = ai_driven_module_creation(
            params, progress_callback=progress_callback, policy="toolkit")
        if not success or not created_name:
            raise RuntimeError("Module generation failed")
        writer.emit("build_complete", module_name=created_name)
        return EXIT_OK
    except ModuleCreationCancelledError:
        writer.emit("build_error", error="Module generation cancelled.",
                    cancelled=True)
        return EXIT_ENGINE_ERROR
    except Exception as exc:
        writer.emit("build_error", error=str(exc))
        return EXIT_ENGINE_ERROR
    finally:
        flush_shim = sys.stdout
        sys.stdout, sys.stderr = real_streams
        try:
            flush_shim.flush()
        except Exception:
            pass
        try:
            raw_log.close()
        except Exception:
            pass


def cmd_saves(args):
    if args.game_dir:
        os.chdir(args.game_dir)
    from updates.save_game_manager import SaveGameManager
    manager = SaveGameManager()
    if args.saves_action == "list":
        print(json.dumps({"ok": True, "saves": manager.list_save_games()},
                         indent=2, ensure_ascii=True))
        return EXIT_OK
    if args.saves_action == "create":
        ok, message = manager.create_save_game(
            description=args.description, save_mode=args.save_mode)
    elif args.saves_action == "restore":
        ok, message = manager.restore_save_game(args.save_folder)
    else:  # delete
        ok, message = manager.delete_save_game(args.save_folder)
    print(json.dumps({"ok": bool(ok), "message": message}))
    return EXIT_OK if ok else EXIT_ENGINE_ERROR


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_headless.py",
        description="Headless CLI mode for agentic automation and testing.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    def add_common(sub, with_seed=True):
        sub.add_argument("--game-dir", default=None,
                         help="isolated game directory (default: repo root)")
        sub.add_argument("--debug", action="store_true",
                         help="emit debug events on the protocol stream")
        if with_seed:
            sub.add_argument("--module", default=None,
                             help="module name for character seeding")
            sub.add_argument("--character", default=None,
                             help="path to a character JSON to seed "
                                  "(skips the startup wizard)")

    serve = subparsers.add_parser(
        "serve", help="interactive NDJSON session on stdio")
    add_common(serve)
    serve.set_defaults(func=cmd_serve)

    script = subparsers.add_parser(
        "script", help="feed newline-separated inputs, then exit")
    script.add_argument("inputs", help="text file: one player input per line")
    script.add_argument("--max-turns", type=int, default=50)
    script.add_argument("--timeout-per-turn", type=float, default=300.0,
                        help="max seconds of engine silence before aborting")
    add_common(script)
    script.set_defaults(func=cmd_script)

    state = subparsers.add_parser(
        "state", help="print a state snapshot without starting the engine")
    state.add_argument("--game-dir", default=None)
    state.set_defaults(func=cmd_state)

    new_game = subparsers.add_parser(
        "new-game", help="bootstrap config + fixture + character, no engine")
    new_game.add_argument("--module", required=True)
    new_game.add_argument("--character", required=True)
    new_game.add_argument("--game-dir", default=None)
    new_game.set_defaults(func=cmd_new_game)

    build = subparsers.add_parser(
        "build-module", help="generate an adventure module (toolkit policy)")
    build.add_argument("--name", required=True,
                       help="module name (normalized to contract form)")
    build.add_argument("--narrative", default=None,
                       help="module concept text")
    build.add_argument("--narrative-file", default=None,
                       help="file containing the module concept")
    build.add_argument("--areas", type=int, default=5)
    build.add_argument("--locations-per-area", type=int, default=3)
    build.add_argument("--game-dir", default=None)
    build.add_argument("--debug", action="store_true")
    build.set_defaults(func=cmd_build_module)

    saves = subparsers.add_parser("saves", help="save-game management")
    saves.add_argument("saves_action",
                       choices=["list", "create", "restore", "delete"])
    saves.add_argument("--game-dir", default=None)
    saves.add_argument("--description", default="")
    saves.add_argument("--save-mode", default="essential",
                       choices=["essential", "full"])
    saves.add_argument("--save-folder", default=None)
    saves.set_defaults(func=cmd_saves)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.subcommand in ("saves",) and \
            args.saves_action in ("restore", "delete") and not args.save_folder:
        print(json.dumps({"ok": False,
                          "error": "--save-folder is required"}))
        return EXIT_BOOTSTRAP
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
