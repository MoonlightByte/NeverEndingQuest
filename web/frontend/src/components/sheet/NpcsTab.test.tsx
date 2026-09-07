// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NpcsTab } from './NpcsTab'
import { usePlayer } from '../../stores'
import { EmberPresentation } from '../layout/EmberPresentation'
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

it('the roster card keeps its identity fixed while inventory updates inside the sheet', () => {
  const elen = { name: 'Ranger Elen', equipment: [{ name: 'Arrow', quantity: 2, type: 'ammunition' }] }
  usePlayer.setState({ npcs: [elen, { name: 'Rusk', equipment: [{ name: 'Secret item' }] }] })
  const { container } = render(<EmberPresentation value={true}><NpcsTab npcName="ranger_elen" /></EmberPresentation>)
  expect(container.textContent).toContain('Ranger Elen')
  expect(container.textContent).not.toContain('Rusk')
  const heading = screen.getByRole('heading', { name: 'Ranger Elen' })
  const portrait = container.querySelector('.tcs-portrait')
  fireEvent.click(screen.getByRole('tab', { name: 'Inventory' }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByRole('tabpanel').textContent).toContain('×2')
  act(() => usePlayer.setState({ npcs: [{ ...elen, equipment: [{ name: 'Arrow', quantity: 9 }] }] }))
  expect(screen.getByRole('tabpanel').textContent).toContain('×9')
  fireEvent.click(screen.getByRole('tab', { name: 'Spells & magic' }))
  expect(screen.getByRole('tabpanel').textContent).toContain('does not have spellcasting')
  expect(screen.getByRole('heading', { name: 'Ranger Elen' })).toBe(heading)
  expect(container.querySelector('.tcs-portrait')).toBe(portrait)
  expect(screen.getByRole('tabpanel').contains(heading)).toBe(false)
  fireEvent.click(screen.getByRole('tab', { name: 'Character sheet' }))
  expect(screen.getByRole('heading', { name: 'Ranger Elen' })).toBe(heading)
  act(() => usePlayer.setState({ npcs: [] }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(container.textContent).toContain('Full character details are not available')
})

it('keeps full desktop sheet data and all conditional menus available in their groups', () => {
  usePlayer.setState({npcs:[{name:'Elen', abilities:{strength:16}, hitPoints:12,maxHitPoints:20,armorClass:15,initiative:2, experience_points:120,exp_required_for_next_level:300, personality_traits:'Patient scout', savingThrows:['Strength'],skills:{Athletics:2},equipment:[{name:'Bow'}],classFeatures:[{name:'Focus'}],racialTraits:[{name:'Vision'}],backgroundFeature:{name:'Scout'},spellcasting:{ability:'Wisdom'}}]})
  const { container } = render(<EmberPresentation value={true}><NpcsTab npcName="Elen" /></EmberPresentation>)
  expect(screen.getByLabelText('strength modifier').textContent).toBe('+3')
  expect(screen.getByLabelText('strength score').textContent).toBe('16')
  expect(container.textContent).toContain('120 / 300')
  expect(container.textContent).toContain('Patient scout')
  for (const name of ['Saving Throw','Skills','Key Abilities','Racial Traits','Background']) expect(screen.getByRole('button',{name})).toBeTruthy()
  for (const name of ['Character sheet','Inventory','Spells & magic']) expect(screen.getByRole('tab',{name})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Key Abilities'}))
  expect(screen.getByRole('dialog').textContent).toContain('Focus')
})

it('keeps NPC tabs keyboard accessible and handles empty inventory without a new dialog', () => {
  usePlayer.setState({npcs:[{name:'Elen', equipment:[]}]})
  render(<EmberPresentation value={true}><NpcsTab npcName="Elen" /></EmberPresentation>)
  fireEvent.keyDown(screen.getByRole('tab', {name:'Character sheet'}), {key:'ArrowRight'})
  expect(screen.getByRole('tab', {name:'Inventory'}).getAttribute('aria-selected')).toBe('true')
  expect(screen.getByRole('tabpanel').textContent).toContain('No items in inventory')
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.keyDown(screen.getByRole('tab', {name:'Inventory'}), {key:'End'})
  expect(screen.getByRole('tab', {name:'Spells & magic'}).getAttribute('aria-selected')).toBe('true')
})
