import { asNumber, asString } from './media'

export function PartyVitals({ stats, down = false }: { stats: Record<string, unknown>; down?: boolean }) {
  const hp = asNumber(stats['currentHp']) ?? asNumber(stats['hitPoints'])
  const max = asNumber(stats['maxHp']) ?? asNumber(stats['maxHitPoints'])
  const ac = asNumber(stats['ac']) ?? asNumber(stats['armorClass'])
  const level = asNumber(stats['level'])
  const xp = asNumber(stats['experience_points'])
  const next = asNumber(stats['exp_required_for_next_level'])
  // A downed card already carries its own Unconscious label (CharacterChip); don't repeat it here.
  const shown = (value: string) => !(down && value.toLowerCase() === 'unconscious')
  const listed = Array.isArray(stats['conditions']) ? stats['conditions'].filter((value): value is string => typeof value === 'string') : [asString(stats['condition']) ?? '']
  const conditions = listed.filter(value => value && shown(value)).join(', ')
  const status = asString(stats['status'])
  return <span className="ember-party-vitals">
    {level !== undefined && <span className="ember-party-level">Level {level}{asString(stats['class']) ? ` · ${stats['class']}` : ''}</span>}
    <span className="ember-party-combat">
      {hp !== undefined && <span><span className="ember-vital-label">HP</span> {hp}{max !== undefined ? ` / ${max}` : ''}</span>}
      {ac !== undefined && <span><span className="ember-vital-label">AC</span> {ac}</span>}
    </span>
    {hp !== undefined && max !== undefined && max > 0 && <span className="ember-party-hp" aria-hidden="true"><span data-low={hp / max <= .25} style={{ width: `${Math.max(0, Math.min(100, hp / max * 100))}%` }} /></span>}
    {xp !== undefined && <span className="ember-party-xp"><span className="ember-vital-label">XP</span> {xp}{next !== undefined ? ` / ${next}` : ''}</span>}
    {conditions && conditions.toLowerCase() !== 'none' && <span className="ember-party-condition">{conditions}</span>}
    {status && status.toLowerCase() !== 'alive' && shown(status) && <span className="ember-party-condition">{status}</span>}
  </span>
}
