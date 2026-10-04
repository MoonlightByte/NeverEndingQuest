"""Configuration wait and terminal controls without loading operator config."""
import ast
import io
import json
from pathlib import Path
import sys
import re
import threading
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import startup_provider_recovery as recovery
from utils.capture import live_provider_call as live


@pytest.mark.parametrize('status,fragment', [(401, 'API key'), (403, 'permissions'), (402, 'credits')])
def test_actionable_status_without_provider_prose(status, fragment):
    exc = SimpleNamespace(http_status=status, envelope={'message': 'irrelevant prose'})
    text = recovery.configuration_required_message(exc)
    assert fragment in text and 'Settings' in text and 'retained' in text


@pytest.mark.parametrize('status', [None, 400, 429, 500])
def test_other_status_does_not_become_configuration_required(status):
    assert recovery.configuration_required_message(SimpleNamespace(http_status=status)) is None


def test_detached_wait_survives_presentation_failure_and_remains_cancellable():
    scope = live.LiveTurnScope()
    emitted = threading.Event()
    failures = []
    revision = recovery.configuration_revision('lmstudio')
    def emit(_message):
        emitted.set()
        raise OSError('Fixture client disconnected')
    def wait():
        try:
            recovery.wait_for_configuration('lmstudio', revision, scope, 'Retained setup', emit)
        except live.LiveProviderSuperseded as exc:
            failures.append(exc)
    worker = threading.Thread(target=wait)
    worker.start()
    try:
        assert emitted.wait(timeout=2)
        assert worker.is_alive() and scope.controls_open
        assert live.get_live_turn_scope() is None
        scope.request_supersession('restore')
    finally:
        scope.request_supersession('restore')
        worker.join(timeout=2)
    assert not worker.is_alive() and len(failures) == 1


def console_handback(inputs):
    source = ast.parse((ROOT / 'utils/startup_wizard.py').read_text(encoding='utf-8'))
    nodes = [node for node in source.body if getattr(node, 'name', None) in
             {'StartupCancelled', '_startup_configuration_handback'}]
    events = []
    answers = iter(inputs)
    namespace = {'web_mode': False, 'input': lambda _prompt: next(answers),
                 '_emit_startup_phase': events.append,
                 'status_manager': SimpleNamespace(update_status=lambda *a: None)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'utils/startup_wizard.py', 'exec'), namespace)
    return namespace, events


def test_terminal_retry_is_explicit_and_does_not_rewrite_choices():
    namespace, events = console_handback(['invalid option', 'retry'])
    scope = live.LiveTurnScope()
    before = recovery.configuration_revision('lmstudio')
    assert namespace['_startup_configuration_handback'](
        live.LiveProviderCompletedError('T092', {'http_status': 401}), 'lmstudio', before, scope)
    assert recovery.configuration_revision('lmstudio') != before
    assert events == ['startup_configuration_required']
    assert scope.controls_open and not scope.is_superseded()


@pytest.mark.parametrize('answer', ['cancel', 'quit', 'exit'])
def test_terminal_cancellation_propagates_to_existing_startup_owner(answer):
    namespace, _ = console_handback([answer])
    before = recovery.configuration_revision('lmstudio')
    with pytest.raises(namespace['StartupCancelled']):
        namespace['_startup_configuration_handback'](
            live.LiveProviderCompletedError('T092', {'http_status': 403}),
            'lmstudio', before, live.LiveTurnScope())
    assert recovery.configuration_revision('lmstudio') == before


def test_actual_web_marker_keeps_startup_in_progress_without_game_started():
    source = ast.parse((ROOT / 'web/web_interface.py').read_text(encoding='utf-8'))
    node = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'WebOutputCapture')
    events = []
    namespace = {'json': json, 're': re,
                 'startup_handoff_active': True, 'startup_ready_emitted': False,
                 'startup_phase': 'startup_review',
                 'socketio': SimpleNamespace(emit=lambda *a: events.append(a))}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'web/web_interface.py', 'exec'), namespace)
    output = namespace['WebOutputCapture'](None, io.StringIO())
    output.write('STARTUP_MARKER: {"phase":"startup_configuration_required"}\n')
    assert namespace['startup_handoff_active']
    assert not namespace['startup_ready_emitted']
    assert events == [('startup_status', {'status': 'in_progress', 'phase': 'startup_configuration_required'})]
