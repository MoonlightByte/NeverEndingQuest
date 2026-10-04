"""Real SDK + spawned provider recovery; synthetic HTTP and no paid network.

The shared fixture is copied from PR558's process-contained, 25-second harness.
It stages the installed SDK unchanged and forbids socket connections in both
the game worker and its provider child. No operator configuration is copied.
"""
import json
from pathlib import Path

import pytest

from provider_subprocess_fixture import installed_openai_sdk, run_case


CONTENT = {
    'interview': 'Choose your background.',
    'review': json.dumps({'version': 1, 'accepted': True, 'feedback': '',
                          'needs_player_clarification': False}),
    'location': json.dumps({'areaId': 'A', 'areaName': 'Proposed name',
                           'locationId': 'A01', 'locationName': 'Proposed entry',
                           'weather': 'Clear', 'politicalClimate': 'Calm'}),
}

# Execute actual wizard and production Settings handler bodies on the worker's
# UI thread. Unrelated Flask/game bootstrap is not imported in this fixture.
RECOVERY_WORKER = r'''
from utils import startup_provider_recovery as recovery
from utils import startup_wizard as wizard
import ast
wizard.web_mode = True
source = ast.parse(Path('web/web_interface.py').read_text(encoding='utf-8'))
handler_names = {'handle_set_local_endpoint', 'handle_set_provider'}
nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in handler_names]
for node in nodes: node.decorator_list = []
ui_events = []
ui = {'emit': lambda event, payload, **kw: ui_events.append((event, payload)),
      'debug': lambda *a, **kw: None, 'error': lambda *a, **kw: None,
      '_provider_selection_lock': threading.Lock()}
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'web/web_interface.py', 'exec'), ui)
configuration_messages = []
wait_observations = []
original_wait_config = recovery.wait_for_configuration
def wait_config(provider, revision, target_scope, message, emit):
    configuration_messages.append(message)
    def controls():
        before = len(Path('http-requests.jsonl').read_text().splitlines())
        time.sleep(0.25)  # No periodic request, even beyond several test heartbeats.
        recovery.notify_configuration_saved('gemini')
        time.sleep(0.15)  # An unrelated provider save must not release the wait.
        assert len(Path('http-requests.jsonl').read_text().splitlines()) == before
        wait_observations.append({'requests': before,
            'children_reaped': all(p.poll() is not None for p in children),
            'scope_live': target_scope.controls_open and not target_scope.is_superseded()})
        if scenario.get('wait_action') == 'cancel':
            target_scope.request_supersession(scenario.get('cancel_kind', 'reset'))
        elif scenario.get('wait_action') == 'switch':
            ui['handle_set_provider']({'provider': 'legacy'})
        else:
            if scenario.get('fail_save'):
                original_persist = model_config.persist_local_endpoint
                model_config.persist_local_endpoint = lambda **kw: (_ for _ in ()).throw(OSError('Fixture write failed'))
                ui['handle_set_local_endpoint']({'api_key': 'fixture-token'})
                model_config.persist_local_endpoint = original_persist
                time.sleep(0.15)
                assert len(Path('http-requests.jsonl').read_text().splitlines()) == before
            ep = model_config.get_local_endpoint()
            ui['handle_set_local_endpoint']({'base_url': ep['base_url'], 'model': ep['model'],
                                            'api_key': 'fixture-token' if scenario.get('correct_key') else ''})
    control = threading.Thread(target=controls, daemon=True)
    control.start()
    try:
        return original_wait_config(provider, revision, target_scope, message, emit)
    finally:
        control.join(timeout=3)
recovery.wait_for_configuration = wait_config
'''


