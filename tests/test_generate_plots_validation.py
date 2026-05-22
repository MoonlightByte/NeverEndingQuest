"""
Tests for MP-C2: production ``generate_plots`` must call ``validate_plot``.

Previously ``PlotGenerator.validate_plot`` was only invoked from the
script's standalone ``main()``. The production pipeline
(``ModuleBuilder.generate_plots``) never called it, so plot references
to non-existent locations (and other validation errors) passed silently
into the on-disk module.

This file pins down three contracts:

  1. (positive) ``validate_plot`` returning an empty list lets
     ``generate_plots`` complete normally and record the plot in
     ``self.plots_data``.

  2. (negative) ``validate_plot`` returning a non-empty list causes
     ``generate_plots`` to raise ``ValueError`` whose message includes
     the offending error text. The raise is intentional: it propagates
     to ``ai_driven_module_creation``'s try/except cleanup wrapper.

  3. (integration) When ``ai_driven_module_creation`` is run end-to-end
     and the plot generator returns bad refs, the function must:
       - return (False, None)
       - clean up the partial module directory (T0-1 / OW-H4 wrapper)

These tests do NOT hit any AI generation paths; ``plot_gen.generate_plot``
is monkeypatched to a deterministic stub.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.generators import module_builder
from core.generators.module_builder import BuilderConfig, ModuleBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_plot_data():
    """Return a deterministic plot_data shape with enough structure for
    the post-validation loop in generate_plots() to iterate plotPoints.
    Field values do NOT need to be schema-valid because validate_plot
    is mocked by these tests."""
    return {
        "plotTitle": "Stub Plot",
        "mainObjective": "Exercise generate_plots",
        "plotPoints": [
            {
                "id": "PP001",
                "title": "Start",
                "description": "Start point",
                "location": "R01",
                "nextPoints": [],
                "status": "not started",
                "plotImpact": "",
            },
        ],
    }


def _make_builder(tmp_path):
    """Construct a ModuleBuilder with minimal in-memory areas/locations
    state so generate_plots() can iterate. We DO NOT call build_module()
    -- we exercise generate_plots() directly with hand-rolled fixtures.

    The builder's __init__ creates output_directory and instantiates the
    real generators; that's fine because tests monkeypatch the specific
    generator methods they touch.
    """
    cfg = BuilderConfig(
        module_name="MP_C2_Test_Module",
        num_areas=1,
        locations_per_area=2,
        output_directory=str(tmp_path / "out_mp_c2"),
        verbose=False,
    )
    builder = ModuleBuilder(cfg)

    # Minimal areas + locations dicts for one area "A".
    builder.areas_data = {
        "A": {
            "areaName": "Test Area",
            "areaType": "wilderness",
            "areaDescription": "A test area.",
            "terrain": "forest",
        },
    }
    builder.locations_data = {
        "A": {"locations": [{"locationId": "R01"}]},
    }
    builder.module_data = {
        "moduleName": "MP C2 Test Module",
        "mainPlot": {},
    }
    # context_header is set by build_module() before generate_plots() in
    # the real flow; supply a stand-in so generate_plots' f-string works.
    builder.context_header = "TEST_CONTEXT_HEADER"
    return builder


# ---------------------------------------------------------------------------
# Test 1 (positive): empty errors -> generate_plots completes
# ---------------------------------------------------------------------------

def test_generate_plots_succeeds_when_validate_plot_returns_no_errors(
    monkeypatch, tmp_path
):
    """When ``validate_plot`` returns ``[]``, ``generate_plots`` must
    complete without raising and must record the generated plot in
    ``self.plots_data`` keyed by area id."""
    builder = _make_builder(tmp_path)

    # Deterministic plot generation -- no AI calls.
    monkeypatch.setattr(
        builder.plot_gen,
        "generate_plot",
        lambda *args, **kwargs: _stub_plot_data(),
    )
    # Force "all clear" from validation.
    monkeypatch.setattr(
        builder.plot_gen,
        "validate_plot",
        lambda plot_data, location_data: [],
    )

    builder.generate_plots()

    assert "A" in builder.plots_data, (
        "Expected generate_plots to store the generated plot under area id "
        f"'A'; got plots_data keys: {list(builder.plots_data.keys())}"
    )
    assert builder.plots_data["A"]["plotPoints"][0]["id"] == "PP001"


# ---------------------------------------------------------------------------
# Test 2 (negative): non-empty errors -> ValueError
# ---------------------------------------------------------------------------

def test_generate_plots_raises_value_error_when_validate_plot_reports_errors(
    monkeypatch, tmp_path
):
    """When ``validate_plot`` returns one or more errors, ``generate_plots``
    must raise ``ValueError`` and the exception message must include the
    validator's error text so the failure is diagnosable in logs."""
    builder = _make_builder(tmp_path)

    monkeypatch.setattr(
        builder.plot_gen,
        "generate_plot",
        lambda *args, **kwargs: _stub_plot_data(),
    )
    bad_msg = "Plot point PP001 references non-existent location R99"
    monkeypatch.setattr(
        builder.plot_gen,
        "validate_plot",
        lambda plot_data, location_data: [bad_msg],
    )

    with pytest.raises(ValueError) as excinfo:
        builder.generate_plots()

    assert bad_msg in str(excinfo.value), (
        f"ValueError message should include the validator's error text. "
        f"Expected substring: {bad_msg!r}; got: {excinfo.value!r}"
    )

    # And on failure the plot must NOT be recorded -- the raise happens
    # before plots_data is populated for that area.
    assert "A" not in builder.plots_data, (
        "When validate_plot reports errors, generate_plots must not store "
        "the plot in plots_data."
    )


