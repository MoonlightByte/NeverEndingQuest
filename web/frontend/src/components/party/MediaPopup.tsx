import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DialogShell } from '../dialogs/DialogShell'
import { mediaVersion, resolveClickMedia, useMediaRevision, type MediaSource } from './media'
import '../../theme/ember-npc-media.css'

export interface MediaPopupProps { media: MediaSource | null; onClose: () => void }

export function MediaPopup({ media, onClose }: MediaPopupProps) {
  const revision = useMediaRevision()
  const version = mediaVersion(media?.selection?.name)
  const entityRevision = media?.selection ? version.entity : revision
  const previous = useRef({ media, global: version.global, entity: entityRevision })
  const generation = useRef(0)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  const [display, setDisplay] = useState(media)
  const [refreshing, setRefreshing] = useState(false)
  const [failed, setFailed] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  useEffect(() => {
    const id = ++generation.current
    const old = previous.current
    previous.current = { media, global: version.global, entity: entityRevision }
    if (old.global !== version.global && media) {
      setDisplay(null); setRefreshing(false); closeRef.current()
    } else if (old.media !== media) {
      setDisplay(media); setFailed(false); setVideoFailed(false); setRefreshing(false)
    } else if (media && old.entity !== entityRevision) {
      if (!media.selection) { setDisplay(null); closeRef.current() }
      else {
        setRefreshing(true); setFailed(false); setVideoFailed(false)
        const { recipe, thumbnail } = media.selection
        void resolveClickMedia(recipe, thumbnail).then(next => {
          if (id !== generation.current) return
          setDisplay(next ? { ...next, selection: media.selection, anchor: media.anchor } : null)
          setRefreshing(false); setFailed(!next)
        })
      }
    }
    return () => { generation.current++ }
  }, [media, version.global, entityRevision])
  const close = () => { generation.current++; closeRef.current() }
  if (!media) return null
  return createPortal(<DialogShell title="Character media" onClose={close} maxWidth="min(44rem, 94vw)" className="ember-media-viewer">
    {refreshing ? <p role="status">Refreshing character media…</p> : failed ? <p role="status">This media could not be loaded. Close this viewer and try the portrait again.</p> : display && (display.kind === 'video' && !videoFailed ?
      <video key={display.src} src={display.src} autoPlay={!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches} loop muted playsInline controls onError={() => display.fallback ? setVideoFailed(true) : setFailed(true)} /> :
      <img src={videoFailed ? display.fallback ?? '' : display.src} alt="Character portrait" onError={() => setFailed(true)} />)}
  </DialogShell>, document.body)
}
