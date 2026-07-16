/**
 * Store reducer tests (plan Task 4.2 Step 1). Tests the store setters the
 * socket service dispatches into -- no socket connection involved.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { useLog } from './log'
import { useSession } from './session'

const initialLog = useLog.getState()
const initialSession = useSession.getState()

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
})

describe('log store', () => {
  it('game_output appends to the log', () => {
    useLog.getState().append({ type: 'narration', content: 'A cold wind rises.' })
    useLog.getState().append({ type: 'user-input', content: 'I draw my sword.' })
    expect(useLog.getState().messages).toEqual([
      { type: 'narration', content: 'A cold wind rises.' },
      { type: 'user-input', content: 'I draw my sword.' },
    ])
  })

  it('cached_messages replaces the log', () => {
    useLog.getState().append({ type: 'narration', content: 'stale entry' })
    useLog.getState().replaceAll([
      { type: 'narration', content: 'restored one' },
      { type: 'info', content: 'restored two' },
    ])
    expect(useLog.getState().messages).toHaveLength(2)
    expect(useLog.getState().messages[0]!.content).toBe('restored one')
  })
})

describe('session store', () => {
  it('status_update with is_processing true locks input', () => {
    useSession.getState().setStatus({ message: 'The DM is thinking...', is_processing: true })
    expect(useSession.getState().isProcessing).toBe(true)
    expect(useSession.getState().statusMessage).toBe('The DM is thinking...')
  })

  it('disconnect sets mode to disconnected', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('welcome')
    expect(useSession.getState().mode).toBe('play')
    useSession.getState().setConnected(false)
    expect(useSession.getState().mode).toBe('disconnected')
    expect(useSession.getState().connected).toBe(false)
  })

  it('initiative active toggles combat mode and back to play', () => {
    useSession.getState().gameStarted('welcome')
    useSession.getState().setCombatActive(true)
    expect(useSession.getState().mode).toBe('combat')
    useSession.getState().setCombatActive(false)
    expect(useSession.getState().mode).toBe('play')
  })
})
