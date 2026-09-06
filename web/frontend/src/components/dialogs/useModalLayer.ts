import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'

type Layer = { element: HTMLElement; modal: boolean; visual: HTMLElement; zIndex: string }
const layers: Layer[] = []
let originalOverflow = ''
let modalCount = 0
const inertOriginals = new Map<HTMLElement, boolean>()
function setInert(element: HTMLElement, value: boolean) { element.inert = value; element.toggleAttribute('inert', value) }
function reconcile() {
  for (const [element, original] of inertOriginals) setInert(element, original)
  inertOriginals.clear()
  layers.forEach((layer, index) => { layer.visual.style.zIndex = String(20000 + index * 10) })
  const top = [...layers].reverse().find(layer => layer.modal)
  if (!top) return
  let branch = top.element
  while (branch.parentElement && branch.parentElement !== document.documentElement) {
    for (const sibling of branch.parentElement.children) {
      if (!(sibling instanceof HTMLElement) || sibling === branch || ['SCRIPT','STYLE','LINK'].includes(sibling.tagName)) continue
      if (layers.slice(layers.indexOf(top) + 1).some(layer => sibling.contains(layer.element))) continue
      inertOriginals.set(sibling, Boolean(sibling.inert) || sibling.hasAttribute('inert'))
      setInert(sibling, true)
    }
    branch = branch.parentElement
  }
}

/** Current-branch inertness prevents older body portals disabling new root layers. */
export function useModalLayer(ref: RefObject<HTMLElement | null>, close?: () => void, { modal = true, restoreFocus = modal }: { modal?: boolean; restoreFocus?: boolean } = {}) {
  const closeRef = useRef(close)
  closeRef.current = close
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const visual = element.closest<HTMLElement>('.ember-dialog-overlay,.neq-search-overlay-parity') ?? element
    const layer: Layer = { element, modal, visual, zIndex: visual.style.zIndex }
    if (modal && modalCount++ === 0) { originalOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden' }
    layers.push(layer)
    reconcile()
    const selector = 'button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[href],[tabindex]:not([tabindex="-1"])'
    const actions = () => Array.from(element.querySelectorAll<HTMLElement>(selector)).filter(node => !node.closest('[hidden],[inert]'))
    if (modal && !element.contains(document.activeElement)) (actions()[0] ?? element).focus()
    const key = (event: KeyboardEvent) => {
      if (layers.at(-1) !== layer) return
      if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); closeRef.current?.(); return }
      if (event.key !== 'Tab' || !modal) return
      const controls = actions()
      const first = controls[0] ?? element
      const last = controls.at(-1) ?? element
      if (!element.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last) || !controls.length) { event.preventDefault(); (event.shiftKey ? last : first).focus() }
    }
    document.addEventListener('keydown', key, true)
    return () => {
      document.removeEventListener('keydown', key, true)
      const wasTop = layers.at(-1) === layer
      const index = layers.indexOf(layer)
      if (index >= 0) layers.splice(index, 1)
      visual.style.zIndex = layer.zIndex
      if (modal && --modalCount === 0) document.body.style.overflow = originalOverflow
      reconcile()
      if (wasTop && restoreFocus) {
        const fallback = layers.at(-1)?.element.querySelector<HTMLElement>(selector) ?? document.querySelector<HTMLElement>('.neq-rail-panel [role="tab"][aria-selected="true"]') ?? document.querySelector<HTMLElement>('button[aria-label="Settings"]')
        ;(previous?.isConnected && !previous.closest('[inert]') ? previous : fallback)?.focus()
      }
    }
  }, [ref, modal, restoreFocus])
  return () => layers.at(-1)?.element === ref.current
}
