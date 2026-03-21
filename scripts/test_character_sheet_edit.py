# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Character Sheet Edit Feature Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for character sheet Edit button, Roll Your Own edit mode, and update_manual endpoint.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCharacterSheetEditUIContracts(unittest.TestCase):
    """Test suite for UI source contracts (Step 1 verification)."""

    def test_edit_button_appears_before_download_pdf(self):
        """Test: Edit button appears before Download PDF in character sheet action row."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "game_interface.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find the action row section with the TABLETOP MODE comment
        action_row_marker = '// TABLETOP MODE: Edit button shown only when tabletop'
        action_row_start = source.find(action_row_marker)
        self.assertGreater(action_row_start, 0, "Action row section should exist with TABLETOP MODE marker")
        
        # Get the relevant section (next ~600 chars should include both buttons)
        section = source[action_row_start:action_row_start + 600]
        
        # Find button tags specifically - need to look for the button tag patterns
        # The Edit button is inside the {% if %} block
        edit_button_pos = section.find('<button class="pdf-button" onclick="openCharacterEdit')
        download_button_pos = section.find('<button class="pdf-button" onclick="downloadCharacterSheetPDF')
        
        # Debug: print what we found
        if edit_button_pos == -1:
            # Try alternative pattern - maybe quotes are escaped differently
            edit_button_pos = section.find('openCharacterEdit')
        if download_button_pos == -1:
            download_button_pos = section.find('downloadCharacterSheetPDF')
        
        self.assertGreater(edit_button_pos, 0, f"Edit button element should exist in section. Section preview: {section[:200]}")
        self.assertGreater(download_button_pos, 0, f"Download PDF button element should exist in section. Section preview: {section[:200]}")
        self.assertLess(edit_button_pos, download_button_pos, "Edit button should appear before Download PDF button")

    def test_edit_button_has_sp_compatibility_guard(self):
        """Test: Edit button is guarded by tabletop mode condition."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "game_interface.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find the action row with Edit button
        action_section = source[source.find('// TABLETOP MODE: Edit button'):source.find('// TABLETOP MODE: Edit button') + 400]
        
        # Verify SP guard exists
        self.assertIn('{% if multiplayer_mode or party_members|length > 1 %}', action_section,
                      "SP compatibility guard should exist")
        self.assertIn('Edit', action_section, "Edit button should exist in guarded block")

    def test_manage_pc_modal_exists(self):
        """Test: Dedicated Manage PC modal exists for edit flow."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "partials", "character_tabs.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verify dedicated Manage PC modal exists (separate from Manage Party)
        self.assertIn('id="manage-pc-modal"', source,
                      "Manage PC modal should exist")
        self.assertIn('Manage PC', source,
                      "Modal title should be 'Manage PC'")
        self.assertIn('id="manage-pc-form"', source,
                      "Manage PC form should exist")
        
        # Verify no tabs in Manage PC modal (should only have the form)
        # (The form should be directly in npc-details-body without tab navigation)
        modal_section = source.split('id="manage-pc-modal"')[1].split('id="manage-pc-form"')[0]
        self.assertNotIn('tab-button', modal_section,
                          "Manage PC modal should not have tab buttons")
        self.assertNotIn('switchManageTab', modal_section,
                          "Manage PC modal should not use tab switching")

    def test_manage_pc_submit_button_text(self):
        """Test: Manage PC modal has 'Save Changes' submit button."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "partials", "character_tabs.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find Manage PC modal section
        pc_modal_section = source.split('id="manage-pc-modal"')[1]
        
        # Verify submit button says "Save Changes"
        self.assertIn('Save Changes', pc_modal_section,
                      "Manage PC submit button should say 'Save Changes'")
        self.assertIn('onclick="submitManagePcEdit()"', pc_modal_section,
                      "Manage PC form should call submitManagePcEdit")

    def test_open_character_edit_function_exists(self):
        """Test: openCharacterEdit function exists and opens Manage PC modal."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn('window.openCharacterEdit = function', source,
                      "openCharacterEdit should be defined")
        self.assertIn('openManagePcModal(characterName)', source,
                      "openCharacterEdit should open dedicated Manage PC modal")
        # NOTE: We no longer use quickCreateMode in edit flow - Manage PC is completely separate

    def test_submit_quick_create_uses_create_endpoint_only(self):
        """Test: submitQuickCreate always uses create_manual endpoint (no edit branching)."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find submitQuickCreate function using regex-like search
        func_start = source.find('function submitQuickCreate()')
        self.assertGreater(func_start, 0, "submitQuickCreate should exist")
        
        # Get full function body (until next function or end)
        next_func = source.find('\nfunction ', func_start + 1)
        if next_func == -1:
            func_body = source[func_start:]
        else:
            func_body = source[func_start:next_func]
        
        # Should use create_manual only (no endpoint branching based on mode)
        self.assertIn("fetch('/api/party/create_manual'", func_body,
                      "submitQuickCreate should use create_manual endpoint")
        self.assertNotIn("'/api/party/update_manual'", func_body,
                         "submitQuickCreate should NOT use update_manual endpoint")
        self.assertNotIn("quickCreateMode === 'edit'", func_body,
                         "submitQuickCreate should NOT branch based on edit mode")

    def test_submit_manage_pc_edit_uses_update_endpoint(self):
        """Test: submitManagePcEdit always uses update_manual endpoint."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find submitManagePcEdit function
        func_start = source.find('function submitManagePcEdit()')
        self.assertGreater(func_start, 0, "submitManagePcEdit should exist")
        
        # Get full function body (until next function or end)
        next_func = source.find('\nfunction ', func_start + 1)
        if next_func == -1:
            func_body = source[func_start:]
        else:
            func_body = source[func_start:next_func]
        
        # Should always use update_manual
        self.assertIn("fetch('/api/party/update_manual'", func_body,
                      "submitManagePcEdit should use update_manual endpoint")
        self.assertNotIn("'/api/party/create_manual'", func_body,
                         "submitManagePcEdit should NOT use create_manual endpoint")

    def test_prefill_helpers_exist(self):
        """Test: Prefill helper functions exist."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn('function _prefillQuickCreateForm', source,
                      "_prefillQuickCreateForm should exist")
        self.assertIn('function _fillQuickCreateForm', source,
                      "_fillQuickCreateForm should exist")

    def test_mode_state_variables_exist(self):
        """Test: Mode state tracking exists."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn("let quickCreateMode = 'create'", source,
                      "quickCreateMode state should exist")
        self.assertIn("let quickCreateEditTarget = null", source,
                      "quickCreateEditTarget state should exist")

    def test_endpoint_separation_no_cross_contamination(self):
        """Test: Create and Edit flows use separate endpoints without cross-contamination."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verify clear separation: submitQuickCreate should only hit create_manual
        # and submitManagePcEdit should only hit update_manual
        
        # Find both functions
        quick_create_start = source.find('function submitQuickCreate()')
        manage_pc_edit_start = source.find('function submitManagePcEdit()')
        
        self.assertGreater(quick_create_start, 0, "submitQuickCreate should exist")
        self.assertGreater(manage_pc_edit_start, 0, "submitManagePcEdit should exist")
        
        # Get function bodies
        next_func_after_quick = source.find('\nfunction ', quick_create_start + 1)
        quick_create_body = source[quick_create_start:next_func_after_quick if next_func_after_quick != -1 else len(source)]
        
        next_func_after_manage = source.find('\nfunction ', manage_pc_edit_start + 1)
        manage_pc_edit_body = source[manage_pc_edit_start:next_func_after_manage if next_func_after_manage != -1 else len(source)]
        
        # submitQuickCreate: create_manual only
        self.assertIn("/api/party/create_manual", quick_create_body,
                      "submitQuickCreate should use create_manual")
        self.assertNotIn("/api/party/update_manual", quick_create_body,
                         "submitQuickCreate should NOT use update_manual")
        
        # submitManagePcEdit: update_manual only
        self.assertIn("/api/party/update_manual", manage_pc_edit_body,
                      "submitManagePcEdit should use update_manual")
        self.assertNotIn("/api/party/create_manual", manage_pc_edit_body,
                         "submitManagePcEdit should NOT use create_manual")

    def test_reset_state_function_exists(self):
        """Test: State reset function exists and is called on modal close."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn('function resetQuickCreateState()', source,
                      "resetQuickCreateState should exist")
        self.assertIn('resetQuickCreateState()', source,
                      "resetQuickCreateState should be called")

    def test_clear_autofill_residue_function_exists(self):
        """Test: Helper to clear autofill residue exists and targets risk fields."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn('function clearQuickCreateAutofillResidue()', source,
                      "clearQuickCreateAutofillResidue should exist")
        
        # Verify it targets high-risk fields for stale carryover
        self.assertIn("'equipment'", source,
                      "Should clear equipment field")
        self.assertIn("'attacks'", source,
                      "Should clear attacks field")
        self.assertIn("'personality_traits'", source,
                      "Should clear personality_traits field")
        self.assertIn("'backstory'", source,
                      "Should clear backstory field")

    def test_open_manage_party_resets_and_sanitizes(self):
        """Test: openManagePartyModal resets state and clears autofill before loading."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Find openManagePartyModal function
        func_start = source.find('function openManagePartyModal()')
        self.assertGreater(func_start, 0, "openManagePartyModal should exist")
        
        # Get function body (until next function or modal display)
        next_func = source.find('\nfunction ', func_start + 1)
        func_body = source[func_start:next_func if next_func != -1 else len(source)]
        
        # Should call reset and sanitize before loadExistingCharacters
        load_existing_pos = func_body.find('loadExistingCharacters()')
        self.assertGreater(load_existing_pos, 0, "Should call loadExistingCharacters")
        
        reset_state_pos = func_body.find('resetQuickCreateState()')
        clear_residue_pos = func_body.find('clearQuickCreateAutofillResidue()')
        switch_tab_pos = func_body.find("switchManageTab('add-existing')")
        
        # All sanitization must happen before loading characters
        self.assertLess(reset_state_pos, load_existing_pos,
                       "resetQuickCreateState must be called before loadExistingCharacters")
        self.assertLess(clear_residue_pos, load_existing_pos,
                       "clearQuickCreateAutofillResidue must be called before loadExistingCharacters")
        self.assertLess(switch_tab_pos, load_existing_pos,
                       "switchManageTab must be called before loadExistingCharacters")

    def test_party_data_socket_payload_includes_tab_sync_fields(self):
        """Test: party_data_response payload includes party_members and active_character."""
        socket_handler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "extensions", "tabletop_socket_handlers.py"
        )

        with open(socket_handler_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn("'party_members': _dedupe_party_member_names_for_emit(party_tracker.get('partyMembers', []))", source,
                      "party_data_response should emit deduped party_members for tab sync")
        self.assertIn("'active_character': party_tracker.get('active_character')", source,
                      "party_data_response should include active_character for tab sync")

    def test_party_tab_sync_has_canonical_name_helper(self):
        """Test: tabletop tab sync defines canonical party-member normalizer."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )

        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('function canonicalizePartyMemberName(characterName)', source,
                      "canonicalizePartyMemberName helper should exist")
        self.assertIn(".replace(/\\s+/g, '_')", source,
                      "canonicalizer should normalize whitespace")
        self.assertIn(".replace(/'/g, '_')", source,
                      "canonicalizer should normalize apostrophes")

    def test_party_tab_sync_dedupes_incoming_party_members(self):
        """Test: tab sync dedupes mixed-form names before DOM rebuild."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )

        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('const seenMembers = new Set();', source,
                      "tab sync should track seen canonical members")
        self.assertIn('const canonical = canonicalizePartyMemberName(memberName);', source,
                      "tab sync should canonicalize each member")
        self.assertIn('if (!canonical || seenMembers.has(canonical)) {', source,
                      "tab sync should skip duplicate/empty canonical names")

    def test_update_tab_ui_uses_canonical_comparison(self):
        """Test: active tab/card highlighting compares canonical names."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )

        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('const activeCanonical = canonicalizePartyMemberName(activeName);', source,
                      "updateTabUI should canonicalize activeName")
        self.assertIn("tab.classList.toggle('active', tabCanonical === activeCanonical);", source,
                      "tab highlighting should use canonical equality")
        self.assertIn("card.classList.toggle('active', cardCanonical === activeCanonical);", source,
                      "sidebar highlighting should use canonical equality")

    def test_party_data_listener_calls_tab_sync_reconciler(self):
        """Test: tabletop socket listener invokes tab reconciler on party updates."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )

        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('function syncCharacterTabsFromPartyResponse(response)', source,
                      "Tab sync reconciler should exist")
        self.assertIn('syncCharacterTabsFromPartyResponse(response);', source,
                      "party_data_response listener should invoke tab sync reconciler")
        self.assertIn('response.party_members', source,
                      "Tab sync should use party_members from payload")

    def test_character_tab_template_displays_spaces_but_preserves_raw_data_attribute(self):
        """Test: tab template shows space-friendly labels while preserving canonical data-character values."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "partials", "character_tabs.html"
        )

        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('data-character="{{ member }}"', source,
                      "Tab data-character should preserve canonical member value")
        self.assertIn("{{ member|replace('_', ' ') }}", source,
                      "Tab label should replace underscores with spaces")

    def test_character_tab_js_uses_display_formatter_and_preserves_raw_identifier(self):
        """Test: runtime tab rebuild formats label text but keeps canonical data-character identifier."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )

        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()

        self.assertIn('function formatTabLabel(characterName)', source,
                      "formatTabLabel helper should exist")
        self.assertIn("tabButton.setAttribute('data-character', memberName);", source,
                      "Runtime tab rebuild should preserve canonical data-character value")
        self.assertIn('tabButton.textContent = formatTabLabel(memberName);', source,
                      "Runtime tab rebuild should display formatted tab label")

    def test_forms_have_autocomplete_off(self):
        """Test: Roll Your Own and Manage PC forms disable browser autofill."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "partials", "character_tabs.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Both forms should have autocomplete="off"
        self.assertIn('id="quick-create-form"', source,
                      "quick-create-form should exist")
        self.assertIn('id="manage-pc-form"', source,
                      "manage-pc-form should exist")
        
        # Check for autocomplete="off" on forms
        quick_create_form_section = source.split('id="quick-create-form"')[1].split('>')[0]
        self.assertIn('autocomplete="off"', quick_create_form_section,
                      "quick-create-form should have autocomplete=\"off\"")
        
        manage_pc_form_section = source.split('id="manage-pc-form"')[1].split('>')[0]
        self.assertIn('autocomplete="off"', manage_pc_form_section,
                      "manage-pc-form should have autocomplete=\"off\"")

    def test_high_risk_fields_have_autocomplete_off(self):
        """Test: Equipment and attacks inputs disable browser autofill."""
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "templates", "partials", "character_tabs.html"
        )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Equipment input should have autocomplete="off"
        equipment_section = source.split('id="quick-create-equipment"')[1].split('>')[0]
        self.assertIn('autocomplete="off"', equipment_section,
                      "quick-create-equipment should have autocomplete=\"off\"")
        
        # Attacks input should have autocomplete="off"
        attacks_section = source.split('id="quick-create-attacks"')[1].split('>')[0]
        self.assertIn('autocomplete="off"', attacks_section,
                      "quick-create-attacks should have autocomplete=\"off\"")


