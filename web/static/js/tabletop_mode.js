/**
 * Tabletop Mode Controller
 * Handles character tab switching and party management for local tabletop play.
 */

const tabletopSocket = window.socket || io();
if (!window.socket) {
    window.socket = tabletopSocket;
}

/**
 * Sets the currently active character for the session.
 * Updates the UI and notifies the backend.
 * @param {string} characterName - The name of the character to activate.
 */
function setActiveCharacter(characterName) {
    console.log(`Setting active character to: ${characterName}`);
    
    fetch('/api/party/set_active', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ character: characterName }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.active_character = characterName;
            if (typeof playerName !== 'undefined') {
                playerName = characterName;
            }

            updateTabUI(characterName);

            // Refresh stats and other data for the new active character
            if (typeof loadCharacterStats === 'function') loadCharacterStats();
            if (typeof loadInventory === 'function') loadInventory();
            if (typeof loadSpellsAndMagic === 'function') loadSpellsAndMagic();
            if (typeof requestInitiativeData === 'function') requestInitiativeData();
        } else {
            console.error('Failed to set active character:', data.error);
        }
    })
    .catch(error => {
        console.error('Error setting active character:', error);
    });
}

/**
 * Updates the tab UI to reflect the active character.
 * @param {string} activeName - The name of the active character.
 */
function updateTabUI(activeName) {
    const activeCanonical = canonicalizePartyMemberName(activeName);
    const tabs = document.querySelectorAll('.character-tab');
    tabs.forEach(tab => {
        const tabCanonical = canonicalizePartyMemberName(tab.getAttribute('data-character'));
        tab.classList.toggle('active', tabCanonical === activeCanonical);
    });
    
    // Also update sidebar if present
    const cards = document.querySelectorAll('.party-member-card');
    cards.forEach(card => {
        const cardCanonical = canonicalizePartyMemberName(card.getAttribute('data-character'));
        card.classList.toggle('active', cardCanonical === activeCanonical);
    });
}

/**
 * TABLETOP MODE: Format tab label for display only.
 * Keeps canonical character identifiers unchanged for routing/state.
 * @param {string} characterName
 * @returns {string}
 */
function formatTabLabel(characterName) {
    return String(characterName || '').replace(/_/g, ' ');
}

