/**
 * Spells tab (plan Task 4.4d): spell save DC / spell attack / slot stats plus
 * the per-level spell list with hover detail cards. Renders
 * player_data_response{spells} (full character file) from the player store;
 * derivations ported from the legacy displaySpellsAndMagic renderer.
 */
import { usePlayer } from '../../stores'
import { formatModifier, slotTone, spellcastingView, type SpellLevelGroup } from './characterData'

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
}: {
  spell: string
  group: SpellLevelGroup
  prepared: boolean
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
        <div className="font-display text-xs text-accent">{spell}</div>
        <div className="mt-1 text-xs text-secondary">
          {group.levelIndex === 0 ? 'Cantrip (at will)' : `${group.levelName} spell`}
        </div>
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

export function SpellsTab() {
  const spells = usePlayer((s) => s.spells)
  const error = usePlayer((s) => s.dataErrors.spells)

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (!spells) {
    return <p className="p-4 font-body text-sm text-secondary">Loading spells...</p>
  }

  const view = spellcastingView(spells)
  if (!view) {
    return (
      <p className="p-4 font-body text-sm italic text-secondary">
        This character does not have spellcasting abilities.
      </p>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-3 font-body">
      <h3 className="font-display text-sm tracking-wide text-accent">Spellcasting</h3>

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
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
