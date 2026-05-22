"""
Tests for VAL-M5: cross-reference plot ``nextPoints`` against existing
plot point IDs.

``schemas/plot_schema.json`` declares ``nextPoints`` as
``{"type": "array", "items": {"type": "string"}}`` with NO cross-reference
constraint. A generated plot containing ``nextPoints: ["PP99"]``, where
PP99 does not appear in ``plotPoints``, therefore passes pure schema
validation. Plot graphs can end up with dead-end or dangling
``nextPoints`` references with no detection.

The runtime validator ``PlotGenerator.validate_plot`` is responsible for
catching this. These tests pin down that contract:

  1. Positive: every nextPoints id resolves to an existing plot point ->
     no nextPoints-related error.
  2. Negative: a nextPoints id that is NOT in plotPoints -> exactly one
     error and the error string names the offending id (e.g. "PP99").
  3. Regression: the existing location cross-reference check still flags
     plot points whose ``location`` is not in the area's location list.
  4. Vacuous: a single plot point with an empty ``nextPoints`` list is
     valid and produces no errors.

These tests do NOT hit the AI generation paths; they exercise only
``validate_plot``, which is pure data validation.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generator(monkeypatch):
    """Build a PlotGenerator. ``load_schema`` reads ``schemas/plot_schema.json``
    via a relative path, so we cd to the repo root for the duration of the
    test. The constructor performs no network or AI calls."""
    monkeypatch.chdir(REPO_ROOT)
    from core.generators.plot_generator import PlotGenerator
    return PlotGenerator()


def _make_plot_point(pp_id: str, location: str = "R01",
                     next_points=None) -> dict:
    """Build a schema-valid plot point object. ``next_points`` defaults
    to an empty list so the caller does not have to repeat boilerplate."""
    return {
        "id": pp_id,
        "title": f"Plot Point {pp_id}",
        "description": f"Description for {pp_id}.",
        "location": location,
        "nextPoints": list(next_points) if next_points is not None else [],
        "status": "not started",
        "plotImpact": "",
    }


def _make_plot(plot_points: list) -> dict:
    """Wrap a list of plot points in the top-level plot envelope expected
    by plot_schema.json. Required keys at the top are plotTitle,
    mainObjective, plotPoints."""
    return {
        "plotTitle": "Test Plot",
        "mainObjective": "Exercise validate_plot contract",
        "plotPoints": plot_points,
    }


def _make_locations(*location_ids: str) -> dict:
    """Build a location_data dict whose ``locations`` array contains
    the given locationIds. ``validate_plot`` only reads
    ``loc["locationId"]`` so other fields are unnecessary."""
    return {
        "locations": [{"locationId": lid} for lid in location_ids],
    }


# ---------------------------------------------------------------------------
# Test 1 (positive): every nextPoints id resolves -> no nextPoints errors
# ---------------------------------------------------------------------------

def test_validate_plot_accepts_resolved_nextpoints(generator):
    """When every value in every ``nextPoints`` list is the id of another
    plot point in the same plot, ``validate_plot`` must not emit any
    error referencing an unknown nextPoint. PP001 -> PP002 -> PP003
    forms a simple linear graph with all references resolved."""
    plot_data = _make_plot([
        _make_plot_point("PP001", "R01", next_points=["PP002"]),
        _make_plot_point("PP002", "R01", next_points=["PP003"]),
        _make_plot_point("PP003", "R01", next_points=[]),
    ])
    location_data = _make_locations("R01")

    errors = generator.validate_plot(plot_data, location_data)

    bad = [
        e for e in errors
        if "nextPoint" in e.lower() or "next point" in e.lower()
    ]
    assert bad == [], (
        f"Expected zero nextPoints errors for fully-resolved graph, got: {bad}. "
        f"Full errors: {errors}"
    )


# ---------------------------------------------------------------------------
# Test 2 (negative): unresolved nextPoint id -> error names the id
# ---------------------------------------------------------------------------

def test_validate_plot_flags_unknown_nextpoint(generator):
    """A plot point that lists ``PP99`` in ``nextPoints``, while PP99 is
    NOT among the plot's actual plot point ids, must produce an error
    naming PP99 so a fixer can locate the dangling reference. There is
    exactly one offending reference, so we expect exactly one matching
    error (the rest of the plot is well-formed)."""
    plot_data = _make_plot([
        _make_plot_point("PP001", "R01", next_points=["PP99"]),
    ])
    location_data = _make_locations("R01")

    errors = generator.validate_plot(plot_data, location_data)

    matching = [e for e in errors if "PP99" in e]
    assert len(matching) == 1, (
        f"Expected exactly one error mentioning the unresolved 'PP99' "
        f"nextPoint id, got {len(matching)}. errors={errors}"
    )


# ---------------------------------------------------------------------------
# Test 3 (regression): the location cross-reference check is untouched
# ---------------------------------------------------------------------------

def test_validate_plot_still_checks_location_existence(generator):
    """``validate_plot`` already cross-references each plot point's
    ``location`` against the area's location list. This test is a
    regression guard: adding the nextPoints check must not remove or
    short-circuit the location check. We use ``R99`` -- not present in
    locations -- and assert an error mentions it."""
    plot_data = _make_plot([
        _make_plot_point("PP001", location="R99", next_points=[]),
    ])
    # Only R01 exists; R99 referenced by PP001 should be flagged.
    location_data = _make_locations("R01")

    errors = generator.validate_plot(plot_data, location_data)

    matching = [e for e in errors if "R99" in e]
    assert len(matching) >= 1, (
        f"Expected at least one error mentioning the non-existent "
        f"location 'R99'. errors={errors}"
    )


# ---------------------------------------------------------------------------
# Test 4 (vacuous): single plot point, empty nextPoints -> no errors
# ---------------------------------------------------------------------------

def test_validate_plot_single_point_empty_nextpoints(generator):
    """A plot with a single plot point and an empty ``nextPoints`` list
    is a valid degenerate case (terminal/only point). It must produce
    no nextPoints errors. Note: orphan-detection considers the FIRST
    plot point as the entry, so a one-point plot is also not orphaned."""
    plot_data = _make_plot([
        _make_plot_point("PP001", "R01", next_points=[]),
    ])
    location_data = _make_locations("R01")

    errors = generator.validate_plot(plot_data, location_data)

    bad = [
        e for e in errors
        if "nextPoint" in e.lower() or "next point" in e.lower()
    ]
    assert bad == [], (
        f"Expected zero nextPoints errors for single-point plot with "
        f"empty nextPoints, got: {bad}. Full errors: {errors}"
    )