function canonicalizePartyMemberName(characterName) {
    return String(characterName || '')
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/'/g, '_')
        .replace(/[^a-z0-9_]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
}

/**
 * TABLETOP MODE: Reconcile character tab DOM from backend party payload.
 * Keeps tabs in sync during startup creation queue without requiring page reload.
 * @param {Object} response - party_data_response payload
 */
function syncCharacterTabsFromPartyResponse(response) {
    const tabsContainer = document.getElementById('character-tabs-container');
    const tabsList = document.getElementById('character-tabs-list');
    if (!tabsContainer || !tabsList) {
        return;
    }

    const rawPartyMembers = Array.isArray(response && response.party_members)
        ? response.party_members
        : [];
    const partyMembers = [];
    const seenMembers = new Set();
    rawPartyMembers.forEach((memberName) => {
        const canonical = canonicalizePartyMemberName(memberName);
        if (!canonical || seenMembers.has(canonical)) {
            return;
        }
        seenMembers.add(canonical);
        partyMembers.push(String(memberName));
    });

    if (!partyMembers.length) {
        return;
    }

    // Unhide when runtime state transitions to tabletop/multi-PC during startup flow.
    if (partyMembers.length > 1) {
        tabsContainer.style.display = 'flex';
    }

    const activeFromPayload = (response && response.active_character) || '';
    const activePayloadCanonical = canonicalizePartyMemberName(activeFromPayload);
    const windowActiveCanonical = canonicalizePartyMemberName(window.active_character || '');
    const resolvedActive =
        partyMembers.find((member) => canonicalizePartyMemberName(member) === activePayloadCanonical) ||
        partyMembers.find((member) => canonicalizePartyMemberName(member) === windowActiveCanonical) ||
        partyMembers[0];

    window.active_character = resolvedActive;

    // Rebuild tab list deterministically in party order.
    tabsList.innerHTML = '';
    partyMembers.forEach((memberName) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'character-tab-wrapper';
        wrapper.style.position = 'relative';
        wrapper.style.display = 'inline-block';

        const tabButton = document.createElement('button');
        tabButton.className = `character-tab${memberName === resolvedActive ? ' active' : ''}`;
        tabButton.setAttribute('data-character', memberName);
        tabButton.textContent = formatTabLabel(memberName);

        const retireButton = document.createElement('span');
        retireButton.className = 'retire-character-btn';
        retireButton.setAttribute('data-character', memberName);
        retireButton.setAttribute('title', 'Retire from Party');
        retireButton.style.position = 'absolute';
        retireButton.style.top = '-5px';
        retireButton.style.right = '-5px';
        retireButton.style.background = '#f44336';
        retireButton.style.color = 'white';
        retireButton.style.borderRadius = '50%';
        retireButton.style.width = '15px';
        retireButton.style.height = '15px';
        retireButton.style.fontSize = '10px';
        retireButton.style.lineHeight = '15px';
        retireButton.style.textAlign = 'center';
        retireButton.style.cursor = 'pointer';
        retireButton.style.display = 'none';
        retireButton.style.zIndex = '10';
        retireButton.innerHTML = '&times;';

        wrapper.appendChild(tabButton);
        wrapper.appendChild(retireButton);
        tabsList.appendChild(wrapper);
    });

    updateTabUI(resolvedActive);

    // Refresh active sheet promptly once runtime party state becomes available.
    if (typeof loadCharacterStats === 'function') {
        loadCharacterStats();
    }
}

/**
 * Opens the modal for managing the party (adding/removing characters).
 */
function openManagePartyModal() {
    const modal = document.getElementById('manage-party-modal');
    if (!modal) {
        console.error('Manage Party Modal not found in DOM');
        return;
    }

    // TABLETOP MODE: Force reset and sanitize Roll Your Own state on every open
    // Prevents stale field carryover from prior UI state/autofill
    resetQuickCreateState();
    clearQuickCreateAutofillResidue();
    
    // Force default tab to prevent landing on Roll Your Own with stale values
    switchManageTab('add-existing');

    modal.style.display = 'block';
    loadExistingCharacters();
}

function closeManagePartyModal() {
    const modal = document.getElementById('manage-party-modal');
    if (!modal) {
        return;
    }

    modal.style.display = 'none';
    
    // Reset quick-create state when closing modal
    resetQuickCreateState();
}

// TABLETOP MODE: Manage PC Modal handlers (Edit Only - separate from Manage Party)
// These handlers manage the dedicated character edit modal

function openManagePcModal(characterName) {
    const modal = document.getElementById('manage-pc-modal');
    if (!modal) {
        console.error('Manage PC Modal not found in DOM');
        return;
    }

    // Prefill the form with character data
    _prefillManagePcForm(characterName);
    
    modal.style.display = 'block';
}

function closeManagePcModal() {
    const modal = document.getElementById('manage-pc-modal');
    if (!modal) {
        return;
    }

    modal.style.display = 'none';
    
    // Reset the form
    const form = document.getElementById('manage-pc-form');
    if (form) {
        form.reset();
    }
}

// TABLETOP MODE: Prefill Manage PC form with existing character data
function _prefillManagePcForm(characterName) {
    // Get character data from global lastCharacterStats or fetch fresh
    const charData = window.lastCharacterStats || {};
    
    // If no data in cache, fetch it
    if (!charData.name || charData.name.toLowerCase().replace(/\s+/g, '_') !== characterName) {
        // Need to fetch - use existing character data from window if available
        fetch(`/api/party/characters?source=players`)
            .then(r => r.json())
            .then(data => {
                const characters = data.characters || [];
                const found = characters.find(c => 
                    c.name.toLowerCase().replace(/\s+/g, '_') === characterName
                );
                if (found) {
                    _fillManagePcForm(found);
                }
            })
            .catch(err => console.error('Error loading character for edit:', err));
        return;
    }
    
    _fillManagePcForm(charData);
}

