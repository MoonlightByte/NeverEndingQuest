"""
Tests for INT-M6 (T5-6): fix the `\\n` double-escape in
`CampaignManager.get_accumulated_summaries_context`.

Bug: the method used the literal Python string `"\\n"` (which represents
two characters: a backslash followed by `n`) in `.append(...)` and
`.join(...)` calls. The intent was a real newline (`"\n"`, character 0x0A).
As a result, the campaign context handed to the AI was a run-on string
peppered with literal "\\n" sequences instead of being broken into lines.

Fix: replace each of those five `"\\n"` literals with `"\n"` so the
resulting string contains actual line breaks.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.managers import campaign_manager  # noqa: E402


def _make_cm_instance(campaign_data, summaries_by_module):
    """Build a CampaignManager without running __init__ (which creates
    the OpenAI client and loads campaign files from disk). We then
    stub `_load_module_summaries` so the test owns the data."""
    inst = object.__new__(campaign_manager.CampaignManager)
    inst.client = MagicMock()
    inst.campaign_data = campaign_data
    inst.summaries_dir = "modules/campaign_summaries"
    inst.archives_dir = "modules/campaign_archives"

    def fake_load(module_name):
        return summaries_by_module.get(module_name, [])

    inst._load_module_summaries = fake_load
    return inst


def test_get_accumulated_summaries_context_uses_real_newlines():
    """The returned context must contain real newline characters
    (chr(10)) joining sections. It must NOT contain the literal
    backslash-n sequence that the bug produced.

    We carefully avoid putting "\\n" inside the test fixture content
    so any literal backslash-n in the output can only have come from
    the buggy join/append calls in the function under test.
    """
    # Note: no "\\n" anywhere in the seeded data, so the only way
    # a literal backslash-n could appear in the output is from the
    # function's own formatting.
    campaign_data = {
        "campaignName": "Test Campaign Alpha",
        "completedModules": ["ModuleOne"],
        "worldState": {"peace_restored": True},
    }
    summaries = {
        "ModuleOne": [
            {
                "sequenceNumber": 1,
                "summary": "The party defeated the bandits and rescued the merchant.",
            },
        ],
    }
    inst = _make_cm_instance(campaign_data, summaries)

    result = inst.get_accumulated_summaries_context("CurrentMod")

    # The result must contain at least one real newline.
    assert "\n" in result, (
        "Context should contain real newline characters separating "
        "sections, but no '\\n' (chr(10)) was found"
    )

    # The result must NOT contain a literal backslash-n sequence,
    # because none of the fixture data contains one. If we see this,
    # it means the function still uses '\\n' (two chars) in its
    # join/append calls.
    assert "\\n" not in result, (
        "Context must not contain literal backslash-n. This indicates "
        "the function is still using '\\\\n' (Python literal '\\n') "
        "instead of the newline escape '\\n' (chr(10))"
    )

    # Sanity: the section headers the function emits should be on
    # their own logical lines, i.e. preceded by a real newline.
    assert "\nPREVIOUS ADVENTURES:" in result
    assert "\nWORLD STATE:" in result
    assert "\n=== CHRONICLES OF MODULEONE ===" in result
    assert "\n--- Visit 1 (Chronicle 001) ---" in result


def test_get_accumulated_summaries_context_no_completed_modules():
    """Even with no completed modules, the join at the end of the
    function must still use a real newline so the campaign header
    lines are separated correctly."""
    campaign_data = {
        "campaignName": "Empty Campaign",
        "completedModules": [],
        "worldState": {},
    }
    inst = _make_cm_instance(campaign_data, {})

    result = inst.get_accumulated_summaries_context("CurrentMod")

    assert "\n" in result, "Final join must use a real newline"
    assert "\\n" not in result, (
        "No literal backslash-n should appear in the joined context"
    )
    # Campaign + current module headers should be on separate lines.
    assert "CAMPAIGN: Empty Campaign\nCurrent Module: CurrentMod" in result
