"""Real authoring routes in a retained tracked export; no provider/build jobs.

Only synthetic packs are created/imported/deleted. Existing packs are listed,
not activated, changed or exported. Validation uses actual Flask/Socket.IO
handlers. This is backend/file evidence, not browser or generated-asset parity.
"""
import argparse
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
import zipfile


def worker(export):
    export = export.resolve()
    root = export.parent
    assert export.name == 'source' and root.name.startswith('neq-ember-toolkit-')
    manifest = json.loads((root / 'probe.json').read_text())
    assert manifest['export'] == str(export) and not (export / '.git').exists()
    sys.dont_write_bytecode = True
    for name in tuple(os.environ):
        if any(part in name.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'CREDENTIAL', 'PROXY')):
            os.environ.pop(name, None)
    secret_store = types.ModuleType('utils.secret_store')
    secret_store.get_secret = lambda name: None
    secret_store.set_secret = lambda name, value: False
    secret_store.delete_secret = lambda name: False
    sys.modules['utils.secret_store'] = secret_store
    def check(target):
        if isinstance(target, int):
            return
        path = Path(os.fsdecode(target)).resolve()
        if path == Path(os.devnull):
            return
        if path == root or not path.is_relative_to(root):
            raise PermissionError(f'Write outside disposable export: {path}')
    def guard(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen'):
            raise PermissionError('Networking and subprocess jobs prohibited')
        if event == 'open':
            if any(char in (args[1] or '') for char in 'wa+') or (args[2] or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                check(args[0])
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'shutil.rmtree'):
            check(args[0])
        elif event == 'os.rename':
            check(args[0]); check(args[1])
    sys.addaudithook(guard)
    os.chdir(export)
    sys.path.insert(0, str(export))
    temporary = root / 'temporary'
    temporary.mkdir(exist_ok=True)
    tempfile.tempdir = str(temporary)
    shutil.copy2(export / 'config_template.py', export / 'config.py')
    from web import web_interface as web
    assert web.TOOLKIT_AVAILABLE and web.game_thread is None
    client = web.app.test_client()
    packs = export / 'graphic_packs'
    baseline = set(packs.iterdir())
    checks = {}
    listed = client.get('/api/toolkit/packs')
    assert listed.status_code == 200 and isinstance(listed.json, list)
    checks['actual_pack_list'] = len(listed.json)
    created = client.post('/api/toolkit/packs/create', json={'name':'ember_probe_source', 'display_name':'Synthetic Ember probe', 'style':'custom', 'author':'Fixture', 'description':'No generated assets'})
    assert created.json['success'], created.json
    original = json.loads((packs / 'ember_probe_source/manifest.json').read_text())
    # Copy, never repaint or generate, one tracked public portrait into the
    # synthetic pack so archive/import checks cover real asset bytes too.
    portrait = packs / 'photorealistic/npcs/ranger_elen.jpg'
    fixture_portrait = packs / 'ember_probe_source/npcs/ranger_elen.jpg'
    fixture_portrait.parent.mkdir(exist_ok=True)
    shutil.copy2(portrait, fixture_portrait)
    duplicate = client.post('/api/toolkit/packs/create', json={'name':'ember_probe_source'})
    assert not duplicate.json['success']
    assert json.loads((packs / 'ember_probe_source/manifest.json').read_text()) == original
    exported = client.get('/api/toolkit/packs/ember_probe_source/export')
    assert exported.status_code == 200 and exported.mimetype == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(exported.data)) as archive:
        assert json.loads(archive.read('manifest.json')) == original
        assert archive.read('npcs/ranger_elen.jpg') == portrait.read_bytes()
    checks['create_duplicate_rejection_export_zip'] = True
    preview = client.post('/api/toolkit/packs/preview', data={'pack':(io.BytesIO(exported.data),'probe.zip')})
    assert preview.json['success'] and preview.json['data']['total_monsters'] == 0
    assert preview.json['data']['total_npcs'] == 1
    for endpoint in ('preview','import'):
        assert not client.post(f'/api/toolkit/packs/{endpoint}', data={}).json['success']
        assert not client.post(f'/api/toolkit/packs/{endpoint}', data={'pack':(io.BytesIO(b'not zip'),'bad.zip')}).json['success']
    imported = client.post('/api/toolkit/packs/import', data={'pack':(io.BytesIO(exported.data),'probe.zip'), 'target_folder_name':'ember_probe_imported'})
    assert imported.json['success'], imported.json
    assert (packs / 'ember_probe_imported/manifest.json').is_file()
    assert (packs / 'ember_probe_imported/npcs/ranger_elen.jpg').read_bytes() == portrait.read_bytes()
    checks['preview_invalid_upload_rejection_actual_import'] = True
    assert client.get('/api/toolkit/packs/ember_probe_missing/export').status_code == 400
    for name in ('ember_probe_source','ember_probe_imported'):
        assert client.delete(f'/api/toolkit/packs/{name}').json['success']
        assert not (packs / name).exists()
    # Public deletion is recoverable: it moves packs into .deleted rather
    # than destroying their contents. Verify that behavior, not an empty tree.
    assert baseline <= set(packs.iterdir())
    assert set(packs.iterdir()) - baseline <= {packs / '.deleted'}
    for name in ('ember_probe_source', 'ember_probe_imported'):
        assert any((backup / 'manifest.json').is_file() for backup in (packs / '.deleted').glob(name + '_*'))
    checks['synthetic_pack_deletion_with_recoverable_backups'] = True
    builder = runpy.run_path(str(export / 'module_builder_web.py'), run_name='ember_toolkit_builder')
    build_client = builder['socketio'].test_client(builder['app'])
    try:
        for data in ({}, {'module_name':'Only name'}, {'narrative':'Only narrative'}):
            build_client.get_received()
            build_client.emit('start_build', data)
            packets = build_client.get_received()
            assert any(packet['name'] == 'module_error' and 'required' in packet['args'][0]['error'] for packet in packets)
            assert builder['current_build']['thread'] is None and not builder['current_build']['active']
        build_client.emit('cancel_build')
        assert any(packet['name'] == 'module_error' for packet in build_client.get_received())
        build_client.emit('request_module_list')
        assert any(packet['name'] == 'module_list_response' for packet in build_client.get_received())
    finally:
        build_client.disconnect()
    assert web.game_thread is None
    checks['builder_required_fields_idle_cancel_module_list_no_jobs'] = True
    report = {**manifest, 'checks':checks, 'network':'blocked', 'credential_store':'stubbed', 'jobs_started':0,
              'limits':['No browser clicks', 'No image/video/module generation', 'No activation or live-game asset-copy test', 'Merge route is pre-existing placeholder, not functional acceptance'], 'synthetic_packs_removed':True}
    (root / 'result.json').write_text(json.dumps(report, indent=2))
    print('TOOLKIT_PROBE_RESULT ' + json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--temp-parent', type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker); return
    repo = Path(__file__).resolve().parents[3]
    root = Path(tempfile.mkdtemp(prefix='neq-ember-toolkit-', dir=args.temp_parent))
    export = root / 'source'; export.mkdir()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    archive = subprocess.Popen(['git','archive',head],cwd=repo,stdout=subprocess.PIPE)
    try:
        subprocess.run(['tar','-x','-C',str(export)],stdin=archive.stdout,check=True)
    finally:
        archive.stdout.close()
    assert archive.wait() == 0
    (root / 'probe.json').write_text(json.dumps({'head':head,'export':str(export)}))
    print(f'Disposable toolkit export: {export}', flush=True)
    subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(export)],cwd=export,check=True)


if __name__ == '__main__':
    main()