@pytest.fixture
def recovery_case(run_case, tmp_path):
    # run_case has finished preparing the temporary public source installation.
    worker = tmp_path / 'worker.py'
    text = worker.read_text()
    text = text.replace("result={}\ntry:", RECOVERY_WORKER + "\nresult={}\ntry:")
    text = text.replace("result.update(envelopes=", "result.update(configuration_messages=configuration_messages, wait_observations=wait_observations, ui_events=ui_events, envelopes=")
    text = text.replace("if len(envelopes)>=3:", "if len(envelopes)>=scenario.get('fixture_generation_guard', 3):")
    text = text.replace("live_scope=scope)", "live_scope=None if scenario.get('owned') else scope)")
    # Mid/trailing system messages reproduced the extra auth POST. Keep them
    # in every auth attempt; successful recovery must preserve them unchanged.
    text = text.replace("'content':'I choose a fighter.'}]", "'content':'I choose a fighter.'},{'role':'system','content':'Retain my fighter choice.'}]")
    text = text.replace("            if scenario['wizard']=='interview':", "            if scenario.get('canonical_messages'): conversation=conversation[:2]\n            if scenario['wizard']=='interview':")
    worker.write_text(text)
    # Handler source is installed separately; the fixture copies core/utils only.
    from provider_subprocess_fixture import ROOT
    (tmp_path / 'web').mkdir()
    (tmp_path / 'web/web_interface.py').write_text((ROOT / 'web/web_interface.py').read_text(encoding='utf-8'), encoding='utf-8')
    return run_case


@pytest.mark.parametrize('wizard', CONTENT)
@pytest.mark.parametrize('status', [401, 403, 402])
def test_actual_startup_waits_for_config_save_and_recovers(recovery_case, wizard, status):
    result = recovery_case({'wizard': wizard, 'fail_save': True},
                           {'statuses': [status, 200], 'content': CONTENT[wizard]})
    assert result['kind'] == 'success', result
    assert result['children'] == 2
    assert len(result['http_requests']) == 2
    assert len(result['configuration_messages']) == 1
    message = result['configuration_messages'][0]
    assert str(status) in message and 'Settings' in message and 'retained' in message
    assert ('credits' in message) == (status == 402)
    assert result['wait_observations'] == [{'requests': 1, 'children_reaped': True, 'scope_live': True}]
    assert result['http_requests'][0]['body'] == result['http_requests'][1]['body']
    assert len(result['usage_rows']) == 1
    assert result['usage_rows'][0]['total_tokens'] == 7
    if wizard == 'location':
        assert json.loads(result['content'])['locationName'] == 'Fixture Entry'


@pytest.mark.parametrize('wizard', CONTENT)
@pytest.mark.parametrize('cancel_kind', ['reset', 'restore', 'web_exit'])
def test_configuration_wait_cancels_without_another_post(recovery_case, wizard, cancel_kind):
    result = recovery_case({'wizard': wizard, 'wait_action': 'cancel', 'cancel_kind': cancel_kind},
                           {'statuses': [401], 'content': CONTENT[wizard]})
    assert result['kind'] == 'LiveProviderSuperseded', result
    assert result['children'] == 1
    assert len(result['http_requests']) == 1
    assert not result['usage_rows']


def test_corrected_credentials_start_new_request(recovery_case):
    result = recovery_case({'wizard': 'interview', 'correct_key': True},
                           {'require_key': True, 'content': CONTENT['interview']},
                           {'local_api_key': 'deliberately-invalid-fixture-key'})
    assert result['kind'] == 'success', result
    assert result['children'] == 2
    assert [r['auth_matches'] for r in result['http_requests']] == [False, True]
    assert len(result['usage_rows']) == 1
    assert result['http_requests'][0]['body'] == result['http_requests'][1]['body']


@pytest.mark.parametrize('wizard', CONTENT)
def test_provider_selection_resumes_with_new_provider(recovery_case, wizard):
    result = recovery_case({'wizard': wizard, 'wait_action': 'switch'},
                           {'statuses': [403, 200], 'content': CONTENT[wizard]})
    assert result['kind'] == 'success', result
    assert 'openrouter.invalid' in result['http_requests'][0]['url']
    assert 'openrouter.invalid' not in result['http_requests'][1]['url']
    assert result['envelopes'][1]['provider'] == 'legacy'
    assert len(result['usage_rows']) == 1