// TABLETOP MODE: Fill Manage PC form fields with character data
function _fillManagePcForm(data) {
    // Set hidden character name field
    const nameField = document.getElementById('manage-pc-character-name');
    if (nameField) nameField.value = data.name || '';
    
    // Identity
    document.getElementById('manage-pc-name').value = data.name || '';
    document.getElementById('manage-pc-race').value = data.race || '';
    document.getElementById('manage-pc-class').value = data.class || '';
    document.getElementById('manage-pc-level').value = data.level || '1';
    document.getElementById('manage-pc-alignment').value = data.alignment || '';
    document.getElementById('manage-pc-background').value = data.background || '';
    
    // Appearance
    document.getElementById('manage-pc-age').value = data.age || '';
    document.getElementById('manage-pc-height').value = data.height || '';
    document.getElementById('manage-pc-weight').value = data.weight || '';
    document.getElementById('manage-pc-eyes').value = data.eyes || '';
    document.getElementById('manage-pc-skin').value = data.skin || '';
    document.getElementById('manage-pc-hair').value = data.hair || '';
    
    // Abilities
    if (data.abilities) {
        document.getElementById('manage-pc-str').value = data.abilities.strength || '10';
        document.getElementById('manage-pc-dex').value = data.abilities.dexterity || '10';
        document.getElementById('manage-pc-con').value = data.abilities.constitution || '10';
        document.getElementById('manage-pc-int').value = data.abilities.intelligence || '10';
        document.getElementById('manage-pc-wis').value = data.abilities.wisdom || '10';
        document.getElementById('manage-pc-cha').value = data.abilities.charisma || '10';
    }
    
    // Combat
    document.getElementById('manage-pc-ac').value = data.armorClass || '10';
    document.getElementById('manage-pc-hp').value = data.hitPoints || '10';
    document.getElementById('manage-pc-initiative').value = data.initiative || '0';
    document.getElementById('manage-pc-speed').value = data.speed || '30';
    
    // Saves and Skills (convert arrays to comma-separated)
    if (data.savingThrows && Array.isArray(data.savingThrows)) {
        document.getElementById('manage-pc-saving-throws').value = data.savingThrows.join(', ');
    }
    if (data.skills) {
        if (Array.isArray(data.skills)) {
            document.getElementById('manage-pc-skills').value = data.skills.join(', ');
        }
    }
    
    // Proficiencies
    if (data.proficiencies) {
        if (data.proficiencies.languages) {
            document.getElementById('manage-pc-languages').value = 
                Array.isArray(data.proficiencies.languages) ? data.proficiencies.languages.join(', ') : data.languages || 'Common';
        }
        if (data.proficiencies.armor) {
            document.getElementById('manage-pc-prof-armor').value = 
                Array.isArray(data.proficiencies.armor) ? data.proficiencies.armor.join(', ') : '';
        }
        if (data.proficiencies.weapons) {
            document.getElementById('manage-pc-prof-weapons').value = 
                Array.isArray(data.proficiencies.weapons) ? data.proficiencies.weapons.join(', ') : '';
        }
        if (data.proficiencies.tools) {
            document.getElementById('manage-pc-prof-tools').value = 
                Array.isArray(data.proficiencies.tools) ? data.proficiencies.tools.join(', ') : '';
        }
    }
    
    // Equipment (convert equipment objects to comma-separated names)
    if (data.equipment && Array.isArray(data.equipment)) {
        const equipmentNames = data.equipment.map(item => item.item_name).filter(Boolean);
        document.getElementById('manage-pc-equipment').value = equipmentNames.join(', ');
    }
    
    // Attacks (convert attacksAndSpellcasting objects to comma-separated names)
    if (data.attacksAndSpellcasting && Array.isArray(data.attacksAndSpellcasting)) {
        const attackNames = data.attacksAndSpellcasting.map(attack => attack.name).filter(Boolean);
        document.getElementById('manage-pc-attacks').value = attackNames.join(', ');
    }
    
    // Spellcasting
    if (data.spellcasting) {
        document.getElementById('manage-pc-spellcasting-ability').value = data.spellcasting.ability || 'none';
        document.getElementById('manage-pc-spell-dc').value = data.spellcasting.spellSaveDC || '8';
        document.getElementById('manage-pc-spell-attack-bonus').value = data.spellcasting.spellAttackBonus || '0';
        if (data.spellcasting.spells) {
            if (data.spellcasting.spells.cantrips) {
                document.getElementById('manage-pc-cantrips').value = 
                    Array.isArray(data.spellcasting.spells.cantrips) ? data.spellcasting.spells.cantrips.join(', ') : '';
            }
            if (data.spellcasting.spells.level1) {
                document.getElementById('manage-pc-level1-spells').value = 
                    Array.isArray(data.spellcasting.spells.level1) ? data.spellcasting.spells.level1.join(', ') : '';
            }
        }
    }
    
    // Personality
    document.getElementById('manage-pc-personality-traits').value = data.personality_traits || '';
    document.getElementById('manage-pc-ideals').value = data.ideals || '';
    document.getElementById('manage-pc-bonds').value = data.bonds || '';
    document.getElementById('manage-pc-flaws').value = data.flaws || '';
    document.getElementById('manage-pc-backstory').value = data.backstory || '';
    
    // Background Feature
    if (data.backgroundFeature) {
        document.getElementById('manage-pc-background-feature-name').value = data.backgroundFeature.name || '';
        document.getElementById('manage-pc-background-feature-description').value = data.backgroundFeature.description || '';
    }
}

