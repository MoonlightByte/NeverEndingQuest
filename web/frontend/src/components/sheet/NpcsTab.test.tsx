// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NpcsTab } from './NpcsTab'
import { usePlayer } from '../../stores'
vi.mock('./useSpellReference', () => ({useSpellReference: () => ({ data: {}, status: 'ready', retry: vi.fn() })}))
const original = usePlayer.getState()
afterEach(() => { cleanup(); usePlayer.setState(original, true) })
it('reconciles an open inventory with the selected identity across refresh and removal', () => {
  const npc = {name:'Elen', equipment:[{name:'Arrow', quantity:2, type:'ammunition'}]}
  usePlayer.setState({ npcs:[npc] })
  render(<NpcsTab />)
  fireEvent.click(screen.getByRole('button', {name:'Inventory'}))
  expect(screen.getByRole('dialog').textContent).toContain('x2')
  act(() => usePlayer.setState({npcs:[{name:'Other'}, {...npc, equipment:[{name:'Arrow', quantity:8, type:'ammunition'}]}]}))
  expect(screen.getByRole('dialog').textContent).toContain('x8')
  expect(screen.getByRole('dialog').textContent).toContain("Elen's Inventory")
  act(() => usePlayer.setState({npcs:[{name:'Other'}]}))
  expect(screen.queryByRole('dialog')).toBeNull()
})
it('preserves all seven conditional detail actions and full feature description', () => {
  usePlayer.setState({npcs:[{name:'Elen', savingThrows:['Strength'], skills:{Athletics:2}, equipment:[{name:'Bow'}], classFeatures:[{name:'Focus',description:'Full feature description',usage:'2/3',refresh:'long rest'}], racialTraits:[{name:'Vision'}], backgroundFeature:{name:'Scout'}, spellcasting:{ability:'Wisdom'}}]})
  render(<NpcsTab />)
  for (const name of ['Saving Throw','Skills','Inventory','Key Abilities','Racial Traits','Background','Spells']) expect(screen.getByRole('button',{name})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Key Abilities'}))
  expect(screen.getByRole('dialog').textContent).toContain('Full feature description')
  expect(screen.getByRole('dialog').textContent).toContain('2/3 · long rest')
})

it('the roster card reuses only the selected full NPC and keeps nested menus live', () => {
  const elen = { name: 'Ranger Elen', equipment: [{ name: 'Arrow', quantity: 2, type: 'ammunition' }] }
  usePlayer.setState({ npcs: [elen, { name: 'Rusk', equipment: [{ name: 'Secret item' }] }] })
  const { container } = render(<NpcsTab npcName="ranger_elen" />)
  expect(container.textContent).toContain('Ranger Elen')
  expect(container.textContent).not.toContain('Rusk')
  fireEvent.click(screen.getByRole('button', { name: 'Inventory' }))
  expect(screen.getByRole('dialog').textContent).toContain('x2')
  act(() => usePlayer.setState({ npcs: [{ ...elen, equipment: [{ name: 'Arrow', quantity: 9 }] }] }))
  expect(screen.getByRole('dialog').textContent).toContain('x9')
  act(() => usePlayer.setState({ npcs: [] }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(container.textContent).toContain('Full character details are not available')
})