@pytest.mark.parametrize('status', [429, 503])
def test_transient_transport_policy_does_not_enter_config_wait(recovery_case, status):
    result = recovery_case({'wizard': 'interview', 'canonical_messages': True},
                           {'statuses': [status, 200], 'content': CONTENT['interview']})
    assert result['kind'] == 'success', result
    assert not result['configuration_messages']
    assert result['http_requests'][0]['body'] == result['http_requests'][1]['body']
    assert len(result['usage_rows']) == 1


def test_jinja_400_keeps_existing_template_repair(recovery_case):
    result = recovery_case({'wizard': 'interview'},
                           {'statuses': [400, 200], 'content': CONTENT['interview']})
    assert result['kind'] == 'success', result
    assert result['children'] == 1
    assert len(result['http_requests']) == 2
    assert not result['configuration_messages']
    assert [m['role'] for m in result['http_requests'][0]['body']['messages']] == ['system', 'user', 'system']
    assert [m['role'] for m in result['http_requests'][1]['body']['messages']] == ['system', 'user', 'user']
    assert len(result['usage_rows']) == 1


def test_completed_400_keeps_callers_model_correction(recovery_case):
    result = recovery_case({'wizard': 'location'},
                           {'statuses': [400, 200], 'content': CONTENT['location']})
    assert result['kind'] == 'success', result
    assert result['children'] == 2
    assert not result['configuration_messages']
    messages = result['http_requests'][1]['body']['messages']
    assert messages[0] == result['http_requests'][0]['body']['messages'][0]
    assert messages[-1]['role'] == 'system'
    assert 'Retain the task' in messages[-1]['content']
    assert len(result['usage_rows']) == 1


def test_connection_failure_keeps_transport_recovery(recovery_case, tmp_path):
    site = tmp_path / 'sitecustomize.py'
    text = site.read_text().replace("    if plan.get('overlap'):",
        "    if calls == 1:\n        raise httpx.ConnectError('Fixture lost connection', request=request)\n    if plan.get('overlap'):")
    site.write_text(text)
    result = recovery_case({'wizard': 'interview'}, {'content': CONTENT['interview']})
    assert result['kind'] == 'success', result
    assert result['envelopes'][0]['disposition'] == 'retryable_transport'
    assert not result['configuration_messages']
    assert result['children'] == 2
    assert len(result['usage_rows']) == 1


def test_owned_game_scope_recovers_and_closes_cleanly(recovery_case):
    result = recovery_case({'wizard': 'interview', 'owned': True},
                           {'statuses': [401, 200], 'content': CONTENT['interview']})
    assert result['kind'] == 'success', result
    assert result['wait_observations'][0]['scope_live']
    assert result['global_scope_untouched']
    assert len(result['usage_rows']) == 1


def test_owned_game_scope_cancel_reaches_quiescence(recovery_case):
    result = recovery_case({'wizard': 'interview', 'owned': True, 'wait_action': 'cancel'},
                           {'statuses': [403], 'content': CONTENT['interview']})
    assert result['kind'] == 'LiveProviderSuperseded', result
    assert result['global_scope_untouched']
    assert result['children'] == 1
    assert not result['usage_rows']


def test_repeated_refusal_requires_another_deliberate_save(recovery_case):
    result = recovery_case({'wizard': 'interview', 'fixture_generation_guard': 4},
                           {'statuses': [401, 403, 200], 'content': CONTENT['interview']})
    assert result['kind'] == 'success', result
    assert result['children'] == 3
    assert len(result['configuration_messages']) == 2
    assert [r['requests'] for r in result['wait_observations']] == [1, 2]
    assert len(result['usage_rows']) == 1
