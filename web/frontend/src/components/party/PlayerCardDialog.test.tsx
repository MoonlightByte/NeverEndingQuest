// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { PartyStrip } from './PartyStrip'
import { InitiativeTracker } from './InitiativeTracker'
import { PlayerCardDialog } from './PlayerCardDialog'
import { usePlayer, useWorld } from '../../stores'
import { emitC } from '../../services/socket'
import { resolveClickMedia } from './media'

vi.mock('../layout/EmberPresentation', () => ({ useEmberDesktop: () => true }))
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../sheet/useSpellReference', () => ({ useSpellReference: () => ({ data: {}, status: 'ready', retry: vi.fn() }) }))
vi.mock('./media', async (importOriginal) => ({ ...await importOriginal<typeof import('./media')>(), resolveFirstImage: vi.fn().mockResolvedValue(null), resolveClickMedia: vi.fn().mockResolvedValue(null) }))
const initialPlayer = usePlayer.getState(), initialWorld = useWorld.getState()
const stats = {name:'Jack',level:3,class:'Barbarian',race:'Half-Orc',abilities:{strength:17},hitPoints:24,maxHitPoints:30,armorClass:14,experience_points:450,exp_required_for_next_level:900,savingThrows:['Strength'],attacksAndSpellcasting:[{name:'Maul',damage:'2d6+3'}],classFeatures:[{name:'Rage',description:'Battle fury',usage:{current:2,max:3}}],temporaryEffects:[{name:'Bless',description:'Blessed by an ally'}],feats:[{name:'Tough',description:'Extra endurance'}]}
beforeEach(() => { usePlayer.setState({...initialPlayer,stats},true); useWorld.setState({...initialWorld,party:[{name:'Jack',type:'player',hitPoints:1}]},true); vi.clearAllMocks() })
afterEach(() => { cleanup(); usePlayer.setState(initialPlayer,true); useWorld.setState(initialWorld,true) })

it('opens the full player sheet from the exploration card using authoritative stats', () => {
  render(<PartyStrip />)
  const opener = screen.getByRole('button',{name:'Jack full character details'})
  opener.focus(); fireEvent.click(opener)
  const dialog = screen.getByRole('dialog',{name:'Jack — Your character'})
  expect(dialog.textContent).toContain('24/30')
  for (const value of ['Weapons & Attacks','Maul','Class Features','Rage','2/3','Active Effects','Bless','Feats','Tough','450 / 900']) expect(dialog.textContent).toContain(value)
  expect(emitC).toHaveBeenCalledWith('request_player_data',{dataType:'stats'})
  expect(resolveClickMedia).not.toHaveBeenCalled()
  act(() => usePlayer.setState({stats:{...stats,hitPoints:18}}))
  expect(dialog.textContent).toContain('18/30')
  fireEvent.keyDown(document.activeElement!,{key:'Escape'})
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(opener)
})

it('opens the same full sheet from the initiative player card', () => {
  useWorld.setState({initiative:{...initialWorld.initiative,active:true,combatants:[{name:'Jack',type:'player'}]}})
  render(<InitiativeTracker />)
  fireEvent.click(screen.getByRole('button',{name:'Jack full character details'}))
  expect(screen.getByRole('dialog').textContent).toContain('Weapons & Attacks')
  act(() => useWorld.setState({initiative:{...initialWorld.initiative,active:false}}))
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('keeps portrait clicks separate from the full player sheet', () => {
  render(<PartyStrip />)
  fireEvent.click(screen.getByRole('button',{name:'Jack portrait'}))
  expect(resolveClickMedia).toHaveBeenCalledOnce()
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('uses the existing inventory and spells requests and surfaces their errors', () => {
  render(<PlayerCardDialog name="Jack" onClose={vi.fn()} />)
  const dialog = within(screen.getByRole('dialog'))
  fireEvent.click(dialog.getByRole('tab',{name:'Inventory'}))
  expect(emitC).toHaveBeenCalledWith('request_player_data',{dataType:'inventory'})
  expect(dialog.getByRole('status').textContent).toContain('Loading inventory')
  act(() => usePlayer.setState({inventory:{equipment:[{item_name:'Healing potion',item_type:'Potion',quantity:2}]}}))
  expect(dialog.getByRole('button',{name:'Healing potion'})).toBeTruthy()
  fireEvent.click(dialog.getByRole('tab',{name:'Spells & magic'}))
  expect(emitC).toHaveBeenCalledWith('request_player_data',{dataType:'spells'})
  act(() => usePlayer.setState({dataErrors:{spells:'Spell data unavailable'}}))
  expect(dialog.getByRole('alert').textContent).toBe('Spell data unavailable')
})

it('does not show another active player record in the selected character popup', () => {
  render(<PlayerCardDialog name="Jack" onClose={vi.fn()} />)
  act(() => usePlayer.setState({stats:{...stats,name:'Other hero'}}))
  expect(screen.getByRole('status').textContent).toContain('no longer the active player')
  expect(screen.queryByText('Maul')).toBeNull()
})

it('retains the same identity and portrait while tabs replace only the lower panel', () => {
  render(<PlayerCardDialog name="Jack" onClose={vi.fn()} />)
  const identity = screen.getByRole('heading', { name: 'Jack' })
  const portrait = screen.getByRole('img', { name: 'Portrait of Jack' })
  for (const tab of ['Inventory', 'Spells & magic', 'Character sheet']) {
    fireEvent.click(screen.getByRole('tab', { name: tab }))
    expect(screen.getByRole('heading', { name: 'Jack' })).toBe(identity)
    expect(screen.getByRole('img', { name: 'Portrait of Jack' })).toBe(portrait)
    expect(screen.getAllByRole('progressbar', { name: 'Experience' })).toHaveLength(1)
    expect(screen.getByRole('tabpanel').contains(identity)).toBe(false)
  }
})
