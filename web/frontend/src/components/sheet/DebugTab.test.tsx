// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useLog } from '../../stores'
import { DebugTab } from './DebugTab'

const logInitial = useLog.getState()

beforeEach(() => {
  cleanup()
  useLog.setState(logInitial, true)
})

describe('DebugTab legacy parity', () => {
  it('keeps an empty debug ledger visually empty while rendering token totals', () => {
    useLog.setState({ tokens: { tpm: 4321, rpm: 7, total_tokens: 98765 } })

    const { container } = render(<DebugTab />)

    expect(screen.getByText('4,321', { exact: true })).toBeTruthy()
    expect(screen.getByText('7', { exact: true })).toBeTruthy()
    expect(screen.getByText('98,765', { exact: true })).toBeTruthy()
    expect(container.querySelectorAll('.neq-debug-message')).toHaveLength(0)
    expect(screen.queryByText('No debug output yet.')).toBeNull()
  })

  it('renders the immutable legacy debug card and locale-formatted timestamp', () => {
    const timestamp = '2026-07-18T14:20:05Z'
    const content = 'Deterministic diagnostic checkpoint verified.'
    useLog.getState().appendDebug({ type: 'debug', timestamp, content })

    const { container } = render(<DebugTab />)

    const card = container.querySelector('.neq-debug-message')
    expect(card).not.toBeNull()
    expect(card?.querySelector('.neq-debug-message-content')).not.toBeNull()
    expect(card?.querySelector('.neq-debug-timestamp')?.textContent).toBe(
      new Date(timestamp).toLocaleTimeString(),
    )
    expect(card?.querySelector('.neq-debug-message-text')?.textContent).toBe(content)
    expect(card?.textContent).not.toContain(`[${timestamp}]`)
  })

  it('pins the debug ledger to its newest entry like legacy addMessage', () => {
    const { container } = render(<DebugTab />)
    const ledger = container.querySelector('.neq-debug-scrollable') as HTMLDivElement
    Object.defineProperty(ledger, 'scrollHeight', { configurable: true, value: 640 })
    ledger.scrollTop = 0

    act(() => {
      useLog.getState().appendDebug({
        type: 'debug',
        timestamp: '2026-07-18T14:20:05Z',
        content: 'Newest checkpoint.',
      })
    })

    expect(ledger.scrollTop).toBe(640)
  })
})
