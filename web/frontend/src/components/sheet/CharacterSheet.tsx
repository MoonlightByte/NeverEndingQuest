/**
 * Character tab (plan Task 4.4d): portrait, name / level / race / class / XP,
 * ability grid with hover skill tooltips, HP / AC / INIT, saving throws.
 * Renders player_data_response{stats} from the player store; field names
 * ported from the legacy displayCharacterStats renderer.
 */
import { useEffect, useRef, useState } from 'react'
import { useLog, usePlayer } from '../../stores'
import { GenericFeatureTooltip, SkillTooltip } from './CharacterTooltips'
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
  str,
} from './characterData'
import type { AbilityName } from './characterData'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberCurrency } from './EmberCurrency'
import { invalidateMediaCaches, useMediaRevision } from '../party/media'
import { EmberInspection } from './EmberInspection'
import { EmberIcon } from '../layout/EmberIcon'

// ASCII-only source: proficiency dots as escapes (filled / open circle).
const PROFICIENT_DOT = '\u25CF'
const UNPROFICIENT_DOT = '\u25CB'

function SheetSection({ title, items, empty, accentItems = false, rightSuffix = false, splitSuffix = false, tooltips = true }: { title: string; items: Array<{ name: string; detail?: string; suffix?: string }>; empty?: string; accentItems?: boolean; rightSuffix?: boolean; splitSuffix?: boolean; tooltips?: boolean }) {
  const ember = useEmberDesktop()
  const [hovered, setHovered] = useState<{ item: { name: string; detail?: string }; anchor: HTMLElement } | null>(null)
  return <>
    <section className="neq-sheet-section mt-1 rounded border border-card bg-panel">
      <h4 className="border-b border-card px-2 py-1 font-display text-sm uppercase text-[#ffa500]">{title}</h4>
      <div className="neq-sheet-section-content px-2 py-1">
        {items.length === 0 ? <div className="text-sm text-secondary">{empty}</div> : items.map((item, index) => (
          <div
            key={`${item.name}-${index}`}
            data-has-tooltip={tooltips ? 'true' : 'false'}
            onMouseEnter={!ember && tooltips ? (event) => setHovered({ item, anchor: event.currentTarget }) : undefined}
            onMouseLeave={!ember && tooltips ? () => setHovered(null) : undefined}
            className={`neq-feature-item text-sm ${rightSuffix ? 'flex justify-between' : ''} ${accentItems ? 'text-accent' : 'text-[#aaa]'}`}
          >
            <span className={splitSuffix ? 'neq-ammo-name' : ''}>{ember && tooltips ? <EmberInspection label={item.name}><p style={{ whiteSpace: 'pre-wrap' }}>{item.detail || 'No description available.'}</p></EmberInspection> : item.name}</span>{item.suffix && (() => {
              const usage = title === 'Class Features' ? item.suffix.match(/^\s*(\d+\/\d+)(?:\s+\((.+)\))?$/) : null
              if (usage) return <><span className="neq-usage-counter">{usage[1]}</span>{usage[2] && <span className="neq-feature-refresh">({usage[2]})</span>}</>
              return <span className={rightSuffix ? 'neq-feature-suffix' : splitSuffix ? 'neq-ammo-quantity' : ''}>{rightSuffix && <span className="sr-only"> — </span>}{rightSuffix ? item.suffix.replace(/^\s*—\s*/, '') : item.suffix}</span>
            })()}
          </div>
        ))}
      </div>
    </section>
    {hovered && <GenericFeatureTooltip anchor={hovered.anchor} title={hovered.item.name} content={hovered.item.detail || 'No description available.'} />}
  </>
}

function Portrait({ name }: { name: string }) {
  const revision = useMediaRevision()
  const [failed, setFailed] = useState(false)
  const [cacheBust, setCacheBust] = useState('')
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { setFailed(false); setCacheBust(revision ? `?media_revision=${revision}` : '') }, [revision])
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
      invalidateMediaCaches(name, true)
      useLog.getState().append({ type: 'system', content: 'Portrait updated successfully!' })
    } catch (error) {
      useLog.getState().append({ type: 'error', content: `Upload failed: ${error instanceof Error ? error.message : String(error)}` })
    } finally {
      setUploading(false); if (inputRef.current) inputRef.current.value = ''
    }
  }
  return (
    <div className="neq-character-portrait group relative h-[150px] w-[150px] shrink-0 overflow-hidden rounded border-2 border-card bg-page">
      <img src={src} alt={`Portrait of ${name}`} onError={() => setFailed(true)} className="h-full w-full object-cover" />
      <button type="button" disabled={uploading} onClick={() => inputRef.current?.click()} className="absolute inset-0 flex cursor-pointer items-center justify-center border-0 bg-black/70 px-2 text-center text-sm font-bold text-white opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100">{uploading ? 'Uploading...' : 'Upload Portrait'}</button>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" aria-label="Choose portrait image" onChange={(event) => void upload(event.target.files?.[0])} />
    </div>
  )
}

