// @vitest-environment jsdom
/**
 * Dialog logic tests (plan 4.4e). The socket service is mocked: these verify
 * that user intents emit the right contract events and that server payloads
 * already in the stores render correctly.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
vi.mock('../../services/restart', () => ({ prepareForServerRestart: vi.fn(async () => 'server-a'), reloadWhenServerReady: vi.fn(async () => undefined) }))

import { emitC } from '../../services/socket'
import { prepareForServerRestart } from '../../services/restart'
import { useDialogs, useLog, useWorld } from '../../stores'
import { SaveDialog } from './SaveDialog'
import { LoadDialog } from './LoadDialog'
import { ResetDialog, generateResetCode } from './ResetDialog'
import { JournalModal } from './JournalModal'
import { UpdateDialog } from './UpdateDialog'
import { StorageModal } from './StorageModal'

const emitMock = vi.mocked(emitC)
const prepareRestartMock = vi.mocked(prepareForServerRestart)
const dialogsInitial = useDialogs.getState()
const worldInitial = useWorld.getState()
const logInitial = useLog.getState()

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  useDialogs.setState(dialogsInitial, true)
  useWorld.setState(worldInitial, true)
  useLog.setState(logInitial, true)
})

describe('SaveDialog', () => {
  it('emits action saveGame with description + saveMode and closes', () => {
    useDialogs.getState().openDialog('save')
    render(<SaveDialog />)

    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: 'Before the dragon fight' },
    })
    fireEvent.change(screen.getByLabelText(/save type/i), { target: { value: 'full' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Game' }))

    expect(emitMock).toHaveBeenCalledWith('action', {
      action: 'saveGame',
      parameters: { description: 'Before the dragon fight', saveMode: 'full' },
    })
    expect(useDialogs.getState().open).toBeNull()
  })
})

describe('LoadDialog', () => {
  it('moves focus inside without a primary input and handles Escape', () => {
    useDialogs.getState().openDialog('load')
    render(<LoadDialog />)
    const dialog = screen.getByRole('dialog', { name: 'Load Saved Game' })
    expect(dialog.contains(document.activeElement)).toBe(true)
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(useDialogs.getState().open).toBeNull()
  })

  it('requests the save list on open and emits restoreGame for the selected save', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([
      { save_folder: 'save_001', save_mode: 'essential', module: 'Keep_of_Doom' },
    ])
    render(<LoadDialog />)

    expect(emitMock).toHaveBeenCalledWith('action', { action: 'listSaves' })

    fireEvent.click(screen.getByText('save_001'))
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))

    await waitFor(() => expect(emitMock).toHaveBeenCalledWith('action', {
      action: 'restoreGame', parameters: { saveFolder: 'save_001' },
    }))
    expect(prepareRestartMock).toHaveBeenCalledOnce()
    expect(useDialogs.getState().open).toBeNull()
  })

  it('keeps the dialog open and does not restore when confirmation is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([{ save_folder: 'save_003' }])
    render(<LoadDialog />)

    fireEvent.click(screen.getByText('save_003'))
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))

    expect(window.confirm).toHaveBeenCalledWith(
      'This will restore the selected save and restart the server. Your current progress will be lost. Continue?',
    )
    expect(prepareRestartMock).not.toHaveBeenCalled()
    expect(emitMock).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'restoreGame' }))
    expect(useDialogs.getState().open).toBe('load')
  })

  it('keeps the dialog open and reports restart preparation failure', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    prepareRestartMock.mockRejectedValueOnce(new Error('session storage unavailable'))
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([{ save_folder: 'save_005' }])
    render(<LoadDialog />)

    fireEvent.click(screen.getByText('save_005'))
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))

    await waitFor(() => expect(useLog.getState().messages.at(-1)?.content).toContain('Game restore could not start'))
    expect(useDialogs.getState().open).toBe('load')
    expect(emitMock).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'restoreGame' }))
  })

  it('emits deleteSave after confirmation', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([{ save_folder: 'save_002' }])
    render(<LoadDialog />)

    fireEvent.click(screen.getByText('save_002'))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(emitMock).toHaveBeenCalledWith('action', {
      action: 'deleteSave',
      parameters: { saveFolder: 'save_002' },
    })
  })

  it('uses the legacy selected-card state on the semantic save button', () => {
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([{ save_folder: 'save_004', save_mode: 'full' }])
    render(<LoadDialog />)

    const save = screen.getByRole('button', { name: /save_004/i })
    expect(save.classList.contains('neq-save-item-parity')).toBe(true)
    expect(save.getAttribute('aria-pressed')).toBe('false')

    fireEvent.click(save)
    expect(save.getAttribute('aria-pressed')).toBe('true')
  })
})

describe('ResetDialog', () => {
  it('generates legacy-compatible five-digit numeric codes', () => {
    for (let i = 0; i < 20; i++) {
      expect(generateResetCode()).toMatch(/^\d{5}$/)
    }
  })

  it('keeps Confirm disabled until the code is retyped, then emits nuclearReset', async () => {
    useDialogs.getState().openDialog('reset')
    render(<ResetDialog />)

    const code = screen.getByTestId('reset-code').textContent ?? ''
    expect(code).toHaveLength(5)

    const input = screen.getByLabelText('Reset confirmation code')
    const confirm = screen.getByRole('button', { name: 'Confirm Reset' }) as HTMLButtonElement

    expect(confirm.disabled).toBe(true)
    fireEvent.change(input, { target: { value: '1234' } })
    expect(confirm.disabled).toBe(true)

    fireEvent.change(input, { target: { value: code } })
    expect(confirm.disabled).toBe(false)

    fireEvent.click(confirm)
    await waitFor(() => expect(emitMock).toHaveBeenCalledWith('action', { action: 'nuclearReset', parameters: {} }))
    expect(useDialogs.getState().actionResult?.kind).toBe('reset')
    expect(useDialogs.getState().open).toBeNull()
  })

  it('allows only one destructive reset while restart preparation is pending', async () => {
    let finishPreparation!: () => void
    prepareRestartMock.mockImplementationOnce(() => new Promise<string>((resolve) => {
      finishPreparation = () => resolve('server-a')
    }))
    useDialogs.getState().openDialog('reset')
    render(<ResetDialog />)
    fireEvent.change(screen.getByLabelText('Reset confirmation code'), {
      target: { value: screen.getByTestId('reset-code').textContent ?? '' },
    })
    const confirm = screen.getByRole('button', { name: 'Confirm Reset' }) as HTMLButtonElement

    fireEvent.click(confirm)
    fireEvent.click(confirm)

    expect(prepareRestartMock).toHaveBeenCalledTimes(1)
    expect(emitMock).not.toHaveBeenCalledWith('action', expect.objectContaining({ action: 'nuclearReset' }))
    expect(confirm.disabled).toBe(true)

    finishPreparation()
    await waitFor(() => expect(emitMock).toHaveBeenCalledTimes(1))
  })
})

describe('JournalModal', () => {
  it('requests plot data and splits discovered quests into the two pages', () => {
    useWorld.getState().setPlot({
      data: {
        plotPoints: [
          { id: 'q1', title: 'Find the Amulet', description: 'Seek it out.', status: 'in progress' },
          { id: 'q2', title: 'Rescue the Miller', description: 'Done deal.', status: 'completed' },
          { id: 'q3', title: 'Hidden Quest', description: 'Secret.', status: 'not started' },
        ],
      },
    })
    useDialogs.getState().openDialog('journal')
    render(<JournalModal />)

    expect(emitMock).toHaveBeenCalledWith('request_plot_data', undefined)

    const leftPage = screen.getByRole('region', { name: 'Current Objectives' })
    const rightPage = screen.getByRole('region', { name: 'A Chronicle of Deeds' })
    expect(leftPage.textContent).toContain('Find the Amulet')
    expect(leftPage.textContent).not.toContain('Rescue the Miller')
    expect(rightPage.textContent).toContain('Rescue the Miller')
    // Undiscovered quests never render.
    expect(screen.queryByText('Hidden Quest')).toBeNull()
  })

  it('matches the legacy two-page error state', () => {
    useWorld.setState({ plot: null, plotError: 'Deterministic quest ledger failure' })
    useDialogs.getState().openDialog('journal')

    const { container } = render(<JournalModal />)

    const pages = container.querySelectorAll('.neq-journal-book > .neq-journal-page')
    expect(pages).toHaveLength(2)
    expect(pages[0]?.querySelector('h2')?.textContent).toBe('Journal')
    expect(pages[0]?.querySelector('p')?.textContent).toBe('Could not load quest data.')
    expect(pages[0]?.querySelector('.neq-journal-empty')).toBeNull()
    expect(pages[1]?.textContent).toBe('')
  })

  it('leaves both legacy pages blank while plot data is pending', () => {
    useWorld.setState({ plot: null, plotError: null })
    useDialogs.getState().openDialog('journal')

    const { container } = render(<JournalModal />)

    const pages = container.querySelectorAll('.neq-journal-book > .neq-journal-page')
    expect(pages).toHaveLength(2)
    expect(pages[0]?.textContent).toBe('')
    expect(pages[1]?.textContent).toBe('')
    expect(screen.queryByText('Consulting the chronicle...')).toBeNull()
  })

  it('renders headings without React-only helper copy when the journal is empty', () => {
    useWorld.getState().setPlot({ data: { plotPoints: [] } })
    useDialogs.getState().openDialog('journal')

    render(<JournalModal />)

    expect(screen.getByText('Current Objectives', { exact: true })).toBeTruthy()
    expect(screen.getByText('A Chronicle of Deeds', { exact: true })).toBeTruthy()
    expect(screen.queryByText(/No active quests/)).toBeNull()
    expect(screen.queryByText(/No completed quests/)).toBeNull()
  })
})

describe('UpdateDialog', () => {
  it('matches the legacy single status line and keeps dialog controls enabled', () => {
    useDialogs.setState({
      open: 'update',
      update: {
        running: true,
        log: ['Starting update...', 'Validating frontend assets...'],
        error: null,
        complete: null,
      },
    })

    render(<UpdateDialog />)

    expect(screen.getByRole('status').textContent).toBe('Validating frontend assets...')
    expect(screen.queryByText('Starting update...', { exact: true })).toBeNull()
    expect((screen.getByRole('button', { name: 'Proceed with Update' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('adds the legacy refresh instruction to the completed status', () => {
    useDialogs.setState({
      open: 'update',
      update: {
        running: false,
        log: [],
        error: null,
        complete: 'Update complete! Server restarting...',
      },
    })

    render(<UpdateDialog />)

    expect(screen.getByRole('status').textContent).toBe(
      'Update complete! Server restarting... Please refresh the page.',
    )
  })

  it('reports restart preparation failure without emitting an update', async () => {
    prepareRestartMock.mockRejectedValueOnce(new Error('session storage unavailable'))
    useDialogs.setState({ open: 'update' })
    render(<UpdateDialog />)

    fireEvent.click(screen.getByRole('button', { name: 'Proceed with Update' }))

    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Update could not start'))
    expect(emitMock).not.toHaveBeenCalledWith('trigger_update', undefined)
  })
})

describe('StorageModal', () => {
  it('shows the legacy terminal empty state when storage hydration fails', () => {
    useWorld.setState({ storage: null, storageError: 'unavailable' })
    useDialogs.getState().openDialog('storage')
    render(<StorageModal />)

    expect(screen.getByText('No player storage found.')).toBeTruthy()
    expect(screen.queryByText('Fetching storage data...')).toBeNull()
  })
})
