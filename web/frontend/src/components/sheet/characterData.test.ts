/**
 * Logic tests for the sheet view-model helpers (plan Task 4.4d).
 * Pure functions only -- no DOM, no socket, no stores.
 */
import { describe, expect, it } from 'vitest'
import {
  abilityModifier,
  abilityScores,
  capitalizeWords,
  currencyOf,
  equipmentFromArray,
  equipmentList,
  filterEquipment,
  formatModifier,
  hpPercent,
  hpTone,
  portraitSlug,
  proficientSkills,
  saveRows,
  skillBonus,
  skillRows,
  slotTone,
  sortEquipment,
  spellcastingView,
} from './characterData'

const CHARACTER: Record<string, unknown> = {
  name: 'Elen Brightwood',
  abilities: {
    strength: 10,
    dexterity: 16,
    constitution: 14,
    intelligence: 12,
    wisdom: 13,
    charisma: 8,
  },
  proficiencyBonus: 2,
  savingThrows: ['Dexterity', 'Intelligence'],
  skills: ['Stealth', 'Arcana'],
  hitPoints: 7,
  maxHitPoints: 21,
  currency: { gold: 12, silver: 3, copper: 40 },
  equipment: [
    { item_name: 'Longbow', item_type: 'weapon', quantity: 1, description: 'A bow.' },
    { item_name: 'Arrow', item_type: 'ammunition', quantity: 20 },
    { item_name: 'Cloak', item_type: 'armor', quantity: 1, equipped: true, magical: true },
  ],
  spellcasting: {
    ability: 'intelligence',
    spellSaveDC: 13,
    spellAttackBonus: 5,
    preparedSpells: ['Magic Missile'],
    spells: {
      cantrips: ['Prestidigitation'],
      level1: ['Magic Missile', 'Shield'],
      level2: [],
    },
    spellSlots: {
      level1: { current: 1, max: 3 },
    },
  },
}

describe('ability helpers', () => {
  it('computes modifiers and formatting', () => {
    expect(abilityModifier(16)).toBe(3)
    expect(abilityModifier(8)).toBe(-1)
    expect(formatModifier(3)).toBe('+3')
    expect(formatModifier(-1)).toBe('-1')
  })

  it('defaults missing ability scores to 10', () => {
    expect(abilityScores({}).strength).toBe(10)
    expect(abilityScores(CHARACTER).dexterity).toBe(16)
  })
})

describe('skills', () => {
  it('passes through the new array format', () => {
    expect(proficientSkills(CHARACTER)).toEqual(['Stealth', 'Arcana'])
  })

  it('infers proficiency from the old object format (bonus > ability mod)', () => {
    const oldFormat = {
      abilities: { dexterity: 16, intelligence: 12 },
      skills: { stealth: 5, arcana: 1 },
    }
    // stealth 5 > dex mod 3 -> proficient; arcana 1 = int mod 1 -> not
    expect(proficientSkills(oldFormat)).toEqual(['Stealth'])
  })

  it('computes skill bonuses from mod + proficiency for array format', () => {
    expect(skillBonus('Stealth', 'dexterity', CHARACTER)).toBe(5) // 3 + 2
    expect(skillBonus('Acrobatics', 'dexterity', CHARACTER)).toBe(3)
  })

  it('prefers stored bonuses from the object format', () => {
    const oldFormat = { abilities: { dexterity: 16 }, skills: { stealth: 7 } }
    expect(skillBonus('Stealth', 'dexterity', oldFormat)).toBe(7)
  })

  it('builds NPC skill rows from the object format', () => {
    const rows = skillRows({ skills: { Perception: 4, Insight: -1 } })
    expect(rows).toEqual([
      { name: 'Perception', bonus: 4 },
      { name: 'Insight', bonus: -1 },
    ])
  })

  it('builds NPC skill rows from the array format', () => {
    const rows = skillRows(CHARACTER)
    expect(rows).toContainEqual({ name: 'Stealth', bonus: 5 })
    expect(rows).toContainEqual({ name: 'Arcana', bonus: 3 }) // int 1 + prof 2
  })
})

