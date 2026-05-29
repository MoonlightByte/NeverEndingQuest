"""
Tests for INT-H8: surface stitching failures + clean up orphan module dir.

When the createNewModule action handler successfully invokes
ai_driven_module_creation() but the subsequent module_stitcher integration
step raises, the previous behavior was to print a WARNING, continue down
the success path, append a "module created" DM note to conversation
history, and return success=True. This left an orphan, unintegrated
module on disk while the game pretended it existed.

The fix:
  - Surface the failure to the caller as success=False with an error
    message and needs_dm_response=False.
  - Skip the DM-note append (conversation history must be untouched).
  - Remove the partially-created module directory so the next stitcher
    scan does not pick it up.

These tests substitute fakes for ai_driven_module_creation and
get_module_stitcher so we don't need any schemas, config, API keys,
or real module-building work. We just verify the action handler's
behavior when stitching raises.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ai import action_handler
from core.generators import module_builder
from core.generators import module_stitcher


@pytest.fixture
def temp_modules_root(monkeypatch, tmp_path):
    """Run the test inside tmp_path so './modules/<name>' lands under tmp_path."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def stub_save_conversation(monkeypatch):
    """Replace main.save_conversation_history so tests don't write to the real file.

    The success path of createNewModule calls
    `from main import save_conversation_history`. We register a no-op
    in sys.modules so the import succeeds without pulling in main.py's
    heavy dependencies.
    """
    import types

    fake_main = types.ModuleType("main")
    fake_main.save_conversation_history = lambda history: None
    monkeypatch.setitem(sys.modules, "main", fake_main)
    return fake_main


def _make_stitcher_that_raises():
    """Return a fake get_module_stitcher() that returns an object whose
    scan_and_integrate_new_modules() raises RuntimeError.
    """

    class _RaisingStitcher:
        def scan_and_integrate_new_modules(self):
            raise RuntimeError("Simulated stitcher failure for INT-H8 test")

    def _get():
        return _RaisingStitcher()

    return _get


def _make_fake_creation(module_name, output_dir):
    """Return a fake ai_driven_module_creation() that creates the partial
    module directory (mirroring real builder behavior) and reports success.
    """

    def _fake(parameters, progress_callback=None):
        os.makedirs(output_dir, exist_ok=True)
        return True, module_name

    return _fake


def test_stitching_failure_surfaces_error_and_skips_dm_note(
    monkeypatch, temp_modules_root, stub_save_conversation
):
    """When stitching raises, the handler must:
      - return success=False with an error message and needs_dm_response=False
      - leave conversation_history unchanged (no DM note appended)
      - remove the partially-created module directory
    """
    module_name = "Stitcher_Failure_Test_Module"
    expected_dir = temp_modules_root / "modules" / module_name

    # Replace ai_driven_module_creation with a fake that creates the dir
    # and returns success.
    monkeypatch.setattr(
        action_handler,
        "ai_driven_module_creation",
        _make_fake_creation(module_name, str(expected_dir)),
        raising=False,
    )
    # The handler imports ai_driven_module_creation inside the function
    # body via `from core.generators.module_builder import ai_driven_module_creation`.
    # Patch the source module attribute so that import resolves to our fake.
    monkeypatch.setattr(
        module_builder,
        "ai_driven_module_creation",
        _make_fake_creation(module_name, str(expected_dir)),
    )

    # Replace get_module_stitcher so stitcher.scan_and_integrate_new_modules raises.
    monkeypatch.setattr(
        module_stitcher,
        "get_module_stitcher",
        _make_stitcher_that_raises(),
    )

    # The action handler reaches for `from core.managers.status_manager import status_ready`.
    # Stub it so it doesn't poke real status state.
    from core.managers import status_manager
    monkeypatch.setattr(status_manager, "status_ready", lambda: None, raising=False)

    action = {
        "action": "createNewModule",
        "parameters": {"narrative": "A test adventure for INT-H8 stitching-failure cleanup."},
    }

    conversation_history = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "create a new module"},
    ]
    history_before = list(conversation_history)

    result = action_handler.process_action(
        action,
        party_tracker_data={},
        location_data={},
        conversation_history=conversation_history,
    )

    # Return shape: partial-failure signal.
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
    assert result.get("success") is False, (
        f"Stitching failure must return success=False, got: {result}"
    )
    assert "error" in result, f"Stitching failure must include an error message, got: {result}"
    assert result.get("needs_dm_response") is False, (
        f"Stitching failure must return needs_dm_response=False, got: {result}"
    )

    # Conversation history must NOT have the "module created" DM note appended.
    assert conversation_history == history_before, (
        "Conversation history was mutated on stitching failure -- the DM note "
        "must not be appended when integration fails."
    )
    for msg in conversation_history:
        assert "successfully created and integrated" not in str(msg.get("content", "")), (
            "DM note about successful module creation must not appear in history "
            "when stitching failed."
        )

    # Partial module directory must be cleaned up.
    assert not expected_dir.exists(), (
        f"Partial module directory was not cleaned up after stitching failure: {expected_dir}"
    )
