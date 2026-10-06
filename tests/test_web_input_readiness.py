"""Real WebInput/status-manager boundary; no network, model, or player files."""
import ast
import queue
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(monkeypatch):
    from core.managers import status_manager as sm

    provider = ModuleType('utils.capture.live_provider_call')
    provider.LiveProviderSuperseded = type('LiveProviderSuperseded', (Exception,), {})
    provider.superseded = False
    def boundary():
        if provider.superseded:
            raise provider.LiveProviderSuperseded('restore accepted')
        return False
    provider.service_live_input_boundary = boundary
    provider.get_live_turn_scope = lambda: None
    monkeypatch.setitem(sys.modules, provider.__name__, provider)
    manager = sm.StatusManager()
    events = []
    manager.set_callback(lambda text, busy: events.append(busy))
    monkeypatch.setattr(sm, 'status_manager', manager)
    monkeypatch.setattr(sm, '_input_poll_hook', None)
    paused = [False]
    source = ROOT / 'web/web_interface.py'
    node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                if isinstance(n, ast.ClassDef) and n.name == 'WebInput')
    env = {'queue': queue, '_web_gameplay_paused': lambda: paused[0]}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), env)
    return SimpleNamespace(sm=sm, manager=manager, events=events, provider=provider,
                           paused=paused, Input=env['WebInput'])


def test_quest_handback_reopens_parked_input_and_accepts_next_command(runtime):
    r = runtime
    q = queue.Queue()
    entered, finish, ready = threading.Event(), threading.Event(), threading.Event()
    def hook():
        r.sm.status_updating_plot()  # actual status used by startup updatePlot
        entered.set()
        assert finish.wait(3)
        r.sm.set_input_poll_hook(None)
    r.sm.set_input_poll_hook(hook)
    r.manager.set_callback(lambda text, busy: (r.events.append(busy), ready.set() if entered.is_set() and not busy else None))
    result = []
    worker = threading.Thread(target=lambda: result.append(r.Input(q).readline()))
    worker.start()
    try:
        assert entered.wait(3)
        assert r.manager.is_processing()  # cannot unlock during quest application
        assert not ready.is_set()
        finish.set()
        assert ready.wait(3), 'completed welcome left command box locked'
        q.put('Look around')
        worker.join(3)
        assert not worker.is_alive() and result == ['Look around\n']
        assert r.events == [False, True, False]
        # A real subsequent turn still owns its busy state; no timer clears it.
        r.sm.status_processing_ai()
        assert r.manager.is_processing()
    finally:
        finish.set()
        q.put(None)
        worker.join(3)


@pytest.mark.parametrize('stop', ['paused', 'superseded'])
def test_lifecycle_control_during_handback_does_not_reopen_input(runtime, stop):
    r = runtime
    def hook():
        r.sm.status_updating_plot()
        if stop == 'paused':
            r.paused[0] = True
        else:
            r.provider.superseded = True
    r.sm.set_input_poll_hook(hook)
    with pytest.raises(r.provider.LiveProviderSuperseded):
        r.Input(queue.Queue()).readline()
    assert r.events == [False, True]


def test_idle_poll_does_not_flood_status_events(runtime):
    r = runtime
    q = queue.Queue()
    polls = []
    def hook():
        polls.append(1)
        if len(polls) == 2:
            q.put('Inventory')
    r.sm.set_input_poll_hook(hook)
    assert r.Input(q).readline() == 'Inventory\n'
    assert r.events == [False]


def test_startup_reclaims_callback_before_a_fast_worker_can_report_ready():
    source = ROOT / 'web/web_interface.py'
    node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == 'handle_start_game')
    node.decorator_list = []
    events = []
    callbacks = []
    def start():
        assert callbacks == [emit_status]
        events.append('ready')
    emit_status = lambda *args: None
    env = dict(game_thread=None, _web_gameplay_paused=lambda: False,
               uninstall_debug_interceptor=lambda: None,
               sys=SimpleNamespace(), WebOutputCapture=lambda *a, **kw: None,
               debug_output_queue=None, original_stdout=None, original_stderr=None,
               WebInput=lambda q: None, user_input_queue=None,
               set_player_output_sink=lambda sink: None, _queue_safe_player_output=None,
               set_status_callback=callbacks.append, emit_status_update=emit_status,
               load_message_cache=lambda **kw: None,
               threading=SimpleNamespace(Thread=lambda **kw: SimpleNamespace(start=start)),
               run_game_loop=lambda: None,
               emit=lambda event, payload: events.append(payload['phase']))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), env)
    env['handle_start_game']()
    assert events == ['launching', 'ready']
