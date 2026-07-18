// @vitest-environment jsdom
/**
 * Component logic tests for the game log group (plan Task 4.4b).
 * services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useDialogs, useLog, useSession, useSettings } from '../../stores'
import { emitC } from '../../services/socket'
import { GameLog } from './GameLog'
import { MessageCard } from './MessageCard'
import { InputBar } from './InputBar'
import { DiceStrip, rollDie } from './DiceStrip'
import { TtsButton } from './TtsButton'
import { GenerateImageButton } from './GenerateImageButton'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

const initialLog = useLog.getState()
const initialSession = useSession.getState()
const initialSettings = useSettings.getState()

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
  useSettings.setState(initialSettings, true)
  useDialogs.setState({ actionResult: null })
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('MessageCard', () => {
  it('renders narration with the DM header treatment and per-message controls', () => {
    const { container } = render(
      <MessageCard message={{ type: 'narration', content: 'A cold wind rises.' }} />,
    )
    expect(screen.getByText('Dungeon Master')).toBeTruthy()
    expect(screen.getByText('A cold wind rises.')).toBeTruthy()
    expect(screen.getByTitle('Play DM Voice')).toBeTruthy()
    expect(screen.getByText('Generate Image')).toBeTruthy()
    expect(container.querySelector('[data-message-type="narration"]')).not.toBeNull()
  })

  it('renders user input in the legacy left-aligned flow', () => {
    const { container } = render(
      <MessageCard message={{ type: 'user-input', content: 'I draw my sword.' }} />,
    )
    const card = container.querySelector('[data-message-type="user-input"]')
    expect(card).not.toBeNull()
    expect(card!.className).not.toContain('flex-row-reverse')
    expect(screen.getByText('I draw my sword.')).toBeTruthy()
  })

  it('styles error messages as centered system cards', () => {
    const { container } = render(
      <MessageCard message={{ type: 'error', content: 'Something failed.' }} />,
    )
    expect(container.querySelector('[data-message-type="error"]')).not.toBeNull()
    expect(screen.getByText('Something failed.')).toBeTruthy()
  })
})

describe('GameLog', () => {
  it('keeps the legacy output area blank before transport hydration', () => {
    render(<GameLog />)

    expect(screen.getByRole('log').textContent).toBe('')
  })

  it('renders log store messages and attaches generated images to the matching narration', () => {
    useLog.getState().append({ type: 'narration', content: 'The dragon roars.' })
    useLog.getState().append({ type: 'user-input', content: 'I run.' })
    useLog.getState().addImage({ image_url: '/media/scene1.jpg', prompt: 'The dragon roars.' })
    const { container } = render(<GameLog />)
    expect(screen.getByText('The dragon roars.')).toBeTruthy()
    expect(screen.getByText('I run.')).toBeTruthy()
    const img = container.querySelector('img[alt^="Generated scene:"]')
    expect(img).not.toBeNull()
    expect(img!.getAttribute('src')).toBe('/media/scene1.jpg')
    expect(img!.closest('[data-message-type="narration"]')).not.toBeNull()
  })

  it('renders unmatched images at the end of the log', () => {
    useLog.getState().append({ type: 'narration', content: 'A quiet village.' })
    useLog.getState().addImage({ image_url: '/media/orphan.jpg', prompt: 'different prompt' })
    const { container } = render(<GameLog />)
    const img = container.querySelector('img[alt^="Generated scene:"]')
    expect(img).not.toBeNull()
    expect(img!.getAttribute('src')).toBe('/media/orphan.jpg')
    expect(img!.closest('[data-message-type="narration"]')).toBeNull()
  })

  it('uses a stable source ID instead of attaching to newer duplicate narration text', () => {
    useLog.getState().append({ type: 'narration', content: 'The same omen appears.', message_id: 'older' })
    useLog.getState().append({ type: 'narration', content: 'The same omen appears.', message_id: 'newer' })
    useLog.getState().addImage({ image_url: '/media/older.jpg', prompt: 'The same omen appears.', source_message_id: 'older', request_id: 'image-older' })
    const { container } = render(<GameLog />)
    const cards = container.querySelectorAll('[data-message-type="narration"]')
    expect(cards).toHaveLength(2)
    expect(cards[0]?.querySelector('img[alt^="Generated scene:"]')?.getAttribute('src')).toBe('/media/older.jpg')
    expect(cards[1]?.querySelector('img[alt^="Generated scene:"]')).toBeNull()
  })
})

describe('InputBar', () => {
  it('emits user_input with the trimmed draft and clears the field', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('ready')
    render(<InputBar />)
    const input = screen.getByPlaceholderText('Enter your command...') as HTMLInputElement
    fireEvent.change(input, { target: { value: '  look around  ' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(emitC).toHaveBeenCalledWith('user_input', { input: 'look around' })
    expect(input.value).toBe('')
  })

  it('does not emit when the draft is empty', () => {
    render(<InputBar />)
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).not.toHaveBeenCalled()
  })

  it('locks while processing and shows the status ticker text', () => {
    useSession.getState().setStatus({ message: 'The DM is thinking...', is_processing: true })
    render(<InputBar />)
    const input = screen.getByLabelText('Player input') as HTMLInputElement
    expect(input.disabled).toBe(true)
    expect((screen.getByText('Send') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('status').textContent).toContain('The DM is thinking...')
  })

  it('stays visible but locked during the startup handoff', () => {
    useSession.getState().setConnected(true)
    useSession.getState().startRequested()
    render(<InputBar />)

    expect((screen.getByPlaceholderText('Enter your command...') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByText('Send') as HTMLButtonElement).disabled).toBe(true)
  })

  it('accepts startup-wizard input after the server settles the prompt', () => {
    useSession.getState().setConnected(true)
    useSession.getState().startRequested()
    useSession.getState().setStartup('in_progress', 'Choose your character')
    render(<InputBar />)
    const input = screen.getByLabelText('Player input') as HTMLInputElement
    expect(input.disabled).toBe(true)

    act(() => useSession.getState().setStatus({ message: 'Ready', is_processing: false }))
    expect(input.disabled).toBe(false)
    fireEvent.change(input, { target: { value: 'Arden Vale' } })
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).toHaveBeenCalledWith('user_input', { input: 'Arden Vale' })
  })

  it('matches the legacy visual unlock but rejects commands when startup fails', () => {
    useSession.setState({ connected: true, mode: 'starting', startupStatus: 'failed' })
    render(<InputBar />)

    const input = screen.getByPlaceholderText('Enter your command...') as HTMLInputElement
    expect(input.disabled).toBe(false)
    expect((screen.getByText('Send') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.change(input, { target: { value: 'do not queue this' } })
    fireEvent.click(screen.getByText('Send'))
    expect(emitC).not.toHaveBeenCalled()
    expect(input.value).toBe('do not queue this')
  })

  it('locks while a confirmed campaign reset is pending', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('ready')
    useDialogs.setState({ actionResult: { kind: 'reset', message: 'Reset pending' } })
    render(<InputBar />)

    expect((screen.getByPlaceholderText('Enter your command...') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByText('Send') as HTMLButtonElement).disabled).toBe(true)
  })

  it('locks after exit without replacing the legacy command placeholder', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('ready')
    useDialogs.setState({ actionResult: { kind: 'exit', message: 'You can now safely close this browser tab.' } })
    render(<InputBar />)

    expect((screen.getByPlaceholderText('Enter your command...') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByText('Send') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('DiceStrip', () => {
  it('rollDie stays within 1..sides for every die', () => {
    for (const sides of [20, 12, 10, 8, 6, 4]) {
      for (let i = 0; i < 200; i++) {
        const result = rollDie(sides)
        expect(result).toBeGreaterThanOrEqual(1)
        expect(result).toBeLessThanOrEqual(sides)
      }
    }
  })

  it('shows d20 results and damage totals, and clears them', () => {
    render(<DiceStrip />)
    fireEvent.click(screen.getByTitle('Roll D20'))
    fireEvent.click(screen.getByTitle('Roll D6'))
    fireEvent.click(screen.getByTitle('Roll D6'))
    const results = screen.getByTestId('dice-results')
    expect(results.textContent).toMatch(/d20: \d+/)
    expect(results.textContent).toMatch(/d6: \d+, d6: \d+/)
    expect(results.textContent).toMatch(/Total: \d+/)
    fireEvent.click(screen.getByTitle('Clear results'))
    expect(screen.queryByTestId('dice-results')).toBeNull()
  })
})

describe('TtsButton', () => {
  it('explains how to enable DM Voice when the feature is disabled', () => {
    useSettings.setState({ ttsEnabled: false })
    render(<TtsButton content="hello" />)
    fireEvent.click(screen.getByTitle('Play DM Voice'))
    expect(useLog.getState().messages.at(-1)?.content).toMatch(/Enable "DM Voice"/)
  })

  it('speaks on click and stops on the second click', () => {
    const speak = vi.fn()
    const cancel = vi.fn()
    class FakeUtterance {
      text: string
      onend: (() => void) | null = null
      onerror: (() => void) | null = null
      constructor(text: string) {
        this.text = text
      }
    }
    useSettings.setState({ ttsEnabled: true, engine: 'browser' })
    vi.stubGlobal('speechSynthesis', { speak, cancel, getVoices: () => [] })
    vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
    render(<TtsButton content="A cold wind rises." />)
    fireEvent.click(screen.getByTitle('Play DM Voice'))
    expect(speak).toHaveBeenCalledTimes(1)
    expect((speak.mock.calls[0]![0] as FakeUtterance).text).toBe('A cold wind rises.')
    fireEvent.click(screen.getByTitle('Stop playback'))
    expect(cancel).toHaveBeenCalled()
    expect(screen.getByTitle('Play DM Voice')).toBeTruthy()
  })

  it('does not let a stale playback callback clear the newer playback owner', () => {
    const utterances: FakeUtterance[] = []
    class FakeUtterance {
      onend: (() => void) | null = null
      onerror: (() => void) | null = null
      text: string
      constructor(text: string) { this.text = text; utterances.push(this) }
    }
    useSettings.setState({ ttsEnabled: true, engine: 'browser' })
    vi.stubGlobal('speechSynthesis', { speak: vi.fn(), cancel: vi.fn(), getVoices: () => [] })
    vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
    render(<><TtsButton content="first" /><TtsButton content="second" /></>)
    const playButtons = screen.getAllByTitle('Play DM Voice')
    fireEvent.click(playButtons[0]!)
    fireEvent.click(playButtons[1]!)
    expect(screen.getAllByTitle('Stop playback')).toHaveLength(1)
    act(() => utterances[0]?.onend?.())
    expect(screen.getAllByTitle('Stop playback')).toHaveLength(1)
    act(() => utterances[1]?.onend?.())
    expect(screen.queryByTitle('Stop playback')).toBeNull()
  })

  it('returns to idle after playback completes under React StrictMode', () => {
    let utterance: FakeUtterance | null = null
    class FakeUtterance {
      onend: (() => void) | null = null
      onerror: (() => void) | null = null
      text: string
      constructor(text: string) { this.text = text; utterance = this }
    }
    useSettings.setState({ ttsEnabled: true, engine: 'browser' })
    vi.stubGlobal('speechSynthesis', { speak: vi.fn(), cancel: vi.fn(), getVoices: () => [] })
    vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)

    render(<StrictMode><TtsButton content="A strict tale." /></StrictMode>)
    fireEvent.click(screen.getByTitle('Play DM Voice'))
    expect(screen.getByTitle('Stop playback')).toBeTruthy()
    act(() => utterance?.onend?.())
    expect(screen.getByTitle('Play DM Voice')).toBeTruthy()
  })

  it('stops active playback when DM Voice is disabled', () => {
    const cancel = vi.fn()
    class FakeUtterance {
      onend: (() => void) | null = null
      onerror: (() => void) | null = null
      text: string
      constructor(text: string) { this.text = text }
    }
    useSettings.setState({ ttsEnabled: true, engine: 'browser' })
    vi.stubGlobal('speechSynthesis', { speak: vi.fn(), cancel, getVoices: () => [] })
    vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
    render(<TtsButton content="Silence falls." />)

    fireEvent.click(screen.getByTitle('Play DM Voice'))
    act(() => useSettings.getState().setTtsEnabled(false))

    expect(cancel).toHaveBeenCalled()
    expect(screen.getByTitle('Play DM Voice')).toBeTruthy()
  })
})

describe('GenerateImageButton', () => {
  it('emits generate_image with the message content and clears pending when the image arrives', () => {
    vi.mocked(emitC).mockReturnValue('image-request-1')
    render(<GenerateImageButton content="The dragon roars." />)
    fireEvent.click(screen.getByText('Generate Image'))
    expect(emitC).toHaveBeenCalledWith('generate_image', {
      prompt: 'Epic fantasy RPG scene: The dragon roars.. Medieval style, darker lighting, highly detailed fantasy art style, professional digital painting, atmospheric depth.',
      source_message_id: undefined,
    })
    expect((screen.getByText('Generating...') as HTMLButtonElement).disabled).toBe(true)
    act(() => {
      useLog.getState().addImage({ image_url: '/media/x.jpg', prompt: 'Epic fantasy RPG scene: The dragon roars.. Medieval style, darker lighting, highly detailed fantasy art style, professional digital painting, atmospheric depth.', request_id: 'image-request-1' })
    })
    expect(screen.getByText('Generate Image')).toBeTruthy()
  })

  it('clears pending only when its correlated image error lands in the log', () => {
    vi.mocked(emitC).mockReturnValue('image-request-2')
    render(<GenerateImageButton content="A quiet village." />)
    fireEvent.click(screen.getByText('Generate Image'))
    expect(screen.getByText('Generating...')).toBeTruthy()
    act(() => {
      useLog.getState().imageFailed({ message: 'Image generation failed.', request_id: 'image-request-2' })
    })
    expect(screen.getByText('Generate Image')).toBeTruthy()
  })
})
