// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDialogs, useSession, useWorld } from '../../stores'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../settings/SettingsMenu', () => ({ SettingsMenu: () => null }))
const uiModeMock = vi.hoisted(() => ({ mode: 'disconnected' }))
vi.mock('../../modes/useUiMode', () => ({ useUiMode: () => ({ mode: uiModeMock.mode }) }))

import { emitC } from '../../services/socket'
import { HeaderBar } from './HeaderBar'

const initialSession = useSession.getState()
const initialWorld = useWorld.getState()

beforeEach(() => {
  useSession.setState(initialSession, true)
  useWorld.setState(initialWorld, true)
  useDialogs.setState({ actionResult: null })
  uiModeMock.mode = 'disconnected'
  localStorage.clear()
  vi.clearAllMocks()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'close').mockImplementation(() => undefined)
})

afterEach(cleanup)

describe('startup parity', () => {
  it.each(['in_progress', 'failed'] as const)('keeps recovery lifecycle actions available during %s startup', (startupStatus) => {
    useSession.setState({ connected: true, mode: 'starting', startupStatus })
    uiModeMock.mode = 'starting'
    render(<HeaderBar />)
    for (const name of ['Save', 'Load', 'Reset']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Load' }))
    expect(useDialogs.getState().open).toBe('load')
  })
  it('keeps the loading label but disables Start Game while disconnected', () => {
    render(<HeaderBar />)

    expect(screen.getByText('Loading location...')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Start Game' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Start Game' }))
    expect(emitC).not.toHaveBeenCalledWith('start_game', undefined)
  })

  it('uses New Game for a connected first-run player', () => {
    useSession.getState().setConnected(true)
    render(<HeaderBar />)

    expect((screen.getByRole('button', { name: 'New Game' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('uses Start Game after the player has previously started a campaign', () => {
    localStorage.setItem('neq_hasPlayed', 'true')
    useSession.getState().setConnected(true)
    render(<HeaderBar />)

    expect((screen.getByRole('button', { name: 'Start Game' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('uses the legacy Starting label and disables the button during handoff', () => {
    useSession.setState({ connected: true, mode: 'starting' })
    render(<HeaderBar />)

    expect((screen.getByRole('button', { name: 'Starting...' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the legacy terminal location fallback after hydration fails', () => {
    useWorld.setState({ location: null, locationError: 'unavailable' })
    render(<HeaderBar />)

    expect(screen.getByText('Location Unknown')).toBeTruthy()
  })

  it('shows the legacy time fallback for an incomplete location payload', () => {
    useWorld.setState({
      location: {
        currentLocation: 'Mosswatch Gate',
        currentArea: 'Emerald March',
        currentLocationId: 'MG01',
        currentAreaId: 'EM001',
        time: '',
        day: 3,
        month: 'Springmonth',
        year: 1492,
      },
    })
    render(<HeaderBar />)

    expect(screen.getByText('Time Unknown [EM001:MG01]')).toBeTruthy()
  })

  it('locks save, load, and reset while a confirmed campaign reset is pending', () => {
    uiModeMock.mode = 'play'
    useSession.setState({ connected: true, mode: 'play' })
    useDialogs.setState({ actionResult: { kind: 'reset', message: 'Reset pending' } })
    render(<HeaderBar />)

    for (const name of ['Save', 'Load', 'Reset']) {
      expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true)
    }
  })
})

describe('exit behavior', () => {
  it('does not queue user_exit while disconnected', () => {
    render(<HeaderBar />)
    fireEvent.click(screen.getByRole('button', { name: /Exit/ }))
    expect(emitC).not.toHaveBeenCalledWith('user_exit', undefined)
    expect(useDialogs.getState().actionResult?.kind).toBe('exit')
  })

  it('notifies the server when connected', () => {
    useSession.getState().setConnected(true)
    render(<HeaderBar />)
    fireEvent.click(screen.getByRole('button', { name: /Exit/ }))
    expect(emitC).toHaveBeenCalledWith('user_exit', undefined)
    expect(useSession.getState().isProcessing).toBe(false)
    expect(useDialogs.getState().actionResult).toEqual({
      kind: 'exit',
      message: 'You can now safely close this browser tab.',
    })
  })
})
