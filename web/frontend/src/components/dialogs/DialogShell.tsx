import type { ReactNode } from 'react'

/** Shared button styles for dialog footers (matches the HeaderBar chrome). */
const buttonBase =
  'rounded border-2 px-4 py-2 font-chrome text-sm cursor-pointer ' +
  'disabled:cursor-not-allowed disabled:opacity-50'
export const dialogButtonSecondary = `${buttonBase} border-card bg-panel text-primary hover:border-soft`
export const dialogButtonPrimary = `${buttonBase} border-accent bg-panel text-accent hover:border-emerald-1`
export const dialogButtonDanger = `${buttonBase} border-[#c0392b] bg-panel text-[#e74c3c] hover:border-[#e74c3c]`

export interface DialogShellProps {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  /** CSS max-width of the dialog card (default 32rem). */
  maxWidth?: string
}

/**
 * Shared modal chrome: dark backdrop + the signature neq-card dialog.
 * Clicking the backdrop (but not the card) closes the dialog.
 */
export function DialogShell({ title, onClose, children, maxWidth = '32rem' }: DialogShellProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="neq-card flex max-h-[85vh] w-full flex-col overflow-hidden"
        style={{ maxWidth }}
      >
        <div className="flex items-center justify-between border-b-2 border-card px-4 py-3">
          <h3 className="font-display text-lg text-primary">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="cursor-pointer border-0 bg-transparent font-chrome text-xl leading-none text-secondary hover:text-primary"
          >
            &times;
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  )
}
