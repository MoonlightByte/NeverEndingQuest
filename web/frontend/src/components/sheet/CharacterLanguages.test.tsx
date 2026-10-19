// @vitest-environment jsdom
// #1276 rows C1-C6: the sheet shows the typed `languages` field.
// Drop into web/frontend/src/components/sheet/.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { usePlayer } from '../../stores'
import { CharacterSheet } from './CharacterSheet'

const initialPlayer = usePlayer.getState()

function sheet(extra: Record<string, unknown> = {}) {
  return {
    name: 'Tova Ironvein', level: 1, race: 'Dwarf', class: 'Cleric',
    abilities: { strength: 14, dexterity: 10, constitution: 15, intelligence: 10, wisdom: 16, charisma: 8 },
    hitPoints: 11, maxHitPoints: 11,
    racialTraits: [
      { name: 'Darkvision', description: 'You see in dim light within 60 feet.' },
      { name: 'Languages', description: 'You can speak, read, and write Common and Dwarvish.' },
    ],
    ...extra,
  }
}

function languagesSection(): HTMLElement | null {
  const heading = screen.queryByRole('heading', { name: 'Languages' })
  return heading ? heading.closest('section') : null
}

function shown(section: HTMLElement): string[] {
  return Array.from(section.querySelectorAll('.neq-feature-item')).map((item) => item.textContent ?? '')
}

beforeEach(() => { usePlayer.setState(initialPlayer, true) })
afterEach(() => { cleanup() })

describe('#1276 languages on the character sheet', () => {
  it('C1: the Character panel lists the languages in order', () => {
    usePlayer.setState({ stats: sheet({ languages: ['Common', 'Dwarvish', 'Giant'] }) })
    render(<CharacterSheet />)
    const section = languagesSection()
    expect(section).not.toBeNull()
    expect(shown(section!)).toEqual(['Common', 'Dwarvish', 'Giant'])
  })

  it('C2: the sheet modal lists the languages in order', () => {
    usePlayer.setState({ stats: sheet({ languages: ['Common', 'Dwarvish', 'Giant'] }) })
    render(<CharacterSheet expanded hideIdentity />)
    const section = languagesSection()
    expect(section).not.toBeNull()
    expect(shown(section!)).toEqual(['Common', 'Dwarvish', 'Giant'])
  })

  it('C3: no languages field, or an empty one, adds nothing', () => {
    usePlayer.setState({ stats: sheet() })
    const without = render(<CharacterSheet />).container.innerHTML
    cleanup()
    usePlayer.setState({ stats: sheet({ languages: [] }) })
    const empty = render(<CharacterSheet />).container.innerHTML
    expect(languagesSection()).toBeNull()
    expect(empty).toBe(without)
  })

  it('C4: non-string and blank entries are skipped; strings are shown verbatim', () => {
    usePlayer.setState({ stats: sheet({ languages: [1, '', '  ', 'Elvish', "Thieves' Cant"] }) })
    render(<CharacterSheet />)
    const section = languagesSection()
    expect(section).not.toBeNull()
    expect(shown(section!)).toEqual(['Elvish', "Thieves' Cant"])
  })

  it('C5: a racial trait named Languages stays out of Racial Traits', () => {
    usePlayer.setState({ stats: sheet({ languages: ['Common', 'Dwarvish'] }) })
    render(<CharacterSheet />)
    const traits = screen.getByRole('heading', { name: 'Racial Traits' }).closest('section') as HTMLElement
    expect(within(traits).queryByText('Languages')).toBeNull()
    expect(within(traits).getByText('Darkvision')).toBeTruthy()
  })
})

describe('#1276 C6: no text reads of a language', () => {
  it('leaves no regex or includes() over a language string in src', () => {
    const root = join(__dirname, '../..')
    const files: string[] = []
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name)
        if (statSync(path).isDirectory()) walk(path)
        else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) files.push(path)
      }
    }
    walk(root)
    // The typed field (lowercase `languages`) is only rendered, never matched
    // or rewritten. The existing racial-trait name filter ('Languages') is
    // CharacterSheet.tsx:151's, kept by the plan, and is not this field.
    const reads = /\blanguages?\b[^\n]*\.(test|match|includes|search|replace|toLowerCase|toUpperCase)\(/
    const hits = files.filter((file) => reads.test(readFileSync(file, 'utf8')))
    expect(hits).toEqual([])
  })
})
