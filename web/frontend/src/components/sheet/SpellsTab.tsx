/**
 * Spells tab (plan Task 4.4d): spell save DC / spell attack / slot stats plus
 * the per-level spell list with hover detail cards. Renders
 * player_data_response{spells} (full character file) from the player store;
 * derivations ported from the legacy displaySpellsAndMagic renderer.
 */
import { useEffect, useState } from 'react'
import { usePlayer } from '../../stores'
import { equipmentList, formatModifier, slotTone, spellcastingView, type EquipmentItem, type SpellLevelGroup } from './characterData'

const TONE_COLOR: Record<'available' | 'low' | 'exhausted', string> = {
  available: 'var(--accent)',
  low: '#e67e22',
  exhausted: '#e74c3c',
}

function SlotBadge({ slots }: { slots: { current: number; max: number } }) {
  return (
    <span
      className="font-chrome text-[10px]"
      style={{ color: TONE_COLOR[slotTone(slots)] }}
    >
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
  return (
    <div className="group relative flex items-center justify-between border-b border-card/60 py-0.5 text-sm last:border-b-0">
      <span className="text-primary">{spell}</span>
      {prepared && (
        <span
          className="rounded border border-accent px-1 font-chrome text-[10px] text-accent"
          title="Prepared"
        >
          P
        </span>
      )}
      {/* hover detail card */}
      <div className="pointer-events-none absolute left-2 top-full z-20 hidden w-56 rounded border-2 border-card bg-panel p-2 shadow-lg group-hover:block">
        <div className="font-display text-xs text-accent">{String(detail?.name ?? spell)}</div>
        <div className="mt-1 text-xs text-secondary">{detail ? `${Number(detail.level ?? group.levelIndex) === 0 ? 'Cantrip' : `Level ${String(detail.level ?? group.levelIndex)}`} ${String(detail.school ?? '')} • ${String(detail.casting_time ?? '')} • ${formatComponents(detail.components)}` : group.levelIndex === 0 ? 'Cantrip (at will)' : `${group.levelName} spell`}</div>
        {detail?.description !== undefined && <div className="mt-1 text-xs text-primary">{String(detail.description)}</div>}
        {Array.isArray(detail?.classes) && <div className="mt-1 text-xs text-secondary">Classes: {detail.classes.map(String).join(', ')}</div>}
        <div className="text-xs text-secondary">{prepared ? 'Prepared' : 'Known'}</div>
        {group.slots && (
          <div className="text-xs" style={{ color: TONE_COLOR[slotTone(group.slots)] }}>
            {group.slots.current}/{group.slots.max} slots remaining
          </div>
        )}
      </div>
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
  return <section className="mt-3 rounded border border-card bg-panel p-2"><h4 className="border-b border-card pb-1 font-display text-sm text-[#ffa500]">{title}</h4>{items.map((item, index) => <div key={`${item.name}-${index}`} title={item.description || 'No description available.'} className="flex justify-between border-b border-card/60 py-1 text-sm last:border-0"><span className="text-accent">{item.name}</span><span className="text-xs text-secondary">{item.spellLevel !== null ? (item.spellLevel === 0 ? 'Cantrip' : `Level ${item.spellLevel}`) : ''}{item.quantity > 1 ? ` ×${item.quantity}` : item.consumable ? ' [1x]' : ''}{item.charges ? ` ${item.charges.current}/${item.charges.max}` : ''}</span></div>)}</section>
}

export function SpellsTab() {
  const spells = usePlayer((s) => s.spells)
  const error = usePlayer((s) => s.dataErrors.spells)
  const [spellData, setSpellData] = useState<Record<string, Record<string, unknown>>>({})

  useEffect(() => {
    let active = true
    fetch('/spell-data').then((response) => response.ok ? response.json() : Promise.reject(new Error(String(response.status)))).then((data: unknown) => { if (active && data && typeof data === 'object') setSpellData(data as Record<string, Record<string, unknown>>) }).catch(() => { if (active) setSpellData({}) })
    return () => { active = false }
  }, [])

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
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
    <div className="h-full overflow-y-auto p-3 font-body">
      {view ? <><h3 className="font-display text-sm tracking-wide text-accent">Spellcasting</h3>

      {/* DC / attack / ability stats */}
      <div className="mt-1 grid grid-cols-2 gap-2">
        <div className="rounded border-2 border-card bg-page p-2 text-center">
          <div className="font-display text-[10px] text-secondary">Save DC</div>
          <div className="text-base text-primary">{view.saveDC ?? '--'}</div>
        </div>
        <div className="rounded border-2 border-card bg-page p-2 text-center">
          <div className="font-display text-[10px] text-secondary">Spell Attack</div>
          <div className="text-base text-primary">
            {view.attackBonus !== null ? formatModifier(view.attackBonus) : '--'}
          </div>
        </div>
      </div>
      {view.ability !== '' && (
        <div className="mt-1 font-chrome text-xs text-secondary">
          Casting ability: <span className="text-primary">{view.ability}</span>
        </div>
      )}

      {/* per-level spell groups */}
      {view.levels.map((group) => (
        <div key={group.levelIndex} className="mt-3 rounded border-2 border-card bg-page p-2">
          <div className="flex items-baseline justify-between">
            <h4 className="font-display text-xs text-accent">{group.levelName}</h4>
            {group.slots && <SlotBadge slots={group.slots} />}
          </div>
          <div className="mt-1">
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
      </> : <div className="rounded border border-card bg-panel p-5 text-center text-sm italic text-secondary">This character does not have spellcasting abilities.</div>}
      <div className="mt-3 rounded border-2 border-card bg-page p-2">
        <MagicCategory title="Scrolls" items={scrolls} />
        <MagicCategory title="Potions" items={potions} />
        <MagicCategory title="Magic Items" items={magical} />
        {scrolls.length === 0 && potions.length === 0 && magical.length === 0 && <section className="rounded border border-card bg-panel p-2"><h4 className="border-b border-card pb-1 font-display text-sm text-[#ffa500]">Magic Items</h4><div className="py-1 text-sm text-accent">No magical items found</div></section>}
      </div>
    </div>
  )
}
