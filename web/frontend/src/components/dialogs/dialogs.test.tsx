// @vitest-environment jsdom
/**
 * Dialog logic tests (plan 4.4e). The socket service is mocked: these verify
 * that user intents emit the right contract events and that server payloads
 * already in the stores render correctly.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

import { emitC } from '../../services/socket'
import { useDialogs, useWorld } from '../../stores'
import { SaveDialog } from './SaveDialog'
import { LoadDialog } from './LoadDialog'
import { ResetDialog, generateResetCode } from './ResetDialog'
import { JournalModal } from './JournalModal'

const emitMock = vi.mocked(emitC)
const dialogsInitial = useDialogs.getState()
const worldInitial = useWorld.getState()

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  useDialogs.setState(dialogsInitial, true)
  useWorld.setState(worldInitial, true)
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
  it('requests the save list on open and emits restoreGame for the selected save', () => {
    useDialogs.getState().openDialog('load')
    useDialogs.getState().setSaveList([
      { save_folder: 'save_001', save_mode: 'essential', module: 'Keep_of_Doom' },
    ])
    render(<LoadDialog />)

    expect(emitMock).toHaveBeenCalledWith('action', { action: 'listSaves' })

    fireEvent.click(screen.getByText('save_001'))
    fireEvent.click(screen.getByRole('button', { name: 'Load Game' }))

    expect(emitMock).toHaveBeenCalledWith('action', {
      action: 'restoreGame',
      parameters: { saveFolder: 'save_001' },
    })
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
})

describe('ResetDialog', () => {
  it('generates 6-char codes from the expected charset', () => {
    for (let i = 0; i < 20; i++) {
      expect(generateResetCode()).toMatch(/^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/)
    }
  })

  it('keeps Confirm disabled until the code is retyped, then emits nuclearReset', () => {
    useDialogs.getState().openDialog('reset')
    render(<ResetDialog />)

    const code = screen.getByTestId('reset-code').textContent ?? ''
    expect(code).toHaveLength(6)

    const input = screen.getByLabelText('Reset confirmation code')
    const confirm = screen.getByRole('button', { name: 'Confirm Reset' }) as HTMLButtonElement

    expect(confirm.disabled).toBe(true)
    // 'WRONG1' contains O and 1, which the code charset excludes -- never a match.
    fireEvent.change(input, { target: { value: 'WRONG1' } })
    expect(confirm.disabled).toBe(true)

    fireEvent.change(input, { target: { value: code } })
    expect(confirm.disabled).toBe(false)

    fireEvent.click(confirm)
    expect(emitMock).toHaveBeenCalledWith('action', { action: 'nuclearReset', parameters: {} })
    expect(useDialogs.getState().open).toBeNull()
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
})