# ---------------------------------------------------------------------------
# Test 3 (integration): bad plot -> ai_driven_module_creation cleanup
# ---------------------------------------------------------------------------

def _stub_parsed_params(module_name):
    return {
        "module_name": module_name,
        "num_areas": 1,
        "locations_per_area": 2,
        "level_range": {"min": 3, "max": 5},
        "adventure_type": "mixed",
        "plot_themes": "test",
    }


def _make_fake_builder_that_raises_in_generate_plots():
    """Fake ModuleBuilder whose ``build_module`` reaches a generate_plots
    stage that raises ValueError -- mimicking validate_plot reporting
    bad refs. The fake's __init__ creates output_directory (mirroring
    real ModuleBuilder.__init__ at line 88) so the cleanup-on-failure
    branch in ai_driven_module_creation has a partial dir to remove.
    """

    class _FakeModuleBuilder:
        def __init__(self, config):
            self.config = config
            self.module_data = {
                "moduleName": config.module_name.replace("_", " "),
                "mainPlot": {},
            }
            self.plots_data = {}
            self.progress_callback = None
            self.per_area_locations = None
            os.makedirs(self.config.output_directory, exist_ok=True)

        def build_module(self, initial_concept):
            # Simulate the production flow reaching generate_plots() and
            # hitting validate_plot()'s new ValueError raise path.
            raise ValueError(
                "Plot validation failed: "
                "Plot point PP001 references non-existent location R99"
            )

    return _FakeModuleBuilder


def test_ai_driven_module_creation_cleans_up_on_plot_validation_failure(
    monkeypatch, tmp_path
):
    """End-to-end-ish: when the build pipeline raises ValueError out of
    generate_plots (e.g., validate_plot reported bad refs), the wrapper
    ``ai_driven_module_creation`` must:

      - return ``(False, None)`` (existing failure contract)
      - delete the partial ``./modules/<name>/`` directory so the
        stitcher does not later pick up an invalid orphan

    The cleanup is provided by T0-1 / OW-H4. This test guards that the
    new raise path in generate_plots integrates correctly with that
    wrapper -- the ValueError must propagate (not be swallowed by
    generate_plots) and the cleanup branch must fire.
    """
    module_name = "MP_C2_Bad_Plot_Module"
    monkeypatch.chdir(tmp_path)

    # Stub the narrative parser so we don't touch any model API.
    monkeypatch.setattr(
        module_builder,
        "parse_narrative_to_module_params",
        lambda narrative: _stub_parsed_params(module_name),
    )

    monkeypatch.setattr(
        module_builder,
        "ModuleBuilder",
        _make_fake_builder_that_raises_in_generate_plots(),
    )

    params = {
        "concept": "A test adventure with a deliberately bad plot reference.",
        "module_name": module_name,
    }

    success, returned_name = module_builder.ai_driven_module_creation(params)

    assert success is False, (
        "Plot-validation failure must surface as success=False from "
        "ai_driven_module_creation."
    )
    assert returned_name is None, (
        "Plot-validation failure must surface as module_name=None from "
        "ai_driven_module_creation."
    )

    expected_dir = tmp_path / "modules" / module_name
    assert not expected_dir.exists(), (
        f"Partial module dir was not cleaned up after plot-validation "
        f"failure: {expected_dir}. The T0-1 / OW-H4 cleanup branch in "
        "ai_driven_module_creation must remove it."
    )
