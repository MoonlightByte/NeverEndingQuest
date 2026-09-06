// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { PartyVitals } from './PartyVitals'
import { matchingNpc, partySummary } from './partyData'
afterEach(cleanup)

it('shows live zero HP, AC and supplied XP without replacing them with sheet defaults', () => {
  const stats = partySummary({ currentHp: 0, maxHp: 14, ac: 13 }, { hitPoints: 14, maxHitPoints: 14, experience_points: 0, exp_required_for_next_level: 300, level: 1 })
  const { container } = render(<PartyVitals stats={stats} />)
  expect(container.textContent).toContain('HP 0 / 14')
  expect(container.textContent).toContain('AC 13')
  expect(container.textContent).toContain('XP 0 / 300')
  expect(container.querySelector('[data-low="true"]')).not.toBeNull()
})

it('never invents HP, XP, AC or level for an unknown townsfolk record', () => {
  const { container } = render(<PartyVitals stats={{ name: 'Innkeeper' }} />)
  expect(container.textContent).toBe('')
})

it('shows supplied conditions and only matches an unambiguous NPC identity', () => {
  render(<PartyVitals stats={{ conditions: ['Poisoned'], status: 'unconscious' }} />)
  expect(screen.getByText('Poisoned')).toBeTruthy()
  const npcs = [{ name: 'Ranger Elen' }, { name: 'Ranger Marcus' }]
  expect(matchingNpc(npcs, 'ranger_elen')).toBe(npcs[0])
  expect(matchingNpc(npcs, 'Ranger')).toBeUndefined()
  expect(matchingNpc([...npcs, { name: 'Ranger Elen' }], 'Ranger Elen')).toBeUndefined()
})
