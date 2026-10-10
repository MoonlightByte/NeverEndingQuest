// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useSession } from '../../stores'
import { ThinkingMist } from './ThinkingMist'

const sessionInitial = useSession.getState()

beforeEach(() => { cleanup(); useSession.setState(sessionInitial, true) })
afterEach(cleanup)

describe('ThinkingMist', () => {
  it('swirls only while the Dungeon Master is working', () => {
    useSession.setState({ isProcessing: true })
    const { rerender } = render(<ThinkingMist />)
    expect(screen.getByTestId('thinking-mist').getAttribute('aria-hidden')).toBe('true')
    useSession.setState({ isProcessing: false })
    rerender(<ThinkingMist />)
    expect(screen.queryByTestId('thinking-mist')).toBeNull()
  })

  it('stays hidden when gameplay is paused for recovery', () => {
    useSession.setState({ isProcessing: true, restoreRecoveryRequired: true })
    render(<ThinkingMist />)
    expect(screen.queryByTestId('thinking-mist')).toBeNull()
  })
})
