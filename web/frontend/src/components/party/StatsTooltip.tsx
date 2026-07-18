/**
 * StatsTooltip (plan Task 4.4c) -- hover tooltip for party / initiative chips.
 * Shows level + class header, HP / AC / speed, primary attack + initiative,
 * ammunition, spell slots, spells known, class features, and conditions --
 * a straight port of the legacy createStatsTooltip() sections. Rendered in a
 * body portal (chips scale on hover; a transformed ancestor would break
 * position:fixed) and positioned above the anchor, flipping below when
 * clipped, clamped to the viewport -- same math as legacy positionTooltip().
 */
import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { asArray, asNumber, asRecord, asString } from './media'
import './party-parity.css'

export interface StatsTooltipProps {
  stats: Record<string, unknown>
  anchor: HTMLElement | null
}

function formatSigned(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`
}

function spellLevelName(level: string): string {
  if (level === '0') return 'Cantrips'
  if (level === '1') return '1st Level'
  if (level === '2') return '2nd Level'
  if (level === '3') return '3rd Level'
  return `${level}th Level`
}

function capitalize(value: string): string {
  return value.length > 0 ? value.charAt(0).toUpperCase() + value.slice(1) : value
}

interface SlotLine {
  label: string
  current: number
  max: number
}

function parseSpellSlots(stats: Record<string, unknown>): SlotLine[] {
  const slots = asRecord(stats['spellSlots'])
  if (!slots) return []
  const lines: SlotLine[] = []
  for (const [levelKey, raw] of Object.entries(slots)) {
    if (raw === null || raw === undefined) continue
    const slotRecord = asRecord(raw)
    const current = slotRecord ? asNumber(slotRecord['current']) ?? 0 : 0
    const max = slotRecord ? asNumber(slotRecord['max']) ?? 0 : asNumber(raw) ?? 0
    if (max > 0) {
      lines.push({ label: levelKey.replace('level', 'L'), current, max })
    }
  }
  return lines
}

interface SpellLine {
  levelName: string
  spells: string
}

function parseSpells(stats: Record<string, unknown>): SpellLine[] {
  const spells = asRecord(stats['spells'])
  if (!spells) return []
  const lines: SpellLine[] = []
  const sortedLevels = Object.keys(spells).sort(
    (a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10),
  )
  for (const level of sortedLevels) {
    const list = asArray(spells[level])
    if (!list || list.length === 0) continue
    const names = list.map((entry) => asString(entry)).filter((entry) => entry !== undefined)
    if (names.length > 0) {
      lines.push({ levelName: spellLevelName(level), spells: names.join(', ') })
    }
  }
  return lines
}

interface FeatureLine {
  name: string
  usage: string | undefined
}

function parseClassFeatures(stats: Record<string, unknown>): FeatureLine[] {
  const features = asArray(stats['classFeatures'])
  if (!features) return []
  const lines: FeatureLine[] = []
  for (const entry of features) {
    const record = asRecord(entry)
    const name = record ? asString(record['name']) : undefined
    if (name) lines.push({ name, usage: record ? asString(record['usage']) : undefined })
  }
  return lines
}

function parseAmmunition(stats: Record<string, unknown>): string | null {
  const ammo = asArray(stats['ammunition'])
  if (!ammo || ammo.length === 0) return null
  const parts: string[] = []
  for (const entry of ammo) {
    const record = asRecord(entry)
    const name = record ? asString(record['name']) : undefined
    if (!record || !name) continue
    const quantity = asNumber(record['quantity']) ?? 0
    parts.push(`${capitalize(name)} (${quantity})`)
  }
  return parts.length > 0 ? parts.join(', ') : null
}

function parseConditions(stats: Record<string, unknown>): string | null {
  const conditions = asArray(stats['conditions'])
  if (!conditions || conditions.length === 0) return null
  const names = conditions
    .map((entry) => asString(entry))
    .filter((entry) => entry !== undefined)
  return names.length > 0 ? names.join(', ') : null
}

export function StatsTooltip({ stats, anchor }: StatsTooltipProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element || !anchor) return
    const rect = anchor.getBoundingClientRect()
    const tip = element.getBoundingClientRect()
    let top = rect.top - tip.height - 8
    if (top < 8) top = rect.bottom + 8
    let left = rect.left + rect.width / 2 - tip.width / 2
    const maxLeft = window.innerWidth - tip.width - 8
    left = Math.min(Math.max(left, 8), Math.max(maxLeft, 8))
    setPosition({ top, left })
  }, [anchor, stats])

  const name = asString(stats['name']) ?? ''
  const level = asNumber(stats['level']) ?? asString(stats['level'])
  const className = asString(stats['class'])
  const header = level && className ? `Lvl ${level} ${className}` : name.replace(/_/g, ' ')

  const currentHp = asNumber(stats['currentHp'])
  const maxHp = asNumber(stats['maxHp'])
  const ac = asNumber(stats['ac'])
  const speed = asNumber(stats['speed']) ?? asString(stats['speed'])
  const initiative = asNumber(stats['initiative'])

  const attack = asRecord(stats['primaryAttack'])
  const attackBonus = attack ? asNumber(attack['bonus']) : undefined
  const attackDamage = attack ? asString(attack['damage']) : undefined
  const attackName = attack ? asString(attack['name']) ?? 'Attack' : undefined

  const ammunition = parseAmmunition(stats)
  const slotLines = parseSpellSlots(stats)
  const spellLines = parseSpells(stats)
  const featureLines = parseClassFeatures(stats)
  const conditions = parseConditions(stats)

  if (header.length === 0) return null

  return createPortal(
    <div
      ref={ref}
      role="tooltip"
      className={`neq-stats-tooltip-parity${position ? ' visible' : ''}`}
      style={{
        top: position ? position.top : 0,
        left: position ? position.left : 0,
      }}
    >
      <div className="neq-stats-tooltip-header-parity">
        {header}
      </div>

      <div className="neq-stats-tooltip-row-parity" style={{ fontSize: 12 }}>
        {currentHp !== undefined && maxHp !== undefined && (
          <span>
            {currentHp}/{maxHp} HP
          </span>
        )}
        {ac !== undefined && <span className="ml-2">AC {ac}</span>}
        {speed !== undefined && <span className="ml-2">{speed}ft</span>}
      </div>

      {(attackBonus !== undefined || initiative !== undefined) && (
        <div className="neq-stats-tooltip-row-parity" style={{ fontSize: 12 }}>
          {attackBonus !== undefined && (
            <span>
              {attackName}: {formatSigned(attackBonus)}
              {attackDamage ? ` (${attackDamage})` : ''}
            </span>
          )}
          {initiative !== undefined && (
            <span className="ml-2">Init: {formatSigned(initiative)}</span>
          )}
        </div>
      )}

      {ammunition && (
        <div className="neq-stats-tooltip-row-parity" style={{ fontSize: 11, color: '#FFB6C1' }}>
          <span>Ammo: </span><span>{ammunition}</span>
        </div>
      )}

      {slotLines.length > 0 && (
        <div className="neq-stats-tooltip-row-parity neq-stats-tooltip-section-parity" style={{ fontSize: 11 }}>
          <span style={{ color: '#87CEEB' }}>Spell Slots: </span>
          <span style={{ color: '#ddd' }}>
            {slotLines.map((slot) => `${slot.label}: ${slot.current}/${slot.max}`).join(' • ')}
          </span>
        </div>
      )}

      {spellLines.length > 0 && (
        <div className="neq-stats-tooltip-section-parity">
          <div style={{ fontSize: 11, color: '#87CEEB', marginBottom: 2 }}>Spells Known:</div>
          {spellLines.map((line) => (
            <div key={line.levelName} style={{ marginTop: 3 }}>
              <span className="font-bold" style={{ fontSize: 10, color: '#FFA500' }}>
                {line.levelName}:
              </span>{' '}
              <span style={{ fontSize: 10, color: '#f0f0f0' }}>{line.spells}</span>
            </div>
          ))}
        </div>
      )}

      {featureLines.length > 0 && (
        <div className="neq-stats-tooltip-section-parity">
          <div style={{ fontSize: 11, color: '#FFD700', marginBottom: 2 }}>Class Features:</div>
          {featureLines.map((feature) => (
            <div key={feature.name} style={{ fontSize: 10, color: '#f0f0f0', marginTop: 2 }}>
              {'\u2022'} {feature.name}
              {feature.usage && <span style={{ color: '#87CEEB' }}> ({feature.usage})</span>}
            </div>
          ))}
        </div>
      )}

      {conditions && (
        <div className="neq-stats-tooltip-row-parity neq-stats-tooltip-section-parity" style={{ fontSize: 11 }}>
          <span className="font-bold" style={{ color: '#ff6666' }}>
            Conditions:{' '}
          </span>
          <span style={{ color: '#ffaaaa' }}>{conditions}</span>
        </div>
      )}
    </div>,
    document.body,
  )
}
