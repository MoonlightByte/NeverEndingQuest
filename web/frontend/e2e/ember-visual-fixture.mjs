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
}
