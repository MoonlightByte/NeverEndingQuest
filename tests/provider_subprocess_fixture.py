"""Real provider subprocess/SDK regressions, isolated from operator settings.

The fake HTTP transport speaks SSE/JSON; socket connections are forbidden. No
credentials, keyring contents or live game files are read. Both the parent and
its real provider child run from a temporary copy of the public Python sources.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(os.environ.get("NEQ_PROVIDER_TEST_ROOT", Path(__file__).resolve().parents[1]))


def _run_fixture_worker(command, *, cwd, env, timeout=25):
    """Contain this fixture's descendants, including on timeout/Ctrl-C.

    subprocess.run(timeout=...) only kills the direct worker. Its provider
    child can survive and retain the captured pipes. Never search for or kill
    unrelated Python processes: the group/tree here belongs to this Popen.
    """
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=os.name == 'posix',
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # Also covers an exited worker with a surviving provider child.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            # The root is still our owned Popen; /T includes its descendants.
            try:
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    capture_output=True, timeout=5, check=False,
                )
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for pipe in (process.stdout, process.stderr):
            pipe.close()


@pytest.fixture(scope='session')
def installed_openai_sdk(tmp_path_factory):
    """Stage the installed SDK unchanged, outside the per-case deadline.

    OpenAI 3.x imports over a thousand small files. On WSL /mnt/c, parent +
    fresh-child imports alone can exceed 25 seconds. A session-local copy on
    pytest's temp filesystem removes that I/O assumption without extending
    deadlines, changing SDK versions or bypassing real child/SDK execution.
    """
    spec = importlib.util.find_spec('openai')
    assert spec and spec.submodule_search_locations, 'Install the OpenAI SDK to run these tests'
    destination = tmp_path_factory.mktemp('installed-openai-sdk')
    shutil.copytree(
        next(iter(spec.submodule_search_locations)), destination / 'openai',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'),
    )
    return destination

SITE_CUSTOMIZE = r'''
import json, socket, httpx
from pathlib import Path

def forbidden(*a, **k):
    raise AssertionError("External networking forbidden in provider fixture")
socket.socket.connect = forbidden
socket.create_connection = forbidden

def handler(request):
    body = json.loads(request.content)
    plan = json.loads(Path("http-plan.json").read_text())
    auth = request.headers.get("Authorization") or request.headers.get("x-goog-api-key")
    record = {"url": str(request.url), "body": body,
              "auth_matches": auth in ("Bearer fixture-token", "fixture-token"),
              "pid": __import__('os').getpid()}
    with Path("http-requests.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    calls = len(Path("http-requests.jsonl").read_text().splitlines())
    if plan.get('overlap'):
        import time, os
        Path('overlap').mkdir(exist_ok=True)
        Path('overlap',str(os.getpid())).touch()
        deadline=time.monotonic()+5
        while len(list(Path('overlap').iterdir()))<2 and time.monotonic()<deadline:
            time.sleep(0.01)
        assert len(list(Path('overlap').iterdir()))==2, 'Provider calls were serialized'
    if plan.get("block"):
        import time
        time.sleep(30)
    if request.url.host == "unavailable.invalid":
        raise httpx.ConnectError("Fixture connection unavailable", request=request)
    if plan.get('require_key') and not record['auth_matches']:
        return httpx.Response(401,json={'error':{'message':'Fixture credential unavailable','type':'authentication_error'}})
    status = plan.get("statuses", [200])[min(calls-1, len(plan.get("statuses", [200]))-1)]
    if status != 200:
        return httpx.Response(status, json={"error": {"message": "Fixture rejected request", "type": "fixture_error"}})
    text = plan.get("content", '{"ok":true}')
    if "generateContent" in request.url.path:
        return httpx.Response(200, json={"candidates":[{"content":{"parts":[{"text":text}],"role":"model"},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":4,"candidatesTokenCount":3,"totalTokenCount":7}})
    if request.url.path.endswith("/responses"):
        response = {"id":"fixture-response-"+str(__import__("os").getpid()), "object":"response", "status":"completed", "model":body["model"], "output":[],"usage":{"input_tokens":4,"output_tokens":3,"total_tokens":7}}
        events = [dict(type="response.created", response=dict(response,status="in_progress")),dict(type="response.output_text.delta",delta=text,output_index=0,content_index=0,item_id="fixture-message"),dict(type="response.completed",response=response)]
        content = ''.join('data: '+json.dumps(event)+'\n\n' for event in events)
    else:
        chunk = {"id":"fixture-response-"+str(__import__("os").getpid()), "object":"chat.completion.chunk", "model":body["model"],"choices":[{"index":0,"delta":{"content":text},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}
        content = 'data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n'
    return httpx.Response(200,headers={"Content-Type":"text/event-stream"},content=content.encode())
httpx.HTTPTransport = lambda *a, **k: httpx.MockTransport(handler)
_original_client_init = httpx.Client.__init__
def mock_client_init(self, *a, **k):
    k['transport'] = httpx.MockTransport(handler)
    k['trust_env'] = False
    _original_client_init(self, *a, **k)
httpx.Client.__init__ = mock_client_init
'''

WORKER = r'''
import copy, json, os, sys, threading, time
from pathlib import Path
import model_config
from core.ai import api_client
from utils.capture import multi_model_capture as capture, live_provider_call as live
from utils import openai_usage_tracker as usage
scenario=json.loads(Path('scenario.json').read_text())
statuses=[];envelopes=[];children=[]
scope=live.LiveTurnScope()
if scenario.get('parent_credential'):
    model_config.get_secret=lambda name:'fixture-token' if name=='local_api_key' else None
# Short polling in tests only; cancellation and authority logic remain real.
live._HEARTBEAT_SECONDS=0.02
original_log=live._log_generation
original_popen=live.subprocess.Popen
original_wait=live._interruptible_wait

def log_generation(task,messages,envelope,started):
    envelopes.append(copy.deepcopy(envelope))
    original_log(task,messages,envelope,started)
    if len(envelopes)>=3:
        scope.request_supersession('reset')  # Bound a broken baseline, not production retry policy.
live._log_generation=log_generation

def spawn(*a,**k):
    if not a or not isinstance(a[0], (list,tuple)) or '--provider-child' not in a[0]:
        return original_popen(*a,**k)
    assert 'fixture-token' not in repr(a) + repr(k), 'Credential escaped stdin transport'
    if scenario.get('change_settings') and not children:
        Path('user_settings.json').write_text(json.dumps({'model_provider':'openai','local_base_url':'https://unavailable.invalid/v1','local_model':'wrong/model','local_api_key':'wrong-fixture-token'}))
        model_config.set_provider('openai')
    p=original_popen(*a,**k);children.append(p)
    return p
live.subprocess.Popen=spawn
live._interruptible_wait=lambda seconds,*a,**k:original_wait(min(seconds,0.02),*a,**k)
if scenario.get('authority')=='before':
    authority=lambda:False
elif scenario.get('authority')=='after':
    authority=lambda:not Path('http-requests.jsonl').exists()
else:
    authority=lambda:True

def cancel():
    deadline=time.monotonic()+10
    while not Path('http-requests.jsonl').exists() and time.monotonic()<deadline:time.sleep(0.01)
    scope.request_supersession('reset')
if scenario.get('cancel'):
    threading.Thread(target=cancel,daemon=True).start()
if scenario.get('retry_change'):
    original_log2=live._log_generation
    def log_and_change(*a):
        original_log2(*a)
        if len(envelopes)==1:
            Path('user_settings.json').write_text(json.dumps({'model_provider':'openai','local_base_url':'https://unavailable.invalid/v1','local_model':'wrong/model','local_api_key':'wrong-fixture-token'}))
            model_config.set_provider('openai')
    live._log_generation=log_and_change
if scenario.get('capture'):
    capture._config={'capture_enabled':True,'full_tier_variants':[], 'mini_tier_variants':[]}
    os.environ['NEQ_MULTI_MODEL_CAPTURE']='1'
    os.environ['NEQ_MODEL_CAPTURE_DIR']=str(Path('model_captures').resolve())
if scenario.get('cancel_after_response'):
    original_reconstruct=live._reconstruct_response
    def reconstruct_and_cancel(envelope):
        response=original_reconstruct(envelope)
        scope.request_supersession('reset')
        return response
    live._reconstruct_response=reconstruct_and_cancel
usage._global_tracker=usage.OpenAIUsageTracker(telemetry_log='fixture-usage.jsonl')
result={}
try:
    with usage.module_build_usage_scope('fixture-startup'):
        if scenario.get('parallel'):
            from concurrent.futures import ThreadPoolExecutor
            from contextvars import copy_context
            def call_one():
                return capture.capture_and_fanout('T092',api_client.create_completion,
                    messages=[{'role':'user','content':'Parallel fixture'}],model='ignored',
                    _request_provider='lmstudio',_live_selected='required',
                    _detached_scope=live.LiveTurnScope(),_detached_status=statuses.append)
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures=[executor.submit(copy_context().run,call_one) for _ in range(2)]
                answers=[future.result().choices[0].message.content for future in futures]
            result={'kind':'success','answers':answers}
        elif scenario.get('wizard'):
            from utils import startup_wizard as wizard
            conversation=[{'role':'system','content':'Fixture character interview'},{'role':'user','content':'I choose a fighter.'}]
            if scenario['wizard']=='interview':
                content=wizard.get_ai_response(conversation,persist_response=False,live_scope=scope)
            elif scenario['wizard']=='review':
                import inspect, copy
                proposal={'decision':'continue_interview'}
                review_kwargs={'live_scope':scope}
                # PR579 adds explicit authorship provenance; transport fixtures
                # exercise either public interface without changing production.
                parameters=inspect.signature(wizard._review_startup_response).parameters
                if 'authored_proposal' in parameters:
                    assert 'normalization_provenance' in parameters
                    review_kwargs.update(authored_proposal=copy.deepcopy(proposal),
                                         normalization_provenance={})
                content=json.dumps(wizard._review_startup_response(
                    conversation,proposal,{},**review_kwargs))
            else:
                content=json.dumps(wizard.get_ai_starting_location({'moduleName':'Fixture'},live_scope=scope))
            result={'kind':'success','content':content}
        else:
            response=capture.capture_and_fanout(scenario.get('task','T092'),api_client.create_completion,
                messages=[{'role':'system','content':'Fixture instructions'},{'role':'user','content':'Character setup '+('x'*90000 if scenario.get('large') else '')}],
                model='ignored-callsite-model',response_format=scenario.get('response_format'),
                _request_provider=scenario.get('provider','lmstudio'),
                _detached_scope=scope,_detached_status=statuses.append,_live_authority_check=None if scenario.get("sync") else authority,
                _live_selected=False if scenario.get("sync") else "required")
            usage.track_module_build_response(response,task_id=scenario.get('task','T092'),provider=scenario.get('provider','lmstudio'))
            result={'kind':'success','model':response.model,'provider':response.provider,'content':response.choices[0].message.content,'usage':response.usage.model_dump()}
except Exception as exc:
    result={'kind':type(exc).__name__, 'error':str(exc)}
result.update(envelopes=envelopes,statuses=statuses,children_reaped=all(p.poll() is not None for p in children),children=len(children),global_scope_untouched=live.get_live_turn_scope() is None,
    usage_rows=[json.loads(line) for line in Path('fixture-usage.jsonl').read_text().splitlines()] if Path('fixture-usage.jsonl').exists() else [])
result['capture_records']=[json.loads(p.read_text()) for p in Path('model_captures').glob('T*.json')]
for directory in ('debug','model_captures'):
    for path in Path(directory).rglob('*'):
        if path.is_file():
            assert 'fixture-token' not in path.read_text(errors='replace'), 'Credential leaked into diagnostics'
assert 'fixture-token' not in json.dumps(result)
Path('result.json').write_text(json.dumps(result))
'''


@pytest.fixture
def run_case(tmp_path, installed_openai_sdk):
    for name in ('core', 'utils'):
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for path in ROOT.glob('*.py'):
        if path.name != 'config.py':
            shutil.copy2(path, tmp_path / path.name)
    (tmp_path / 'config.py').write_text(
        "from model_config import *\nOPENAI_API_KEY='fixture-token'\nGEMINI_API_KEY='fixture-token'\n")
    (tmp_path / 'keyring.py').write_text(
        "def get_keyring(): raise RuntimeError('No credential backend in fixture')\n")
    (tmp_path / 'sitecustomize.py').write_text(SITE_CUSTOMIZE)
    (tmp_path / 'worker.py').write_text(WORKER)
    area=tmp_path/'modules/Fixture/areas'
    area.mkdir(parents=True)
    (area/'A.json').write_text(json.dumps({'areaId':'A','areaName':'Fixture Area','locations':[{'locationId':'A01','name':'Fixture Entry'}]}))
    def run(scenario=None, plan=None, endpoint=None):
        scenario=scenario or {}
        settings={'model_provider':scenario.get('provider','lmstudio'),
                  'local_base_url':'https://openrouter.invalid/api/v1',
                  'local_model':'fixture/openrouter-model','local_api_key':'fixture-token'}
        settings.update(endpoint or {})
        (tmp_path / 'user_settings.json').write_text(json.dumps(settings))
        (tmp_path / 'scenario.json').write_text(json.dumps(scenario))
        (tmp_path / 'http-plan.json').write_text(json.dumps(plan or {}))
        # Inherit platform plumbing only; never operator provider credentials,
        # proxy credentials, cloud project selection or SDK configuration.
        env={key:value for key,value in os.environ.items() if key.upper() in
             {'PATH','SYSTEMROOT','WINDIR','LANG','LC_ALL','TEMP','TMP','TMPDIR','LD_LIBRARY_PATH'}}
        env.update(PYTHONPATH=os.pathsep.join((str(tmp_path), str(installed_openai_sdk))),
                   PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',
                   NEQ_MULTI_MODEL_CAPTURE='0',NEQ_MODEL_EVAL_PRIMARY='')
        proc=_run_fixture_worker([sys.executable,str(tmp_path/'worker.py')],
                                 cwd=tmp_path,env=env,timeout=25)
        assert proc.returncode==0, proc.stderr
        assert 'fixture-token' not in proc.stdout + proc.stderr
        for request in [json.loads(line) for line in (tmp_path/'http-requests.jsonl').read_text().splitlines()] if (tmp_path/'http-requests.jsonl').exists() else []:
            assert '_request_local_endpoint' not in request['body']
        result=json.loads((tmp_path/'result.json').read_text())
        requests=[json.loads(line) for line in (tmp_path/'http-requests.jsonl').read_text().splitlines()] if (tmp_path/'http-requests.jsonl').exists() else []
        result['http_requests']=requests
        result['usage_rows']=[row for row in result['usage_rows'] if 'total_tokens' in row]
        assert result['children_reaped']
        assert result['global_scope_untouched']
        return result
    return run
