// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UpdateDialog } from './UpdateDialog'
import { useDialogs, useSession } from '../../stores'
import { emitC } from '../../services/socket'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../../services/restart', async importOriginal => ({
  ...await importOriginal<typeof import('../../services/restart')>(), reloadWhenServerReady: vi.fn(),
}))
const viewport = vi.hoisted(() => ({ desktop: true }))
vi.mock('../layout/useEmberViewport', () => ({ useEmberViewport: () => viewport.desktop }))
const dialogsInitial = useDialogs.getState()
const sessionInitial = useSession.getState()
beforeEach(() => {
  vi.clearAllMocks()
  useDialogs.setState(dialogsInitial, true)
  useSession.setState({ ...sessionInitial, connected: true }, true)
  sessionStorage.clear()
  viewport.desktop = true
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear() })
function openAndProceed() {
  useDialogs.getState().openDialog('update')
  render(<UpdateDialog />)
  fireEvent.click(screen.getByRole('button', { name: 'Proceed with Update' }))
}
function holdPreparation() {
  let resolve!: (response: Response) => void
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => new Promise(r => { resolve = r }))
  return { fetchMock, finish: () => resolve(new Response(JSON.stringify({ server_instance_id: 'old-process' }))) }
}

describe('update preparation ownership', () => {
  it.each([true, false])('prevents duplicate preparation and sends the original event once (desktop=%s)', async desktop => {
    viewport.desktop = desktop
    const preparation = holdPreparation()
    openAndProceed()
    const proceed = screen.getByRole('button', { name: 'Proceed with Update' }) as HTMLButtonElement
    expect(proceed.disabled).toBe(true)
    fireEvent.click(proceed)
    expect(preparation.fetchMock).toHaveBeenCalledTimes(1)
    expect(emitC).not.toHaveBeenCalled()
    await act(async () => preparation.finish())
    await waitFor(() => expect(emitC).toHaveBeenCalledTimes(1))
    expect(emitC).toHaveBeenCalledWith('trigger_update', undefined)
    expect(useDialogs.getState().update.running).toBe(true)
    fireEvent.click(proceed)
    expect(emitC).toHaveBeenCalledTimes(1)
  })

  it.each(['Cancel', 'Escape', 'backdrop', 'Close', 'unmount', 'disconnect'])('does not trigger or replace a newer marker after %s', async transition => {
    const preparation = holdPreparation()
    openAndProceed()
    if (['Cancel', 'Close'].includes(transition)) fireEvent.click(screen.getByRole('button', { name: transition }))
    if (transition === 'Escape') fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    if (transition === 'backdrop') fireEvent.mouseDown(screen.getByRole('dialog'))
    if (transition === 'unmount') cleanup()
    if (transition === 'disconnect') act(() => useSession.getState().setConnected(false))
    sessionStorage.setItem('neq_restart_server_instance', 'newer-operation')
    await act(async () => preparation.finish())
    expect(emitC).not.toHaveBeenCalled()
    expect(useDialogs.getState().update.running).toBe(false)
    expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('newer-operation')
  })

  it('requires an explicit retry after reconnect and rejects the old preparation', async () => {
    const preparation = holdPreparation()
    openAndProceed()
    act(() => useSession.getState().setConnected(false))
    expect((screen.getByRole('button', { name: 'Proceed with Update' }) as HTMLButtonElement).disabled).toBe(true)
    act(() => useSession.getState().setConnected(true))
    await act(async () => preparation.finish())
    expect(emitC).not.toHaveBeenCalled()
    preparation.fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ server_instance_id: 'current-process' })))
    fireEvent.click(screen.getByRole('button', { name: 'Proceed with Update' }))
    await waitFor(() => expect(emitC).toHaveBeenCalledTimes(1))
    expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('current-process')
  })
})
