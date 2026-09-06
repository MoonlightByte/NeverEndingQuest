import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DialogShell } from '../dialogs/DialogShell'
import { useMediaRevision, type MediaSource } from './media'
import '../../theme/ember-npc-media.css'

export interface MediaPopupProps { media: MediaSource | null; onClose: () => void }

export function MediaPopup({ media, onClose }: MediaPopupProps) {
  const revision = useMediaRevision()
  const previousRevision = useRef(revision)
  const [failed, setFailed] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  useEffect(() => { setFailed(false); setVideoFailed(false) }, [media])
  useEffect(() => {
    if (previousRevision.current !== revision) { previousRevision.current = revision; onClose() }
  }, [revision, onClose])
  if (!media) return null
  return createPortal(<DialogShell title="Character media" onClose={onClose} maxWidth="min(44rem, 94vw)" className="ember-media-viewer">
    {failed ? <p role="status">This media could not be loaded. Close this viewer and try the portrait again.</p> : media.kind === 'video' && !videoFailed ?
      <video key={media.src} src={media.src} autoPlay={!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches} loop muted playsInline controls onError={() => media.fallback ? setVideoFailed(true) : setFailed(true)} /> :
      <img src={videoFailed ? media.fallback ?? '' : media.src} alt="Character portrait" onError={() => setFailed(true)} />}
  </DialogShell>, document.body)
}
