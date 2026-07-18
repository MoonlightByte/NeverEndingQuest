/**
 * MediaPopup (plan Task 4.4c) -- fullscreen media overlay for party /
 * initiative chips: plays the character or monster video when one exists,
 * otherwise shows the full-size image. Controlled component: the strip that
 * owns the chips holds the MediaSource state. Closes on Escape, on a click
 * outside the media, or via the close button. Rendered in a body portal.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { MediaSource } from './media'

export interface MediaPopupProps {
  media: MediaSource | null
  onClose: () => void
}

export function MediaPopup({ media, onClose }: MediaPopupProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const closeTimerRef = useRef<number | null>(null)
  const [renderedMedia, setRenderedMedia] = useState<MediaSource | null>(media)
  const [visible, setVisible] = useState(media !== null)
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)

  useEffect(() => {
    if (!media) return
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setRenderedMedia(media)
    setVisible(true)
  }, [media])

  useLayoutEffect(() => {
    if (!renderedMedia || !contentRef.current) { setPosition(null); return }
    const popup = contentRef.current.getBoundingClientRect()
    const anchor = renderedMedia.anchor
    if (!anchor) {
      setPosition({ top: Math.max(10, (window.innerHeight - popup.height) / 2), left: Math.max(10, (window.innerWidth - popup.width) / 2) })
      return
    }
    let top = anchor.top - popup.height - 10
    if (top < 10) top = anchor.bottom + 10
    let left = anchor.left + anchor.width / 2 - popup.width / 2
    left = Math.max(10, Math.min(left, window.innerWidth - popup.width - 10))
    setPosition({ top, left })
  }, [renderedMedia])

  const requestClose = useCallback(() => {
    if (!renderedMedia || closeTimerRef.current !== null) return
    setVisible(false)
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null
      setRenderedMedia(null)
      setPosition(null)
      onClose()
    }, 200)
  }, [onClose, renderedMedia])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') requestClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [requestClose])

  useEffect(() => () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current)
  }, [])

  if (!renderedMedia) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Character media"
      className={`neq-media-popup-parity fixed inset-0${visible ? ' visible' : ''}`}
      style={{ zIndex: 10000 }}
      onClick={(event) => { if (event.target === event.currentTarget) requestClose() }}
    >
      <div ref={contentRef} className="absolute w-[350px] rounded-lg border-[3px] border-[#ffa500] bg-[#1a1a1a] p-[5px] shadow-[0_5px_20px_rgba(0,0,0,.7)]" style={{ top: position?.top ?? 0, left: position?.left ?? 0, visibility: position ? 'visible' : 'hidden' }}>
        {renderedMedia.kind === 'video' ? (
          <video src={renderedMedia.src} autoPlay loop muted playsInline className="block h-auto w-full rounded-[5px]" />
        ) : (
          <img src={renderedMedia.src} alt="Character Portrait" className="block h-auto w-full rounded-[5px]" />
        )}
      </div>
    </div>,
    document.body,
  )
}