// TABLETOP MODE: Submit Manage PC edit (always update_manual endpoint)
function submitManagePcEdit() {
    const form = document.getElementById('manage-pc-form');
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    
    // Always use update_manual endpoint for Manage PC modal
    fetch('/api/party/update_manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            // Close modal and refresh stats
            closeManagePcModal();
            
            // Refresh character stats to show updates
            if (typeof loadCharacterStats === 'function') {
                loadCharacterStats();
            }
        } else {
            if (result.missing_paths && result.missing_paths.length > 0) {
                alert('Error: ' + result.error + '\nMissing or invalid: ' + result.missing_paths.join(', '));
            } else {
                alert('Error: ' + result.error);
            }
        }
    })
    .catch(error => {
        console.error('Error in Manage PC edit:', error);
    });
}

function switchManageTab(tabId) {
    const tabButtons = document.querySelectorAll('#manage-party-modal .tab-button');
    const tabContents = document.querySelectorAll('.manage-tab-content');
    
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.style.display = 'none');
    
    document.querySelector(`#manage-party-modal .tab-button[onclick="switchManageTab('${tabId}')"]`).classList.add('active');
    document.getElementById(`tab-${tabId}`).style.display = 'block';
    
    // Reset quick-create state when switching away from quick-create tab
    if (tabId !== 'quick-create') {
        resetQuickCreateState();
    }
}

