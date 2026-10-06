// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useSession, useDialogs } from '../../stores'
import { useRulesRoll } from '../../stores/rulesRoll'
import { emitC } from '../../services/socket'
import { InputBar } from './InputBar'
import { DiceStrip } from './DiceStrip'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
const initialSession = useSession.getState()
beforeEach(() => {
  vi.clearAllMocks()
  useSession.setState({ ...initialSession, connected: true, mode: 'play', startupStatus: 'ready', inputAuthorized: true })
  useDialogs.setState({ actionResult: null })
  useRulesRoll.getState().setPrompt({ id: 'check', characterName: 'Hero', label: 'Strength check', faces: 2, netMode: 'advantage', reason: 'Lift the gate', submitted: false })
})
afterEach(() => { cleanup(); useRulesRoll.getState().setPrompt(null) })
it('replaces normal input with a server-owned check', () => {
  render(<InputBar />)
  expect(screen.queryByLabelText('Player input')).toBeNull()
  fireEvent.click(screen.getByText('Roll for me'))
  expect(emitC).toHaveBeenCalledWith('submit_check_roll', { id: 'check', faces: null })
})
it('sends individual advantage faces without adding a bonus or summing them', () => {
  render(<InputBar />)
  fireEvent.change(screen.getByLabelText('Die 1'), { target: { value: '2' } })
  fireEvent.change(screen.getByLabelText('Die 2'), { target: { value: '18' } })
  fireEvent.click(screen.getByText('Use rolls'))
  expect(emitC).toHaveBeenCalledWith('submit_check_roll', { id: 'check', faces: [2, 18] })
})
it('blocks input after submission and while disconnected', () => {
  useRulesRoll.getState().setPrompt({ ...useRulesRoll.getState().prompt!, submitted: true })
  render(<InputBar />)
  expect((screen.getByText('Resolving…') as HTMLButtonElement).disabled).toBe(true)
})

it('submits quick dice to the current check and never carries them into a new check', () => {
  render(<><DiceStrip /><InputBar /></>)
  fireEvent.click(screen.getByTitle('Roll D20'))
  expect((screen.getByText(/Submit rolled dice/) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByTitle('Roll D20'))
  const faces = [...useRulesRoll.getState().quickFaces]
  fireEvent.click(screen.getByText(/Submit rolled dice/))
  expect(emitC).toHaveBeenCalledWith('submit_check_roll', { id: 'check', faces })
  expect(faces).toHaveLength(2)
  useRulesRoll.getState().setPrompt({ ...useRulesRoll.getState().prompt!, id: 'next' })
  expect(useRulesRoll.getState().quickFaces).toEqual([])
})
it('ignores local dice with no pending check and preserves dice on reconnect', () => {
  const store = useRulesRoll.getState()
  store.setPrompt(null)
  store.addQuickFace(20)
  expect(useRulesRoll.getState().quickFaces).toEqual([])
  store.setPrompt({ id: 'one', characterName: 'Hero', label: 'Perception', faces: 1, netMode: 'normal', reason: 'Inspect', submitted: false })
  store.addQuickFace(15)
  store.setPrompt({ ...useRulesRoll.getState().prompt! })
  expect(useRulesRoll.getState().quickFaces).toEqual([15])
  store.clearQuickFaces()
  expect(useRulesRoll.getState().quickFaces).toEqual([])
})
