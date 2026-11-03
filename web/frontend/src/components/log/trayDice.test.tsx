// @vitest-environment jsdom
/**
 * #1750: the dice tray's typed faces ride beside its unchanged sentence.
 * services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useSession } from '../../stores'
import { emitC } from '../../services/socket'
import { InputBar } from './InputBar'
import { formatFreeRolls, freeRollDice } from './DiceStrip'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

const initialSession = useSession.getState()
const sides = [4, 6, 8, 10, 12, 20]

beforeEach(() => {
  useSession.setState(initialSession, true)
  useSession.getState().setConnected(true)
  useSession.getState().gameStarted('ready')
  vi.clearAllMocks()
})

afterEach(() => cleanup())

describe('freeRollDice', () => {
  it('gives the sentence faces in the sentence order, d20s first', () => {
    for (const a of sides) for (const b of sides) {
      const rolls = [{ sides: a, result: a }, { sides: b, result: 1 }]
      const d20 = rolls.filter((r) => r.sides === 20).map((r) => r.result)
      const damage = rolls.filter((r) => r.sides !== 20)
      const dice = freeRollDice(d20, damage)
      const named = dice.map((d) => `a ${d.face} on a d${d.sides}`)
      const sentence = formatFreeRolls(d20, damage)
      let at = 0
      for (const part of named) {
        const found = sentence.indexOf(part, at)
        expect(found).toBeGreaterThanOrEqual(at)
        at = found + part.length
      }
      expect(dice).toHaveLength(2)
    }
    expect(freeRollDice([], [])).toEqual([])
  })
})

describe('InputBar with a tray insertion', () => {
  const dice = [{ sides: 20, face: 14 }, { sides: 8, face: 5 }]
  const text = formatFreeRolls([14], [{ sides: 8, result: 5 }])

  it('sends the typed dice beside an unchanged sentence that filled an empty draft', () => {
    render(<InputBar rollInsertion={{ id: 1, text, dice }} />)
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).toHaveBeenCalledWith('user_input', { input: text, dice })
  })

  it('sends the line only once the sentence is edited', () => {
    render(<InputBar rollInsertion={{ id: 1, text, dice }} />)
    const input = screen.getByPlaceholderText('Enter your command...') as HTMLInputElement
    fireEvent.change(input, { target: { value: `${text} Take that!` } })
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).toHaveBeenCalledWith('user_input', { input: `${text} Take that!` })
  })

  it('sends the line only when the sentence joined words already typed', () => {
    const { rerender } = render(<InputBar />)
    const input = screen.getByPlaceholderText('Enter your command...') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'I swing' } })
    rerender(<InputBar rollInsertion={{ id: 2, text, dice }} />)
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).toHaveBeenCalledWith('user_input', { input: `I swing ${text}` })
  })

  it('sends the dice once: the next line goes alone', () => {
    render(<InputBar rollInsertion={{ id: 3, text, dice }} />)
    fireEvent.click(screen.getByText('Send'))
    const input = screen.getByPlaceholderText('Enter your command...') as HTMLInputElement
    fireEvent.change(input, { target: { value: text } })
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).toHaveBeenLastCalledWith('user_input', { input: text })
  })
})