function loadExistingCharacters() {
    const listContainer = document.getElementById('existing-character-list');
    const sourceSelect = document.getElementById('add-existing-source');
    const sourceMode = sourceSelect ? sourceSelect.value : 'players';
    listContainer.innerHTML = '<div class="loading">Loading candidates...</div>';

    fetch(`/api/party/characters?source=${encodeURIComponent(sourceMode)}`)
    .then(response => response.json())
    .then(data => {
        if (data.characters && data.characters.length > 0) {
            let html = '';
            data.characters.forEach(char => {
                const candidateName = escapeHtml(char.name || 'Unknown');
                const roleBadge = char.action === 'promote'
                    ? '<span class="save-mode-badge" style="background: #6a4f1f;">NPC -> PC</span>'
                    : '<span class="save-mode-badge essential">Player</span>';
                const primaryAction = char.action === 'promote' ? 'Promote' : 'Add';
                html += `
                    <div class="save-item" style="cursor: default;">
                        <div class="save-item-header">
                            ${candidateName}
                            <span class="save-mode-badge essential">Lvl ${char.level || 1} ${escapeHtml(char.class || 'Unknown')}</span>
                            ${roleBadge}
                        </div>
                        <div style="margin-top: 8px; display: flex; justify-content: flex-end; gap: 8px;">
                            <button class="dialog-button primary" onclick='handleExistingCharacterAction(${JSON.stringify(char.name)}, ${JSON.stringify(char.action)})'>${primaryAction}</button>
                        </div>
                    </div>
                `;
            });
            listContainer.innerHTML = html;
        } else {
            listContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">No unused characters found.</div>';
        }
    })
    .catch(error => {
        console.error('Error loading characters:', error);
        listContainer.innerHTML = '<div class="error">Failed to load characters.</div>';
    });
}

function escapeHtml(value) {
    const text = String(value == null ? '' : value);
    return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function handleExistingCharacterAction(characterName, action) {
    if (action === 'promote') {
        previewPromotion(characterName);
        return;
    }
    addCharacterToParty(characterName);
}

function previewPromotion(characterName) {
    fetch('/api/party/promotion/preview', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ character: characterName }),
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('Error: ' + (data.error || 'Failed to preview promotion.'));
            return;
        }

        const character = data.character || {};
        const warnings = Array.isArray(data.warnings) && data.warnings.length > 0
            ? `\n\nWarnings:\n- ${data.warnings.join('\n- ')}`
            : '';
        const confirmText =
            `Promote ${character.name || characterName}?\n\n` +
            `Role: ${character.before_role || 'npc'} -> ${character.after_role || 'player'}\n` +
            `This keeps the same character file and does not switch active character.${warnings}`;

        if (!confirm(confirmText)) {
            return;
        }

        applyPromotion(characterName);
    })
    .catch(error => {
        console.error('Error previewing promotion:', error);
        alert('Failed to preview promotion.');
    });
}

function applyPromotion(characterName) {
    fetch('/api/party/promotion/apply', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ character: characterName, confirm: true }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (Array.isArray(data.warnings) && data.warnings.length > 0) {
                alert('Promotion completed with warnings:\n- ' + data.warnings.join('\n- '));
            }
            window.location.reload();
        } else {
            alert('Error: ' + (data.error || 'Promotion failed.'));
        }
    })
    .catch(error => {
        console.error('Error applying promotion:', error);
        alert('Failed to apply promotion.');
    });
}

// TABLETOP MODE: Quick Create form mode state ('create' or 'edit')
let quickCreateMode = 'create';
let quickCreateEditTarget = null;

// TABLETOP MODE: Open character edit from character sheet
// Opens dedicated Manage PC modal (separate from Manage Party)
window.openCharacterEdit = function(characterName) {
    // Open the dedicated Manage PC modal for editing
    openManagePcModal(characterName);
};

// TABLETOP MODE: Prefill Roll Your Own form with existing character data (for Manage Party create flow)
function _prefillQuickCreateForm(characterName) {
    // Get character data from global lastCharacterStats or fetch fresh
    const charData = window.lastCharacterStats || {};
    
    // If no data in cache, fetch it
    if (!charData.name || charData.name.toLowerCase().replace(/\s+/g, '_') !== characterName) {
        // Need to fetch - use existing character data from window if available
        fetch(`/api/party/characters?source=players`)
            .then(r => r.json())
            .then(data => {
                const characters = data.characters || [];
                const found = characters.find(c => 
                    c.name.toLowerCase().replace(/\s+/g, '_') === characterName
                );
                if (found) {
                    _fillQuickCreateForm(found);
                }
            })
            .catch(err => console.error('Error loading character for edit:', err));
        return;
    }
    
    _fillQuickCreateForm(charData);
}