export function CharacterSheet() {
  const ember = useEmberDesktop()
  const stats = usePlayer((s) => s.stats)
  const error = usePlayer((s) => s.dataErrors.stats)
  const notice = usePlayer((s) => s.dataNotices.stats)
  const [skillHover, setSkillHover] = useState<{ ability: AbilityName; anchor: HTMLElement } | null>(null)

  if (error) {
    return <p role={ember ? 'alert' : undefined} data-state="error" className="ember-sheet-status p-4 font-body text-sm text-red-400">{error}</p>
  }
  if (notice) {
    return <p role={ember ? 'status' : undefined} data-state="notice" className="ember-sheet-status p-4 font-body text-sm text-secondary">{notice}</p>
  }
  if (!stats) {
    return <p role={ember ? 'status' : undefined} data-state="loading" className="ember-sheet-status neq-character-loading-parity">Loading character stats...</p>
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
    <div className="neq-character-tab h-full overflow-y-auto font-body">
      <div className="neq-character-sheet">
      {/* header: portrait + identity */}
      <div className="neq-character-sheet-top flex gap-3">
        <Portrait key={name} name={name} />
        <div className="neq-character-header min-w-0 flex-1 rounded border border-card bg-page p-2">
          <div className="neq-character-name font-display">{name}</div>
          <div className="neq-character-details mt-1 space-y-0.5 text-sm text-[#ccc]">
            <div>
              <span className="text-accent">Level {num(stats['level'], 1)}</span>{' '}
              <span className="text-primary">
                {str(stats['race'], 'Unknown')} {str(stats['class'], 'Adventurer')}
              </span>
            </div>
            <div className="ember-xp-line">
              <span className="text-accent">XP:</span> {num(stats['experience_points'])} /{' '}
              {num(stats['exp_required_for_next_level'])}
            </div>
            {ember && <div className="ember-xp-track" role="progressbar" aria-label="Experience" aria-valuemin={0} aria-valuemax={num(stats['exp_required_for_next_level']) || 1} aria-valuenow={num(stats['experience_points'])}><span style={{ width: `${Math.max(0, Math.min(100, num(stats['experience_points']) / (num(stats['exp_required_for_next_level']) || 1) * 100))}%` }} /></div>}
            <div className="ember-profession">
              <span className="text-accent">Profession:</span>{' '}
              {str(stats['background'], 'Adventurer')}
            </div>
            <div className="ember-alignment">
              <span className="text-accent">Alignment:</span>{' '}
              {capitalizeWords(str(stats['alignment'], 'Neutral'))}
            </div>
          </div>
        </div>
      </div>

      {/* ability grid with hover skill tooltips */}
      <div className="neq-abilities-row mt-3 grid grid-cols-6 gap-1">
        {ABILITIES.map((ability) => {
          const score = scores[ability]
          const abilityLabel = capitalize(ability)
          const abilitySkills = SKILL_MAP[abilityLabel] ?? []
          if (ember && abilitySkills.length > 0) return <div key={ability} className="neq-ability-score relative rounded border-2 border-card bg-panel py-1 text-center">
            <EmberInspection label={`${abilityLabel} ${score}, modifier ${formatModifier(abilityModifier(score))}`} className="ember-ability-inspection" triggerContent={<>
              <span className="neq-ability-name block font-display text-[10px] text-secondary">{ability.slice(0, 3).toUpperCase()}</span>
              <span className="neq-ability-value block text-base leading-tight text-primary">{score}</span>
              <span className="neq-ability-modifier block text-xs text-accent">{formatModifier(abilityModifier(score))}</span>
            </>}>
              <h4>{abilityLabel} Skills</h4>
              <dl>{abilitySkills.map(skill => <div className="ember-inspection-meta" key={skill}><dt>{skills.includes(skill) ? PROFICIENT_DOT : UNPROFICIENT_DOT} {skill}</dt><dd>{formatModifier(abilityModifier(score) + (skills.includes(skill) ? num(stats['proficiencyBonus'], 2) : 0))}</dd></div>)}</dl>
            </EmberInspection>
          </div>
          return (
            <div
              key={ability}
              tabIndex={ember && abilitySkills.length > 0 ? 0 : undefined}
              aria-label={ember ? `${abilityLabel} ${score}, modifier ${formatModifier(abilityModifier(score))}` : undefined}
              onFocus={ember && abilitySkills.length > 0 ? (event) => setSkillHover({ ability, anchor: event.currentTarget }) : undefined}
              onBlur={ember ? () => setSkillHover(null) : undefined}
              onMouseEnter={abilitySkills.length > 0 ? (event) => setSkillHover({ ability, anchor: event.currentTarget }) : undefined}
              onMouseLeave={abilitySkills.length > 0 ? () => setSkillHover(null) : undefined}
              className="neq-ability-score relative rounded border-2 border-card bg-panel py-1 text-center"
            >
              <div className="neq-ability-name font-display text-[10px] text-secondary">
                {ability.slice(0, 3).toUpperCase()}
              </div>
              <div className="neq-ability-value text-base leading-tight text-primary">{score}</div>
              <div className="neq-ability-modifier text-xs text-accent">{formatModifier(abilityModifier(score))}</div>
            </div>
          )
        })}
      </div>
      {skillHover && (() => {
        const label = capitalize(skillHover.ability)
        const mod = abilityModifier(scores[skillHover.ability])
        const rows = (SKILL_MAP[label] ?? []).map((skill) => {
          const proficient = skills.includes(skill)
          return { name: skill, proficient, bonus: mod + (proficient ? num(stats['proficiencyBonus'], 2) : 0) }
        })
        return <SkillTooltip anchor={skillHover.anchor} ability={label} rows={rows} />
      })()}

      {/* HP / AC / INIT / currency */}
      <div className="neq-combat-stats mt-3 grid grid-cols-6 gap-1">
        <div className="neq-combat-stat rounded border border-accent bg-panel p-2 text-center">
          <div className="neq-combat-label font-display text-[10px] text-secondary">{ember && <EmberIcon name="heart" />}HP</div>
          <div className="neq-combat-value text-base text-accent">
            {hp}/{maxHp}
          </div>
          <div className="neq-hp-bar mt-1 h-1.5 overflow-hidden rounded bg-page">
            <div
              className="h-full transition-all"
              style={{ width: `${hpPercent(hp, maxHp)}%`, backgroundColor: hpColor }}
            />
          </div>
        </div>
        <div className="neq-combat-stat rounded border border-accent bg-panel p-2 text-center">
          <div className="neq-combat-label font-display text-[10px] text-secondary">{ember && <EmberIcon name="shield" />}AC</div>
          <div className="neq-combat-value text-base text-accent">{num(stats['armorClass'], 10)}</div>
        </div>
        <div className="neq-combat-stat rounded border border-accent bg-panel p-2 text-center">
          <div className="neq-combat-label font-display text-[10px] text-secondary">{ember && <EmberIcon name="boot" />}INIT</div>
          <div className="neq-combat-value text-base text-accent">
            {formatModifier(num(stats['initiative']))}
          </div>
        </div>
        {!ember && [['GP', currency.gold], ['SP', currency.silver], ['CP', currency.copper]].map(([label, value]) => (
          <div key={label} className="neq-combat-stat neq-currency rounded border border-[#b8860b] bg-panel p-2 text-center">
            <div className="neq-combat-label font-display text-[10px] text-secondary">{label}</div>
            <div className="neq-combat-value text-base text-accent">{value}</div>
          </div>
        ))}
      </div>

      <div className="neq-weapons-grid grid grid-cols-2 gap-1">
        <SheetSection title="Weapons & Attacks" items={attacks} empty="No weapons defined." accentItems />
        <SheetSection title="Ammunition" items={ammunition} empty="No ammunition." accentItems splitSuffix tooltips={false} />
      </div>

      {/* saving throws */}
      {hasSavingThrows && <div className="neq-saving-throws mt-3 rounded border border-card bg-panel p-2">
        <h4 className="font-display text-xs text-[#ffa500]">Saving Throws</h4>
        <div className="neq-saving-throws-grid mt-1 grid grid-cols-2 gap-x-4 gap-y-1">
          {saves.map((save) => (
            <div key={save.name} className="flex justify-between text-sm" aria-label={ember ? `${save.name} ${formatModifier(save.bonus)}${save.proficient ? ', proficient' : ''}` : undefined} title={`${save.name}${save.proficient ? ' — proficient' : ''}`}>
              <span className={save.proficient ? 'text-primary' : 'text-secondary'}>
                {ember ? save.name.slice(0, 3).toUpperCase() : save.name} {!ember && (save.proficient ? PROFICIENT_DOT : UNPROFICIENT_DOT)}
              </span>
              <span className="text-accent">{formatModifier(save.bonus)}</span>
            </div>
          ))}
        </div>
      </div>}
      <div className="neq-abilities-grid">
      <SheetSection title="Class Features" items={featureItems('classFeatures')} />
      {arr(stats['temporaryEffects']).length > 0 && <SheetSection title="Active Effects" items={featureItems('temporaryEffects')} rightSuffix />}
      {racialTraits.length > 0 && <SheetSection title="Racial Traits" items={racialTraits} />}
      {background?.['name'] !== undefined && <SheetSection title="Background" items={[{ name: str(background['name']), detail: str(background['description']) }]} />}
      {arr(stats['feats']).length > 0 && <SheetSection title="Feats" items={featureItems('feats')} />}
      </div>
      {ember && <EmberCurrency currency={currency} />}
      </div>
    </div>
  )
}
