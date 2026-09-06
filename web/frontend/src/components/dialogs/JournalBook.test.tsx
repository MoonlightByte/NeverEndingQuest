// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { JournalModal } from './JournalModal'
import { useDialogs, useWorld } from '../../stores'
import { emitC } from '../../services/socket'
const viewport = vi.hoisted(() => ({ desktop: true }))
vi.mock('../layout/useEmberViewport', () => ({ useEmberViewport: () => viewport.desktop }))
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
const initialDialogs = useDialogs.getState()
const initialWorld = useWorld.getState()
beforeEach(() => {
  vi.clearAllMocks()
  viewport.desktop = true
  useDialogs.setState(initialDialogs, true)
  useWorld.setState(initialWorld, true)
})
afterEach(cleanup)
function openJournal() {
  const result = render(<><button onClick={() => useDialogs.getState().openDialog('journal')}>Open journal</button><JournalModal /></>)
  const opener = screen.getByRole('button', { name: 'Open journal' })
  opener.focus(); fireEvent.click(opener)
  return { ...result, opener }
}
describe('restored parchment journal', () => {
  it('uses the open book with separate discovered/finished pages and shared modal ownership', () => {
    useWorld.setState({ plot: { plotPoints: [
      { id: 'active', title: 'Known trail', description: 'Follow the trail.', status: 'in progress', sideQuests: [{ title: 'Hidden detail', status: 'not started' }] },
      { id: 'done', title: 'Completed trail', description: 'Returned safely.', status: 'completed' },
      { id: 'hidden', title: 'Hidden trail', description: 'Unrevealed', status: 'not started' },
    ] }, plotError: null })
    const { container, opener } = openJournal()
    const dialog = screen.getByRole('dialog', { name: 'Adventure Journal' })
    expect(dialog.classList.contains('neq-journal-desktop')).toBe(true)
    expect(dialog.querySelector('.ember-dialog-card')).toBeNull()
    expect(dialog.querySelectorAll('.neq-journal-page')).toHaveLength(2)
    expect(within(screen.getByRole('region', { name: 'Current Objectives' })).getByText('Known trail')).toBeTruthy()
    expect(within(screen.getByRole('region', { name: 'A Chronicle of Deeds' })).getByText('Completed trail')).toBeTruthy()
    expect(screen.queryByText('Hidden trail')).toBeNull()
    expect(screen.queryByText('Hidden detail')).toBeNull()
    expect(emitC).toHaveBeenCalledWith('request_plot_data', undefined)
    expect(container.hasAttribute('inert')).toBe(true)
    expect(document.activeElement).toBe(within(dialog).getByRole('button', { name: 'Close' }))
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(container.hasAttribute('inert')).toBe(false)
    expect(document.activeElement).toBe(opener)
  })

  it.each(['loading', 'empty', 'error'])('retains both parchment pages for %s', state => {
    useWorld.setState({ plot: state === 'empty' ? { plotPoints: [] } : null, plotError: state === 'error' ? 'Read failed' : null })
    openJournal()
    expect(screen.getByRole('dialog').querySelectorAll('.neq-journal-page')).toHaveLength(2)
    if (state === 'loading') expect(screen.getByRole('status').textContent).toContain('Fetching your journal')
    if (state === 'error') expect(screen.getByRole('alert').textContent).toContain('Could not load quest data')
    if (state === 'empty') expect(screen.getByText('No discovered quests have been recorded yet.')).toBeTruthy()
  })

  it('preserves the existing phone book and blank loading pages', () => {
    viewport.desktop = false
    openJournal()
    const dialog = screen.getByRole('dialog')
    expect(dialog.classList.contains('neq-journal-desktop')).toBe(false)
    expect(dialog.querySelectorAll('.neq-journal-page')).toHaveLength(2)
    expect(screen.queryByRole('status')).toBeNull()
    act(() => useDialogs.getState().closeDialog())
  })
})
