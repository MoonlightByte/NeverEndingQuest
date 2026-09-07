// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { NpcInventoryPanel } from './NpcInventoryPanel'
import { SpellcastingSummary } from './SpellcastingSummary'
import { spellcastingView } from './characterData'

vi.mock('./useSpellReference', () => ({useSpellReference: () => ({ data: {}, status: 'ready', retry: vi.fn() })}))
beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('shows compact real inventory metadata, filters entries, and opens the complete item description', () => {
  const npc = {equipment:[
    {item_name:'Longbow',item_type:'Weapon',quantity:1,equipped:true,description:'A carefully carved yew bow.'},
    {item_name:'Moonlit Compass',item_type:'Wondrous Item',quantity:2,charges:{current:0,max:3},description:'A compass that remembers the road home.'},
  ]}
  const {rerender} = render(<NpcInventoryPanel npc={npc} />)
  const table = screen.getByRole('table', {name:'Inventory items'})
  expect(within(table).getAllByRole('row')).toHaveLength(3)
  expect(table.textContent).toContain('Equipped')
  expect(table.textContent).toContain('×2')
  expect(table.textContent).toContain('0/3')
  fireEvent.change(screen.getByRole('textbox', {name:'Search NPC inventory'}), {target:{value:'compass'}})
  expect(within(table).queryByRole('button', {name:'Longbow'})).toBeNull()
  fireEvent.click(within(table).getByRole('button', {name:'Moonlit Compass'}))
  expect(screen.getByRole('dialog', {name:'Moonlit Compass details'}).textContent).toContain('A compass that remembers the road home.')
  fireEvent.click(screen.getByRole('button', {name:'Close Moonlit Compass details'}))
  rerender(<NpcInventoryPanel npc={{equipment:[npc.equipment[0]]}} />)
  expect(screen.getByRole('status').textContent).toContain('No items match')
})

it('shows available and spent slots, including upcasting levels with no listed spells', () => {
  const data = {spellcasting:{ability:'wisdom',spellSaveDC:13,spellAttackBonus:5,spells:{cantrips:['Light'],level1:['Goodberry']},preparedSpells:['Goodberry'],spellSlots:{level1:{current:2,max:3},level2:{current:0,max:2}}}}
  const {rerender} = render(<SpellcastingSummary data={data} casting={spellcastingView(data)!} />)
  const first = screen.getByRole('group', {name:'Level 1 spell slots: 2 of 3 available'})
  expect(first.querySelectorAll('.is-available')).toHaveLength(2)
  expect(first.querySelectorAll('.is-spent')).toHaveLength(1)
  expect(screen.getByRole('group', {name:'Level 2 spell slots: 0 of 2 available'}).querySelectorAll('.is-spent')).toHaveLength(2)
  expect(screen.getByRole('region', {name:'Spellcasting resources'}).textContent).toContain('2 listed spells · 1 prepared')
  const updated = {spellcasting:{...data.spellcasting,spellSlots:{level1:{current:1,max:3}}}}
  rerender(<SpellcastingSummary data={updated} casting={spellcastingView(updated)!} />)
  expect(screen.getByRole('group', {name:'Level 1 spell slots: 1 of 3 available'}).querySelectorAll('.is-available')).toHaveLength(1)
})

it('does not invent slot totals and caps decorative pips for large pools', () => {
  const data = {spellcasting:{spells:{level1:['Goodberry']}}}
  const {rerender} = render(<SpellcastingSummary data={data} casting={spellcastingView(data)!} />)
  expect(screen.getByText('No spell-slot totals recorded.')).toBeTruthy()
  const large = {spellcasting:{...data.spellcasting,spellSlots:{level1:{current:15,max:20}}}}
  rerender(<SpellcastingSummary data={large} casting={spellcastingView(large)!} />)
  const pool = screen.getByRole('group', {name:'Level 1 spell slots: 15 of 20 available'})
  expect(pool.querySelectorAll('i')).toHaveLength(0)
})
