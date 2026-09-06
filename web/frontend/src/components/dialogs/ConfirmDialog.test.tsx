// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDialogs, useSession } from '../../stores'
import { LoadDialog } from './LoadDialog'
import { HeaderBar } from '../layout/HeaderBar'
import { emitC } from '../../services/socket'
import { prepareForServerRestart } from '../../services/restart'

const viewport = vi.hoisted(() => ({ desktop: true }))
vi.mock('../layout/useEmberViewport', () => ({ useEmberViewport: () => viewport.desktop }))
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../../services/restart', () => ({ prepareForServerRestart: vi.fn(async () => 'server-a'), cancelPendingRestart: vi.fn(), reloadWhenServerReady: vi.fn() }))
vi.mock('../settings/SettingsMenu', () => ({ SettingsMenu: () => null }))
const initialDialogs = useDialogs.getState()
const initialSession = useSession.getState()
beforeEach(() => {
  vi.clearAllMocks()
  viewport.desktop = true
  useDialogs.setState(initialDialogs, true)
  useSession.setState({ ...initialSession, connected: true, mode: 'play' }, true)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'close').mockImplementation(() => undefined)
})
afterEach(cleanup)
function openLoad() {
  useDialogs.getState().openDialog('load')
  useDialogs.getState().setSaveList([{ save_folder: 'save_001' }])
  render(<LoadDialog />)
  fireEvent.click(screen.getByText('save_001'))
}

describe('desktop public action confirmations', () => {
  it('cancels nested restore with Escape, preserving parent selection and exact opener focus', () => {
    openLoad()
    const trigger = screen.getByRole('button', { name: 'Load Game' })
    trigger.focus(); fireEvent.click(trigger)
    const confirmation = screen.getByRole('dialog', { name: 'Restore Saved Game' })
    expect(document.activeElement).toBe(within(confirmation).getByRole('button', { name: 'Cancel' }))
    expect(window.confirm).not.toHaveBeenCalled()
    expect(prepareForServerRestart).not.toHaveBeenCalled()
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Restore Saved Game' })).toBeNull()
    expect(useDialogs.getState().open).toBe('load')
    expect(document.activeElement).toBe(trigger)
    expect(screen.getByRole('button', { name: /save_001/ }).getAttribute('aria-pressed')).toBe('true')
  })

  it('emits exactly one restore only after themed confirmation', async () => {
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))
    const confirm = screen.getByRole('button', { name: 'Restore Game' })
    fireEvent.click(confirm); fireEvent.click(confirm)
    await waitFor(() => expect(useDialogs.getState().open).toBeNull())
    expect(prepareForServerRestart).toHaveBeenCalledTimes(1)
    expect(vi.mocked(emitC).mock.calls.filter(([event, data]) => event === 'action' && (data as {action:string}).action === 'restoreGame')).toEqual([
      ['action', { action: 'restoreGame', parameters: { saveFolder: 'save_001' } }],
    ])
  })

  it.each(['cancel', 'disconnect', 'unmount', 'save removal'])('does not restore after %s while preparation is pending', async (transition) => {
    let resolve!: (value: string) => void
    vi.mocked(prepareForServerRestart).mockImplementationOnce(() => new Promise(r => { resolve = r }))
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))
    fireEvent.click(screen.getByRole('button', { name: 'Restore Game' }))
    if (transition === 'cancel') fireEvent.click(within(screen.getByRole('dialog', { name: 'Restore Saved Game' })).getByRole('button', { name: 'Cancel' }))
    if (transition === 'disconnect') act(() => useSession.getState().setConnected(false))
    if (transition === 'unmount') cleanup()
    if (transition === 'save removal') {
      sessionStorage.setItem('neq_restart_server_instance', 'another-operation')
      act(() => useDialogs.getState().setSaveList([{ save_folder: 'replacement_save' }]))
    }
    await act(async () => resolve('server-a'))
    expect(emitC).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'restoreGame' }))
    expect(vi.mocked(prepareForServerRestart).mock.calls[0]?.[0]?.()).toBe(false)
    if (transition === 'save removal') {
      expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('another-operation')
      sessionStorage.removeItem('neq_restart_server_instance')
    }
  })

  it.each(['Load Game', 'Delete'])('dismisses stale %s confirmation when its selected save disappears', (action) => {
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: action }))
    act(() => useDialogs.getState().setSaveList([{ save_folder: 'replacement_save' }]))
    expect(screen.queryByRole('dialog', { name: /^(Restore|Delete) Saved Game$/ })).toBeNull()
    expect(screen.getByRole('dialog', { name: 'Load Saved Game' })).toBeTruthy()
    expect((screen.getByRole('button', { name: action }) as HTMLButtonElement).disabled).toBe(true)
    expect(emitC).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'restoreGame' }))
    expect(emitC).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'deleteSave' }))
  })

  it('requires delete confirmation and never deletes on cancel', () => {
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Delete Saved Game' })).getByRole('button', { name: 'Cancel' }))
    expect(emitC).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'deleteSave' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete Save' }))
    expect(emitC).toHaveBeenCalledWith('action', { action: 'deleteSave', parameters: { saveFolder: 'save_001' } })
  })

  it('shows preparation failure inside the confirmation and permits retry', async () => {
    vi.mocked(prepareForServerRestart).mockRejectedValueOnce(new Error('storage unavailable'))
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))
    fireEvent.click(screen.getByRole('button', { name: 'Restore Game' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('storage unavailable'))
    expect((screen.getByRole('button', { name: 'Restore Game' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Restore Game' }))
    await waitFor(() => expect(useDialogs.getState().open).toBeNull())
    expect(prepareForServerRestart).toHaveBeenCalledTimes(2)
  })

  it('cancels exit safely and checks live connection before final confirmation', () => {
    render(<HeaderBar />)
    fireEvent.click(screen.getByRole('button', { name: /× Exit/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(window.close).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /× Exit/ }))
    act(() => useSession.getState().setConnected(false))
    fireEvent.click(screen.getByRole('button', { name: 'Exit Game' }))
    expect(emitC).not.toHaveBeenCalledWith('user_exit', undefined)
    expect(window.close).toHaveBeenCalledTimes(1)
    expect(useDialogs.getState().actionResult?.kind).toBe('exit')
  })

  it('keeps the native phone delete prompt and exact copy', () => {
    viewport.desktop = false
    openLoad()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(window.confirm).toHaveBeenCalledWith('Delete this save? This cannot be undone.')
    expect(screen.queryByRole('dialog', { name: 'Delete Saved Game' })).toBeNull()
    expect(emitC).toHaveBeenCalledWith('action', { action: 'deleteSave', parameters: { saveFolder: 'save_001' } })
  })
})
