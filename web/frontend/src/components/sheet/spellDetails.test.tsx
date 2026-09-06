// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
// @ts-expect-error Node is test-only; do not add Node globals to the browser app tsconfig.
import { execFileSync } from 'node:child_process'
// @ts-expect-error Node is test-only; do not add Node globals to the browser app tsconfig.
import { resolve } from 'node:path'
// @ts-expect-error Node is test-only; do not add Node globals to the browser app tsconfig.
import process from 'node:process'
import { SpellDetails } from './spellDetails'
import { spellKey } from './spellKey'

afterEach(cleanup)

describe('public spell reference lookup', () => {
  it('matches every canonical and historical key in the real public compatibility map', () => {
    // Import the actual production implementation rather than duplicating its
    // normalization or assuming that legacy names are still canonical keys.
    const cwd = resolve(process.cwd(), '../..')
    const python = process.env.NEQ_TEST_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3')
    const result = JSON.parse(execFileSync(python, ['-c', `
import json
from core.ai.srd_reference import SRDReferenceIndex, normalize_rule_name
index = SRDReferenceIndex.from_path()
names = [term for _, term, _ in index.lookup_terms()]
names += ["  MÉLF’S   Acid—Arrow!! ", "Melf's Acid Arrow", "Ａｃｉｄ Ａｒｒｏｗ", "Éclair", "Cafe\\u0301", "A\\u034fB", "A\\u20ddB", "A\\u05b0B", ""]
print(json.dumps({"map": index.compatibility_spell_map(), "names": [[n, normalize_rule_name(n)] for n in names]}))
`], { cwd, encoding: 'utf8' })) as { map: Record<string, Record<string, unknown>>; names: [string, string][] }
    expect(Object.keys(result.map).length).toBeGreaterThan(339)
    for (const [name, key] of result.names) expect(spellKey(name), name).toBe(key)
    expect(result.map[spellKey('Melf’s Acid Arrow')].name).toBe('Acid Arrow')
    expect(result.map[spellKey('Acid Arrow')]).toEqual(result.map[spellKey("Melf's Acid Arrow")])
    render(<SpellDetails detail={result.map.acid_arrow} fallbackName="Acid Arrow" />)
    expect(screen.getByText('powdered rhubarb leaf')).toBeTruthy()
    expect(screen.getByText('90 feet')).toBeTruthy()
  })

  it('does not coerce malformed names into lookup keys', () => {
    for (const value of [undefined, null, 0, {}, []]) expect(spellKey(value)).toBe('')
  })
})

describe('SpellDetails', () => {
  it('exposes complete metadata, higher-level text and explicit boolean states', () => {
    const { container } = render(<SpellDetails fallbackName="Fallback" detail={{
      name: 'Reference spell', level: 0, school: 'Divination', casting_time: 'Action', range: 'Touch',
      components: { verbal: true, somatic: false, material: true, materials: 'A silver coin' },
      duration: '1 minute', ritual: true, concentration: false, classes: ['Wizard', 'Bard'],
      description: 'The original description.', higher_levels: 'The original upgrade.', source: 'SRD 5.2.1', version: '5.2.1',
    }} />)
    const rows = Object.fromEntries(Array.from(container.querySelectorAll('dl > div')).map((row) => [row.querySelector('dt')?.textContent, row.querySelector('dd')?.textContent]))
    expect(rows).toEqual({ Level: 'Cantrip', School: 'Divination', 'Casting time': 'Action', Range: 'Touch', Components: 'V, M', Materials: 'A silver coin', Duration: '1 minute', Ritual: 'Yes', Concentration: 'No', Classes: 'Wizard, Bard' })
    expect(screen.getByText('The original description.')).toBeTruthy()
    expect(screen.getByText('The original upgrade.')).toBeTruthy()
    expect(screen.getByText('Source: SRD 5.2.1')).toBeTruthy()
  })

  it('shows unavailable details without inventing cantrip or ritual defaults', () => {
    const { rerender, container } = render(<SpellDetails fallbackName="Custom spell" />)
    expect(screen.getByText(/Spell reference details are unavailable/)).toBeTruthy()
    rerender(<SpellDetails fallbackName="Custom spell" detail={{ name: 'Custom spell' }} />)
    expect(screen.getByText('Spell description is unavailable.')).toBeTruthy()
    expect(container.querySelectorAll('dt')).toHaveLength(0)
    expect(container.textContent).not.toContain('undefined')
  })

  it('renders untrusted reference strings as text, not executable markup', () => {
    const markup = '<img src=x onerror="alert(1)">'
    const { container } = render(<SpellDetails fallbackName={markup} detail={{ description: markup, higher_levels: markup, components: { materials: markup } }} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getAllByText(markup)).toHaveLength(4)
  })
})