describe('saving throws', () => {
  it('marks proficient saves and adds the proficiency bonus', () => {
    const rows = saveRows(CHARACTER)
    expect(rows).toHaveLength(6)
    const dex = rows.find((r) => r.name === 'Dexterity')
    const str = rows.find((r) => r.name === 'Strength')
    expect(dex).toEqual({ name: 'Dexterity', proficient: true, bonus: 5 })
    expect(str).toEqual({ name: 'Strength', proficient: false, bonus: 0 })
  })
})

describe('hit points', () => {
  it('grades HP tone at the legacy thresholds', () => {
    expect(hpTone(21, 21)).toBe('healthy')
    expect(hpTone(10, 21)).toBe('medium') // 47%
    expect(hpTone(5, 21)).toBe('low') // 23%
    expect(hpTone(0, 0)).toBe('low')
  })

  it('clamps the bar percentage', () => {
    expect(hpPercent(30, 21)).toBe(100)
    expect(hpPercent(-2, 21)).toBe(0)
    expect(hpPercent(7, 0)).toBe(0)
  })
})

describe('inventory', () => {
  it('extracts currency with zero defaults', () => {
    expect(currencyOf(CHARACTER)).toEqual({ gold: 12, silver: 3, copper: 40 })
    expect(currencyOf({})).toEqual({ gold: 0, silver: 0, copper: 0 })
  })

  it('parses equipment and skips malformed entries', () => {
    const items = equipmentList(CHARACTER)
    expect(items).toHaveLength(3)
    expect(items[0]).toMatchObject({ name: 'Longbow', type: 'weapon', quantity: 1 })
    expect(equipmentFromArray([null, 'junk', { item_name: 'Rope' }])).toHaveLength(1)
  })

  it('sorts by each mode', () => {
    const items = equipmentList(CHARACTER)
    expect(sortEquipment(items, 'name-asc').map((i) => i.name)).toEqual([
      'Arrow',
      'Cloak',
      'Longbow',
    ])
    expect(sortEquipment(items, 'name-desc')[0]!.name).toBe('Longbow')
    expect(sortEquipment(items, 'quantity')[0]!.name).toBe('Arrow')
    expect(sortEquipment(items, 'type')[0]!.type).toBe('ammunition')
  })

  it('filters by name or type text', () => {
    const items = equipmentList(CHARACTER)
    expect(filterEquipment(items, 'bow').map((i) => i.name)).toEqual(['Longbow'])
    expect(filterEquipment(items, 'ARMOR')).toHaveLength(1)
    expect(filterEquipment(items, '  ')).toHaveLength(3)
    expect(filterEquipment(items, 'zzz')).toHaveLength(0)
  })
})

describe('spellcasting', () => {
  it('builds the view with slots and skips empty levels', () => {
    const view = spellcastingView(CHARACTER)
    expect(view).not.toBeNull()
    expect(view!.saveDC).toBe(13)
    expect(view!.attackBonus).toBe(5)
    expect(view!.levels.map((l) => l.levelName)).toEqual(['Cantrips', '1st Level'])
    expect(view!.levels[1]!.slots).toEqual({ current: 1, max: 3 })
    expect(view!.levels[0]!.slots).toBeNull()
    expect(view!.prepared).toEqual(['Magic Missile'])
  })

  it('returns null for non-casters', () => {
    expect(spellcastingView({})).toBeNull()
    expect(spellcastingView({ spellcasting: { spells: { level1: [] } } })).toBeNull()
  })

  it('grades slot tone at the legacy thresholds', () => {
    expect(slotTone({ current: 0, max: 3 })).toBe('exhausted')
    expect(slotTone({ current: 1, max: 3 })).toBe('low')
    expect(slotTone({ current: 3, max: 3 })).toBe('available')
  })
})

describe('text helpers', () => {
  it('capitalizes words and slugs portrait names', () => {
    expect(capitalizeWords('chaotic good')).toBe('Chaotic Good')
    expect(portraitSlug('Elen Brightwood')).toBe('elen_brightwood')
  })
})
