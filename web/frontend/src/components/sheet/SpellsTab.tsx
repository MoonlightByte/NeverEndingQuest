/**
 * Spells tab (plan Task 4.4d): spell save DC / spell attack / slot stats plus
 * the per-level spell list with hover detail cards. Renders
 * player_data_response{spells} (full character file) from the player store;
 * derivations ported from the legacy displaySpellsAndMagic renderer.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { usePlayer } from '../../stores'
import { equipmentList, formatModifier, slotTone, spellcastingView, type EquipmentItem, type SpellLevelGroup } from './characterData'

function SlotBadge({ slots }: { slots: { current: number; max: number } }) {
  return (
    <span className={`neq-spell-slots ${slotTone(slots)}`}>
      {slots.current}/{slots.max} slots
    </span>
  )
}

function SpellRow({
  spell,
  group,
  prepared,
  detail,
}: {
  spell: string
  group: SpellLevelGroup
  prepared: boolean
  detail?: Record<string, unknown>
}) {
  const targetRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [hovered, setHovered] = useState(false)
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)

  useLayoutEffect(() => {
    if (!hovered || !detail || !targetRef.current || !tooltipRef.current) return
    const rect = targetRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    let top = rect.top - tooltipRect.height - 8
    if (top < 8) top = rect.bottom + 8
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2)
    if (left < 8) left = 8
    else if (left + tooltipRect.width > window.innerWidth - 8) left = window.innerWidth - tooltipRect.width - 8
    setPosition({ left, top })
  }, [detail, hovered])

  return (
    <div
      className="neq-spell-item relative flex items-center justify-between text-sm"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setPosition(null) }}
    >
      <span ref={targetRef} className="neq-spell-name text-primary">{spell}</span>
      {prepared && (
        <div className="neq-spell-badges"><span className="neq-spell-badge prepared" title="Prepared">P</span></div>
      )}
      {hovered && detail && <div
        ref={tooltipRef}
        role="tooltip"
        className={`neq-spell-tooltip-parity${position ? ' visible' : ''}`}
        style={position ?? { left: 0, top: 0, visibility: 'hidden' }}
      >
        <div className="neq-spell-tooltip-header-parity">{String(detail.name ?? spell)}</div>
        <div className="neq-spell-tooltip-meta-parity">{`${Number(detail.level ?? group.levelIndex) === 0 ? 'Cantrip' : `Level ${String(detail.level ?? group.levelIndex)}`} ${String(detail.school ?? '')} • ${String(detail.casting_time ?? '')} • ${formatComponents(detail.components)}`}</div>
        <div className="neq-spell-tooltip-description-parity">{String(detail.description ?? '')}</div>
        {Array.isArray(detail.classes) && detail.classes.length > 0 && <div className="neq-spell-tooltip-classes-parity">Classes: {detail.classes.map(String).join(', ')}</div>}
      </div>}
    </div>
  )
}

function formatComponents(raw: unknown): string {
  if (!raw || typeof raw !== 'object') return ''
  const value = raw as Record<string, unknown>
  return [['verbal','V'],['somatic','S'],['material','M']].filter(([key]) => value[key] === true).map(([,label]) => label).join(', ')
}

function spellKey(name: string): string { return name.toLowerCase().replace(/['\s/-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '') }

function MagicCategory({ title, items }: { title: string; items: EquipmentItem[] }) {
  if (items.length === 0) return null
  return <section className="neq-magic-category"><h4>{title}</h4>{items.map((item, index) => <div key={`${item.name}-${index}`} title={item.description || 'No description available.'} className="neq-magic-item"><span className="neq-magic-item-name">{item.name}</span>{title === 'Scrolls' && item.spellLevel !== null && <span className="neq-spell-badge">{item.spellLevel === 0 ? 'Cantrip' : `Level ${item.spellLevel}`}</span>}{title !== 'Magic Items' && (item.quantity > 1 ? <span className="neq-magic-item-charges">×{item.quantity}</span> : item.consumable ? <span className="neq-magic-item-charges neq-consumable">[1x]</span> : null)}{title === 'Magic Items' && item.charges && <span className={`neq-magic-item-charges ${slotTone(item.charges)}`}>{item.charges.current}/{item.charges.max}</span>}</div>)}</section>
}

export function SpellsTab() {
  const spells = usePlayer((s) => s.spells)
  const error = usePlayer((s) => s.dataErrors.spells)
  const notice = usePlayer((s) => s.dataNotices.spells)
  const [spellData, setSpellData] = useState<Record<string, Record<string, unknown>>>({})

  useEffect(() => {
    let active = true
    fetch('/spell-data').then((response) => response.ok ? response.json() : Promise.reject(new Error(String(response.status)))).then((data: unknown) => { if (active && data && typeof data === 'object') setSpellData(data as Record<string, Record<string, unknown>>) }).catch(() => { if (active) setSpellData({}) })
    return () => { active = false }
  }, [])

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (notice) {
    return <p className="p-4 font-body text-sm text-secondary">{notice}</p>
  }
  if (!spells) {
    return <p className="p-4 font-body text-sm text-secondary">Loading spells...</p>
  }

  const view = spellcastingView(spells)
  const equipment = equipmentList(spells)
  const scrolls = equipment.filter((item) => item.subtype === 'scroll')
  const potions = equipment.filter((item) => item.subtype === 'potion')
  const magical = equipment.filter((item) => item.magical && item.subtype !== 'scroll' && item.subtype !== 'potion')

  return (
    <div className="neq-spells-tab">
      <div className="neq-spells-sheet">
      {view ? <div className="neq-spellcasting-section"><h3>SPELLCASTING</h3>
      {(view.saveDC !== null || view.attackBonus !== null) && <div className="neq-spell-stats">
        {view.saveDC !== null && <span>Save DC: {view.saveDC}</span>}
        {view.attackBonus !== null && <span>Spell Attack: {formatModifier(view.attackBonus)}</span>}
      </div>}
      {view.levels.map((group) => (
        <div key={group.levelIndex} className="neq-spell-level-group">
          <div className="neq-spell-level-header">
            <span className="neq-spell-level-name">{group.levelName}</span>
            {group.slots && <SlotBadge slots={group.slots} />}
          </div>
          <div className="neq-spell-list">
            {group.spells.map((spell) => (
              <SpellRow
                key={spell}
                spell={spell}
                group={group}
                prepared={view.prepared.includes(spell)}
                detail={spellData[spellKey(spell)]}
              />
            ))}
          </div>
        </div>
      ))}
      </div> : <div className="neq-no-spells">This character does not have spellcasting abilities.</div>}
      <div className="neq-magic-items-section">
        <MagicCategory title="Scrolls" items={scrolls} />
        <MagicCategory title="Potions" items={potions} />
        <MagicCategory title="Magic Items" items={magical} />
        {scrolls.length === 0 && potions.length === 0 && magical.length === 0 && <section className="neq-magic-category"><h4>MAGIC ITEMS</h4><div className="neq-magic-item"><span className="neq-magic-item-name">No magical items found</span></div></section>}
      </div>
      </div>
    </div>
  )
}
