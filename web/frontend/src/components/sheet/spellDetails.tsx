/** Presentation-only reference details; never resolves or executes spell mechanics. */

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function SpellDetails({ detail, fallbackName }: {
  detail?: Record<string, unknown>
  fallbackName: string
}) {
  const name = text(detail?.name) || fallbackName
  if (!detail || !Object.keys(detail).length) return <>
    <h4 className="ember-inspection-title">{name}</h4>
    <p className="ember-inspection-description">Spell reference details are unavailable. Your character’s spell list is unchanged.</p>
  </>

  const components = detail.components && typeof detail.components === 'object' && !Array.isArray(detail.components)
    ? detail.components as Record<string, unknown> : undefined
  const componentNames = components
    ? [['verbal', 'V'], ['somatic', 'S'], ['material', 'M']].filter(([key]) => components[key] === true).map(([, label]) => label).join(', ')
    : text(detail.components)
  const level = typeof detail.level === 'number' && Number.isFinite(detail.level)
    ? detail.level === 0 ? 'Cantrip' : `Level ${detail.level}` : ''
  const classes = Array.isArray(detail.classes) ? detail.classes.map(text).filter(Boolean).join(', ') : text(detail.classes)
  const rows: [string, string][] = [
    ['Level', level], ['School', text(detail.school)], ['Casting time', text(detail.casting_time)],
    ['Range', text(detail.range)], ['Components', componentNames],
    ['Materials', text(components?.materials) || text(detail.materials)], ['Duration', text(detail.duration)],
    ['Ritual', typeof detail.ritual === 'boolean' ? detail.ritual ? 'Yes' : 'No' : ''],
    ['Concentration', typeof detail.concentration === 'boolean' ? detail.concentration ? 'Yes' : 'No' : ''],
    ['Classes', classes],
  ]
  return <>
    <h4 className="ember-inspection-title">{name}</h4>
    <dl className="ember-inspection-meta">{rows.filter(([, value]) => value).map(([label, value]) =>
      <div key={label}><dt>{label}</dt><dd>{value}</dd></div>,
    )}</dl>
    <p className="ember-inspection-description">{text(detail.description) || 'Spell description is unavailable.'}</p>
    {text(detail.higher_levels) && <section className="ember-inspection-section">
      <h5>At higher levels</h5><p className="ember-inspection-description">{text(detail.higher_levels)}</p>
    </section>}
    {text(detail.source) && <p className="ember-inspection-source">Source: {text(detail.source)}{text(detail.version) && !text(detail.source).includes(text(detail.version)) ? ` · ${text(detail.version)}` : ''}</p>}
    {text(detail._srd_attribution) && <p className="ember-inspection-source">{text(detail._srd_attribution)}</p>}
  </>
}
