/**
 * Character tab (plan Task 4.4d): portrait, name / level / race / class / XP,
 * ability grid with hover skill tooltips, HP / AC / INIT, saving throws.
 * Renders player_data_response{stats} from the player store; field names
 * ported from the legacy displayCharacterStats renderer.
 */
import { useState } from 'react'
import { usePlayer } from '../../stores'
import {
  ABILITIES,
  SKILL_MAP,
  abilityModifier,
  abilityScores,
  capitalize,
  capitalizeWords,
  formatModifier,
  hpPercent,
  hpTone,
  num,
  portraitSlug,
  proficientSkills,
  saveRows,
  skillBonus,
  str,
} from './characterData'

// ASCII-only source: proficiency dots as escapes (filled / open circle).
const PROFICIENT_DOT = '\u25CF'
const UNPROFICIENT_DOT = '\u25CB'

function Portrait({ name }: { name: string }) {
  const [failed, setFailed] = useState(false)
  const src = failed
    ? '/static/icons/default_portrait.png'
    : `/static/portraits/${portraitSlug(name)}.png`
  return (
    <img
      src={src}
      alt={`Portrait of ${name}`}
      onError={() => setFailed(true)}
      className="h-28 w-24 shrink-0 rounded border-2 border-card bg-page object-cover"
    />
  )
}

export function CharacterSheet() {
  const stats = usePlayer((s) => s.stats)
  const error = usePlayer((s) => s.dataErrors.stats)

  if (error) {
    return <p className="p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (!stats) {
    return <p className="p-4 font-body text-sm text-secondary">Loading character...</p>
  }

  const name = str(stats['name'], 'Unknown Adventurer')
  const scores = abilityScores(stats)
  const skills = proficientSkills(stats)
  const saves = saveRows(stats)
  const hp = num(stats['hitPoints'])
  const maxHp = num(stats['maxHitPoints'])
  const tone = hpTone(hp, maxHp)
  const hpColor = tone === 'low' ? '#e74c3c' : tone === 'medium' ? '#e67e22' : 'var(--accent)'

  return (
    <div className="h-full overflow-y-auto p-3 font-body">
      {/* header: portrait + identity */}
      <div className="flex gap-3">
        <Portrait key={name} name={name} />
        <div className="min-w-0 flex-1 rounded border-2 border-card bg-page p-2">
          <div className="truncate font-display text-lg text-primary">{name}</div>
          <div className="mt-1 space-y-0.5 text-sm text-secondary">
            <div>
              <span className="text-accent">Level {num(stats['level'], 1)}</span>{' '}
              <span className="text-primary">
                {str(stats['race'], 'Unknown')} {str(stats['class'], 'Adventurer')}
              </span>
            </div>
            <div>
              <span className="text-accent">XP:</span> {num(stats['experience_points'])} /{' '}
              {num(stats['exp_required_for_next_level'])}
            </div>
            <div>
              <span className="text-accent">Profession:</span>{' '}
              {str(stats['background'], 'Adventurer')}
            </div>
            <div>
              <span className="text-accent">Alignment:</span>{' '}
              {capitalizeWords(str(stats['alignment'], 'Neutral'))}
            </div>
          </div>
        </div>
      </div>

      {/* ability grid with hover skill tooltips */}
      <div className="mt-3 grid grid-cols-6 gap-1">
        {ABILITIES.map((ability) => {
          const score = scores[ability]
          const abilityLabel = capitalize(ability)
          const abilitySkills = SKILL_MAP[abilityLabel] ?? []
          return (
            <div
              key={ability}
              className="group relative rounded border-2 border-card bg-page py-1 text-center"
            >
              <div className="font-display text-[10px] text-secondary">
                {ability.slice(0, 3).toUpperCase()}
              </div>
              <div className="text-base leading-tight text-primary">{score}</div>
              <div className="text-xs text-accent">{formatModifier(abilityModifier(score))}</div>
              <div className="pointer-events-none absolute left-1/2 top-full z-20 hidden w-48 -translate-x-1/2 rounded border-2 border-card bg-panel p-2 text-left shadow-lg group-hover:block">
                <div className="font-display text-xs text-accent">{abilityLabel} Skills</div>
                {abilitySkills.length === 0 ? (
                  <div className="mt-1 text-xs text-secondary">No associated skills</div>
                ) : (
                  abilitySkills.map((skill) => (
                    <div key={skill} className="mt-1 flex justify-between text-xs">
                      <span
                        className={skills.includes(skill) ? 'text-primary' : 'text-secondary'}
                      >
                        {skills.includes(skill) ? PROFICIENT_DOT : UNPROFICIENT_DOT} {skill}
                      </span>
                      <span className="text-accent">
                        {formatModifier(skillBonus(skill, ability, stats))}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* HP / AC / INIT */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded border-2 border-card bg-page p-2 text-center">
          <div className="font-display text-[10px] text-secondary">HP</div>
          <div className="text-base text-primary">
            {hp}/{maxHp}
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-panel">
            <div
              className="h-full rounded transition-all"
              style={{ width: `${hpPercent(hp, maxHp)}%`, backgroundColor: hpColor }}
            />
          </div>
        </div>
        <div className="rounded border-2 border-card bg-page p-2 text-center">
          <div className="font-display text-[10px] text-secondary">AC</div>
          <div className="text-base text-primary">{num(stats['armorClass'], 10)}</div>
        </div>
        <div className="rounded border-2 border-card bg-page p-2 text-center">
          <div className="font-display text-[10px] text-secondary">INIT</div>
          <div className="text-base text-primary">
            {formatModifier(num(stats['initiative']))}
          </div>
        </div>
      </div>

      {/* saving throws */}
      <div className="mt-3 rounded border-2 border-card bg-page p-2">
        <h4 className="font-display text-xs text-accent">Saving Throws</h4>
        <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1">
          {saves.map((save) => (
            <div key={save.name} className="flex justify-between text-sm">
              <span className={save.proficient ? 'text-primary' : 'text-secondary'}>
                {save.name} {save.proficient ? PROFICIENT_DOT : UNPROFICIENT_DOT}
              </span>
              <span className="text-accent">{formatModifier(save.bonus)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