// TABLETOP MODE: Fill form fields with character data (for Manage Party create flow)
function _fillQuickCreateForm(data) {
    const form = document.getElementById('quick-create-form');
    if (!form) return;
    
    // Identity
    form.querySelector('[name="name"]').value = data.name || '';
    if (quickCreateMode === 'edit') {
        // Make name read-only in edit mode
        form.querySelector('[name="name"]').setAttribute('readonly', 'readonly');
        form.querySelector('[name="name"]').style.background = '#333';
    }
    form.querySelector('[name="race"]').value = data.race || '';
    form.querySelector('[name="class"]').value = data.class || '';
    form.querySelector('[name="level"]').value = data.level || '1';
    form.querySelector('[name="alignment"]').value = data.alignment || '';
    form.querySelector('[name="background"]').value = data.background || '';
    
    // Appearance
    form.querySelector('[name="age"]').value = data.age || '';
    form.querySelector('[name="height"]').value = data.height || '';
    form.querySelector('[name="weight"]').value = data.weight || '';
    form.querySelector('[name="eyes"]').value = data.eyes || '';
    form.querySelector('[name="skin"]').value = data.skin || '';
    form.querySelector('[name="hair"]').value = data.hair || '';
    
    // Abilities
    if (data.abilities) {
        form.querySelector('[name="str"]').value = data.abilities.strength || '10';
        form.querySelector('[name="dex"]').value = data.abilities.dexterity || '10';
        form.querySelector('[name="con"]').value = data.abilities.constitution || '10';
        form.querySelector('[name="int"]').value = data.abilities.intelligence || '10';
        form.querySelector('[name="wis"]').value = data.abilities.wisdom || '10';
        form.querySelector('[name="cha"]').value = data.abilities.charisma || '10';
    }
    
    // Combat
    form.querySelector('[name="ac"]').value = data.armorClass || '10';
    form.querySelector('[name="hp"]').value = data.hitPoints || '10';
    form.querySelector('[name="initiative"]').value = data.initiative || '0';
    form.querySelector('[name="speed"]').value = data.speed || '30';
    
    // Saves and Skills (convert arrays to comma-separated)
    if (data.savingThrows && Array.isArray(data.savingThrows)) {
        form.querySelector('[name="saving_throws"]').value = data.savingThrows.join(', ');
    }
    if (data.skills) {
        if (Array.isArray(data.skills)) {
            form.querySelector('[name="skills"]').value = data.skills.join(', ');
        }
    }
    
    // Proficiencies
    if (data.proficiencies) {
        if (data.proficiencies.languages) {
            form.querySelector('[name="languages"]').value = 
                Array.isArray(data.proficiencies.languages) ? data.proficiencies.languages.join(', ') : data.languages || 'Common';
        }
        if (data.proficiencies.armor) {
            form.querySelector('[name="prof_armor"]').value = 
                Array.isArray(data.proficiencies.armor) ? data.proficiencies.armor.join(', ') : '';
        }
        if (data.proficiencies.weapons) {
            form.querySelector('[name="prof_weapons"]').value = 
                Array.isArray(data.proficiencies.weapons) ? data.proficiencies.weapons.join(', ') : '';
        }
        if (data.proficiencies.tools) {
            form.querySelector('[name="prof_tools"]').value = 
                Array.isArray(data.proficiencies.tools) ? data.proficiencies.tools.join(', ') : '';
        }
    }
    
    // Equipment (convert equipment objects to comma-separated names)
    if (data.equipment && Array.isArray(data.equipment)) {
        const equipmentNames = data.equipment.map(item => item.item_name).filter(Boolean);
        form.querySelector('[name="equipment"]').value = equipmentNames.join(', ');
    }
    
    // Attacks (convert attacksAndSpellcasting objects to comma-separated names)
    if (data.attacksAndSpellcasting && Array.isArray(data.attacksAndSpellcasting)) {
        const attackNames = data.attacksAndSpellcasting.map(attack => attack.name).filter(Boolean);
        form.querySelector('[name="attacks"]').value = attackNames.join(', ');
    }
    
    // Spellcasting
    if (data.spellcasting) {
        form.querySelector('[name="spellcasting_ability"]').value = data.spellcasting.ability || 'none';
        form.querySelector('[name="spell_dc"]').value = data.spellcasting.spellSaveDC || '8';
        form.querySelector('[name="spell_attack_bonus"]').value = data.spellcasting.spellAttackBonus || '0';
        if (data.spellcasting.spells) {
            if (data.spellcasting.spells.cantrips) {
                form.querySelector('[name="cantrips"]').value = 
                    Array.isArray(data.spellcasting.spells.cantrips) ? data.spellcasting.spells.cantrips.join(', ') : '';
            }
            if (data.spellcasting.spells.level1) {
                form.querySelector('[name="level1_spells"]').value = 
                    Array.isArray(data.spellcasting.spells.level1) ? data.spellcasting.spells.level1.join(', ') : '';
            }
        }
    }
    
    // Personality
    form.querySelector('[name="personality_traits"]').value = data.personality_traits || '';
    form.querySelector('[name="ideals"]').value = data.ideals || '';
    form.querySelector('[name="bonds"]').value = data.bonds || '';
    form.querySelector('[name="flaws"]').value = data.flaws || '';
    form.querySelector('[name="backstory"]').value = data.backstory || '';
    
    // Background Feature
    if (data.backgroundFeature) {
        form.querySelector('[name="background_feature_name"]').value = data.backgroundFeature.name || '';
        form.querySelector('[name="background_feature_description"]').value = data.backgroundFeature.description || '';
    }
}

