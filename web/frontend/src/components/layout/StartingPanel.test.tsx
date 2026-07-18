// @vitest-environment jsdom
import { StrictMode } from 'react'
import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useLog, useSession } from '../../stores'
import { StartingPanel } from './StartingPanel'

const initialLog = useLog.getState()
const initialSession = useSession.getState()

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
})

afterEach(cleanup)

describe('StartingPanel legacy effects', () => {
  it('renders no React-only startup surface', () => {
    const { container } = render(<StartingPanel />)
    expect(container.firstChild).toBeNull()
  })

  it('reports a handoff failure once in the game log under StrictMode', () => {
    render(<StrictMode><StartingPanel /></StrictMode>)

    act(() => useSession.getState().setStartup('failed', 'opening_scene', 'attempt-1'))

    expect(useLog.getState().messages).toEqual([{
      type: 'error',
      content: 'Startup handoff failed. You can use recovery from settings.',
      message_id: 'startup-failure-attempt-1',
    }])
  })

  it('reports a recovery response using the exact legacy wording', () => {
    render(<StartingPanel />)

    act(() => useSession.getState().setRecovery({
      status: 'failed',
      error: 'Opening scene handoff timed out',
      retryAfterSeconds: 3,
    }))

    expect(useLog.getState().messages.at(-1)?.content).toBe(
      'Startup recovery failed (Opening scene handoff timed out). Retry in 3s.',
    )
  })
})

describe('startup recovery legacy messages', () => {
  it.each([
    ['recovered', 'system', 'Startup recovery completed. Adventure flow resumed.'],
    ['already_ready', 'system', 'Startup is already complete.'],
    ['in_progress', 'system', 'Startup recovery is already in progress.'],
    ['not_recoverable', 'error', 'Startup recovery not allowed in current state.'],
  ] as const)('maps %s exactly like legacy', (status, type, content) => {
    render(<StartingPanel />)

    act(() => useSession.getState().setRecovery({ status }))

    expect(useLog.getState().messages.at(-1)).toMatchObject({ type, content })
  })
})
