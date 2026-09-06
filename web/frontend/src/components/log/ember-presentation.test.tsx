// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { EmberPresentation } from '../layout/EmberPresentation'
import { MessageCard } from './MessageCard'
import { useSettings } from '../../stores'

vi.mock('./TtsButton', () => ({ TtsButton: ({ content }: { content: string }) => <button data-content={content}>Listen</button> }))
vi.mock('./GenerateImageButton', () => ({ GenerateImageButton: ({ content }: { content: string }) => <button data-content={content}>Generate image</button> }))
afterEach(cleanup)

describe('Ember message presentation boundary', () => {
  const content = 'First paragraph.\n\nSecond paragraph.\n\nThird paragraph.'
  const message = { type: 'narration' as const, content, message_id: 'narration-1' }
  const images = [{ image_url: '/scene.jpg', prompt: content, source_message_id: 'narration-1' }]

  it('places optional art after the first paragraph without changing action inputs', () => {
    useSettings.setState({ aiImages: true })
    const { container } = render(<EmberPresentation value={true}><MessageCard message={message} images={images} /></EmberPresentation>)
    const blocks = container.querySelectorAll('.neq-message-text, .neq-inline-images')
    expect(blocks).toHaveLength(3)
    expect(blocks[0]?.textContent).toBe('First paragraph.')
    expect(blocks[1]?.querySelector('img')?.getAttribute('src')).toBe('/scene.jpg')
    expect(blocks[2]?.textContent).toBe('Second paragraph.\n\nThird paragraph.')
    expect(screen.getByRole('button', { name: 'Listen' }).getAttribute('data-content')).toBe(content)
    expect(screen.getByRole('button', { name: 'Generate image' }).getAttribute('data-content')).toBe(content)
  })

  it('renders no media container or reserved caption without an image', () => {
    const { container } = render(<EmberPresentation value={true}><MessageCard message={message} /></EmberPresentation>)
    expect(container.querySelector('.neq-inline-images')).toBeNull()
    expect(container.querySelector('.neq-message-text')?.textContent).toBe(content)
  })

  it('keeps the non-Ember append-only presentation unchanged', () => {
    const { container } = render(<MessageCard message={message} images={images} />)
    const blocks = container.querySelectorAll('.neq-message-text, .neq-inline-images')
    expect(blocks).toHaveLength(2)
    expect(blocks[0]?.textContent).toBe(content)
    expect(container.querySelector('.ember-image-caption')).toBeNull()
  })

  it('preserves untrusted content as text', () => {
    const { container } = render(<EmberPresentation value={true}><MessageCard message={{ ...message, content: '<script>alert(1)</script>' }} /></EmberPresentation>)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('.neq-message-text')?.textContent).toBe('<script>alert(1)</script>')
  })
})