// TABLETOP MODE: Reset quick-create form state when switching tabs or closing modal
function resetQuickCreateState() {
    quickCreateMode = 'create';
    quickCreateEditTarget = null;
    
    const form = document.getElementById('quick-create-form');
    if (form) {
        form.reset();
        
        // Reset name field read-only state
        const nameField = form.querySelector('[name="name"]');
        if (nameField) {
            nameField.removeAttribute('readonly');
            nameField.style.background = '';
        }
    }
    
    // Reset submit button text
    const submitBtn = document.querySelector('#quick-create-form button[onclick="submitQuickCreate()"]');
    if (submitBtn) {
        submitBtn.textContent = 'Create & Add to Party';
    }
}

// TABLETOP MODE: Clear residual autofill values from Roll Your Own form fields
// Called on Manage Party open to prevent stale field carryover (e.g., equipment from prior characters)
function clearQuickCreateAutofillResidue() {
    const form = document.getElementById('quick-create-form');
    if (!form) return;
    
    // Fields likely to carry stale autofill/narrative values
    const fieldsToClear = [
        'equipment',
        'attacks',
        'personality_traits',
        'ideals',
        'bonds',
        'flaws',
        'backstory',
        'background_feature_name',
        'background_feature_description'
    ];
    
    fieldsToClear.forEach(fieldName => {
        const field = form.querySelector(`[name="${fieldName}"]`);
        if (field) {
            field.value = '';
        }
    });
}

// TABLETOP MODE: Quick Create form submit (Manage Party create flow only)
// NOTE: Edit flow now uses submitManagePcEdit() via dedicated Manage PC modal
function submitQuickCreate() {
    const form = document.getElementById('quick-create-form');
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => data[key] = value);
    
    // Always use create_manual endpoint for Manage Party create flow
    fetch('/api/party/create_manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            // Reset state after successful operation
            resetQuickCreateState();
            closeManagePartyModal();
            
            // Reload page for create flow
            window.location.reload();
        } else {
            if (result.missing_paths && result.missing_paths.length > 0) {
                alert('Error: ' + result.error + '\nMissing or invalid: ' + result.missing_paths.join(', '));
            } else {
                alert('Error: ' + result.error);
            }
        }
    })
    .catch(error => {
        console.error('Error in Roll Your Own create:', error);
    });
}

