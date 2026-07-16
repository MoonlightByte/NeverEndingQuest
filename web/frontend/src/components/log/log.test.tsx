// @vitest-environment jsdom
/**
 * Component logic tests for the game log group (plan Task 4.4b).
 * services/socket is mocked -- no socket connection is made.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useLog, useSession } from '../../stores'
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

beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
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
    expect(screen.getByText('Play')).toBeTruthy()
    expect(screen.getByText('Generate Image')).toBeTruthy()
    expect(container.querySelector('[data-message-type="narration"]')).not.toBeNull()
  })

  it('right-aligns user input', () => {
    const { container } = render(
      <MessageCard message={{ type: 'user-input', content: 'I draw my sword.' }} />,
    )
    const card = container.querySelector('[data-message-type="user-input"]')
    expect(card).not.toBeNull()
    expect(card!.className).toContain('flex-row-reverse')
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
  it('renders log store messages and attaches generated images to the matching narration', () => {
    useLog.getState().append({ type: 'narration', content: 'The dragon roars.' })
    useLog.getState().append({ type: 'user-input', content: 'I run.' })
    useLog.getState().addImage({ image_url: '/media/scene1.jpg', prompt: 'The dragon roars.' })
    const { container } = render(<GameLog />)
    expect(screen.getByText('The dragon roars.')).toBeTruthy()
    expect(screen.getByText('I run.')).toBeTruthy()
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img!.getAttribute('src')).toBe('/media/scene1.jpg')
    expect(img!.closest('[data-message-type="narration"]')).not.toBeNull()
  })

  it('renders unmatched images at the end of the log', () => {
    useLog.getState().append({ type: 'narration', content: 'A quiet village.' })
    useLog.getState().addImage({ image_url: '/media/orphan.jpg', prompt: 'different prompt' })
    const { container } = render(<GameLog />)
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img!.getAttribute('src')).toBe('/media/orphan.jpg')
    expect(img!.closest('[data-message-type="narration"]')).toBeNull()
  })
})

describe('InputBar', () => {
  it('emits user_input with the trimmed draft and clears the field', () => {
    render(<InputBar />)
    const input = screen.getByPlaceholderText('What do you do?') as HTMLInputElement
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
  it('is disabled when the Web Speech API is unavailable', () => {
    render(<TtsButton content="hello" />)
    expect((screen.getByText('Play') as HTMLButtonElement).disabled).toBe(true)
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
    vi.stubGlobal('speechSynthesis', { speak, cancel })
    vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
    render(<TtsButton content="A cold wind rises." />)
    fireEvent.click(screen.getByText('Play'))
    expect(speak).toHaveBeenCalledTimes(1)
    expect((speak.mock.calls[0]![0] as FakeUtterance).text).toBe('A cold wind rises.')
    fireEvent.click(screen.getByText('Stop'))
    expect(cancel).toHaveBeenCalled()
    expect(screen.getByText('Play')).toBeTruthy()
  })
})

describe('GenerateImageButton', () => {
  it('emits generate_image with the message content and clears pending when the image arrives', () => {
    render(<GenerateImageButton content="The dragon roars." />)
    fireEvent.click(screen.getByText('Generate Image'))
    expect(emitC).toHaveBeenCalledWith('generate_image', { prompt: 'The dragon roars.' })
    expect((screen.getByText('Generating...') as HTMLButtonElement).disabled).toBe(true)
    act(() => {
      useLog.getState().addImage({ image_url: '/media/x.jpg', prompt: 'The dragon roars.' })
    })
    expect(screen.getByText('Generate Image')).toBeTruthy()
  })

  it('clears pending when a subsequent error message lands in the log', () => {
    render(<GenerateImageButton content="A quiet village." />)
    fireEvent.click(screen.getByText('Generate Image'))
    expect(screen.getByText('Generating...')).toBeTruthy()
    act(() => {
      useLog.getState().append({ type: 'error', content: 'Image generation failed.' })
    })
    expect(screen.getByText('Generate Image')).toBeTruthy()
  })
})
