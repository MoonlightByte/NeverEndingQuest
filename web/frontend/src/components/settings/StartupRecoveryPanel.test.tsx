// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { StartupRecoveryPanel } from './StartupRecoveryPanel'
import { useSession } from '../../stores'
import { emitC } from '../../services/socket'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
const initial = useSession.getState()
beforeEach(() => { useSession.setState({ ...initial, connected: true, startupStatus: 'failed', startupAttemptId: 'attempt-1' }, true); vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.useRealTimers() })
it('uses exact existing token/attempt contract and clears the secret immediately', () => {
  render(<StartupRecoveryPanel />)
  fireEvent.change(screen.getByLabelText('Recovery token'), { target: { value: 'synthetic-token' } })
  fireEvent.click(screen.getByRole('button', { name: 'Recover startup' }))
  expect(emitC).toHaveBeenCalledWith('action', { action: 'recover_startup_handoff', parameters: { recoveryToken: 'synthetic-token', startupAttemptId: 'attempt-1' } })
  expect((screen.getByLabelText('Recovery token') as HTMLInputElement).value).toBe('')
  expect((screen.getByRole('button', { name: 'Recovering…' }) as HTMLButtonElement).disabled).toBe(true)
})
it('does not emit disconnected or incomplete requests and respects server cooldown', () => {
  vi.useFakeTimers()
  render(<StartupRecoveryPanel />)
  fireEvent.change(screen.getByLabelText('Recovery token'), { target: { value: 'synthetic-token' } })
  act(() => useSession.setState({ connected: false }))
  fireEvent.click(screen.getByRole('button', { name: 'Recover startup' }))
  expect(emitC).not.toHaveBeenCalled()
  act(() => useSession.setState({ connected: true, recovery: { status: 'failed', error: 'cooldown_active', retryAfterSeconds: 2 } }))
  expect((screen.getByRole('button', { name: 'Retry in 2s' }) as HTMLButtonElement).disabled).toBe(true)
  act(() => vi.advanceTimersByTime(1000))
  expect(screen.getByRole('button', { name: 'Retry in 1s' })).toBeTruthy()
})