class TestUpdateManualBackendContract(unittest.TestCase):
    """Test suite for /api/party/update_manual endpoint (Step 2 verification)."""

    def _get_route_source(self):
        """Helper to read route source without importing Flask-dependent module."""
        route_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "tabletop_party_routes.py"
        )
        with open(route_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_update_manual_route_exists(self):
        """Test: Backend edit route is registered."""
        source = self._get_route_source()
        
        self.assertIn("@app.route('/api/party/update_manual'", source,
                      "update_manual route should be registered")
        self.assertIn("def update_manual_character()", source,
                      "update_manual_character function should exist")

    def test_update_manual_loads_existing_character(self):
        """Test: Edit route loads existing character before merging."""
        source = self._get_route_source()
        
        self.assertIn("pc_manager.get_character_state(character_name)", source,
                      "Should load existing character")
        self.assertIn("if not existing_char:", source,
                      "Should check if character exists")
        self.assertIn("return jsonify({'error': f'Character {character_name} not found'})", source,
                      "Should return 404 if character not found")

    def test_update_manual_runs_audit_before_save(self):
        """Test: Edit route runs audit validation before saving."""
        source = self._get_route_source()
        
        self.assertIn("audit_character_creation(", source,
                      "Should run audit validation")
        self.assertIn("if audit_result.result_type != AUDIT_RESULT_SUCCESS:", source,
                      "Should check audit result")
        self.assertIn("'error': 'Manual character edit validation failed'", source,
                      "Should return validation error on audit failure")

    def test_update_manual_no_party_mutation(self):
        """Test: Edit route does not mutate party membership."""
        source = self._get_route_source()
        
        # Split to get update_manual function specifically (it's the last function)
        update_section = source.split("@app.route('/api/party/update_manual'")[-1]
        
        # Should NOT have these create-only side effects in the update section
        self.assertNotIn("pc_manager.add_pc", update_section,
                         "Edit route should NOT add to party")
        self.assertNotIn("user_input_queue.put", update_section,
                         "Edit route should NOT enqueue prompts")
        self.assertNotIn("get_entrance_prompt", update_section,
                         "Edit route should NOT get entrance prompt")

    def test_update_manual_preserves_non_targeted_state(self):
        """Test: Edit route preserves non-targeted nested structures."""
        source = self._get_route_source()
        
        # Check for preservation logic in equipment/attacks
        self.assertIn("existing_item = next(", source,
                      "Should check for existing items to preserve details")
        self.assertIn("if existing_item:", source,
                      "Should preserve existing item details")


class TestCreateModeNonRegression(unittest.TestCase):
    """Test suite to ensure create mode still works correctly."""

    def _get_route_source(self):
        """Helper to read route source without importing Flask-dependent module."""
        route_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "tabletop_party_routes.py"
        )
        with open(route_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_create_manual_route_unchanged(self):
        """Test: Create route still exists and functions."""
        source = self._get_route_source()
        
        self.assertIn("@app.route('/api/party/create_manual'", source,
                      "create_manual route should still exist")
        self.assertIn("def create_manual_character()", source,
                      "create_manual_character function should exist")

    def test_create_mode_still_adds_to_party(self):
        """Test: Create mode still has party mutation side effects."""
        source = self._get_route_source()
        
        # Split to get create_manual section (before update_manual)
        create_section = source.split("@app.route('/api/party/create_manual'")[1].split("@app.route('/api/party/update_manual'")[0]
        
        self.assertIn("pc_manager.add_pc(name)", create_section,
                      "Create should still add to party")
        self.assertIn("user_input_queue.put(intro_prompt)", create_section,
                      "Create should still enqueue intro prompt")

    def test_submit_defaults_to_create_mode(self):
        """Test: Default mode is create (quickCreateMode initialized to 'create')."""
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "static", "js", "tabletop_mode.js"
        )
        
        with open(js_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        self.assertIn("let quickCreateMode = 'create'", source,
                      "Default mode should be 'create'")


class TestLanguagesFieldMapping(unittest.TestCase):
    """Test suite for languages field mapping consistency."""

    def _get_route_source(self):
        """Helper to read route source without importing Flask-dependent module."""
        route_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web", "routes", "tabletop_party_routes.py"
        )
        with open(route_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_create_manual_uses_top_level_languages(self):
        """Test: Create route uses top-level languages field."""
        source = self._get_route_source()
        
        # In create_manual section
        create_section = source.split("@app.route('/api/party/create_manual'")[1].split("@app.route('/api/party/update_manual'")[0]
        
        # Should set top-level languages
        self.assertIn('"languages": _split_csv(data.get(\'languages\',', create_section,
                      "Create should set top-level languages")

    def test_update_manual_preserves_proficiencies_languages(self):
        """Test: Update route updates proficiencies.languages."""
        source = self._get_route_source()
        
        # In update_manual section
        update_section = source.split("@app.route('/api/party/update_manual'")[-1]
        
        # Updates proficiencies.languages if data provided
        self.assertIn("if data.get('languages'):", update_section,
                      "Update should check for languages in data")
        self.assertIn("merged_char['proficiencies']['languages']", update_section,
                      "Update should set proficiencies.languages")


class TestOnePcRecoveryVisibilityContracts(unittest.TestCase):
    """Source contracts for one-PC tabletop recovery visibility."""

    @staticmethod
    def _project_root() -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_web_interface_exposes_startup_recovery_context(self):
        """Web index route exposes startup recovery booleans for templates."""
        source_path = os.path.join(self._project_root(), "web", "web_interface.py")
        with open(source_path, 'r', encoding='utf-8') as file_handle:
            source = file_handle.read()

        self.assertIn("startup_incomplete = party_data.get('startup_incomplete') is True", source,
                      "index route should compute startup_incomplete")
        self.assertIn("show_one_pc_tabletop_recovery = bool(", source,
                      "index route should compute one-PC tabletop recovery visibility")
        self.assertIn("MULTIPLAYER_MODE and startup_incomplete and len(party_members) == 1", source,
                      "one-PC recovery visibility should remain conservative")
        self.assertIn("startup_incomplete=startup_incomplete,", source,
                      "startup_incomplete should be passed to template context")
        self.assertIn("show_one_pc_tabletop_recovery=show_one_pc_tabletop_recovery,", source,
                      "recovery visibility boolean should be passed to template context")

    def test_game_interface_character_tabs_include_allows_recovery(self):
        """Character tabs include gate should allow one-PC tabletop recovery state."""
        source_path = os.path.join(self._project_root(), "web", "templates", "game_interface.html")
        with open(source_path, 'r', encoding='utf-8') as file_handle:
            source = file_handle.read()

        self.assertIn(
            "{% if multiplayer_mode or party_members|length > 1 or show_one_pc_tabletop_recovery %}",
            source,
            "Character tabs include should allow one-PC tabletop recovery",
        )

    def test_character_tabs_outer_container_allows_recovery(self):
        """Character tabs container hidden guard should allow one-PC recovery visibility."""
        source_path = os.path.join(self._project_root(), "web", "templates", "partials", "character_tabs.html")
        with open(source_path, 'r', encoding='utf-8') as file_handle:
            source = file_handle.read()

        self.assertIn(
            "{% if not (multiplayer_mode or party_members|length > 1 or show_one_pc_tabletop_recovery) %}",
            source,
            "Character tabs container should remain visible during one-PC recovery",
        )

    def test_unrelated_tabletop_asset_gates_remain_unchanged(self):
        """CSS/JS tabletop asset gates remain scoped to existing multiplayer condition."""
        source_path = os.path.join(self._project_root(), "web", "templates", "game_interface.html")
        with open(source_path, 'r', encoding='utf-8') as file_handle:
            source = file_handle.read()

        self.assertIn(
            "{% if multiplayer_mode or party_members|length > 1 %}\n    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/tabletop_mode.css') }}\">",
            source,
            "Top-level tabletop CSS gate should remain unchanged",
        )
        self.assertIn(
            "{% if multiplayer_mode or party_members|length > 1 %}\n    <script src=\"{{ url_for('static', filename='js/tabletop_mode.js') }}\"></script>",
            source,
            "tabletop_mode.js include gate should remain unchanged",
        )


if __name__ == '__main__':
    # Run with verbosity
    unittest.main(verbosity=2)
