"""#1342 through a real provider child and the real SDK, with no network.

The provider is the local/custom server (no key; an empty key is sent). The
HTTP layer is the fixture's mock transport, so every status and connection
failure is played without a socket. Run under a loopback-only namespace.
"""
import json
import os
import shutil
import sys

import pytest

from provider_subprocess_fixture import ROOT, SITE_CUSTOMIZE, _run_fixture_worker, installed_openai_sdk  # noqa: F401

WORKER = r'''
import json
from pathlib import Path
from core.ai import api_client
from utils.capture import multi_model_capture as capture, live_provider_call as live
scenario = json.loads(Path('scenario.json').read_text())
original_wait = live._interruptible_wait
live._interruptible_wait = lambda seconds, *a, **k: original_wait(min(seconds, 0.02), *a, **k)
waits = []
live_wait = live._interruptible_wait
live._interruptible_wait = lambda seconds, *a, **k: (waits.append(seconds), live_wait(seconds, *a, **k))
scope = live.LiveTurnScope()
scope.provider_generations = scenario.get('used', 0)
try:
    response = capture.capture_and_fanout(
        'T092', api_client.create_completion,
        messages=[{'role': 'user', 'content': 'Fixture'}], model='ignored',
        _request_provider='lmstudio', _detached_scope=scope,
        _detached_status=lambda _m: None, _live_selected='required')
    result = {'kind': 'success', 'content': response.choices[0].message.content}
except Exception as exc:
    envelope = getattr(exc, 'envelope', None) or {}
    result = {'kind': type(exc).__name__, 'limit': envelope.get('error_class')}
result.update(generations=scope.provider_generations, max_wait=max(waits or [0]))
Path('result.json').write_text(json.dumps(result))
'''


@pytest.fixture
def child_case(tmp_path, installed_openai_sdk):  # noqa: F811
    for name in ('core', 'utils'):
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for path in ROOT.glob('*.py'):
        if path.name != 'config.py':
            shutil.copy2(path, tmp_path / path.name)
    # No key anywhere: config re-exports model settings only.
    (tmp_path / 'config.py').write_text("from model_config import *\n")
    (tmp_path / 'keyring.py').write_text(
        "def get_keyring(): raise RuntimeError('No credential backend in fixture')\n")
    (tmp_path / 'sitecustomize.py').write_text(SITE_CUSTOMIZE)
    (tmp_path / 'worker.py').write_text(WORKER)

    def run(plan, scenario=None, host='fixture.invalid'):
        (tmp_path / 'user_settings.json').write_text(json.dumps({
            'model_provider': 'lmstudio', 'local_base_url': 'https://%s/v1' % host,
            'local_model': 'fixture/model', 'local_api_key': ''}))
        (tmp_path / 'scenario.json').write_text(json.dumps(scenario or {}))
        (tmp_path / 'http-plan.json').write_text(json.dumps(plan))
        requests = tmp_path / 'http-requests.jsonl'
        if requests.exists():
            requests.unlink()
        env = {key: value for key, value in os.environ.items() if key.upper() in
               {'PATH', 'SYSTEMROOT', 'WINDIR', 'LANG', 'LC_ALL', 'TEMP', 'TMP', 'TMPDIR', 'LD_LIBRARY_PATH'}}
        env.update(PYTHONPATH=os.pathsep.join((str(tmp_path), str(installed_openai_sdk))),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                   NEQ_MULTI_MODEL_CAPTURE='0', NEQ_MODEL_EVAL_PRIMARY='')
        proc = _run_fixture_worker([sys.executable, str(tmp_path / 'worker.py')],
                                   cwd=tmp_path, env=env, timeout=60)
        assert proc.returncode == 0, proc.stderr
        result = json.loads((tmp_path / 'result.json').read_text())
        result['requests'] = len(requests.read_text().splitlines()) if requests.exists() else 0
        return result
    return run


def test_server_errors_end_at_the_free_limit(child_case):
    result = child_case({'statuses': [503]})
    assert result['kind'] == 'LiveProviderCompletedError' and result['limit'] == 'reissue_limit'
    assert result['requests'] == 7 and result['generations'] == 7


def test_rate_limit_429_ends_at_the_free_limit_without_sixty_second_waits(child_case):
    result = child_case({'statuses': [429]})
    assert result['limit'] == 'reissue_limit' and result['requests'] == 7
    assert result['max_wait'] <= 8.0


def test_unreachable_host_ends_at_the_free_limit(child_case):
    # The netblock case: every connection fails before a request is sent.
    result = child_case({}, host='unavailable.invalid')
    assert result['limit'] == 'reissue_limit' and result['generations'] == 7


def test_refused_401_is_one_request(child_case):
    result = child_case({'statuses': [401]})
    assert result['kind'] == 'LiveProviderCompletedError' and result['requests'] == 1


def test_recovery_inside_the_limit_returns(child_case):
    result = child_case({'statuses': [503] * 6 + [200], 'content': 'recovered'})
    assert result == dict(result, kind='success', content='recovered', requests=7)


def test_turn_ceiling_sends_nothing(child_case):
    result = child_case({'statuses': [200]}, scenario={'used': 24})
    assert result['limit'] == 'turn_call_ceiling' and result['requests'] == 0
