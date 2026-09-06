// Synthetic sample state for the approved visual reference, never live saves.
export const emberNarration = 'Welcome back, traveler. As you return to the dim, mist-shrouded Command Post, the scent of woodsmoke and old parchment greets you once more. Ranger Marcus looks up from his patrol map, a small smile briefly breaking his gruff features.\n\nCommander Elen remains at the central table, her expression a mix of professional resolve and cautious hope. “You are here, that is good. We still need to break this prisoner, Jack. The safety of the outposts depends on what he knows of the sorcerer in the woods. How would you like to proceed?”'

export function applyEmberFixture({ location, stats, party, locationNpcs, initialMessages }) {
  Object.assign(location, { currentLocation: 'Rangers’ Command Post', currentArea: 'Rangers’ Outpost', currentLocationId: 'R001', currentAreaId: 'RO01', time: '09:00', day: 1, month: 'Springmonth', year: 1492 })
  Object.assign(stats, {
    name: 'Smashing Jack', race: 'Half-Orc', class: 'Barbarian', level: 1,
    background: 'Folk Hero', alignment: 'chaotic good', hitPoints: 14, maxHitPoints: 14, armorClass: 13, initiative: 1,
    abilities: { strength: 17, dexterity: 13, constitution: 15, intelligence: 8, wisdom: 12, charisma: 10 },
    strength: 17, dexterity: 13, constitution: 15, intelligence: 8, wisdom: 12, charisma: 10,
    currency: { gold: 10, silver: 0, copper: 0 },
    savingThrows: ['Strength', 'Constitution'],
    attacksAndSpellcasting: [{ name: 'Maul', damage: '2d6+3' }, { name: 'Javelin', damage: '1d6+3' }],
    classFeatures: [{ name: 'Rage', usage: { current: 2, max: 2 } }, { name: 'Unarmored Defense', description: 'Your defense while not wearing armor.' }],
    racialTraits: [{ name: 'Relentless Endurance' }, { name: 'Savage Attacks' }],
    backgroundFeature: { name: 'Rustic Hospitality' },
  })
  party.splice(0, party.length, ...['Smashing Jack', 'Ranger Elen', 'Ranger Marcus', 'Scout Kira', 'Messenger Tom'].map((name, index) => ({ name, type: index === 0 ? 'player' : 'npc', currentHp: 14, maxHp: 14, ac: 13 })))
  locationNpcs.splice(0, locationNpcs.length, { name: 'Rusk', type: 'location_npc' })
  initialMessages.splice(0, initialMessages.length, { message_id: 'ember-you', type: 'user-input', content: 'hi!' }, { message_id: 'ember-dm', type: 'narration', content: emberNarration })
}

// Explicit test-only aliases to assets already present in the PUBLIC repository.
// These sample identities are not production portrait assignments.
export const emberMediaFiles = {
  '/static/dm_logo.png': 'dm_logo.png',
  '/static/portraits/smashing_jack.png': 'web/static/media/class_portraits/ranger.png',
  '/static/media/environment/midday.jpg': 'web/static/media/environment/midday.jpg',
  '/__e2e__/scene.jpg': 'web/static/media/environment/nightfall.jpg',
  ...Object.fromEntries(['ranger_elen', 'ranger_marcus', 'scout_kira', 'messenger_tom', 'rusk'].map(name => [
    `/media/npcs/${name}_thumb.jpg`, `graphic_packs/photorealistic/npcs/${name}.jpg`,
  ])),
  ...Object.fromEntries(['ranger_elen', 'ranger_marcus', 'scout_kira', 'messenger_tom', 'rusk'].map(name => [
    `/media/npcs/${name}.jpg`, `graphic_packs/photorealistic/npcs/${name}.jpg`,
  ])),
}

// Broader inspection data belongs only to this explicitly synthetic preview.
export const emberEquipment = [
  { item_name: 'Maul', item_type: 'Weapon', quantity: 1, equipped: true, description: 'A sturdy two-handed maul. Sample inventory, not a live save.' },
  { item_name: 'Potion of Healing', item_type: 'Potion', item_subtype: 'potion', quantity: 2, consumable: true, magical: true, description: 'A stoppered vial of healing potion.' },
  { item_name: 'Scroll of Goodberry', item_type: 'Scroll', item_subtype: 'scroll', quantity: 1, consumable: true, magical: true, spellLevel: 1 },
  { item_name: 'Scroll of Melf’s Acid Arrow', item_type: 'Scroll', item_subtype: 'scroll', quantity: 1, consumable: true, magical: true, spellLevel: 2 },
  { item_name: 'Moonlit Compass', item_type: 'Wondrous Item', quantity: 1, magical: true, charges: { current: 2, max: 3 }, description: 'A sample charged item for inspecting the interface.' },
]
export function emberNpcs(stats) {
  return ['Ranger Elen', 'Ranger Marcus', 'Scout Kira', 'Messenger Tom', 'Rusk'].map(name => ({
    ...stats, name, class: 'Ranger', race: 'Human', level: 3, status: 'alive', conditions: [],
    skills: { Nature: 4, Perception: 5, Survival: 5 }, savingThrows: ['Strength', 'Dexterity'],
    equipment: emberEquipment, personality_traits: 'Careful and observant. Synthetic preview biography.',
    ideals: 'Keep the roads safe.', bonds: 'The people of the outpost.', flaws: 'Slow to trust strangers.',
    classFeatures: [{ name: 'Favored Foe', description: 'Mark a foe. Sample supplied feature description.', usage: { current: 2, max: 3, refreshOn: 'long rest' } }],
    racialTraits: [{ name: 'Versatile', description: 'Adaptable training.' }],
    backgroundFeature: { name: 'Wanderer', description: 'Excellent memory for maps.' },
    spellcasting: { ability: 'wisdom', spellSaveDC: 13, spellAttackBonus: 5, spellSlots: { level1: { current: 2, max: 3 } }, spells: { level1: ['Goodberry'], level2: ['Melf’s Acid Arrow'] }, preparedSpells: ['Goodberry'] },
  }))
}
export const emberPlot = { plotPoints: [
  { id: 'preview-road', title: 'The Thornwood Road', description: 'Investigate the reports at the command post. Synthetic preview journal entry.', status: 'in progress' },
  { id: 'preview-arrival', title: 'Arrival at the Outpost', description: 'You reached the rangers’ command post.', status: 'completed' },
] }
export const emberStorage = { success: true, storage: [
  { name: 'Outpost Locker', location: 'Rangers’ Command Post', contents: [{ item_name: 'Rations', quantity: 6 }, { item_name: 'Traveler’s cloak', quantity: 1 }] },
] }
