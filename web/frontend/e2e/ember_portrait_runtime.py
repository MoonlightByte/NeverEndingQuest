"""Disposable browser runtime for the actual public portrait-upload handler.

The parity harness replaces engine/generation/update actions, but not upload.
Upload processing is ordinary Pillow verification, center crop and 256px resize.
No face model or provider is invoked. All writes stay within this fresh export
and synthetic campaign; original public artwork is an unchanged upload input.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4217)
    parser.add_argument('--temp-parent', type=Path, required=True)
    parser.add_argument('--probe-upload', action='store_true', help='Exercise actual upload handler then exit; require both persistence targets')
    parser.add_argument('--overlay-upload-handler', action='store_true', help='Overlay only working-tree web/web_interface.py; record its SHA256')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    dist = repo / 'web/frontend/dist'
    assert (dist / 'index.html').is_file(), 'Build the public frontend first'
    root = Path(tempfile.mkdtemp(prefix='neq-ember-portrait-', dir=args.temp_parent))
    export = root / 'source'; export.mkdir()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    archive = subprocess.Popen(['git','archive',head],cwd=repo,stdout=subprocess.PIPE)
    try:
        subprocess.run(['tar','-x','-C',str(export)],stdin=archive.stdout,check=True)
    finally:
        archive.stdout.close()
    assert archive.wait() == 0
    overlay = None
    if args.overlay_upload_handler:
        relative = Path('web/web_interface.py')
        shutil.copy2(repo / relative, export / relative)
        overlay = {'path': str(relative), 'sha256': hashlib.sha256((export / relative).read_bytes()).hexdigest()}
    shutil.copytree(dist, export / 'web/frontend/dist')
    frontend_manifest = {str(path.relative_to(dist)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sorted(dist.rglob('*')) if path.is_file()}
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ('API_KEY','TOKEN','SECRET','CREDENTIAL','PROXY')):
            os.environ.pop(name, None)
    secret_store = types.ModuleType('utils.secret_store')
    secret_store.get_secret = lambda name: None
    secret_store.set_secret = lambda name, value: False
    secret_store.delete_secret = lambda name: False
    sys.modules['utils.secret_store'] = secret_store
    sys.dont_write_bytecode = True
    def check(target):
        if isinstance(target,int): return
        path = Path(os.fsdecode(target)).resolve()
        if path == Path(os.devnull): return
        if path == root or not path.is_relative_to(root):
            raise PermissionError(f'Portrait runtime write outside disposable root: {path}')
    def guard(event, values):
        if event == 'socket.connect':
            address = values[1]
            if not (isinstance(address,tuple) and address[0] in {'127.0.0.1','::1'} and address[1] == args.port):
                raise PermissionError('External network disabled')
        elif event == 'socket.getaddrinfo':
            if values[0] not in {'127.0.0.1','::1','localhost',None}:
                raise PermissionError('External DNS disabled')
        elif event == 'subprocess.Popen':
            raise PermissionError('Subprocess jobs disabled')
        elif event == 'open':
            if any(char in (values[1] or '') for char in 'wa+') or (values[2] or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                check(values[0])
        elif event in ('os.remove','os.rmdir','os.mkdir','shutil.rmtree'):
            check(values[0])
        elif event == 'os.rename':
            check(values[0]); check(values[1])
    sys.addaudithook(guard)
    os.chdir(export); sys.path.insert(0,str(export))
    temporary = root / 'temporary'; temporary.mkdir(); tempfile.tempdir = str(temporary)
    shutil.copy2(export / 'config_template.py',export / 'config.py')
    campaign = root / 'campaign'
    public_portrait = export / 'graphic_packs/photorealistic/npcs/ranger_elen.jpg'
    static_target = export / 'web/static/portraits/arden_vale.png'
    module_target = campaign / 'modules/Parity_Expedition/portraits/arden_vale.png'
    proof = {'head':head,'overlay':overlay,'root':str(root),'export':str(export),'campaign':str(campaign),'port':args.port,
             'upload_handler':'Actual public upload_portrait with the optional source overlay recorded above',
             'frontend_dist_sha256':frontend_manifest,
             'expected_static_target':str(static_target),'intended_module_target':str(module_target),
             'initial_static_target_exists':static_target.exists(),
             'unchanged_upload_input':str(public_portrait),'input_sha256':hashlib.sha256(public_portrait.read_bytes()).hexdigest(),
             'network':'external blocked','writes':'disposable root only','credential_store':'stubbed',
             'limits':['No paid generation or live engine','Both static and module persistence must pass; success response alone is insufficient']}
    (root / 'portrait-isolation.json').write_text(json.dumps(proof,indent=2))
    print('PORTRAIT_ISOLATION ' + json.dumps(proof),flush=True)
    from flask_socketio import SocketIO
    from flask import jsonify
    from PIL import Image
    original_run = SocketIO.run
    def run_with_portrait_state(socketio, app, **kwargs):
        def describe(path):
            if not path.exists(): return {'exists': False}
            with Image.open(path) as image:
                dimensions = list(image.size)
            return {'exists': True, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'dimensions': dimensions}
        @app.get('/__portrait__/state')
        def portrait_state():
            return jsonify({'head': head, 'overlay': overlay, 'static': describe(static_target), 'module': describe(module_target)})
        if args.probe_upload:
            client = app.test_client()
            initial = client.get('/__portrait__/state').get_json()
            assert not initial['static']['exists'] and not initial['module']['exists']
            response = client.post('/upload-portrait', data={'characterName': 'arden_vale', 'portrait': (io.BytesIO(public_portrait.read_bytes()), 'ranger_elen.jpg')})
            uploaded = client.get('/__portrait__/state').get_json()
            rejected = client.post('/upload-portrait', data={'characterName': 'arden_vale', 'portrait': (io.BytesIO(b'not a valid PNG'), 'broken.png')})
            after_rejection = client.get('/__portrait__/state').get_json()
            result = {'head': head, 'initial': initial, 'upload': response.get_json(), 'uploaded': uploaded,
                      'invalid_upload': rejected.get_json(), 'after_rejection': after_rejection}
            (root / 'portrait-result.json').write_text(json.dumps(result, indent=2))
            assert response.get_json()['success'] is True
            assert rejected.get_json()['success'] is False
            assert uploaded == after_rejection, 'Rejected upload changed prior portrait bytes'
            assert uploaded['static']['exists'] and uploaded['static']['dimensions'] == [256, 256]
            assert uploaded['module']['exists'], 'Upload reported success without module persistence'
            assert uploaded['module'] == uploaded['static'], 'Static and module portrait differ'
            print('PORTRAIT_PROBE_PASS ' + str(root / 'portrait-result.json'), flush=True)
            return
        return original_run(socketio, app, **kwargs)
    SocketIO.run = run_with_portrait_state
    sys.argv = ['react_parity_server.py','--port',str(args.port),'--fixture-dir',str(campaign)]
    runpy.run_path(str(export / 'tests/react_parity_server.py'),run_name='__main__')


if __name__ == '__main__':
    main()
