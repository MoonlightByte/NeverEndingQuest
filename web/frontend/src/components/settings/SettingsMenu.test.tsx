// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDialogs, useLog, useSettings } from '../../stores'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

import { emitC } from '../../services/socket'
import { SettingsMenu } from './SettingsMenu'

const initialDialogs = useDialogs.getState()
const initialLog = useLog.getState()
const initialSettings = useSettings.getState()

beforeEach(() => {
  useDialogs.setState(initialDialogs, true)
  useLog.setState(initialLog, true)
  useSettings.setState(initialSettings, true)
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('provider and voice settings behavior', () => {
  it('re-enables provider selection when the server never confirms a change', () => {
    vi.useFakeTimers()
    useDialogs.getState().setProvider({ provider: 'legacy' })
    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    const select = screen.getByLabelText('Provider') as HTMLSelectElement

    fireEvent.change(select, { target: { value: 'openai' } })
    expect(emitC).toHaveBeenCalledWith('set_model_provider', { provider: 'openai' })
    expect(select.disabled).toBe(true)

    act(() => vi.advanceTimersByTime(10000))
    expect(select.disabled).toBe(false)
    expect(select.value).toBe('legacy')
  })

  it('stops and releases an OpenAI preview when settings closes', async () => {
    const pause = vi.fn()
    const play = vi.fn(async () => undefined)
    const revokeObjectURL = vi.fn()
    class CompatibleAudio {
      onended: (() => void) | null = null
      onerror: (() => void) | null = null
      pause = pause
      play = play
      src: string
      constructor(src: string) { this.src = src }
    }
    useSettings.setState({ ttsEnabled: true, engine: 'openai' })
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, blob: async () => new Blob(['voice']) })))
    vi.stubGlobal('Audio', CompatibleAudio)
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL })

    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    fireEvent.click(screen.getByTitle('Preview voice'))
    await waitFor(() => expect(play).toHaveBeenCalledOnce())

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(pause).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview')
  })

  it('uses the legacy voice-control geometry hooks and playing state', async () => {
    class CompatibleAudio {
      onended: (() => void) | null = null
      onerror: (() => void) | null = null
      pause = vi.fn()
      play = vi.fn(async () => undefined)
      constructor(_src: string) {}
    }
    useSettings.setState({ ttsEnabled: true, engine: 'openai' })
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, blob: async () => new Blob(['voice']) })))
    vi.stubGlobal('Audio', CompatibleAudio)
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() })

    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    const preview = screen.getByTitle('Preview voice')
    expect(preview.parentElement?.classList.contains('neq-voice-controls-parity')).toBe(true)

    fireEvent.click(preview)
    await waitFor(() => expect(screen.getByTitle('Stop preview').classList.contains('playing')).toBe(true))
  })

  it('uses a legacy justify-between row for local Save and Test Connection', () => {
    useDialogs.getState().setProvider({ provider: 'lmstudio' })
    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))

    const save = screen.getByRole('button', { name: /^Save$/ })
    expect(save.parentElement?.classList.contains('neq-settings-button-row-parity')).toBe(true)
    expect(screen.getByRole('button', { name: 'Test Connection' }).parentElement).toBe(save.parentElement)
  })

  it('uses the legacy pending, pass, and fail endpoint status colors', () => {
    useDialogs.getState().setProvider({ provider: 'lmstudio' })
    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    fireEvent.change(screen.getByLabelText('Server URL'), { target: { value: 'http://localhost:1234/v1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Test Connection' }))

    expect(screen.getByRole('status').getAttribute('style')).toContain('color: rgb(136, 136, 136)')

    act(() => useDialogs.getState().setEndpointTestResult({ ok: true, detail: 'Connected' }))
    expect(screen.getByRole('status').getAttribute('style')).toContain('color: rgb(46, 125, 50)')

    act(() => useDialogs.getState().setEndpointTestResult({ ok: false, detail: 'Unavailable' }))
    expect(screen.getByRole('status').getAttribute('style')).toContain('color: rgb(198, 40, 40)')
  })

  it('shows the legacy Auto-play Voice explanation below the hovered row', () => {
    useSettings.setState({ ttsEnabled: true })
    render(<SettingsMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    const row = screen.getByText('Auto-play').parentElement as HTMLDivElement
    vi.spyOn(row, 'getBoundingClientRect').mockReturnValue({
      x: 100, y: 200, left: 100, top: 200, right: 380, bottom: 226,
      width: 280, height: 26, toJSON: () => ({}),
    })

    fireEvent.mouseEnter(row)
    const tooltip = screen.getByRole('tooltip')
    expect(screen.getByText('Auto-play Voice')).toBeTruthy()
    expect(tooltip.getAttribute('style')).toContain('left: 100px')
    expect(tooltip.getAttribute('style')).toContain('top: 231px')

    fireEvent.mouseLeave(row)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})
