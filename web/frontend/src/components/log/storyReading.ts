import type { GameMessage } from '../../contract/events'

/** IDs survive hydration; object identity covers older servers without IDs.
 * Compare messages rather than array lengths because the history ring is capped. */
export function firstNewNarration(messages: GameMessage[], previous: GameMessage[], cachedCount: number) {
  const ids = new Set(previous.flatMap(message => message.message_id ? [message.message_id] : []))
  const objects = new Set(previous)
  return messages.findIndex((message, index) => index >= cachedCount && message.type === 'narration'
    && !(message.message_id ? ids.has(message.message_id) : objects.has(message)))
}

/** Reveal the first lines, never the end of an unread response. The entire
 * message remains available immediately; no artificial typing delay. */
export function revealStoryStart(log: HTMLElement, message: HTMLElement) {
  log.scrollTop = Math.max(0, log.scrollTop + message.getBoundingClientRect().top
    - log.getBoundingClientRect().top - 16)
}

export function softenStoryArrival(message: HTMLElement) {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  message.animate?.([{ opacity: .35 }, { opacity: 1 }], { duration: 300, easing: 'ease-out' })
}
