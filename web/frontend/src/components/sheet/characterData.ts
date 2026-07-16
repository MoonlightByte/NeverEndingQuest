/**
 * Pure data helpers for the right-panel sheet components (plan Task 4.4d).
 * player_data_response / npc_details_response payloads carry raw character
 * JSON files (Record<string, unknown> in the frozen contract), so every view
 * model here narrows at runtime. No socket or store access -- pure functions
 * only, so they are unit-testable without a DOM.
 *
 * Field names and derivations are ported 1:1 from the legacy
 * game_interface.html renderers (displayCharacterStats, displayInventory,
 * displaySpellsAndMagic, displayNPCs, showNPC*).
 */

// ---------- unknown-narrowing primitives ----------

export function rec(v: unknown): Record<string, unknown> | null {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null
}

export function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : []
}

export function num(v: unknown, fallback = 0): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback
}

export function str(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : fallback
}

function strings(v: unknown): string[] {
  return arr(v).filter((s): s is string => typeof s === 'string')
}

// ---------- text helpers ----------

export function capitalize(word: string): string {
  return word.length === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1)
}

export function capitalizeWords(text: string): string {
  return text.replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Portrait filename slug used by /static/portraits/<slug>.png. */
export function portraitSlug(name: string): string {
  return name.toLowerCase().replace(/\s+/g, '_')
}

// ---------- abilities / modifiers ----------

export const ABILITIES = [
  'strength',
  'dexterity',
  'constitution',
  'intelligence',
  'wisdom',
  'charisma',
] as const
export type AbilityName = (typeof ABILITIES)[number]

export function abilityModifier(score: number): number {
  return Math.floor((score - 10) / 2)
}

export function formatModifier(mod: number): string {
  return mod >= 0 ? `+${mod}` : `${mod}`
}

export function abilityScores(data: Record<string, unknown>): Record<AbilityName, number> {
  const abilities = rec(data['abilities']) ?? {}
  const out = {} as Record<AbilityName, number>
  for (const name of ABILITIES) out[name] = num(abilities[name], 10)
  return out
}

// Legacy SKILL_MAP (game_interface.html) -- Constitution has no skills.
export const SKILL_MAP: Record<string, string[]> = {
  Strength: ['Athletics'],
  Dexterity: ['Acrobatics', 'Sleight of Hand', 'Stealth'],
  Intelligence: ['Arcana', 'History', 'Investigation', 'Nature', 'Religion'],
  Wisdom: ['Animal Handling', 'Insight', 'Medicine', 'Perception', 'Survival'],
  Charisma: ['Deception', 'Intimidation', 'Performance', 'Persuasion'],
}

/** Look a skill up in the old object-format skills map, tolerating key styles. */
function skillMapValue(skills: Record<string, unknown>, skill: string): number | null {
  const candidates = [skill.toLowerCase().replace(/\s+/g, ''), skill.toLowerCase(), skill]
  for (const key of candidates) {
    const value = skills[key]
    if (typeof value === 'number') return value
  }
  return null
}

/**
 * Normalize skill proficiencies (legacy displayCharacterStats logic):
 * - NEW format: data.skills is already an array of proficient skill names.
 * - OLD format: data.skills maps skill -> bonus; proficiency is inferred
 *   when the stored bonus exceeds the raw ability modifier.
 */
export function proficientSkills(data: Record<string, unknown>): string[] {
  const skills = data['skills']
  if (Array.isArray(skills)) return strings(skills)
  const skillsObj = rec(skills)
  if (!skillsObj) return []
  const scores = abilityScores(data)
  const out: string[] = []
  for (const [abilityLabel, skillNames] of Object.entries(SKILL_MAP)) {
    const ability = abilityLabel.toLowerCase() as AbilityName
    for (const skill of skillNames) {
      const value = skillMapValue(skillsObj, skill)
      if (value !== null && value > abilityModifier(scores[ability])) out.push(skill)
    }
  }
  return out
}

/**
 * Skill bonus: prefer the stored bonus (old object format); otherwise
 * ability modifier plus proficiency bonus when proficient.
 */
export function skillBonus(
  skill: string,
  ability: AbilityName,
  data: Record<string, unknown>,
): number {
  const skillsObj = rec(data['skills'])
  if (skillsObj) {
    const direct = skillMapValue(skillsObj, skill)
    if (direct !== null) return direct
  }
  const mod = abilityModifier(abilityScores(data)[ability])
  return proficientSkills(data).includes(skill)
    ? mod + num(data['proficiencyBonus'], 2)
    : mod
}

// ---------- saving throws ----------

export interface SaveRow {
  name: string
  proficient: boolean
  bonus: number
}

/** Six saving-throw rows (legacy: savingThrows lists proficient save names). */
export function saveRows(data: Record<string, unknown>): SaveRow[] {
  const proficiencies = strings(data['savingThrows'])
  const scores = abilityScores(data)
  return ABILITIES.map((ability) => {
    const name = capitalize(ability)
    const proficient = proficiencies.includes(name)
    const mod = abilityModifier(scores[ability])
    return {
      name,
      proficient,
      bonus: proficient ? mod + num(data['proficiencyBonus'], 2) : mod,
    }
  })
}

// ---------- skills list (NPC detail modal) ----------

export interface SkillRow {
  name: string
  bonus: number
}

/**
 * Full skill list rows. Object format maps names to bonuses directly
 * (legacy displayNPCs); array format lists proficient skills, for which
 * bonuses are derived from ability modifier plus proficiency bonus.
 */
export function skillRows(data: Record<string, unknown>): SkillRow[] {
  const skills = data['skills']
  const skillsObj = rec(skills)
  if (skillsObj) {
    return Object.entries(skillsObj)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number')
      .map(([name, bonus]) => ({ name, bonus }))
  }
  if (Array.isArray(skills)) {
    const rows: SkillRow[] = []
    for (const [abilityLabel, skillNames] of Object.entries(SKILL_MAP)) {
      const ability = abilityLabel.toLowerCase() as AbilityName
      for (const skill of skillNames) {
        if (skills.includes(skill)) {
          rows.push({ name: skill, bonus: skillBonus(skill, ability, data) })
        }
      }
    }
    return rows
  }
  return []
}

// ---------- hit points ----------

export type HpTone = 'healthy' | 'medium' | 'low'

export function hpTone(current: number, max: number): HpTone {
  const pct = max > 0 ? (current / max) * 100 : 0
  if (pct <= 25) return 'low'
  if (pct <= 50) return 'medium'
  return 'healthy'
}

export function hpPercent(current: number, max: number): number {
  if (max <= 0) return 0
  return Math.max(0, Math.min(100, (current / max) * 100))
}

// ---------- currency ----------

export interface Currency {
  gold: number
  silver: number
  copper: number
}

export function currencyOf(data: Record<string, unknown>): Currency {
  const c = rec(data['currency']) ?? {}
  return { gold: num(c['gold']), silver: num(c['silver']), copper: num(c['copper']) }
}

// ---------- equipment ----------

export interface EquipmentItem {
  name: string
  type: string
  subtype: string
  description: string
  quantity: number
  equipped: boolean
  magical: boolean
  charges: { current: number; max: number } | null
}

function toEquipmentItem(raw: unknown): EquipmentItem | null {
  const item = rec(raw)
  if (!item) return null
  const charges = rec(item['charges'])
  return {
    name: str(item['item_name'], 'Unknown item'),
    type: str(item['item_type'], 'misc'),
    subtype: str(item['item_subtype']),
    description: str(item['description']),
    quantity: num(item['quantity'], 1),
    equipped: item['equipped'] === true,
    magical: item['magical'] === true,
    charges: charges ? { current: num(charges['current']), max: num(charges['max']) } : null,
  }
}

/** Equipment list from a character file (data.equipment). */
export function equipmentList(data: Record<string, unknown>): EquipmentItem[] {
  return equipmentFromArray(data['equipment'])
}

/** Equipment list from a bare array (npc_inventory_response.data). */
export function equipmentFromArray(rawItems: unknown): EquipmentItem[] {
  const out: EquipmentItem[] = []
  for (const raw of arr(rawItems)) {
    const item = toEquipmentItem(raw)
    if (item) out.push(item)
  }
  return out
}

export type InventorySort = 'name-asc' | 'name-desc' | 'type' | 'quantity'

export function sortEquipment(items: EquipmentItem[], sort: InventorySort): EquipmentItem[] {
  const sorted = [...items]
  if (sort === 'name-asc') {
    sorted.sort((a, b) => a.name.localeCompare(b.name))
  } else if (sort === 'name-desc') {
    sorted.sort((a, b) => b.name.localeCompare(a.name))
  } else if (sort === 'type') {
    sorted.sort((a, b) => a.type.localeCompare(b.type) || a.name.localeCompare(b.name))
  } else {
    sorted.sort((a, b) => b.quantity - a.quantity || a.name.localeCompare(b.name))
  }
  return sorted
}

export function filterEquipment(items: EquipmentItem[], query: string): EquipmentItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return items
  return items.filter(
    (i) =>
      i.name.toLowerCase().includes(q) ||
      i.type.toLowerCase().includes(q) ||
      i.subtype.toLowerCase().includes(q),
  )
}

