/**
 * GenerateImageButton -- per-narration "Generate Image" control (plan 4.4b).
 * Emits generate_image with the message content as the prompt; the server
 * answers with image_generated (stored in the log store and rendered inline
 * by GameLog next to the narration whose content matches the echoed prompt)
 * or image_generation_error (appended to the log as an error message).
 * The pending state clears when either response lands.
 */
import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useLog } from '../../stores'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'

const buttonClass =
  'inline-flex h-[22px] cursor-pointer items-center justify-center rounded border-0 bg-[#4caf50] px-2 ' +
  'font-chrome text-[11px] font-bold text-white hover:bg-[#45a049] disabled:cursor-not-allowed disabled:bg-[#666]'

const buildImagePrompt = (content: string) => `Epic fantasy RPG scene: ${content}. Medieval style, darker lighting, highly detailed fantasy art style, professional digital painting, atmospheric depth.`

export function GenerateImageButton({ content, messageId }: { content: string; messageId?: string }) {
  const ember = useEmberDesktop()
  const [pending, setPending] = useState(false)
  const requestIdRef = useRef<string | undefined>(undefined)
  const images = useLog((s) => s.images)
  const messages = useLog((s) => s.messages)

  useEffect(() => {
    if (!pending) return
    const requestId = requestIdRef.current
    const matched = images.some((image) =>
      requestId ? image.request_id === requestId : image.source_message_id === messageId)
    const errored = Boolean(requestId && messages.some((message) => message.message_id === `image-error-${requestId}`))
    if (matched || errored) setPending(false)
  }, [pending, images, messages, content, messageId])

  const request = () => {
    if (pending) return
    setPending(true)
    requestIdRef.current = emitC('generate_image', { prompt: buildImagePrompt(content), source_message_id: messageId })
  }

  return (
    <button
      type="button"
      onClick={request}
      disabled={pending}
      title={pending ? 'Image generation in progress' : 'Generate an image for this scene'}
      className={ember ? 'ember-message-action' : buttonClass}
    >
      {ember && <EmberIcon name="image" />}{pending ? 'Generating...' : ember ? 'Generate image' : 'Generate Image'}
    </button>
  )
}
