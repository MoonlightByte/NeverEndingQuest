/**
 * GenerateImageButton -- per-narration "Generate Image" control (plan 4.4b).
 * Emits generate_image with the message content as the prompt; the server
 * answers with image_generated (stored in the log store and rendered inline
 * by GameLog next to the narration whose content matches the echoed prompt)
 * or image_generation_error (appended to the log as an error message).
 * The pending state clears when either response lands.
 */
import { useEffect, useRef, useState } from 'react'
import type { GameMessage } from '../../contract/events'
import { emitC } from '../../services/socket'
import { useLog } from '../../stores'

const buttonClass =
  'cursor-pointer rounded border border-card bg-page px-1.5 py-0.5 font-chrome text-[11px] ' +
  'text-secondary hover:border-accent disabled:cursor-not-allowed disabled:opacity-50'

function countErrors(messages: readonly GameMessage[]): number {
  return messages.filter((m) => m.type === 'error').length
}

export function GenerateImageButton({ content }: { content: string }) {
  const [pending, setPending] = useState(false)
  const imagesAtRequest = useRef(0)
  const errorsAtRequest = useRef(0)
  const images = useLog((s) => s.images)
  const messages = useLog((s) => s.messages)

  useEffect(() => {
    if (!pending) return
    const matched = images
      .slice(imagesAtRequest.current)
      .some((image) => image.prompt === content)
    const errored = countErrors(messages) > errorsAtRequest.current
    if (matched || errored) setPending(false)
  }, [pending, images, messages, content])

  const request = () => {
    if (pending) return
    imagesAtRequest.current = useLog.getState().images.length
    errorsAtRequest.current = countErrors(useLog.getState().messages)
    setPending(true)
    emitC('generate_image', { prompt: content })
  }

  return (
    <button
      type="button"
      onClick={request}
      disabled={pending}
      title={pending ? 'Image generation in progress' : 'Generate an image for this scene'}
      className={buttonClass}
    >
      {pending ? 'Generating...' : 'Generate Image'}
    </button>
  )
}