// ---------- spellcasting ----------

export interface SpellLevelGroup {
  /** 0 = cantrips, 1-9 = spell levels. */
  levelIndex: number
  levelName: string
  spells: string[]
  slots: { current: number; max: number } | null
}

export interface SpellcastingView {
  ability: string
  saveDC: number | null
  attackBonus: number | null
  prepared: string[]
  levels: SpellLevelGroup[]
}

const SPELL_LEVEL_KEYS = [
  'cantrips',
  'level1',
  'level2',
  'level3',
  'level4',
  'level5',
  'level6',
  'level7',
  'level8',
  'level9',
] as const

const SPELL_LEVEL_NAMES = [
  'Cantrips',
  '1st Level',
  '2nd Level',
  '3rd Level',
  '4th Level',
  '5th Level',
  '6th Level',
  '7th Level',
  '8th Level',
  '9th Level',
] as const

/**
 * Spellcasting view from a character file. Returns null when the character
 * has no spells at any level (legacy hasSpellcasting check).
 */
export function spellcastingView(data: Record<string, unknown>): SpellcastingView | null {
  const casting = rec(data['spellcasting'])
  if (!casting) return null
  const spellsObj = rec(casting['spells']) ?? {}
  const slotsObj = rec(casting['spellSlots']) ?? {}
  const levels: SpellLevelGroup[] = []
  SPELL_LEVEL_KEYS.forEach((key, index) => {
    const spells = strings(spellsObj[key])
    if (spells.length === 0) return
    const slotRec = index > 0 ? rec(slotsObj[`level${index}`]) : null
    levels.push({
      levelIndex: index,
      levelName: SPELL_LEVEL_NAMES[index] ?? `Level ${index}`,
      spells,
      slots: slotRec ? { current: num(slotRec['current']), max: num(slotRec['max']) } : null,
    })
  })
  if (levels.length === 0) return null
  return {
    ability: str(casting['ability']),
    saveDC: typeof casting['spellSaveDC'] === 'number' ? casting['spellSaveDC'] : null,
    attackBonus:
      typeof casting['spellAttackBonus'] === 'number' ? casting['spellAttackBonus'] : null,
    prepared: strings(casting['preparedSpells']),
    levels,
  }
}

export type SlotTone = 'available' | 'low' | 'exhausted'

/** Slot color tone (legacy slotClass logic). */
export function slotTone(slots: { current: number; max: number }): SlotTone {
  if (slots.current === 0) return 'exhausted'
  if (slots.current <= slots.max * 0.5) return 'low'
  return 'available'
}
