// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ResetDialog } from './ResetDialog'
import { useDialogs, useLog, useSession } from '../../stores'
import { emitC } from '../../services/socket'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../../services/restart', async importOriginal => ({
  ...await importOriginal<typeof import('../../services/restart')>(),
  reloadWhenServerReady: vi.fn(),
}))
const viewport = vi.hoisted(() => ({ desktop: true }))
vi.mock('../layout/useEmberViewport', () => ({ useEmberViewport: () => viewport.desktop }))
const dialogsInitial = useDialogs.getState()
const sessionInitial = useSession.getState()
const logInitial = useLog.getState()
beforeEach(() => {
  vi.clearAllMocks()
  useDialogs.setState(dialogsInitial, true)
  useSession.setState({ ...sessionInitial, connected: true }, true)
  useLog.setState(logInitial, true)
  sessionStorage.clear()
  viewport.desktop = true
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear() })
function openAndConfirm() {
  useDialogs.getState().openDialog('reset')
  render(<ResetDialog />)
  fireEvent.change(screen.getByLabelText('Reset confirmation code'), { target: { value: screen.getByTestId('reset-code').textContent } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }))
}
function holdPreparation() {
  let resolve!: (response: Response) => void
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => new Promise(r => { resolve = r }))
  return { fetchMock, finish: () => resolve(new Response(JSON.stringify({ server_instance_id: 'old-process' }))) }
}

describe('reset preparation ownership', () => {
  it.each([true, false])('rejects every dismissal while pending (desktop=%s), then sends the exact single reset', async desktop => {
    viewport.desktop = desktop
    const preparation = holdPreparation()
    openAndConfirm()
    const dialog = screen.getByRole('dialog')
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    fireEvent.mouseDown(dialog)
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }))
    expect(useDialogs.getState().open).toBe('reset')
    expect(emitC).not.toHaveBeenCalled()
    expect(preparation.fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status').textContent).toContain('Preparing')
    await act(async () => preparation.finish())
    await waitFor(() => expect(emitC).toHaveBeenCalledTimes(1))
    expect(emitC).toHaveBeenCalledWith('action', { action: 'nuclearReset', parameters: {} })
  })

  it.each(['unmount', 'disconnect', 'replacement dialog'])('never emits or overwrites another marker after %s', async transition => {
    const preparation = holdPreparation()
    openAndConfirm()
    if (transition === 'unmount') cleanup()
    if (transition === 'disconnect') act(() => useSession.getState().setConnected(false))
    if (transition === 'replacement dialog') act(() => useDialogs.getState().openDialog('load'))
    sessionStorage.setItem('neq_restart_server_instance', 'newer-operation')
    await act(async () => preparation.finish())
    expect(emitC).not.toHaveBeenCalled()
    expect(useDialogs.getState().actionResult).toBeNull()
    expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('newer-operation')
    expect(useLog.getState().messages.some(message => message.content.includes('Campaign reset initiated'))).toBe(false)
  })

  it('requires fresh confirmation after reconnect and ignores old preparation', async () => {
    const preparation = holdPreparation()
    openAndConfirm()
    act(() => useSession.getState().setConnected(false))
    act(() => useSession.getState().setConnected(true))
    expect((screen.getByLabelText('Reset confirmation code') as HTMLInputElement).value).toBe('')
    expect((screen.getByRole('button', { name: 'Confirm Reset' }) as HTMLButtonElement).disabled).toBe(true)
    await act(async () => preparation.finish())
    expect(emitC).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('neq_restart_server_instance')).toBeNull()
    preparation.fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ server_instance_id: 'current-process' })))
    fireEvent.change(screen.getByLabelText('Reset confirmation code'), { target: { value: screen.getByTestId('reset-code').textContent } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }))
    await waitFor(() => expect(emitC).toHaveBeenCalledTimes(1))
    expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('current-process')
  })

  it('shows preparation failure without emitting, then permits a safe retry', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ server_instance_id: 'process' })))
    vi.spyOn(Storage.prototype, 'setItem').mockImplementationOnce(() => { throw new Error('storage unavailable') })
    openAndConfirm()
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('storage unavailable'))
    expect(emitC).not.toHaveBeenCalled()
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Reset' }))
    await waitFor(() => expect(emitC).toHaveBeenCalledTimes(1))
  })
})
