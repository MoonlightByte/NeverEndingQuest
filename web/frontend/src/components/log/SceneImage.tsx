import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'
import type { GeneratedImage } from '../../stores'
import { useModalLayer } from '../dialogs/useModalLayer'
import './SceneImage.css'

type View = { scale: number; x: number; y: number }
type Point = { x: number; y: number }
const FIT: View = { scale: 1, x: 0, y: 0 }
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y)
const midpoint = (a: Point, b: Point) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 })
const clamp = (value: number, limit: number) => Math.max(-limit, Math.min(limit, value))

export function ScenePreview({ image, onClose }: { image: GeneratedImage; onClose: () => void }) {
  const modal = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const picture = useRef<HTMLImageElement>(null)
  const [view, setView] = useState<View>(FIT)
  const current = useRef<View>(FIT)
  const pointers = useRef(new Map<number, Point>())
  const gesture = useRef<{ view: View; points: Point[] }>({ view: FIT, points: [] })
  const [failed, setFailed] = useState(false)
  useModalLayer(modal, onClose)

  function update(next: View) {
    const bounds = stage.current?.getBoundingClientRect()
    const img = picture.current
    const scale = Math.max(1, Math.min(5, next.scale))
    let x = next.x, y = next.y
    if (bounds && bounds.width > 0 && bounds.height > 0) {
      const ratio = img?.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : bounds.width / bounds.height
      const width = Math.min(bounds.width, bounds.height * ratio)
      const height = Math.min(bounds.height, bounds.width / ratio)
      x = clamp(x, Math.max(0, (width * scale - bounds.width) / 2))
      y = clamp(y, Math.max(0, (height * scale - bounds.height) / 2))
    }
    current.current = { scale, x, y }
    setView(current.current)
  }
  function zoom(scale: number, point: Point = { x: 0, y: 0 }) {
    const before = current.current
    const next = Math.max(1, Math.min(5, scale))
    update({ scale: next, x: point.x - (point.x - before.x) * next / before.scale,
      y: point.y - (point.y - before.y) * next / before.scale })
  }
  function localPoint(clientX: number, clientY: number): Point {
    const rect = stage.current!.getBoundingClientRect()
    return { x: clientX - rect.left - rect.width / 2, y: clientY - rect.top - rect.height / 2 }
  }
  function resetGesture() {
    gesture.current = { view: current.current, points: [...pointers.current.values()] }
  }
  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    pointers.current.set(event.pointerId, localPoint(event.clientX, event.clientY))
    resetGesture()
  }
  function pointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!pointers.current.has(event.pointerId)) return
    event.preventDefault()
    pointers.current.set(event.pointerId, localPoint(event.clientX, event.clientY))
    const points = [...pointers.current.values()]
    const start = gesture.current
    if (points.length >= 2 && start.points.length >= 2) {
      const origin = midpoint(start.points[0]!, start.points[1]!)
      const center = midpoint(points[0]!, points[1]!)
      const scale = Math.max(1, Math.min(5, start.view.scale * distance(points[0]!, points[1]!) / Math.max(1, distance(start.points[0]!, start.points[1]!))))
      update({ scale, x: center.x - (origin.x - start.view.x) * scale / start.view.scale,
        y: center.y - (origin.y - start.view.y) * scale / start.view.scale })
    } else if (points[0] && start.points[0]) {
      update({ ...start.view, x: start.view.x + points[0].x - start.points[0].x,
        y: start.view.y + points[0].y - start.points[0].y })
    }
  }
  function pointerEnd(event: ReactPointerEvent<HTMLDivElement>) {
    pointers.current.delete(event.pointerId)
    resetGesture()
  }
  useEffect(() => {
    const element = stage.current
    if (!element) return
    const wheel = (event: WheelEvent) => {
      event.preventDefault()
      zoom(current.current.scale * Math.exp(-event.deltaY * 0.002), localPoint(event.clientX, event.clientY))
    }
    const resize = () => { pointers.current.clear(); update(FIT); resetGesture() }
    element.addEventListener('wheel', wheel, { passive: false })
    window.addEventListener('resize', resize)
    return () => { element.removeEventListener('wheel', wheel); window.removeEventListener('resize', resize) }
  }, [])

  return createPortal(
    <div ref={modal} className="neq-scene-preview" role="dialog" aria-modal="true" aria-label="Scene preview" tabIndex={-1}>
      <header><span>Scene preview</span><button type="button" onClick={onClose} aria-label="Close scene preview">Close ×</button></header>
      <div ref={stage} className="neq-scene-stage" aria-label="Zoomable scene"
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd}
        onPointerCancel={pointerEnd} onLostPointerCapture={pointerEnd}
        onDoubleClick={(event) => zoom(current.current.scale > 1 ? 1 : 2, localPoint(event.clientX, event.clientY))}>
        {failed ? <p role="status">This scene could not be loaded. Close the preview and try again.</p> :
          <img ref={picture} src={image.image_url} alt={`Generated scene: ${image.prompt.slice(0, 80)}`} draggable={false}
            onError={() => setFailed(true)} style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }} />}
      </div>
      <footer><div className="neq-scene-tools" role="group" aria-label="Image zoom">
        <button type="button" aria-label="Zoom out" disabled={view.scale <= 1} onClick={() => zoom(view.scale - .5)}>−</button>
        <output aria-live="polite" aria-label="Zoom level">{Math.round(view.scale * 100)}%</output>
        <button type="button" aria-label="Zoom in" disabled={view.scale >= 5} onClick={() => zoom(view.scale + .5)}>+</button>
        <button type="button" onClick={() => update(FIT)}>Fit image</button>
      </div><p>Pinch to zoom · Drag to explore</p></footer>
    </div>, document.body,
  )
}

/** Shared by attached and orphan scenes on both game layouts. */
export function SceneImage({ image, className = '' }: { image: GeneratedImage; className?: string }) {
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  return <>
    {failed ? <div className="ember-image-error" role="status">Scene image unavailable. <button type="button" onClick={() => setFailed(false)}>Retry image</button></div> :
      <button type="button" className="neq-scene-thumbnail" aria-label={`Open scene preview: ${image.prompt.slice(0, 80)}`} onClick={() => setOpen(true)}>
        <img src={image.image_url} alt={`Generated scene: ${image.prompt.slice(0, 80)}`} className={className} onError={() => setFailed(true)} />
        <span className="neq-scene-open-hint" aria-hidden="true">View scene ↗</span>
      </button>}
    {open && <ScenePreview image={image} onClose={() => setOpen(false)} />}
  </>
}
