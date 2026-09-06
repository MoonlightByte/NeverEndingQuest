// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SaveDialog } from './SaveDialog'
import { useDialogs, useSession } from '../../stores'
import { emitC } from '../../services/socket'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
const viewport = vi.hoisted(() => ({ desktop: true }))
vi.mock('../layout/useEmberViewport', () => ({ useEmberViewport: () => viewport.desktop }))
const dialogsInitial = useDialogs.getState()
const sessionInitial = useSession.getState()
beforeEach(() => {
  vi.clearAllMocks()
  useDialogs.setState(dialogsInitial, true)
  useSession.setState({ ...sessionInitial, connected: true }, true)
})
afterEach(cleanup)

it.each([true, false])('does not queue offline saves and preserves the draft for an explicit connected save (desktop=%s)', desktop => {
  viewport.desktop = desktop
  useDialogs.getState().openDialog('save')
  render(<SaveDialog />)
  fireEvent.change(screen.getByLabelText(/description/i), { target: { value: '  Keep this draft  ' } })
  fireEvent.change(screen.getByLabelText(/save type/i), { target: { value: 'full' } })
  act(() => useSession.getState().setConnected(false))
  const save = screen.getByRole('button', { name: 'Save Game' }) as HTMLButtonElement
  expect(save.disabled).toBe(true)
  fireEvent.click(save)
  expect(emitC).not.toHaveBeenCalled()
  expect(useDialogs.getState().open).toBe('save')
  expect(screen.getByRole('status').textContent).toContain('Your draft is kept')
  act(() => useSession.getState().setConnected(true))
  expect((screen.getByLabelText(/description/i) as HTMLTextAreaElement).value).toBe('  Keep this draft  ')
  expect((screen.getByLabelText(/save type/i) as HTMLSelectElement).value).toBe('full')
  expect(emitC).not.toHaveBeenCalled()
  fireEvent.click(save); fireEvent.click(save)
  expect(emitC).toHaveBeenCalledTimes(1)
  expect(emitC).toHaveBeenCalledWith('action', { action: 'saveGame', parameters: { description: 'Keep this draft', saveMode: 'full' } })
  expect(useDialogs.getState().open).toBeNull()
})
