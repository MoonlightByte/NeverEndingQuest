"""Test that legacy characters are repaired and persisted on startup."""

import json
import os
import tempfile
import pytest
from pathlib import Path


class TestLegacyCharacterRepair:
    """Test startup repair of legacy character files."""

    def test_missing_ammunition_is_repaired_and_persisted(self, tmp_path):
        """Character missing ammunition field should be fixed and saved."""
        from utils.character_sheet_contract import repair_and_persist_character

        # Create a legacy character missing ammunition
        char_file = tmp_path / "test_char.json"
        legacy_char = {
            "name": "Test Hero",
            "level": 1,
            "hitPoints": 10,
            "maxHitPoints": 10,
            "equipment": []
            # Note: ammunition is missing
        }
        with open(char_file, 'w') as f:
            json.dump(legacy_char, f)

        # Run repair
        repaired, changes = repair_and_persist_character(str(char_file))

        # Verify in-memory fix
        assert "ammunition" in repaired
        assert repaired["ammunition"] == []
        assert "ammunition" in changes

        # Verify persisted to disk
        with open(char_file, 'r') as f:
            saved_char = json.load(f)
        assert "ammunition" in saved_char
        assert saved_char["ammunition"] == []

    def test_complete_character_not_modified(self, tmp_path):
        """Character with all fields should not be re-saved."""
        from utils.character_sheet_contract import repair_and_persist_character

        char_file = tmp_path / "complete_char.json"
        complete_char = {
            "name": "Complete Hero",
            "level": 1,
            "hitPoints": 10,
            "maxHitPoints": 10,
            "equipment": [],
            "ammunition": [],
            "condition_affected": [],
            "temporaryEffects": [],
            "injuries": [],
            "equipment_effects": [],
            "feats": [],
        }
        with open(char_file, 'w') as f:
            json.dump(complete_char, f)

        original_mtime = os.path.getmtime(char_file)

        # Run repair
        repaired, changes = repair_and_persist_character(str(char_file))

        # Verify no changes reported
        assert len(changes) == 0

        # File should not be rewritten (mtime unchanged)
        # Note: This is a best-effort check; some filesystems have low resolution
        assert os.path.getmtime(char_file) == original_mtime

    def test_multiple_missing_fields_all_repaired(self, tmp_path):
        """Multiple missing fields should all be fixed in one pass."""
        from utils.character_sheet_contract import repair_and_persist_character

        char_file = tmp_path / "minimal_char.json"
        minimal_char = {
            "name": "Minimal Hero"
            # Missing: level, hitPoints, equipment, ammunition, etc.
        }
        with open(char_file, 'w') as f:
            json.dump(minimal_char, f)

        repaired, changes = repair_and_persist_character(str(char_file))

        # Should have multiple repairs
        assert len(changes) > 5

        # Core fields should be present
        assert "ammunition" in repaired
        assert "level" in repaired
        assert "hitPoints" in repaired

        # Verify persisted
        with open(char_file, 'r') as f:
            saved = json.load(f)
        assert "ammunition" in saved

    def test_file_not_found_returns_none(self):
        """Non-existent file should return None gracefully."""
        from utils.character_sheet_contract import repair_and_persist_character

        result = repair_and_persist_character("/nonexistent/path/char.json")
        assert result is None

    def test_invalid_json_returns_none(self, tmp_path):
        """Invalid JSON file should return None gracefully."""
        from utils.character_sheet_contract import repair_and_persist_character

        bad_file = tmp_path / "bad.json"
        with open(bad_file, 'w') as f:
            f.write("{ not valid json }")

        result = repair_and_persist_character(str(bad_file))
        assert result is None
