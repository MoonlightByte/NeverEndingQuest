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
    const tabs = document.querySelectorAll('.character-tab');
    tabs.forEach(tab => {
        if (tab.getAttribute('data-character') === activeName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Also update sidebar if present
    const cards = document.querySelectorAll('.party-member-card');
    cards.forEach(card => {
        if (card.getAttribute('data-character') === activeName) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
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

    modal.style.display = 'block';
    loadExistingCharacters();
}

function closeManagePartyModal() {
    const modal = document.getElementById('manage-party-modal');
    if (!modal) {
        return;
    }

    modal.style.display = 'none';
}

function switchManageTab(tabId) {
    const tabButtons = document.querySelectorAll('#manage-party-modal .tab-button');
    const tabContents = document.querySelectorAll('.manage-tab-content');
    
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.style.display = 'none');
    
    document.querySelector(`#manage-party-modal .tab-button[onclick="switchManageTab('${tabId}')"]`).classList.add('active');
    document.getElementById(`tab-${tabId}`).style.display = 'block';
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

function submitQuickCreate() {
    const form = document.getElementById('quick-create-form');
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => data[key] = value);

    fetch('/api/party/create_manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
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
    // Request initial data
    if (typeof requestPartyData === 'function') requestPartyData();
});
