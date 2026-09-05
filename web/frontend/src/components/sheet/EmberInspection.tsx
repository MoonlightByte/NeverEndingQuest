import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import './ember-inspection.css'

const activationEvent = 'neq:inspection-open'
let pinnedOwner: string | null = null

/** Nonmodal inspection: hover/focus previews; activation pins scrollable details.
 * One inspection at a time. No game actions or data fetching are owned here. */
export function EmberInspection({ label, children, className = '' }: { label: string; children: ReactNode; className?: string }) {
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const suppressFocus = useRef(false)
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [position, setPosition] = useState({ left: 12, top: 12 })
  const cancelTimer = () => { if (timer.current) clearTimeout(timer.current); timer.current = null }
  const close = (restore = false) => {
    cancelTimer(); setOpen(false); setPinned(false)
    if (pinnedOwner === id) pinnedOwner = null
    if (restore && trigger.current?.isConnected) {
      suppressFocus.current = true
      trigger.current.focus()
    }
  }
  const show = (deliberate = false) => {
    if (!deliberate && pinnedOwner !== null && pinnedOwner !== id) return
    cancelTimer()
    window.dispatchEvent(new CustomEvent(activationEvent, { detail: id }))
    setOpen(true)
  }
  const leave = () => {
    cancelTimer()
    if (!pinned) timer.current = setTimeout(() => {
      if (!panel.current?.contains(document.activeElement) && document.activeElement !== trigger.current) setOpen(false)
    }, 160)
  }
  useEffect(() => {
    const replace = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== id) {
        if (timer.current) clearTimeout(timer.current)
        timer.current = null
        setOpen(false); setPinned(false)
        if (pinnedOwner === id) pinnedOwner = null
      }
    }
    window.addEventListener(activationEvent, replace)
    return () => { window.removeEventListener(activationEvent, replace); if (timer.current) clearTimeout(timer.current); if (pinnedOwner === id) pinnedOwner = null }
  }, [id])
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) {
        setOpen(false); setPinned(false)
        if (pinnedOwner === id) pinnedOwner = null
      }
    }
    document.addEventListener('pointerdown', outside)
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return
      const dialog = event.target instanceof Element ? event.target.closest('[role="dialog"]') : null
      if (dialog && dialog !== panel.current) return
      event.preventDefault(); event.stopPropagation()
      setOpen(false); setPinned(false)
      if (timer.current) clearTimeout(timer.current)
      timer.current = null
      if (pinnedOwner === id) pinnedOwner = null
    }
    window.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); window.removeEventListener('keydown', escape) }
  }, [open, id])
  useLayoutEffect(() => {
    if (open && pinned) panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [open, pinned])
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      if (!trigger.current || !panel.current) return
      const anchor = trigger.current.getBoundingClientRect()
      const card = panel.current.getBoundingClientRect()
      const below = anchor.bottom + 8
      const rail = trigger.current.closest('.neq-rail-area')?.getBoundingClientRect()
      const beside = rail && rail.right + card.width + 20 <= window.innerWidth ? rail.right + 8 : null
      setPosition({
        left: beside ?? Math.max(12, Math.min(anchor.left, window.innerWidth - card.width - 12)),
        top: Math.max(12, Math.min(beside !== null ? anchor.top : below + card.height <= window.innerHeight - 12 ? below : anchor.top - card.height - 8, window.innerHeight - card.height - 12)),
      })
    }
    place()
    const observer = new ResizeObserver(place)
    if (panel.current) observer.observe(panel.current)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => { observer.disconnect(); window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true) }
  }, [open])
  return <>
    <button ref={trigger} type="button" className={`ember-inspection-trigger ${className}`}
      aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
      onMouseEnter={() => show()} onMouseLeave={leave}
      onFocus={() => { if (!suppressFocus.current) show() }}
      onBlur={(event) => { suppressFocus.current = false; if (!panel.current?.contains(event.relatedTarget)) leave() }}
      onKeyDown={(event) => { if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); close(true) } }}
      onClick={() => { if (pinned) close(true); else { show(true); pinnedOwner = id; setPinned(true) } }}>
      {label}
    </button>
    {open && createPortal(<div ref={panel} id={id} role="dialog" aria-label={`${label} details`} aria-modal="false"
      className="ember-inspection" style={position} onMouseEnter={cancelTimer} onMouseLeave={leave}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget) && event.relatedTarget !== trigger.current) close() }}
      onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true) } }}>
      <header><h3>{label}</h3><button type="button" aria-label={`Close ${label} details`} onClick={() => close(true)}>×</button></header>
      <div className="ember-inspection-body" tabIndex={0}>{children}</div>
    </div>, document.body)}
  </>
}
