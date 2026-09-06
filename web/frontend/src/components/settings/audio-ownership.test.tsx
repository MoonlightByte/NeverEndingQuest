// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SettingsMenu } from './SettingsMenu'
import { TtsButton, resetNarrationAudio } from '../log/TtsButton'
import { useSettings, useDialogs } from '../../stores'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
const initial = useSettings.getState()
let spoken: Array<{ onend?: () => void; onerror?: () => void }>
beforeEach(() => {
  spoken = []
  useSettings.setState({ ...initial, ttsEnabled: true, engine: 'browser' }, true)
  useDialogs.getState().closeDialog()
  vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(_text: string) {} })
  vi.stubGlobal('speechSynthesis', { speak: (value: typeof spoken[number]) => spoken.push(value), cancel: vi.fn(), getVoices: () => [], addEventListener: vi.fn(), removeEventListener: vi.fn() })
})
afterEach(() => { cleanup(); resetNarrationAudio(); vi.unstubAllGlobals() })
it('does not cancel narration when unrelated Settings opens and closes', () => {
  render(<><TtsButton content="Narration owned elsewhere" /><SettingsMenu /></>)
  fireEvent.click(screen.getByTitle('Play DM Voice'))
  const cancelsBefore = vi.mocked(window.speechSynthesis.cancel).mock.calls.length
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  expect(window.speechSynthesis.cancel).toHaveBeenCalledTimes(cancelsBefore)
  expect(screen.getByTitle('Stop playback')).toBeTruthy()
})
it('ignores cancelled narration callbacks after restarting the same control', () => {
  render(<TtsButton content="One tale" />)
  fireEvent.click(screen.getByTitle('Play DM Voice'))
  const old = spoken[0]
  fireEvent.click(screen.getByTitle('Stop playback'))
  fireEvent.click(screen.getByTitle('Play DM Voice'))
  act(() => old.onend?.())
  expect(screen.getByTitle('Stop playback')).toBeTruthy()
})
it('ignores cancelled preview callbacks and turns off settings-only playback', () => {
  render(<SettingsMenu />)
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.click(screen.getByTitle('Preview voice'))
  const old = spoken[0]
  fireEvent.click(screen.getByTitle('Stop preview'))
  fireEvent.click(screen.getByTitle('Preview voice'))
  act(() => old.onend?.())
  expect(screen.getByTitle('Stop preview')).toBeTruthy()
  fireEvent.click(screen.getByRole('checkbox', { name: 'DM Voice' }))
  expect(window.speechSynthesis.cancel).toHaveBeenCalled()
  expect(screen.queryByTitle('Stop preview')).toBeNull()
})
it('never starts a late paid preview response after the settings-only voice toggle turns off', async () => {
  useSettings.setState({ engine: 'openai' })
  let deliver!: (response: { ok: boolean; blob: () => Promise<Blob> }) => void
  const pending = new Promise<{ ok: boolean; blob: () => Promise<Blob> }>(resolve => { deliver = resolve })
  const audio = vi.fn()
  vi.stubGlobal('fetch', vi.fn(() => pending))
  vi.stubGlobal('Audio', audio)
  render(<SettingsMenu />)
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.click(screen.getByTitle('Preview voice'))
  fireEvent.click(screen.getByRole('checkbox', { name: 'DM Voice' }))
  await act(async () => { deliver({ ok: true, blob: async () => new Blob(['synthetic']) }); await pending })
  expect(audio).not.toHaveBeenCalled()
})
