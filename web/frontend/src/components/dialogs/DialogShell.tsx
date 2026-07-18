import { useEffect, useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode, RefObject } from 'react'
import './dialog-parity.css'

/** Shared button styles for dialog footers (matches the HeaderBar chrome). */
const buttonBase = 'neq-dialog-button-parity'
export const dialogButtonSecondary = `${buttonBase} secondary`
export const dialogButtonPrimary = `${buttonBase} primary`
export const dialogButtonDanger = `${buttonBase} danger`

export interface DialogShellProps {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  /** CSS max-width of the dialog card (default 32rem). */
  maxWidth?: string
  /** Use the legacy save/reset chrome instead of the generic card header. */
  legacy?: boolean
  /** Optional scoped parity modifier for a legacy dialog subtype. */
  className?: string
  /** Legacy dialogs focus their primary input when opened. */
  initialFocusRef?: RefObject<HTMLElement | null>
}

/**
 * Shared modal chrome: dark backdrop + the signature neq-card dialog.
 * Clicking the backdrop (but not the card) closes the dialog.
 */
export function DialogShell({ title, onClose, children, maxWidth = '32rem', legacy = false, className = '', initialFocusRef }: DialogShellProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null
    if (initialFocusRef?.current) initialFocusRef.current.focus()
    else if (!legacy) closeButtonRef.current?.focus()
    return () => previousFocus?.focus()
  }, [initialFocusRef, legacy])

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab' || !dialogRef.current) return

    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
      'textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    ))
    if (focusable.length === 0) {
      event.preventDefault()
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }

  return (
    <div
      className={legacy ? 'neq-dialog-overlay-parity' : 'fixed inset-0 z-50 flex items-center justify-center p-4'}
      style={legacy ? undefined : { backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={dialogRef}
        className={legacy ? `neq-save-dialog-parity ${className}` : `neq-card flex max-h-[85vh] w-full flex-col overflow-hidden ${className}`}
        style={{ maxWidth }}
      >
        <div className={legacy ? 'neq-dialog-heading-parity' : 'flex items-center justify-between border-b-2 border-card px-4 py-3'}>
          <h3 id={titleId} className={legacy ? '' : 'font-display text-lg text-primary'}>{title}</h3>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className={legacy ? 'sr-only' : 'cursor-pointer border-0 bg-transparent font-chrome text-xl leading-none text-secondary hover:text-primary'}
          >
            &times;
          </button>
        </div>
        <div className={legacy ? 'neq-dialog-body-parity' : 'min-h-0 flex-1 overflow-y-auto p-4'}>{children}</div>
      </div>
    </div>
  )
}
