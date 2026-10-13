"""Cache-only chronicles must not leave a running status on the player screen."""
import ast
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys
import threading


def progress_method():
    source = Path(__file__).resolve().parents[1] / 'utils/compression/conversation_compressor_parallel.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_update_progress')
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_update_progress']


def run_pass(monkeypatch, active, sources):
    events = []
    module = ModuleType('core.managers.status_manager')
    module.status_manager = SimpleNamespace(emit_compression_event=lambda name, data: events.append((name, data)))
    monkeypatch.setitem(sys.modules, 'core.managers.status_manager', module)
    state = SimpleNamespace(progress_lock=threading.Lock(), completed_count=0, total_sections=len(sources), needs_active_compression=active)
    update = progress_method()
    for cached in sources:
        update(state, cached)
    return state, events


def test_all_cached_pass_stays_silent_and_counts_work(monkeypatch):
    state, events = run_pass(monkeypatch, False, [True, True])
    assert state.completed_count == 2
    assert events == []


def test_active_pass_still_reports_cached_and_new_sections(monkeypatch):
    state, events = run_pass(monkeypatch, True, [True, False])
    assert state.completed_count == 2
    assert [name for name, _ in events] == ['compression_progress'] * 2
    assert [data for _, data in events] == [
        {'completed': 1, 'total': 2, 'from_cache': True},
        {'completed': 2, 'total': 2, 'from_cache': False},
    ]


def test_standalone_section_without_a_ui_pass_only_counts_progress():
    state = SimpleNamespace(progress_lock=threading.Lock(), completed_count=0, total_sections=1)
    progress_method()(state, True)
    assert state.completed_count == 1
