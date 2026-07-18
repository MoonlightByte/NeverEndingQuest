// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { usePlayer } from '../../stores'
import { CharacterSheet } from './CharacterSheet'
import { GenericFeatureTooltip, SkillTooltip } from './CharacterTooltips'

const initialPlayer = usePlayer.getState()

function box(top: number, left: number, width: number, height: number): DOMRect {
  return {
    x: left,
    y: top,
    top,
    left,
    width,
    height,
    right: left + width,
    bottom: top + height,
    toJSON: () => ({}),
  }
}

beforeEach(() => {
  usePlayer.setState(initialPlayer, true)
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 })
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('character tooltip positioning', () => {
  it('flips the skill tooltip left and clamps it above the viewport bottom', () => {
    const anchor = document.createElement('div')
    anchor.getBoundingClientRect = vi.fn(() => box(550, 760, 40, 40))
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return this.classList.contains('neq-skill-tooltip-parity')
        ? box(0, 0, 220, 180)
        : box(0, 0, 0, 0)
    })
    render(<SkillTooltip anchor={anchor} ability="Dexterity" rows={[
      { name: 'Acrobatics', proficient: true, bonus: 5 },
      { name: 'Stealth', proficient: false, bonus: 3 },
    ]} />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.classList.contains('neq-skill-tooltip-parity')).toBe(true)
    expect(tooltip.style.left).toBe('530px')
    expect(tooltip.style.top).toBe('410px')
    expect(tooltip.textContent).toContain('Dexterity Skills')
    expect(tooltip.textContent).toContain('● Acrobatics')
    expect(tooltip.textContent).toContain('○ Stealth')
    expect(tooltip.textContent).toContain('+5')
  })

  it('flips a generic feature tooltip below and clamps it to the right edge', () => {
    const anchor = document.createElement('div')
    anchor.getBoundingClientRect = vi.fn(() => box(4, 780, 20, 40))
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return this.classList.contains('neq-generic-tooltip-parity')
        ? box(0, 0, 350, 160)
        : box(0, 0, 0, 0)
    })
    render(<GenericFeatureTooltip anchor={anchor} title="Sneak Attack" content="Deal extra damage once per turn." />)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.classList.contains('neq-generic-tooltip-parity')).toBe(true)
    expect(tooltip.style.left).toBe('442px')
    expect(tooltip.style.top).toBe('52px')
    expect(tooltip.textContent).toBe('Sneak AttackDeal extra damage once per turn.')
  })
})

describe('CharacterSheet tooltip integration', () => {
  beforeEach(() => {
    usePlayer.setState({
      stats: {
        name: 'Arden Vale',
        level: 4,
        race: 'Human',
        class: 'Rogue',
        abilities: { strength: 14, dexterity: 18, constitution: 12, intelligence: 11, wisdom: 10, charisma: 13 },
        skills: ['Athletics', 'Stealth'],
        proficiencyBonus: 2,
        hitPoints: 24,
        maxHitPoints: 30,
        armorClass: 15,
        initiative: 4,
        classFeatures: [{ name: 'Sneak Attack', description: 'Deal extra damage once per turn.' }],
      },
    })
  })

  it('renders the exact legacy skill rows from an ability hover', () => {
    render(<CharacterSheet />)
    const strength = screen.getByText('STR').closest('.neq-ability-score') as HTMLElement
    fireEvent.mouseEnter(strength)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.textContent).toContain('Strength Skills')
    expect(tooltip.textContent).toContain('● Athletics')
    expect(tooltip.textContent).toContain('+4')
    fireEvent.mouseLeave(strength)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.mouseEnter(screen.getByText('CON').closest('.neq-ability-score') as HTMLElement)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('replaces the native title with the legacy generic feature tooltip', () => {
    render(<CharacterSheet />)
    const feature = screen.getByText('Sneak Attack').closest('.neq-feature-item') as HTMLElement
    expect(feature.getAttribute('title')).toBeNull()
    fireEvent.mouseEnter(feature)
    const tooltip = screen.getByRole('tooltip')
    expect(tooltip.textContent).toBe('Sneak AttackDeal extra damage once per turn.')
    fireEvent.mouseLeave(feature)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})
