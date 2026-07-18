// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDialogs } from '../../stores'
import { CompressionOverlay } from './CompressionOverlay'
import { ModuleProgressOverlay } from './ModuleProgressOverlay'

const initialDialogs = useDialogs.getState()

beforeEach(() => {
  useDialogs.setState(initialDialogs, true)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('terminal operation feedback', () => {
  it('shows a compression error restored without a preceding start event', () => {
    useDialogs.getState().compressionFailed({ error: 'Provider unavailable' })
    render(<CompressionOverlay />)
    expect(screen.getByText('Chronicle compression failed: Provider unavailable')).toBeTruthy()
  })

  it('hides a restored compression terminal result after the legacy delay', () => {
    vi.useFakeTimers()
    useDialogs.getState().compressionComplete({ reduction_percentage: 42, original_size: 100, compressed_size: 58 })
    render(<CompressionOverlay />)
    expect(screen.getByText(/Reduced by 42%/)).toBeTruthy()
    act(() => vi.advanceTimersByTime(1999))
    expect(screen.getByText(/Reduced by 42%/)).toBeTruthy()
    act(() => vi.advanceTimersByTime(1))
    expect(screen.queryByText(/Reduced by 42%/)).toBeNull()
  })

  it('marks compression completion for the legacy pulse treatment', () => {
    useDialogs.getState().compressionComplete({ reduction_percentage: 42, original_size: 100, compressed_size: 58 })
    const { container } = render(<CompressionOverlay />)

    expect(container.querySelector('.neq-compression-progress-parity')?.classList.contains('complete')).toBe(true)
    expect(container.querySelector('.neq-compression-bar-parity')?.classList.contains('complete')).toBe(true)
  })

  it('marks compression failure as an explicit red safety state', () => {
    useDialogs.getState().compressionFailed({ error: 'Provider unavailable' })
    const { container } = render(<CompressionOverlay />)

    expect(container.querySelector('.neq-compression-progress-parity')?.classList.contains('failed')).toBe(true)
    expect(container.querySelector('.neq-compression-bar-parity')?.classList.contains('failed')).toBe(true)
  })

  it('renders failed module terminal state with the legacy red treatment', () => {
    useDialogs.getState().moduleProgress({
      build_id: 'failed-build',
      stage: 7,
      total_stages: 9,
      stage_name: 'Publication Failed',
      percentage: 100,
      message: 'Could not publish the next module.',
      status: 'failed',
      terminal: true,
      success: false,
      error: 'disk error',
    })
    const { container } = render(<ModuleProgressOverlay />)
    expect(screen.getByText('Publication Failed').style.color).toBe('rgb(255, 138, 128)')
    expect(screen.getByText('Could not publish the next module.').parentElement?.style.color).toBe('rgb(255, 138, 128)')
    expect((container.querySelector('.neq-module-progress-bar-parity') as HTMLElement).style.background).toContain('rgb(183, 28, 28)')
  })
})