function submitDMInterviewCreate() {
    const nameInput = document.getElementById('interview-char-name');
    const name = nameInput.value.trim();
    
    if (!name) {
        alert('Please enter a character name.');
        return;
    }

    // Disable button to prevent double-submit
    const btn = document.querySelector('#dm-interview-form button');
    if (btn) btn.disabled = true;

    fetch('/api/party/create_player', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name })
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            // Close modal and reload to see the new tab and start the conversation
            closeManagePartyModal();
            window.location.reload();
        } else {
            alert('Error: ' + result.error);
            if (btn) btn.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error starting DM interview:', error);
        alert('Failed to connect to the server.');
        if (btn) btn.disabled = false;
    });
}

/**
 * Removes a character from the party (retirement).
 * @param {string} characterName
 */
function retireCharacter(characterName) {
    if (confirm(`Are you sure you want to retire ${characterName} from the party? They will remain in the /characters folder and can rejoin later.`)) {
        // TABLETOP MODE: Collect optional farewell text for retirement narration
        const farewellText = prompt(`Enter optional farewell message for ${characterName} (or leave blank):`) || '';
        const departureText = farewellText.trim();

        fetch('/api/party/remove_character', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            // TABLETOP MODE: Include departure_text in retirement payload
            body: JSON.stringify({ character: characterName, departure_text: departureText }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error retiring character:', error);
        });
    }
}

/**
 * Adds a character to the party.
 * @param {string} characterName 
 */
function addCharacterToParty(characterName) {
    fetch('/api/party/add_character', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ character: characterName }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload(); // Reload to refresh tabs and state
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error adding character:', error);
    });
}

/**
 * Update Sidebar stats with real-time data
 */
tabletopSocket.on('party_data_response', (response) => {
    syncCharacterTabsFromPartyResponse(response);

    if (response && response.members) {
        response.members.forEach(member => {
            // Escape names for ID usage if they contain spaces
            const safeName = member.name;
            const hpElement = document.getElementById(`sidebar-hp-${safeName}`);
            const acElement = document.getElementById(`sidebar-ac-${safeName}`);
            
            if (hpElement) {
                hpElement.textContent = `${member.currentHp || 0}/${member.maxHp || 0} HP`;
            }
            if (acElement) {
                acElement.textContent = `AC ${member.ac || '--'}`;
            }
        });
    }
});

/**
 * Listen for active character updates from the backend (e.g. auto-advance combat turn)
 */
tabletopSocket.on('active_character_update', (data) => {
    if (data && data.character) {
        console.log(`[Socket] Active character updated to: ${data.character}`);
        
        // CRITICAL: Update global state so chat messages are attributed correctly
        window.active_character = data.character;
        
        updateTabUI(data.character);
        
        // Also refresh the stats for the new character to ensure data is current
        if (typeof loadCharacterStats === 'function') loadCharacterStats();
        if (typeof loadInventory === 'function') loadInventory();
    }
});

// Initialize UI on load
document.addEventListener('DOMContentLoaded', () => {
    // TABLETOP MODE: Delegate character-tab click handlers to avoid inline JS in templates
    const characterTabsList = document.getElementById('character-tabs-list');
    if (characterTabsList) {
        characterTabsList.addEventListener('click', (event) => {
            const retireButton = event.target.closest('.retire-character-btn[data-character]');
            if (retireButton) {
                event.preventDefault();
                event.stopPropagation();
                const characterName = retireButton.getAttribute('data-character');
                if (characterName) {
                    retireCharacter(characterName);
                }
                return;
            }

            const characterTab = event.target.closest('.character-tab[data-character]');
            if (characterTab) {
                event.preventDefault();
                const characterName = characterTab.getAttribute('data-character');
                if (characterName) {
                    setActiveCharacter(characterName);
                }
            }
        });
    }

    // Request initial data
    if (typeof requestPartyData === 'function') requestPartyData();
});
