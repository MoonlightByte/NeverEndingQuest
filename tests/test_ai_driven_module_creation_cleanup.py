"""
Tests for OW-H4: cleanup of partial module directory on build failure.

When ai_driven_module_creation() raises an exception after the module's
output directory has been created (e.g., during builder.build_module()),
the partial directory must be removed so the stitcher / scan integration
does not later pick it up as a "new module".

These tests substitute a fake ModuleBuilder so we don't need any schemas,
config, or API keys -- the fake just creates the configured output_directory
in __init__ (mirroring the real builder's behavior at line 87) and then
either raises or no-ops in build_module().
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_builder


def _stub_parsed_params(module_name):
    return {
        "module_name": module_name,
        "num_areas": 2,
        "locations_per_area": 4,
        "level_range": {"min": 3, "max": 5},
        "adventure_type": "mixed",
        "plot_themes": "test",
    }


def _make_fake_builder(build_module_behavior):
    """Build a fake ModuleBuilder class with controllable build_module().

    The fake's __init__ replicates the real builder's behavior of creating
    config.output_directory on construction (the real one does this at
    module_builder.py:87).
    """

    class _FakeModuleBuilder:
        def __init__(self, config):
            self.config = config
            self.module_data = {"moduleName": config.module_name.replace("_", " "), "mainPlot": {}}
            self.plots_data = {}
            self.progress_callback = None
            self.per_area_locations = None
            # Mirror real ModuleBuilder.__init__ line 87:
            os.makedirs(self.config.output_directory, exist_ok=True)

        def build_module(self, initial_concept):
            build_module_behavior(self, initial_concept)

    return _FakeModuleBuilder


@pytest.fixture
def temp_modules_root(monkeypatch, tmp_path):
    """Run the test inside tmp_path so './modules/<name>' lands under tmp_path."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_partial_module_dir_is_cleaned_up_on_build_failure(monkeypatch, temp_modules_root):
    """If build_module raises, the partial ./modules/<name>/ dir must be removed.

    Asserts both:
      - The function returns (False, None) on failure (existing contract).
      - The partial output directory does NOT remain on disk.
    """
    module_name = "Cleanup_Test_Module"

    # Stub the narrative parser so we don't touch any model API.
    monkeypatch.setattr(
        module_builder,
        "parse_narrative_to_module_params",
        lambda narrative: _stub_parsed_params(module_name),
    )

    # Track that the partial directory really did exist mid-flight, so we
    # know the cleanup is meaningful (not a vacuous pass).
    observed = {"dir_existed_before_raise": False}

    def _raise_during_build(builder_self, initial_concept):
        observed["dir_existed_before_raise"] = os.path.isdir(builder_self.config.output_directory)
        raise RuntimeError("Simulated build failure for OW-H4 cleanup test")

    monkeypatch.setattr(
        module_builder,
        "ModuleBuilder",
        _make_fake_builder(_raise_during_build),
    )

    params = {
        "concept": "A test adventure for verifying cleanup of orphan module directories.",
        "module_name": module_name,
    }

    success, returned_name = module_builder.ai_driven_module_creation(params)

    # Existing return contract on failure.
    assert success is False, "Failure path must return success=False"
    assert returned_name is None, "Failure path must return module_name=None"

    # The partial directory was created (otherwise the test is vacuous).
    assert observed["dir_existed_before_raise"], (
        "Test prerequisite failed: partial output directory should have existed "
        "before build_module raised"
    )

    # Core assertion: the partial directory must NOT remain on disk.
    expected_dir = temp_modules_root / "modules" / module_name
    assert not expected_dir.exists(), (
        f"Partial module directory was not cleaned up after build failure: {expected_dir}"
    )


def test_successful_module_dir_is_not_deleted(monkeypatch, temp_modules_root):
    """Regression guard: a successful build must NOT delete the output directory.

    This guards against the cleanup being incorrectly placed in a finally block.
    """
    module_name = "Success_Path_Module"

    monkeypatch.setattr(
        module_builder,
        "parse_narrative_to_module_params",
        lambda narrative: _stub_parsed_params(module_name),
    )

    def _successful_build(builder_self, initial_concept):
        # No-op: real build_module would do work, but __init__ already
        # created output_directory so the success path can proceed.
        return None

    monkeypatch.setattr(
        module_builder,
        "ModuleBuilder",
        _make_fake_builder(_successful_build),
    )

    params = {
        "concept": "A successful adventure.",
        "module_name": module_name,
    }

    success, returned_name = module_builder.ai_driven_module_creation(params)

    assert success is True, "Success path must return success=True"
    assert returned_name == module_name, "Success path must return the module name"

    expected_dir = temp_modules_root / "modules" / module_name
    assert expected_dir.exists(), (
        f"Successful build must NOT delete output directory: {expected_dir}"
    )
