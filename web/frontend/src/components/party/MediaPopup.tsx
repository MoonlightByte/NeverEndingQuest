/**
 * MediaPopup (plan Task 4.4c) -- fullscreen media overlay for party /
 * initiative chips: plays the character or monster video when one exists,
 * otherwise shows the full-size image. Controlled component: the strip that
 * owns the chips holds the MediaSource state. Closes on Escape, on a click
 * outside the media, or via the close button. Rendered in a body portal.
 */
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import type { MediaSource } from './media'

export interface MediaPopupProps {
  media: MediaSource | null
  onClose: () => void
}

export function MediaPopup({ media, onClose }: MediaPopupProps) {
  useEffect(() => {
    if (!media) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [media, onClose])

  if (!media) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Character media"
      className="fixed inset-0 flex items-center justify-center"
      style={{ zIndex: 3000, backgroundColor: 'rgba(0, 0, 0, 0.85)' }}
      onClick={onClose}
    >
      <button
        type="button"
        aria-label="Close media"
        onClick={onClose}
        className="absolute right-4 top-4 h-9 w-9 cursor-pointer rounded font-chrome text-lg text-primary hover:border-accent"
        style={{ backgroundColor: 'var(--bg-panel)', border: '2px solid var(--border-card)' }}
      >
        X
      </button>
      {media.kind === 'video' ? (
        <video
          src={media.src}
          autoPlay
          loop
          controls
          playsInline
          className="rounded"
          style={{ maxWidth: '85vw', maxHeight: '85vh', border: '2px solid var(--border-card)' }}
          onClick={(event) => event.stopPropagation()}
        />
      ) : (
        <img
          src={media.src}
          alt="Full-size character portrait"
          className="rounded"
          style={{
            maxWidth: '85vw',
            maxHeight: '85vh',
            objectFit: 'contain',
            border: '2px solid var(--border-card)',
          }}
          onClick={(event) => event.stopPropagation()}
        />
      )}
    </div>,
    document.body,
  )
}
