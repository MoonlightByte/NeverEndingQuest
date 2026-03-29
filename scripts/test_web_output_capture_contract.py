#!/usr/bin/env python3
"""Source-contract checks for WebOutputCapture narration/log separation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_INTERFACE_PATH = PROJECT_ROOT / "web" / "web_interface.py"


def _load_source() -> str:
    return WEB_INTERFACE_PATH.read_text(encoding="utf-8")


def test_non_narrative_prefixes_cover_combat_init_leak_markers() -> None:
    source = _load_source()

    required_prefixes = [
        "'[DEBUG ACTION_HANDLER]'",
        "'[Py]'",
        "'[COMBAT_BUILDER]'",
        "'STDOUT:'",
        '"Starting NeverEndingQuest Web Interface..."',
    ]
    for required_prefix in required_prefixes:
        assert required_prefix in source, (
            f"Expected combat-init leak marker {required_prefix} to be filtered as non-narrative"
        )


def test_narration_exceptions_preserve_system_messages() -> None:
    source = _load_source()

    assert "WEB_OUTPUT_NARRATION_PREFIX_EXCEPTIONS" in source
    assert "'[SYSTEM]'" in source
    assert "'[skipTTS]'" in source


def test_dm_section_uses_non_narrative_helper() -> None:
    source = _load_source()

    helper_call = "is_non_narrative_output_line(clean_line)"
    assert helper_call in source, "WebOutputCapture should centralize non-narrative detection"

    dm_section_pos = source.find("elif self.in_dm_section:")
    helper_pos = source.find(helper_call, dm_section_pos)
    non_dm_pos = source.find("if is_non_narrative_output_line(clean_line):", dm_section_pos)

    assert helper_pos != -1, "DM section should terminate narration on runtime/log lines"
    assert non_dm_pos != -1, "Non-DM lines should also route through the helper"


def main() -> None:
    test_non_narrative_prefixes_cover_combat_init_leak_markers()
    test_narration_exceptions_preserve_system_messages()
    test_dm_section_uses_non_narrative_helper()
    print("[PASS] web output capture contract checks")


if __name__ == "__main__":
    main()
