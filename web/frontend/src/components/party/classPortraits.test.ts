import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { npcClassFallbackPortrait } from './media'

// web/static/media/class_portraits, served at /static/media/class_portraits.
const STATIC_ROOT = fileURLToPath(new URL('../../../../static/', import.meta.url))

const CLASSES = [
  'Barbarian', 'Bard', 'Cleric', 'Druid', 'Fighter', 'Monk', 'Paladin',
  'Ranger', 'Rogue', 'Sorcerer', 'Warlock', 'Wizard', 'Scout Kira', 'Innkeeper Bram',
]

describe('class portrait fallback (#278)', () => {
  it.each(CLASSES)('%s points at a portrait that ships', (name) => {
    const url = npcClassFallbackPortrait(name)
    expect(url.startsWith('/static/')).toBe(true)
    expect(existsSync(STATIC_ROOT + url.slice('/static/'.length))).toBe(true)
  })
})
