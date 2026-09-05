/**
 * GameLog -- scrolling message log (plan Task 4.4b).
 * Renders the log store ring as typed MessageCards, attaches generated
 * images (image_generated) inline to the narration whose content matches
 * the echoed prompt (GenerateImageButton emits the message content as the
 * prompt), and auto-scrolls with bottom-pin: new messages keep the view at
 * the bottom unless the player has scrolled up to read history.
 */
import { useEffect, useMemo, useRef } from 'react'
import { useLog } from '../../stores'
import type { GeneratedImage } from '../../stores'
import { MessageCard } from './MessageCard'
import { useEmberDesktop } from '../layout/EmberPresentation'

/** Within this many pixels of the bottom still counts as pinned. */
const BOTTOM_PIN_THRESHOLD_PX = 48

export function GameLog() {
  const ember = useEmberDesktop()
  const messages = useLog((s) => s.messages)
  const images = useLog((s) => s.images)
  const previousSessionCount = useLog((s) => s.previousSessionCount)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const pinnedRef = useRef(true)

  // Attach each generated image to the most recent narration whose content
  // equals the image prompt; anything unmatched renders at the end of the log.
  const { imagesByMessage, orphanImages } = useMemo(() => {
    const byMessage = new Map<number, GeneratedImage[]>()
    const orphans: GeneratedImage[] = []
    for (const image of images) {
      let matchIndex = -1
      for (let i = messages.length - 1; i >= 0; i--) {
        const message = messages[i]
        if (message !== undefined && message.type === 'narration' && (
          image.source_message_id
            ? image.source_message_id === message.message_id
            : image.prompt.includes(message.content)
        )) {
          matchIndex = i
          break
        }
      }
      if (matchIndex >= 0) {
        const list = byMessage.get(matchIndex)
        if (list) {
          list.push(image)
        } else {
          byMessage.set(matchIndex, [image])
        }
      } else {
        orphans.push(image)
      }
    }
    return { imagesByMessage: byMessage, orphanImages: orphans }
  }, [messages, images])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_PIN_THRESHOLD_PX
  }

  useEffect(() => {
    const el = containerRef.current
    if (el && pinnedRef.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, images])

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      onLoadCapture={() => {
        const el = containerRef.current
        if (ember && el && pinnedRef.current) el.scrollTop = el.scrollHeight
      }}
      role="log"
      aria-label="Game log"
      className="neq-game-log h-full min-h-0 overflow-y-auto px-[10px] py-2"
    >
      {messages.length > 0 || orphanImages.length > 0 ? (
        <>
          {previousSessionCount > 0 && <div className="neq-session-divider mx-auto my-8 max-w-[500px] rounded border border-card py-2 text-center font-log text-sm italic text-secondary">--- Previous Session Messages ---</div>}
          {messages.map((message, index) => <div key={message.message_id ?? index}>{index === previousSessionCount && <div className="neq-session-divider mx-auto my-8 max-w-[500px] rounded border border-card py-2 text-center font-log text-sm italic text-secondary">{ember ? 'Current session' : '--- Current Session ---'}</div>}<MessageCard message={message} images={imagesByMessage.get(index)} /></div>)}
          {previousSessionCount === messages.length && previousSessionCount > 0 && <div className="neq-session-divider mx-auto my-8 max-w-[500px] rounded border border-card py-2 text-center font-log text-sm italic text-secondary">--- Current Session ---</div>}
          {orphanImages.map((image, index) => (
            <div key={`${image.image_url}-${index}`} className="my-4 flex justify-center">
              <img
                src={image.image_url}
                alt={`Generated scene: ${image.prompt.slice(0, 80)}`}
                className="max-w-full rounded-lg border-2 border-card"
              />
            </div>
          ))}
        </>
      ) : null}
    </div>
  )
}
