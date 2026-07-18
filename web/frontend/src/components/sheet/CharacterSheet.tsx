/**
 * Character tab (plan Task 4.4d): portrait, name / level / race / class / XP,
 * ability grid with hover skill tooltips, HP / AC / INIT, saving throws.
 * Renders player_data_response{stats} from the player store; field names
 * ported from the legacy displayCharacterStats renderer.
 */
import { useRef, useState } from 'react'
import { useLog, usePlayer } from '../../stores'
import {
  ABILITIES,
  SKILL_MAP,
  arr,
  abilityModifier,
  abilityScores,
  capitalize,
  capitalizeWords,
  currencyOf,
  formatModifier,
  hpPercent,
  hpTone,
  num,
  rec,
  portraitSlug,
  proficientSkills,
  saveRows,
  skillBonus,
  str,
} from './characterData'

// ASCII-only source: proficiency dots as escapes (filled / open circle).
const PROFICIENT_DOT = '\u25CF'
const UNPROFICIENT_DOT = '\u25CB'

function SheetSection({ title, items, empty }: { title: string; items: Array<{ name: string; detail?: string; suffix?: string }>; empty?: string }) {
  return (
    <section className="mt-1 rounded border border-card bg-panel">
      <h4 className="border-b border-card px-2 py-1 font-display text-sm uppercase text-[#ffa500]">{title}</h4>
      <div className="px-2 py-1">
        {items.length === 0 ? <div className="text-sm text-secondary">{empty}</div> : items.map((item, index) => (
          <div key={`${item.name}-${index}`} title={item.detail || 'No description available.'} className="text-sm text-accent">
            {item.name}{item.suffix ?? ''}
          </div>
        ))}
      </div>
    </section>
  )
}

function Portrait({ name }: { name: string }) {
  const [failed, setFailed] = useState(false)
  const [cacheBust, setCacheBust] = useState('')
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const slug = portraitSlug(name)
  const src = failed
    ? '/static/icons/default_portrait.png'
    : `/static/portraits/${slug}.png${cacheBust}`
  const upload = async (file: File | undefined) => {
    if (!file || uploading) return
    if (!file.type.startsWith('image/')) {
      useLog.getState().append({ type: 'error', content: 'Upload failed: select an image file.' })
      return
    }
    setUploading(true)
    useLog.getState().append({ type: 'system', content: 'Uploading and processing portrait...' })
    const body = new FormData(); body.append('portrait', file); body.append('characterName', slug)
    try {
      const response = await fetch('/upload-portrait', { method: 'POST', body })
      const result = await response.json() as { success?: boolean; message?: string }
      if (!response.ok || !result.success) throw new Error(result.message || 'Upload failed')
      setFailed(false); setCacheBust(`?v=${Date.now()}`)
      useLog.getState().append({ type: 'system', content: 'Portrait updated successfully!' })
    } catch (error) {
      useLog.getState().append({ type: 'error', content: `Upload failed: ${error instanceof Error ? error.message : String(error)}` })
    } finally {
      setUploading(false); if (inputRef.current) inputRef.current.value = ''
    }
  }
  return (
    <div className="group relative h-28 w-24 shrink-0 overflow-hidden rounded border-2 border-card bg-page">
      <img src={src} alt={`Portrait of ${name}`} onError={() => setFailed(true)} className="h-full w-full object-cover" />
      <button type="button" disabled={uploading} onClick={() => inputRef.current?.click()} className="absolute inset-0 flex cursor-pointer items-center justify-center border-0 bg-black/70 px-2 text-center text-sm font-bold text-white opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100">{uploading ? 'Uploading...' : 'Upload Portrait'}</button>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" aria-label="Choose portrait image" onChange={(event) => void upload(event.target.files?.[0])} />
    </div>
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
  const hasSavingThrows = Array.isArray(stats['savingThrows']) && stats['savingThrows'].length > 0
  const hp = num(stats['hitPoints'])
  const maxHp = num(stats['maxHitPoints'])
  const tone = hpTone(hp, maxHp)
  const hpColor = tone === 'low' ? '#e74c3c' : tone === 'medium' ? '#e67e22' : 'var(--accent)'
  const currency = currencyOf(stats)
  const attacks = arr(stats['attacksAndSpellcasting']).map(rec).filter((item): item is Record<string, unknown> => item !== null).map((weapon) => {
    const damage = str(weapon['damage']) || `${str(weapon['damageDice'], '1d4')}+${num(weapon['damageBonus'])}`
    return { name: str(weapon['name'], 'Unknown weapon'), suffix: ` (${damage})`, detail: str(weapon['description']) }
  })
  const ammunition = arr(stats['ammunition']).map(rec).filter((item): item is Record<string, unknown> => item !== null).map((ammo) => ({ name: str(ammo['name'], 'Unknown'), suffix: `×${num(ammo['quantity'])}` }))
  const featureItems = (key: string) => arr(stats[key]).map(rec).filter((item): item is Record<string, unknown> => item !== null).map((item) => {
    const usage = rec(item['usage'])
    const duration = str(item['duration'])
    const usageSuffix = usage && num(usage['max']) > 0 ? ` ${num(usage['current'])}/${num(usage['max'])}${str(usage['refreshOn']) ? ` (${str(usage['refreshOn'])})` : ''}` : ''
    const suffix = `${duration ? ` — ${duration}` : ''}${usageSuffix}`
    return { name: str(item['name'], 'Unknown'), detail: str(item['description']), suffix }
  })
  const racialTraits = featureItems('racialTraits').filter((trait) => !['Ability Score Increase', 'Languages', 'Extra Language'].includes(trait.name))
  const background = rec(stats['backgroundFeature'])

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

      {/* HP / AC / INIT / currency */}
      <div className="mt-3 grid grid-cols-6 gap-1">
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
        {[['GP', currency.gold], ['SP', currency.silver], ['CP', currency.copper]].map(([label, value]) => (
          <div key={label} className="rounded border-2 border-[#b8860b] bg-page p-2 text-center">
            <div className="font-display text-[10px] text-secondary">{label}</div>
            <div className="text-base text-accent">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-1">
        <SheetSection title="Weapons & Attacks" items={attacks} empty="No weapons defined." />
        <SheetSection title="Ammunition" items={ammunition} empty="No ammunition." />
      </div>

      {/* saving throws */}
      {hasSavingThrows && <div className="mt-3 rounded border-2 border-card bg-page p-2">
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
      </div>}
      <SheetSection title="Class Features" items={featureItems('classFeatures')} />
      {arr(stats['temporaryEffects']).length > 0 && <SheetSection title="Active Effects" items={featureItems('temporaryEffects')} />}
      {racialTraits.length > 0 && <SheetSection title="Racial Traits" items={racialTraits} />}
      {background?.['name'] !== undefined && <SheetSection title="Background" items={[{ name: str(background['name']), detail: str(background['description']) }]} />}
      {arr(stats['feats']).length > 0 && <SheetSection title="Feats" items={featureItems('feats')} />}
    </div>
  )
}
