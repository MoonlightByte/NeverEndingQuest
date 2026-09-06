import { capitalizeWords, formatModifier, rec, type SpellcastingView } from './characterData'
import '../../theme/tavern-inventory-spells.css'

/** Read every recorded slot level, including higher-level slots used for upcasting. */
export function SpellcastingSummary({ data, casting }: { data: Record<string, unknown>; casting: SpellcastingView }) {
  const rawSlots = rec(rec(data['spellcasting'])?.['spellSlots'])
  const slots = Array.from({ length: 9 }, (_, i) => {
    const level = i + 1
    const raw = rec(rawSlots?.[`level${level}`])
    if (!raw || typeof raw['current'] !== 'number' || typeof raw['max'] !== 'number' || !Number.isFinite(raw['current']) || !Number.isFinite(raw['max'])) return null
    return { level, current: raw['current'], max: raw['max'] }
  }).filter(slot => slot !== null)
  const spellCount = new Set(casting.levels.flatMap(group => group.spells)).size
  return <section className="tis-casting-summary" aria-label="Spellcasting resources">
    <div className="tis-casting-overview"><div><span className="tis-eyebrow">Spellcasting</span><h4>{casting.ability ? `${capitalizeWords(casting.ability)} caster` : 'Spellcaster'}</h4><span className="tis-spell-count">{spellCount} listed {spellCount === 1 ? 'spell' : 'spells'}{casting.prepared.length > 0 ? ` · ${new Set(casting.prepared).size} prepared` : ''}</span></div>
      <dl>{casting.saveDC !== null && <div><dt>Save DC</dt><dd>{casting.saveDC}</dd></div>}{casting.attackBonus !== null && <div><dt>Spell attack</dt><dd>{formatModifier(casting.attackBonus)}</dd></div>}</dl>
    </div>
    {slots.length > 0 ? <><div className="tis-slot-levels">{slots.map(slot => <div key={slot.level} className="tis-slot-level" role="group" aria-label={`Level ${slot.level} spell slots: ${slot.current} of ${slot.max} available`}>
      <span className="tis-slot-label">Level {slot.level}</span><strong>{slot.current}<small> / {slot.max} available</small></strong>
      {slot.max > 0 && slot.max <= 12 && Number.isInteger(slot.max) && <span className="tis-slot-pips" aria-hidden="true">{Array.from({length:slot.max}, (_, index) => <i key={index} className={index < slot.current ? 'is-available' : 'is-spent'} />)}</span>}
    </div>)}</div><p className="tis-slot-legend">Filled: available <span aria-hidden="true">·</span> Outlined: spent</p></> : <p className="tis-slot-legend">{casting.levels.every(level => level.levelIndex === 0) ? 'Cantrips do not use spell slots.' : 'No spell-slot totals recorded.'}</p>}
  </section>
}
