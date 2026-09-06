// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useWorld } from '../../stores'
import { PartyStrip } from './PartyStrip'
import { InitiativeTracker } from './InitiativeTracker'
vi.mock('./CharacterChip', () => ({CharacterChip: ({name,onOpenMedia}: {name:string;onOpenMedia:(media:unknown)=>void}) => <button onClick={() => onOpenMedia({kind:'image',src:'/portrait.jpg'})}>{name}</button>}))
const original = useWorld.getState()
afterEach(() => { cleanup(); useWorld.setState(original,true) })
it('does not reopen exploration media after entering and leaving combat', () => {
  useWorld.setState({party:[{name:'Elen',type:'npc'}]})
  render(<PartyStrip />)
  fireEvent.click(screen.getByRole('button',{name:'Elen'}))
  expect(screen.getByRole('dialog')).toBeTruthy()
  act(() => useWorld.setState({initiative:{...original.initiative,active:true}}))
  expect(screen.queryByRole('dialog')).toBeNull()
  act(() => useWorld.setState({initiative:original.initiative}))
  expect(screen.queryByRole('dialog')).toBeNull()
})
it('dismisses removed combatant media while preserving initiative identity', () => {
  useWorld.setState({initiative:{...original.initiative,active:true,combatants:[{name:'Goblin',type:'enemy'}]}})
  render(<InitiativeTracker />)
  fireEvent.click(screen.getByRole('button',{name:'Goblin'}))
  expect(screen.getByRole('dialog')).toBeTruthy()
  act(() => useWorld.setState({initiative:{...original.initiative,active:true,combatants:[{name:'Orc',type:'enemy'}]}}))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByRole('button',{name:'Orc'})).toBeTruthy()
})
